import json
import math
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text, or_
from fastapi import HTTPException
from .models import Node, Revision, Relation, ReviewState, ReviewLog, ImportReceipt, Category, Attachment
from .schemas import NodeInput, ImportBundle, SYMMETRIC, normalize
from .workspace import now, uid, dumps, sha

MATH_CATEGORIES = ['Linear Algebra','Matrix Analysis','Matrix Calculus','Probability Theory','Mathematical Statistics','Information Theory','Optimization','Stochastic Processes','Reinforcement Learning Theory','Dynamical Systems','Optimal Control','Differential Geometry','Lie Groups and Lie Algebras','Numerical Methods','Other Topics']
ALGORITHM_CATEGORIES = ['Model-free RL','Model-based RL','Imitation Learning','Motion Priors','World Models','Latent Variable Models','Representation Learning','Planning','Optimal Control','State Estimation','Sim-to-Real','Multi-agent Learning']

def seed_categories(ws):
    with ws.lock, ws.Session.begin() as s:
        if s.scalar(select(Category.id).limit(1)):
            return
        for kind, names in [('mathematics',MATH_CATEGORIES),('algorithm',ALGORITHM_CATEGORIES)]:
            for name in names:
                s.add(Category(id=uid(), name=name, kind=kind))

def get_node(s, node_id, deleted=False):
    n = s.get(Node, node_id)
    if not n or (n.deleted and not deleted):
        raise HTTPException(404, '知识条目不存在或已在回收站')
    return n

def node_dict(n, ws=None):
    d = {k:getattr(n,k) for k in ['id','kind','title','status','version','created_at','updated_at','deleted']}
    d.update(tags=json.loads(n.tags_json), metadata=json.loads(n.metadata_json))
    if ws:
        d['markdown'] = ws.read_note(n.note_path)
    return d

def check_version(n, expected):
    if n.version != expected:
        raise HTTPException(409, '笔记已有更新。当前草稿已保留，请重新加载后合并。')

def index_node(s, ws, n):
    s.execute(text('DELETE FROM search_index WHERE node_id=:id'), {'id':n.id})
    if not n.deleted:
        value = normalize(' '.join([n.title, n.tags_json, n.metadata_json, ws.read_note(n.note_path)]))
        s.execute(text('INSERT INTO search_index(node_id,text) VALUES (:id,:value)'), {'id':n.id,'value':value})

def save_node(s, ws, data: NodeInput, node=None):
    if node and node.kind != data.kind:
        raise HTTPException(422,'不能改变知识条目的类型')
    for cid in data.metadata.category_ids:
        category = s.get(Category,cid)
        if not category or category.kind != data.kind:
            raise HTTPException(422, '分类不存在或类型不匹配')
    if not node:
        node = Node(id=uid(), kind=data.kind, created_at=now(), version=0, deleted=False)
        s.add(node)
    node.version += 1
    node.title, node.normalized_title = data.title, normalize(data.title)
    node.status, node.tags_json = data.status, dumps(data.tags)
    node.metadata_json = dumps(data.metadata.model_dump(mode='json'))
    node.note_path = ws.write_note(node.kind, node.id, node.version, data.markdown)
    node.updated_at = now()
    s.flush()
    s.add(Revision(id=uid(),node_id=node.id,version=node.version,note_path=node.note_path,snapshot=dumps(node_dict(node)),created_at=now()))
    if node.kind == 'vocabulary' and not s.get(ReviewState,node.id):
        s.add(ReviewState(node_id=node.id,repetitions=0,interval_days=0,ease='2.5',due_at=now(),lapses=0,version=1))
    index_node(s,ws,node)
    s.flush()
    return node

def add_relation(s, source, target, type_, description='', evidence=''):
    if source == target:
        raise HTTPException(422, '不能关联自身')
    get_node(s,source); get_node(s,target)
    if type_ in SYMMETRIC:
        source, target = sorted([source,target])
    existing = s.scalar(select(Relation).where(Relation.source==source,Relation.target==target,Relation.type==type_))
    if existing:
        # Preserve additional evidence without silently overwriting old descriptions.
        for key, value in [('description',description),('evidence',evidence)]:
            old = getattr(existing,key)
            if value and value not in old:
                setattr(existing,key,old + ('\n' if old else '') + value)
        return existing
    r = Relation(id=uid(),source=source,target=target,type=type_,description=description,evidence=evidence,created_at=now())
    s.add(r); s.flush()
    return r

def relation_dict(r):
    return {k:getattr(r,k) for k in ['id','source','target','type','description','evidence','created_at']}

def related(s, node_id):
    rows = s.scalars(select(Relation).where(or_(Relation.source==node_id,Relation.target==node_id))).all()
    result = []
    for r in rows:
        other = s.get(Node,r.target if r.source==node_id else r.source)
        if other and not other.deleted:
            result.append({**relation_dict(r),'node':node_dict(other),'direction':'symmetric' if r.type in SYMMETRIC else ('outgoing' if r.source==node_id else 'incoming')})
    return result

def search_nodes(s, query='', kind=None, tag=None, since=None, until=None, deleted=False, limit=100, offset=0, sort='updated', status=None, year=None, importance=None, direction=None, incomplete=False):
    stmt = select(Node).where(Node.deleted==deleted)
    if kind: stmt = stmt.where(Node.kind==kind)
    if status: stmt = stmt.where(Node.status==status)
    if since: stmt = stmt.where(Node.updated_at>=since)
    if until: stmt = stmt.where(Node.updated_at<=until+'T23:59:59.999999+00:00')
    if query.strip():
        q = normalize(query)
        # Phrase-escape FTS syntax. LIKE fallback handles Chinese and substrings.
        phrase = '"'+q.replace('"','""')+'"'
        escaped = q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        ids = s.execute(text("SELECT node_id FROM search_index WHERE search_index MATCH :q UNION SELECT node_id FROM search_index WHERE text LIKE :sub ESCAPE '\\'"),{'q':phrase,'sub':'%'+escaped+'%'}).scalars().all()
        stmt = stmt.where(Node.id.in_(ids))
    rows = s.scalars(stmt).all()
    def matches(n):
        m = json.loads(n.metadata_json)
        if incomplete and (n.kind!='vocabulary' or (m.get('meaning') or '').strip() or (m.get('contextual_meaning') or '').strip()): return False
        return (not tag or tag in json.loads(n.tags_json)) and (not year or m.get('year')==year) and (not importance or m.get('importance')==importance) and (not direction or direction in m.get('directions',[]))
    rows = [n for n in rows if matches(n)]
    rows.sort(key=(lambda n: normalize(n.title)) if sort=='title' else ((lambda n:json.loads(n.metadata_json).get('year') or 0) if sort=='year' else (lambda n:n.updated_at)), reverse=sort!='title')
    return {'items':[node_dict(n) for n in rows[offset:offset+limit]],'total':len(rows)}

def candidates(s, entry):
    rows = s.scalars(select(Node).where(Node.deleted==False,Node.kind==entry.kind)).all()
    result = []
    incoming = entry.metadata
    for n in rows:
        m = json.loads(n.metadata_json)
        reason = None
        if entry.match_id == n.id: reason = 'explicit_id'
        elif entry.kind=='paper' and incoming.doi and normalize(incoming.doi)==normalize(m.get('doi','')): reason='doi'
        elif entry.kind=='paper' and incoming.arxiv_id and normalize(incoming.arxiv_id)==normalize(m.get('arxiv_id','')): reason='arxiv'
        elif n.normalized_title==normalize(entry.title):
            reason = 'same_title'
            if entry.kind=='vocabulary':
                reason = 'same_term_sense_pos' if all(normalize(m.get(k,''))==normalize(getattr(incoming,k)) for k in ['sense','part_of_speech']) else 'different_sense_or_pos'
        if reason:
            result.append({**node_dict(n),'reason':reason})
    return result

def bundle_digest(bundle):
    return sha(dumps(bundle.model_dump(mode='json')).encode())

def preview_import(s, ws, bundle):
    receipt = s.get(ImportReceipt,bundle_digest(bundle))
    return {'digest':bundle_digest(bundle),'already_imported':bool(receipt),'entries':[{'key':e.key,'incoming':e.model_dump(mode='json'),'candidates':[{**c,'markdown':ws.read_note(get_node(s,c['id']).note_path)} for c in candidates(s,e)]} for e in bundle.entries()]}

def merge_data(ws, old, incoming):
    data = node_dict(old,ws)
    meta = data['metadata']
    new_meta = incoming.metadata.model_dump(mode='json',exclude_unset=True)
    conflicts = {}
    for key, value in new_meta.items():
        if isinstance(value,list):
            meta[key] = list(dict.fromkeys(meta.get(key,[]) + value))
        elif not meta.get(key): meta[key]=value
        elif value != meta[key] and value not in ['', None]: conflicts[key]=value
    addition = incoming.markdown.strip()
    if conflicts:
        addition += '\n\n### 导入元数据差异（保留原字段，供人工确认）\n```json\n'+dumps(conflicts)+'\n```'
    body = data['markdown']
    if addition and addition not in body:
        body += '\n\n---\n## 导入补充 · '+now()[:10]+'\n\n'+addition
    return NodeInput(kind=old.kind,title=old.title,status=old.status,tags=list(dict.fromkeys(data['tags']+incoming.tags)),metadata=meta,markdown=body)

def commit_import(s, ws, request):
    bundle = request.bundle
    digest = bundle_digest(bundle)
    receipt = s.get(ImportReceipt,digest)
    if receipt:
        return {**json.loads(receipt.report_json),'already_imported':True}
    entries = bundle.entries()
    if set(request.decisions) != {e.key for e in entries}:
        raise HTTPException(422,'每个条目均需明确选择新增、合并或跳过')
    # Validate every decision against original versions before any write.
    for e in entries:
        d = request.decisions[e.key]
        if d.action=='merge' or (d.action=='skip' and d.target_id):
            target = get_node(s,d.target_id)
            if target.kind != e.kind: raise HTTPException(422,'合并对象类型不匹配')
            check_version(target,d.expected_version)
    mapping, report = {}, {'created':0,'merged':0,'skipped':0,'relations':0,'nodes':{},'warnings':[],'digest':digest}
    for e in entries:
        d = request.decisions[e.key]
        if d.action=='skip':
            report['skipped'] += 1
            if d.target_id: mapping[e.key]=d.target_id
            continue
        body = e.markdown
        if e.key==bundle.paper.key:
            body = '\n\n'.join(x for x in [body,bundle.literature_note,('## 阅读总结\n'+bundle.reading_summary) if bundle.reading_summary else ''] if x)
        item = e.model_copy(update={'markdown':body})
        old = get_node(s,d.target_id) if d.action=='merge' else None
        data = merge_data(ws,old,item) if old else NodeInput(**item.model_dump(exclude={'key','match_id'}))
        saved = save_node(s,ws,data,old)
        mapping[e.key]=saved.id
        report['merged' if old else 'created'] += 1
    paper_id = mapping.get(bundle.paper.key)
    for key, node_id in mapping.items():
        if paper_id and node_id!=paper_id:
            add_relation(s,node_id,paper_id,'derived_from',evidence='结构化阅读总结导入')
    for r in bundle.relations:
        if r.source in mapping and r.target in mapping:
            if mapping[r.source] != mapping[r.target]:
                add_relation(s,mapping[r.source],mapping[r.target],r.type,r.description,r.evidence)
                report['relations'] += 1
        else: report['warnings'].append(f'跳过未映射的关系 {r.source} → {r.target}')
    report['nodes']=mapping
    s.add(ImportReceipt(digest=digest,report_json=dumps(report),created_at=now()))
    return report

def state_dict(st):
    return {k:getattr(st,k) for k in ['repetitions','interval_days','ease','due_at','last_review','lapses','version']}

def schedule_review(before, rating, at=None):
    """SM-2 v1: Again=0, Hard=3, Good=4, Easy=5. UTC timestamps."""
    at = at or datetime.now(timezone.utc)
    quality = {'again':0,'hard':3,'good':4,'easy':5}[rating]
    ease = float(before['ease'])
    reps, interval, lapses = before['repetitions'], before['interval_days'], before['lapses']
    ease = max(1.3, ease + (0.1 - (5-quality)*(0.08+(5-quality)*0.02)))
    if quality < 3:
        reps, interval, lapses = 0, 1, lapses+1
        due = at + timedelta(minutes=10)
    else:
        interval = 1 if reps==0 else (6 if reps==1 else max(1,math.ceil(interval*ease)))
        reps += 1
        due = at + timedelta(days=interval)
    return dict(repetitions=reps,interval_days=interval,ease=str(round(ease,4)),due_at=due.isoformat(),last_review=at.isoformat(),lapses=lapses,version=before['version']+1)

def review(s, node_id, request):
    n = get_node(s,node_id)
    if n.kind != 'vocabulary': raise HTTPException(422,'只有词汇可复习')
    from .reading import eligible_vocabulary
    if not eligible_vocabulary(n): raise HTTPException(422,'请先补充中文含义或语境含义，再开始闪卡复习')
    st = s.get(ReviewState,node_id)
    if st.version != request.expected_version: raise HTTPException(409,'该词汇已在另一窗口复习，请刷新')
    before = state_dict(st)
    after = schedule_review(before,request.rating)
    for k,v in after.items(): setattr(st,k,v)
    s.add(ReviewLog(id=uid(),node_id=node_id,rating=request.rating,reviewed_at=now(),before_json=dumps(before),after_json=dumps(after),algorithm='sm2-v1'))
    return after

def merge_nodes(s, ws, source_id, target_id, source_version, target_version):
    source, target = get_node(s,source_id), get_node(s,target_id)
    if source.id==target.id or source.kind!=target.kind: raise HTTPException(422,'需选择两个不同的同类条目')
    check_version(source,source_version); check_version(target,target_version)
    if source.kind=='vocabulary': raise HTTPException(422,'已有词汇含复习历史，请通过导入附加新语境，暂不支持合并两个独立复习队列')
    incoming = NodeInput(**{k:v for k,v in node_dict(source,ws).items() if k in NodeInput.model_fields})
    save_node(s,ws,merge_data(ws,target,incoming),target)
    from .models import SourceLink
    for source_link in s.scalars(select(SourceLink).where(SourceLink.node_id==source_id)):
        if not s.get(SourceLink,(source_link.anchor_id,target_id)):
            s.add(SourceLink(anchor_id=source_link.anchor_id,node_id=target_id,created_at=now()))
    edges = s.scalars(select(Relation).where(or_(Relation.source==source_id,Relation.target==source_id))).all()
    for r in edges:
        a,b = (target_id if r.source==source_id else r.source),(target_id if r.target==source_id else r.target)
        if a!=b and not get_node(s,a,True).deleted and not get_node(s,b,True).deleted:
            add_relation(s,a,b,r.type,r.description,r.evidence)
    source.deleted=True; source.updated_at=now(); source.version+=1
    index_node(s,ws,source)
    return node_dict(target,ws)

def graph_data(s,center=None,depth=1,kind=None,edge_type=None,q='',limit=100):
    """Bound both the returned nodes and each traversal query; never load the entire graph."""
    truncated=False
    selected=None
    if center:
        get_node(s,center)
        selected={center};frontier={center}
        for _ in range(depth):
            stmt=select(Relation).where(or_(Relation.source.in_(frontier),Relation.target.in_(frontier)))
            if edge_type: stmt=stmt.where(Relation.type==edge_type)
            edges=s.scalars(stmt.order_by(Relation.created_at.desc()).limit(2001)).all()
            if len(edges)>2000: truncated=True
            candidate_ids=set()
            for r in edges[:2000]: candidate_ids.update([r.source,r.target])
            candidate_ids-=selected
            rows=s.scalars(select(Node.id).where(Node.id.in_(candidate_ids),Node.deleted==False).order_by(Node.updated_at.desc()).limit(limit+1)).all()
            remaining=max(0,limit-len(selected))
            if len(rows)>remaining: truncated=True
            frontier=set(rows[:remaining]);selected.update(frontier)
            if not frontier or len(selected)>=limit: break
    stmt=select(Node).where(Node.deleted==False)
    if selected is not None: stmt=stmt.where(Node.id.in_(selected))
    if kind: stmt=stmt.where(Node.kind==kind)
    if q: stmt=stmt.where(Node.normalized_title.contains(normalize(q),autoescape=True))
    nodes=s.scalars(stmt.order_by(Node.updated_at.desc()).limit(limit+1)).all()
    truncated=truncated or len(nodes)>limit
    nodes=nodes[:limit];ids=[n.id for n in nodes]
    edge_query=select(Relation).where(Relation.source.in_(ids),Relation.target.in_(ids))
    if edge_type:edge_query=edge_query.where(Relation.type==edge_type)
    edges=s.scalars(edge_query.limit(2001)).all()
    truncated=truncated or len(edges)>2000
    return {'nodes':[node_dict(n) for n in nodes],'edges':[relation_dict(r) for r in edges[:2000]],'truncated':truncated,'limit':limit}
