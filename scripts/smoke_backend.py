"""Exercise the packaged backend with a scrubbed runtime environment and isolated data."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import urllib.request
import urllib.error
import uuid

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--executable',type=Path,default=ROOT/'build/backend/ResearchHubBackend/ResearchHubBackend.exe');args=parser.parse_args()
    directory=ROOT/'.test-workspaces'/('桌面后端-v030-'+uuid.uuid4().hex[:8]);directory.mkdir(parents=True,exist_ok=True)
    token=secrets.token_hex(32)
    env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','CONDA_PREFIX'}}
    env.update(PATH=os.environ.get('SystemRoot','C:\\Windows')+'\\System32',RESEARCH_HUB_WORKSPACE=str(directory/'科研资料'),RESEARCH_HUB_LOG_DIR=str(directory/'logs'),RESEARCH_HUB_DESKTOP_TOKEN=token,RESEARCH_HUB_INSTANCE='packaged-smoke')
    process=subprocess.Popen([str(args.executable.resolve())],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    ready=[];errors=[]
    def reader():
        for line in process.stdout:
            try:
                value=json.loads(line)
                if value.get('event')=='ready':ready.append(value);return
            except ValueError:pass
    thread=threading.Thread(target=reader,daemon=True);thread.start();thread.join(60)
    try:
        if not ready:raise RuntimeError('Packaged startup failed: '+str(process.poll())+' '+(process.stderr.read() if process.poll() is not None else 'timeout'))
        base='http://127.0.0.1:'+str(ready[0]['port'])
        def request(path,data=None,auth=True,method=None,content_type='application/json'):
            headers={'Content-Type':content_type}
            if auth:headers['X-Research-Hub-Token']=token
            req=urllib.request.Request(base+path,data=data if isinstance(data,bytes) else json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
            return urllib.request.urlopen(req,timeout=20)
        try:request('/api/settings',auth=False);raise AssertionError('Missing token should fail')
        except urllib.error.HTTPError as e:assert e.code==401
        health=json.load(request('/api/health'))
        assert health['instance']=='packaged-smoke' and health['version']==json.loads((ROOT/'desktop/package.json').read_text())['version']
        assert b'<div id="root">' in request('/').read()
        assert request('/pdfjs/cmaps/Adobe-GB1-UCS2.bcmap').status==200
        bundle=json.loads((ROOT/'examples/reading_summary.json').read_text(encoding='utf-8'))
        preview=json.load(request('/api/import/preview',bundle));decisions={e['key']:{'action':'new'} for e in preview['entries']}
        report=json.load(request('/api/import/commit',{'bundle':bundle,'decisions':decisions}))
        assert report['created']==7
        assert json.load(request('/api/nodes?q=BPTT'))['total']>=5
        # Exercise new migrations, modules and Markdown resources inside the frozen executable.
        paper=json.load(request('/api/nodes',{'kind':'paper','title':'Public packaged reading fixture'}))
        boundary='ResearchHubPublicFixture'
        pdf=(ROOT/'.artifacts/中文论文阅读验收.pdf').read_bytes()
        payload=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="public.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+pdf+('\r\n--'+boundary+'--\r\n').encode()
        attachment=json.load(request('/api/nodes/'+paper['id']+'/attachments',payload,content_type='multipart/form-data; boundary='+boundary))
        detail=json.load(request('/api/nodes/'+paper['id']))
        sha256=detail['attachments'][0]['sha256']
        anchor={'paper_id':paper['id'],'attachment_id':attachment['id'],'pdf_sha256':sha256,'page':1,'raw_text':'posterior','cleaned_text':'posterior','rects':[{'page':1,'rect':[70,690,110,702]}]}
        captured=json.load(request('/api/reading/capture',{'anchor':anchor,'node':{'kind':'vocabulary','title':'packaged posterior','metadata':{'meaning':'后验'}},'annotation':{'markdown':'Packaged $p(z|x)$ annotation','color':'#8db9da'}}))
        source=json.load(request('/api/sources/'+captured['source']['id']))
        assert source['available'] and source['annotation']['markdown']=='Packaged $p(z|x)$ annotation'
        assert json.load(request('/api/nodes/'+captured['node']['id']+'/sources'))[0]['id']==source['id']
        state={'mode':'split','split_width':61,'panel_tab':'vocabulary','selected_anchor':source['id'],'selected_node':captured['node']['id'],'attachment_id':attachment['id'],'draft':{'text':'Durable draft'}}
        assert json.load(request('/api/papers/'+paper['id']+'/reading-workspace',state,method='PUT'))==state
        exported=json.load(request('/api/export/json'));assert exported['annotation_revisions'][0]['markdown']=='Packaged $p(z|x)$ annotation'
        assert request('/api/backup',method='POST').read().startswith(b'PK')
        duplicate=subprocess.Popen([str(args.executable.resolve())],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert duplicate.wait(timeout=15)!=0
        result={'version':health['version'],'executable':str(args.executable.resolve()),'port':ready[0]['port'],'health_identity':True,'unauthorized_read_blocked':True,'isolated_workspace':str(directory/'科研资料'),'runtime_path_scrubbed':True,'frontend_and_pdf_resources':True,'import_and_search':True,'interactive_capture_sources_annotations_drafts_backup':True,'duplicate_workspace_rejected':True}
    finally:
        if process.poll() is None:
            process.stdin.write('stop\n');process.stdin.flush();process.wait(timeout=15)
    result['graceful_exit_code']=process.returncode
    output=ROOT/'.artifacts/desktop-backend-smoke.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(output)
if __name__=='__main__':main()
