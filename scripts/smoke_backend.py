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

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--executable',type=Path,default=ROOT/'build/backend/ResearchHubBackend/ResearchHubBackend.exe');args=parser.parse_args()
    directory=ROOT/'.test-workspaces/桌面后端验收';directory.mkdir(parents=True,exist_ok=True)
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
        def request(path,data=None,auth=True,method=None):
            headers={'Content-Type':'application/json'}
            if auth:headers['X-Research-Hub-Token']=token
            req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
            return urllib.request.urlopen(req,timeout=20)
        try:request('/api/settings',auth=False);raise AssertionError('Missing token should fail')
        except urllib.error.HTTPError as e:assert e.code==401
        assert json.load(request('/api/health'))['instance']=='packaged-smoke'
        assert b'<div id="root">' in request('/').read()
        assert request('/pdfjs/cmaps/Adobe-GB1-UCS2.bcmap').status==200
        bundle=json.loads((ROOT/'examples/reading_summary.json').read_text(encoding='utf-8'))
        preview=json.load(request('/api/import/preview',bundle));decisions={e['key']:{'action':'new'} for e in preview['entries']}
        report=json.load(request('/api/import/commit',{'bundle':bundle,'decisions':decisions}))
        assert report['created']==7
        assert json.load(request('/api/nodes?q=BPTT'))['total']>=5
        duplicate=subprocess.Popen([str(args.executable.resolve())],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert duplicate.wait(timeout=15)!=0
        result={'executable':str(args.executable.resolve()),'port':ready[0]['port'],'health_identity':True,'unauthorized_read_blocked':True,'isolated_workspace':str(directory/'科研资料'),'runtime_path_scrubbed':True,'frontend_and_pdf_resources':True,'import_and_search':True,'duplicate_workspace_rejected':True}
    finally:
        if process.poll() is None:
            process.stdin.write('stop\n');process.stdin.flush();process.wait(timeout=15)
    result['graceful_exit_code']=process.returncode
    output=ROOT/'.artifacts/desktop-backend-smoke.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(output)
if __name__=='__main__':main()
