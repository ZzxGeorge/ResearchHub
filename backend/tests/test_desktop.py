import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.backup import restore_backup

ROOT=Path(__file__).resolve().parents[2]

def test_desktop_token_protects_reads_writes_static_and_health(tmp_path,monkeypatch):
    monkeypatch.setenv('RESEARCH_HUB_DESKTOP_TOKEN','test-secret-'*4)
    monkeypatch.setenv('RESEARCH_HUB_INSTANCE','test-instance')
    app=create_app(tmp_path/'secure')
    with TestClient(app,base_url='http://127.0.0.1') as c:
        for path in ['/api/health','/api/settings','/api/export/json','/']:
            assert c.get(path).status_code==401
        assert c.get('/api/health',headers={'X-Research-Hub-Token':'wrong'}).status_code==401
        headers={'X-Research-Hub-Token':'test-secret-'*4}
        assert c.get('/api/health',headers=headers).json()['instance']=='test-instance'
        assert c.post('/api/nodes',json={'kind':'paper','title':'blocked'},headers={**headers,'Origin':'https://evil.example'}).status_code==403
    app.state.workspace.engine.dispose()

def test_reading_position_validation_and_backup(client,tmp_path):
    n=client.post('/api/nodes',json={'kind':'paper','title':'中文论文'}).json()
    a=client.post('/api/nodes/'+n['id']+'/attachments',files={'file':('测试论文.pdf',b'%PDF-1.4\ntest')}).json()
    url='/api/attachments/'+a['id']+'/reading-state'
    assert client.get(url).json()=={'page':1,'scale':'page-width','offset':0,'rotation':0}
    position={'page':7,'scale':'1.5','offset':.35,'rotation':90}
    assert client.put(url,json=position).status_code==200
    assert client.put(url,json={**position,'scale':'javascript:bad'}).status_code==422
    assert client.put(url,json={**position,'offset':2}).status_code==422
    archive=client.post('/api/backup').content
    restore_backup(io.BytesIO(archive),tmp_path/'恢复资料')
    other=create_app(tmp_path/'恢复资料')
    with TestClient(other,base_url='http://127.0.0.1') as c:assert c.get(url).json()==position
    other.state.workspace.engine.dispose()

@pytest.mark.parametrize('historical_tag',['v0.1.0','v0.2.0'])
def test_actual_historical_workspace_migration_and_backup(tmp_path,historical_tag):
    archive=subprocess.run(['git','archive','--format=zip',historical_tag,'backend'],cwd=ROOT,capture_output=True)
    if archive.returncode:pytest.skip('Historical Git tag is needed for the historical integration fixture')
    old=tmp_path/'old-source';old.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive.stdout)) as z:z.extractall(old)
    workspace=tmp_path/'旧科研资料'
    code="""
import json,sys
from fastapi.testclient import TestClient
from app.main import create_app
app=create_app(sys.argv[1])
with TestClient(app,base_url='http://127.0.0.1') as c:
 p=c.post('/api/nodes',json={'kind':'paper','title':'保留论文','markdown':'我的手写笔记'}).json()
 v=c.post('/api/nodes',json={'kind':'vocabulary','title':'posterior','metadata':{'meaning':'后验'}}).json()
 c.post('/api/relations',json={'source':v['id'],'target':p['id'],'type':'derived_from'})
 c.post('/api/reviews/'+v['id'],json={'rating':'good','expected_version':1})
 c.post('/api/nodes/'+p['id']+'/attachments',files={'file':('中文.pdf',b'%PDF-1.4 test')})
 print(json.dumps({'paper':c.get('/api/nodes/'+p['id']).json(),'vocabulary':c.get('/api/nodes/'+v['id']).json()},ensure_ascii=True))
app.state.workspace.engine.dispose()
"""
    env={**os.environ,'PYTHONPATH':str(old/'backend')};env.pop('RESEARCH_HUB_DESKTOP_TOKEN',None)
    result=subprocess.run([sys.executable,'-c',code,str(workspace)],cwd=old,env=env,capture_output=True,text=True,check=True)
    before=json.loads(result.stdout)
    app=create_app(workspace)
    with TestClient(app,base_url='http://127.0.0.1') as c:
        for kind in ['paper','vocabulary']:
            after=c.get('/api/nodes/'+before[kind]['id']).json()
            for attachment in after['attachments']:
                assert len(attachment.pop('sha256'))==64
            assert after==before[kind]
    backups=list((workspace/'backups').glob('*.zip'));assert len(backups)==1
    restore_backup(backups[0],tmp_path/'迁移前恢复副本')
    app.state.workspace.engine.dispose()
