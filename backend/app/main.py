import csv
import io
import json
import logging
import os
import zipfile
from pathlib import Path
from urllib.parse import urlparse, quote
from datetime import date
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, text
from .workspace import Workspace, now, uid, dumps, sha
from .models import Node, Relation, Attachment, Revision, ReviewState, ReviewLog, Category
from .schemas import NodeInput, NodeUpdate, ImportBundle, ImportCommit, RelationInput, ReviewInput, CategoryInput, MergeInput, KINDS, STATES
from .services import seed_categories, get_node, node_dict, save_node, check_version, index_node, related, search_nodes, add_relation, relation_dict, preview_import, commit_import, state_dict, review, merge_nodes, graph_data
from .backup import create_backup, restore_backup

logger = logging.getLogger('research_hub')
MAX_UPLOAD = 50 * 1024 * 1024
MAX_JSON = 10 * 1024 * 1024

def create_app(workspace=None):
    ws = Workspace(Path(workspace or os.environ.get('RESEARCH_HUB_WORKSPACE',Path.home()/'.research-hub/workspace')))
    seed_categories(ws)
    app = FastAPI(title='Research Hub',version='0.1.0')
    app.state.workspace = ws

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.url.hostname
        if host not in {'127.0.0.1','localhost','::1'}:
            return JSONResponse({'detail':'仅允许本机 Host'},status_code=403)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and (urlparse(origin).hostname not in {'127.0.0.1','localhost','::1'} or urlparse(origin).scheme not in {'http','https'}):
                return JSONResponse({'detail':'禁止外站写入本地知识库'},status_code=403)
        try:
            length = int(request.headers.get('content-length','0'))
        except ValueError:
            return JSONResponse({'detail':'非法 Content-Length'},status_code=400)
        if length > MAX_UPLOAD+1024*1024:
            return JSONResponse({'detail':'请求超过 50 MB 上限'},status_code=413)
        # Count streamed/chunked bodies as well, before parsers allocate memory.
        if request.method in {'POST','PUT','PATCH'}:
            data = bytearray()
            limit = MAX_UPLOAD+1024*1024 if 'multipart/form-data' in request.headers.get('content-type','') else MAX_JSON
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data)>limit: return JSONResponse({'detail':'请求体超过大小上限'},status_code=413)
            request._body = bytes(data)
        response = await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        return response

    @app.exception_handler(ValueError)
    @app.exception_handler(zipfile.BadZipFile)
    async def value_error(request, exc):
        return JSONResponse({'detail':str(exc)},status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        logger.exception('Operation failed: %s',request.url.path)
        return JSONResponse({'detail':'操作失败，原有记录未被覆盖。请检查服务日志和工作空间文件权限。'},status_code=500)

    @app.get('/api/health')
    def health(): return {'status':'ok','version':'0.1.0'}

    @app.get('/api/settings')
    def settings(): return {'workspace':str(ws.root),'data_format_version':'1.0','review_algorithm':'sm2-v1','states':STATES,'max_upload_mb':50,'backup_directory':str(Path(os.environ.get('RESEARCH_HUB_BACKUP_DIR',ws.root/'backups')).expanduser().resolve())}

    @app.get('/api/dashboard')
    def dashboard():
        with ws.lock, ws.Session() as s:
            nodes = s.scalars(select(Node).where(Node.deleted==False)).all()
            counts = {kind:sum(n.kind==kind for n in nodes) for kind in KINDS}
            status_counts = {status:sum(n.kind=='paper' and n.status==status for n in nodes) for status in STATES['paper']}
            due = s.scalar(select(func.count()).select_from(ReviewState).join(Node,Node.id==ReviewState.node_id).where(Node.deleted==False,ReviewState.due_at<=now()))
            recent = sorted(nodes,key=lambda n:n.updated_at,reverse=True)
            return {'counts':counts,'paper_status':status_counts,'due_vocabulary':due,'open_questions':sum(n.kind=='question' and n.status in ['open','in_progress'] for n in nodes),'recent':[node_dict(n) for n in recent[:8]],'papers':[node_dict(n) for n in recent if n.kind=='paper'][:5],'ideas':[node_dict(n) for n in recent if n.kind=='idea'][:4],'questions':[node_dict(n) for n in recent if n.kind=='question' and n.status in ['open','in_progress']][:5]}

    @app.get('/api/nodes')
    def list_nodes(q='', kind: str|None=None, tag: str|None=None, since: date|None=None, until: date|None=None, deleted:bool=False, limit: int=Query(100,ge=1,le=500), offset:int=Query(0,ge=0),sort='updated',status: str|None=None,year:int|None=None,importance:int|None=None,direction:str|None=None):
        with ws.lock, ws.Session() as s:
            return search_nodes(s,q,kind,tag,str(since) if since else None,str(until) if until else None,deleted,limit,offset,sort,status,year,importance,direction)

    @app.post('/api/nodes',status_code=201)
    def create_node(data: NodeInput):
        with ws.lock, ws.Session.begin() as s:
            n = save_node(s,ws,data)
            return node_dict(n,ws)

    @app.get('/api/nodes/{node_id}')
    def detail(node_id:str):
        with ws.lock, ws.Session() as s:
            n = get_node(s,node_id)
            d = node_dict(n,ws)
            d['relations'] = related(s,n.id)
            d['attachments'] = [{k:getattr(a,k) for k in ['id','name','media_type','size','created_at']} for a in s.scalars(select(Attachment).where(Attachment.node_id==n.id))]
            if n.kind=='vocabulary':
                d['review'] = state_dict(s.get(ReviewState,n.id))
                d['review_history'] = [{k:getattr(r,k) for k in ['id','rating','reviewed_at','before_json','after_json','algorithm']} for r in s.scalars(select(ReviewLog).where(ReviewLog.node_id==n.id).order_by(ReviewLog.reviewed_at.desc()))]
            return d

    @app.put('/api/nodes/{node_id}')
    def update_node(node_id:str,data: NodeUpdate):
        with ws.lock, ws.Session.begin() as s:
            n = get_node(s,node_id)
            check_version(n,data.expected_version)
            return node_dict(save_node(s,ws,data,n),ws)

    @app.delete('/api/nodes/{node_id}')
    def delete_node(node_id:str, expected_version:int):
        with ws.lock, ws.Session.begin() as s:
            n = get_node(s,node_id)
            check_version(n,expected_version)
            n.deleted=True; n.updated_at=now(); n.version+=1
            index_node(s,ws,n)
            return {'deleted':True}

    @app.post('/api/nodes/{node_id}/restore')
    def restore_node(node_id:str):
        with ws.lock, ws.Session.begin() as s:
            n=get_node(s,node_id,True)
            n.deleted=False; n.updated_at=now(); n.version+=1
            index_node(s,ws,n)
            return node_dict(n)

    @app.get('/api/nodes/{node_id}/history')
    def history(node_id:str):
        with ws.lock, ws.Session() as s:
            get_node(s,node_id)
            return [{'id':r.id,'version':r.version,'created_at':r.created_at,'snapshot':json.loads(r.snapshot),'markdown':ws.read_note(r.note_path)} for r in s.scalars(select(Revision).where(Revision.node_id==node_id).order_by(Revision.version.desc()))]

    @app.post('/api/merge')
    def merge(data:MergeInput):
        with ws.lock, ws.Session.begin() as s:
            return merge_nodes(s,ws,data.source_id,data.target_id,data.source_version,data.target_version)

    @app.post('/api/relations')
    def create_relation(data: RelationInput):
        with ws.lock, ws.Session.begin() as s:
            return relation_dict(add_relation(s,data.source,data.target,data.type,data.description,data.evidence))

    @app.delete('/api/relations/{relation_id}')
    def delete_relation(relation_id:str):
        with ws.lock, ws.Session.begin() as s:
            r=s.get(Relation,relation_id)
            if not r: raise HTTPException(404,'关联不存在')
            s.delete(r)
            return {'deleted':True}

    @app.post('/api/nodes/{node_id}/attachments')
    def upload(node_id:str,file:UploadFile=File()):
        allowed = {'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.txt':'text/plain','.csv':'text/csv','.py':'text/plain','.md':'text/plain','.json':'application/json'}
        suffix=Path(file.filename or '').suffix.lower()
        if suffix not in allowed: raise HTTPException(415,'支持 PDF、PNG/JPEG/WebP、TXT、CSV、PY、MD 和 JSON')
        data=file.file.read(MAX_UPLOAD+1)
        if len(data)>MAX_UPLOAD: raise HTTPException(413,'附件不得超过 50 MB')
        if suffix=='.pdf' and not data.startswith(b'%PDF-'): raise HTTPException(422,'无效 PDF 文件')
        if suffix=='.png' and not data.startswith(b'\x89PNG\r\n\x1a\n'): raise HTTPException(422,'无效 PNG')
        if suffix in {'.jpg','.jpeg'} and not data.startswith(b'\xff\xd8\xff'): raise HTTPException(422,'无效 JPEG')
        if suffix=='.webp' and not (data[:4]==b'RIFF' and data[8:12]==b'WEBP'): raise HTTPException(422,'无效 WebP')
        with ws.lock, ws.Session.begin() as s:
            n=get_node(s,node_id)
            aid=uid()
            relative=f'{"literature/papers" if suffix==".pdf" and n.kind=="paper" else "attachments"}/{aid}{suffix}'
            ws.write_bytes(relative,data)
            name=(file.filename or 'attachment').replace('\\','/').split('/')[-1]
            s.add(Attachment(id=aid,node_id=n.id,name=name,path=relative,media_type=allowed[suffix],size=len(data),sha256=sha(data),created_at=now()))
            return {'id':aid,'name':name,'url':f'/api/attachments/{aid}'}

    @app.get('/api/attachments/{attachment_id}')
    def attachment(attachment_id:str):
        with ws.lock, ws.Session() as s:
            a=s.get(Attachment,attachment_id)
            if not a: raise HTTPException(404,'附件不存在')
            get_node(s,a.node_id)
            path=ws.path(a.path)
            if not path.is_file(): raise HTTPException(404,'附件文件缺失，请从备份恢复')
            disposition='inline' if a.media_type in {'application/pdf','image/png','image/jpeg','image/webp'} else 'attachment'
            return FileResponse(path,media_type=a.media_type,filename=a.name,content_disposition_type=disposition)

    @app.get('/api/import/schema')
    def schema(): return ImportBundle.model_json_schema()

    @app.post('/api/import/preview')
    def preview(bundle: ImportBundle):
        with ws.lock, ws.Session() as s: return preview_import(s,ws,bundle)

    @app.post('/api/import/commit')
    def commit(data: ImportCommit):
        with ws.lock, ws.Session.begin() as s: return commit_import(s,ws,data)

    @app.get('/api/reviews')
    def reviews(due:bool=True,tag: str|None=None,category:str|None=None,priority:int|None=None,paper_id:str|None=None,mistakes:bool=False):
        with ws.lock, ws.Session() as s:
            result=[]
            paper_nodes=None
            if paper_id:
                paper_nodes={r['node']['id'] for r in related(s,paper_id)}
            for st in s.scalars(select(ReviewState).order_by(ReviewState.due_at)):
                n=s.get(Node,st.node_id)
                if n.deleted or (due and st.due_at>now()) or (mistakes and st.lapses==0): continue
                m=json.loads(n.metadata_json)
                if tag and tag not in json.loads(n.tags_json): continue
                if category and m.get('vocabulary_category')!=category: continue
                if priority and m.get('priority')!=priority: continue
                if paper_nodes is not None and n.id not in paper_nodes: continue
                result.append({**node_dict(n,ws),'review':state_dict(st),'relations':related(s,n.id)})
                if len(result)>=100: break
            return result

    @app.post('/api/reviews/{node_id}')
    def review_word(node_id:str,data: ReviewInput):
        with ws.lock, ws.Session.begin() as s: return review(s,node_id,data)

    @app.get('/api/graph')
    def graph(center:str|None=None,depth:int=Query(1,ge=1,le=4),kind:str|None=None,type:str|None=None,q='',limit:int=Query(100,ge=1,le=250)):
        with ws.lock, ws.Session() as s:
            return graph_data(s,center,depth,kind,type,q,limit)

    @app.get('/api/categories')
    def categories():
        with ws.lock, ws.Session() as s: return [{k:getattr(c,k) for k in ['id','name','kind','parent_id']} for c in s.scalars(select(Category))]

    def check_parent(s,data,cid=None):
        seen={cid}
        current=data.parent_id
        while current:
            if current in seen: raise HTTPException(422,'分类不能形成循环')
            seen.add(current)
            p=s.get(Category,current)
            if not p or p.kind!=data.kind: raise HTTPException(422,'父分类不存在或类型不匹配')
            current=p.parent_id

    @app.post('/api/categories')
    def add_category(data:CategoryInput):
        with ws.lock, ws.Session.begin() as s:
            check_parent(s,data)
            c=Category(id=uid(),**data.model_dump());s.add(c)
            return {'id':c.id,**data.model_dump()}

    @app.put('/api/categories/{cid}')
    def update_category(cid:str,data:CategoryInput):
        with ws.lock, ws.Session.begin() as s:
            c=s.get(Category,cid)
            if not c: raise HTTPException(404,'分类不存在')
            if c.kind!=data.kind: raise HTTPException(422,'不能更改分类类型')
            check_parent(s,data,cid)
            c.name,c.parent_id=data.name,data.parent_id
            return {'id':cid,**data.model_dump()}

    @app.delete('/api/categories/{cid}')
    def delete_category(cid:str):
        with ws.lock, ws.Session.begin() as s:
            c=s.get(Category,cid)
            if not c: raise HTTPException(404,'分类不存在')
            if s.scalar(select(Category.id).where(Category.parent_id==cid).limit(1)) or any(cid in json.loads(n.metadata_json).get('category_ids',[]) for n in s.scalars(select(Node))):
                raise HTTPException(409,'分类仍有子分类或关联知识，请先调整')
            s.delete(c);return {'deleted':True}

    @app.post('/api/search/rebuild')
    def rebuild():
        with ws.lock, ws.Session.begin() as s:
            s.execute(text('DELETE FROM search_index'))
            for n in s.scalars(select(Node)): index_node(s,ws,n)
            return {'rebuilt':True}

    @app.get('/api/export/nodes/{node_id}')
    def export_note(node_id:str):
        with ws.lock, ws.Session() as s:
            n=get_node(s,node_id)
            data='# '+n.title+'\n\n'+ws.read_note(n.note_path)
            return Response(data,media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':f"attachment; filename*=UTF-8''{quote(n.title[:80],safe='')}.md"})

    @app.get('/api/export/json')
    def export_json():
        with ws.lock, ws.Session() as s:
            data={'data_format_version':'1.0','exported_at':now(),'nodes':[node_dict(n,ws) for n in s.scalars(select(Node))],'relations':[relation_dict(r) for r in s.scalars(select(Relation))],'categories':[{k:getattr(c,k) for k in ['id','kind','name','parent_id']} for c in s.scalars(select(Category))],'review_states':[{'node_id':r.node_id,**state_dict(r)} for r in s.scalars(select(ReviewState))],'review_history':[{k:getattr(r,k) for k in ['id','node_id','rating','reviewed_at','before_json','after_json','algorithm']} for r in s.scalars(select(ReviewLog))]}
            data['attachments']=[{k:getattr(a,k) for k in ['id','node_id','name','path','media_type','sha256','size','created_at']} for a in s.scalars(select(Attachment))]
            data['revisions']=[{'id':r.id,'node_id':r.node_id,'version':r.version,'snapshot':json.loads(r.snapshot),'markdown':ws.read_note(r.note_path),'created_at':r.created_at} for r in s.scalars(select(Revision))]
            return Response(dumps(data),media_type='application/json',headers={'Content-Disposition':'attachment; filename="research-hub.json"'})

    @app.get('/api/export/vocabulary')
    def export_vocabulary():
        stream=io.StringIO();writer=csv.writer(stream)
        writer.writerow(['id','term','part_of_speech','sense','meaning','contextual_meaning','sources','tags','review_count','due_at'])
        with ws.lock, ws.Session() as s:
            for n in s.scalars(select(Node).where(Node.kind=='vocabulary',Node.deleted==False)):
                m=json.loads(n.metadata_json); st=s.get(ReviewState,n.id)
                values=[n.id,n.title,m.get('part_of_speech',''),m.get('sense',''),m.get('meaning',''),m.get('contextual_meaning',''),'; '.join(m.get('sources',[])),'; '.join(json.loads(n.tags_json)),s.scalar(select(func.count()).select_from(ReviewLog).where(ReviewLog.node_id==n.id)),st.due_at]
                writer.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for v in values])
        return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="vocabulary.csv"'})

    @app.post('/api/backup')
    def backup():
        path=create_backup(ws,os.environ.get('RESEARCH_HUB_BACKUP_DIR'))
        return FileResponse(path,media_type='application/zip',filename=path.name)

    @app.post('/api/backup/restore')
    def restore(file:UploadFile=File(), name:str=Query(pattern=r'^[A-Za-z0-9_-]{1,80}$')):
        if not file.filename or not file.filename.lower().endswith('.zip'): raise HTTPException(415,'需上传 ZIP 备份')
        target=ws.root.parent/name
        with ws.lock:
            return restore_backup(file.file,target)

    dist=Path(__file__).resolve().parents[2]/'frontend/dist'
    if dist.exists():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app
