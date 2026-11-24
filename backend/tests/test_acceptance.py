import copy
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy import select
from jsonschema import Draft202012Validator
from app.schemas import ImportBundle
from app.models import Node,Attachment,Revision
from app.services import schedule_review
from app.backup import create_backup,restore_backup
from app.main import create_app
from fastapi.testclient import TestClient
from conftest import create,commit

def update(client,node,**kwargs):
    data={k:node[k] for k in ['kind','title','status','tags','metadata','markdown']}
    return client.put('/api/nodes/'+node['id'],json={**data,**kwargs,'expected_version':node['version']})

def test_dashboard_is_empty_and_categories_exist(client):
    d=client.get('/api/dashboard').json()
    assert sum(d['counts'].values())==0
    assert d['due_vocabulary']==0
    assert len(client.get('/api/categories').json())==27

@pytest.mark.parametrize('kind',['paper','vocabulary','mathematics','algorithm','idea','question'])
def test_crud_history_soft_delete_restore(client,kind):
    n=create(client,kind,markdown='Original **knowledge** $x^2$')
    r=update(client,n,title='Updated',markdown='手写科研理解 BPTT')
    assert r.status_code==200,r.text
    new=r.json()
    assert new['version']==2 and new['markdown']=='手写科研理解 BPTT'
    assert update(client,n,markdown='stale edit').status_code==409
    assert client.get('/api/nodes/'+n['id']).json()['markdown']==new['markdown']
    history=client.get('/api/nodes/'+n['id']+'/history').json()
    assert len(history)==2 and history[1]['markdown'].startswith('Original')
    assert client.get('/api/nodes?q=手写科研').json()['total']==1
    assert client.delete('/api/nodes/'+n['id']+'?expected_version=1').status_code==409
    assert client.delete('/api/nodes/'+n['id']+'?expected_version=2').status_code==200
    assert client.get('/api/nodes/'+n['id']).status_code==404
    assert client.get('/api/nodes?q=BPTT').json()['total']==0
    assert client.get('/api/nodes?deleted=true').json()['total']==1
    assert client.post('/api/nodes/'+n['id']+'/restore').status_code==200
    assert client.get('/api/nodes?q=BPTT').json()['total']==1

def test_paper_pdf_attachment_status_export(client):
    n=create(client,title='Paper',metadata={'year':2025,'authors':['Alice'],'doi':'10.example/test'})
    data=b'%PDF-1.4\nexample'
    upload=client.post('/api/nodes/'+n['id']+'/attachments',files={'file':('../../paper.pdf',data,'application/pdf')})
    assert upload.status_code==200,upload.text
    aid=upload.json()['id']
    assert upload.json()['name']=='paper.pdf'
    r=client.get('/api/attachments/'+aid)
    assert r.content==data and r.headers['content-type']=='application/pdf'
    assert update(client,n,status='reading',metadata={**n['metadata'],'reproduction_status':'in_progress'}).status_code==200
    assert client.get('/api/nodes?kind=paper&year=2025&status=reading&importance=3').json()['total']==1
    assert client.get('/api/export/nodes/'+n['id']).headers['content-type'].startswith('text/markdown')
    assert client.post('/api/nodes/'+n['id']+'/attachments',files={'file':('bad.pdf',b'not PDF')}).status_code==422
    assert client.post('/api/nodes/'+n['id']+'/attachments',files={'file':('evil.html',b'<script>')}).status_code==415
    assert client.post('/api/nodes/'+n['id']+'/attachments',files={'file':('evil.png',b'<script>')}).status_code==422
    archive=client.get('/api/export/json').json()
    assert archive['attachments'][0]['id']==aid and len(archive['revisions'])==2

def test_schema_example_and_prompt_match(client,bundle):
    schema=json.loads(Path('schemas/reading-summary-v1.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(bundle)
    parsed=ImportBundle.model_validate(bundle)
    assert len(parsed.entries())==7
    actual=client.get('/api/import/schema').json()
    assert {k:v for k,v in schema.items() if k not in ['$schema','$id']}==actual
    prompt=Path('docs/chatgpt_export_prompt.md').read_text(encoding='utf-8')
    assert json.dumps(schema,ensure_ascii=False,indent=2) in prompt

def test_full_import_idempotency_relationships_search(client,bundle):
    report=commit(client,bundle)
    assert report.status_code==200,report.text
    r=report.json();assert r['created']==7
    paper=client.get('/api/nodes/'+r['nodes']['paper']).json()
    assert 'begin{bmatrix}' in paper['markdown']
    bptt=client.get('/api/nodes/'+r['nodes']['bptt']).json()
    jac=client.get('/api/nodes/'+r['nodes']['jacobian']).json()
    assert any(e['node']['id']==jac['id'] for e in bptt['relations'])
    assert any(e['node']['id']==bptt['id'] and e['direction']=='incoming' for e in jac['relations'])
    idea=client.get('/api/nodes/'+r['nodes']['idea']).json()
    assert '实验设计' in idea['markdown'] and idea['status']=='design'
    search=client.get('/api/nodes?q=BPTT').json()
    assert {'paper','mathematics','algorithm','idea','question'} <= {n['kind'] for n in search['items']}
    assert client.get('/api/nodes?q=科研').json()['total']>=1
    duplicate=commit(client,bundle).json()
    assert duplicate['already_imported'] and duplicate['nodes']==r['nodes']
    assert sum(client.get('/api/dashboard').json()['counts'].values())==7
    graph=client.get('/api/graph?center='+r['nodes']['bptt']+'&depth=2&limit=3').json()
    assert len(graph['nodes'])<=3 and graph['truncated']
    assert all(e['source'] in {n['id'] for n in graph['nodes']} and e['target'] in {n['id'] for n in graph['nodes']} for e in graph['edges'])

def test_posterior_multiple_papers_merge_preserves_notes_review(client,bundle):
    first=commit(client,bundle).json()
    vocab=client.get('/api/nodes/'+first['nodes']['posterior']).json()
    vocab=update(client,vocab,markdown='我的手写笔记').json()
    review=client.post('/api/reviews/'+vocab['id'],json={'rating':'good','expected_version':1})
    assert review.status_code==200
    second=copy.deepcopy(bundle)
    second['paper']['title']='Second Paper'
    second['vocabulary'][0]['title']='POSTERIOR'
    second['vocabulary'][0]['metadata']['examples']=['A second posterior context.']
    second['vocabulary'][0]['metadata']['meaning']='新语境中的解释'
    second['vocabulary'][0]['markdown']='新论文应用场景'
    preview=client.post('/api/import/preview',json=second).json()
    decisions={e['key']:{'action':'skip'} for e in preview['entries']}
    decisions['paper']={'action':'new'}
    candidates=next(e['candidates'] for e in preview['entries'] if e['key']=='posterior')
    assert candidates[0]['reason']=='same_term_sense_pos'
    decisions['posterior']={'action':'merge','target_id':vocab['id'],'expected_version':vocab['version']}
    report=commit(client,second,decisions)
    assert report.status_code==200,report.text
    detail=client.get('/api/nodes/'+vocab['id']).json()
    assert detail['markdown'].startswith('我的手写笔记') and '新论文应用场景' in detail['markdown']
    assert detail['metadata']['meaning']=='后验分布'
    assert '新语境中的解释' in detail['markdown']
    assert len(detail['metadata']['examples'])==2
    assert len([e for e in detail['relations'] if e['node']['kind']=='paper'])==2
    assert len(detail['review_history'])==1 and detail['review']['version']==2
    assert client.get('/api/nodes?kind=vocabulary').json()['total']==1
    second['vocabulary'][0]['metadata']['part_of_speech']='adjective'
    p=client.post('/api/import/preview',json=second).json()
    assert next(e for e in p['entries'] if e['key']=='posterior')['candidates'][0]['reason']=='different_sense_or_pos'

def test_import_validation_and_atomic_failure(client,bundle,monkeypatch):
    before=create(client,title='Must survive',markdown='Permanent')
    invalid=copy.deepcopy(bundle);invalid['relations'][0]['target']='missing'
    assert client.post('/api/import/preview',json=invalid).status_code==422
    invalid=copy.deepcopy(bundle);invalid['schema_version']='99'
    assert client.post('/api/import/preview',json=invalid).status_code==422
    assert client.post('/api/import/preview',content='{broken',headers={'content-type':'application/json'}).status_code==422
    ws=client.app.state.workspace
    original=ws.write_note
    calls=[]
    def fail(*args):
        calls.append(1)
        if len(calls)==3: raise OSError('Injected disk failure')
        return original(*args)
    monkeypatch.setattr(ws,'write_note',fail)
    r=commit(client,bundle)
    assert r.status_code==500,r.text
    assert client.get('/api/nodes').json()['total']==1
    assert client.get('/api/nodes/'+before['id']).json()['markdown']=='Permanent'
    with ws.Session() as s:
        assert len(s.scalars(select(Revision)).all())==1
    monkeypatch.setattr(ws,'write_note',original)
    assert commit(client,bundle).status_code==200

def test_import_stale_merge_transaction_rejected(client,bundle):
    old=create(client,'algorithm','BPTT',markdown='hand-written')
    decisions={e.key:{'action':'new'} for e in ImportBundle.model_validate(bundle).entries()}
    decisions['bptt']={'action':'merge','target_id':old['id'],'expected_version':1}
    assert update(client,old,markdown='new manual edit').status_code==200
    assert commit(client,bundle,decisions).status_code==409
    assert client.get('/api/nodes').json()['total']==1
    assert client.get('/api/nodes/'+old['id']).json()['markdown']=='new manual edit'

def test_review_algorithm_and_history(client):
    n=create(client,'vocabulary','term')
    state=client.get('/api/nodes/'+n['id']).json()['review']
    at=datetime(2026,1,1,tzinfo=timezone.utc)
    hard=schedule_review(state,'hard',at)
    assert hard['ease']=='2.36' and hard['interval_days']==1
    again=schedule_review(state,'again',at)
    assert datetime.fromisoformat(again['due_at'])==at+timedelta(minutes=10) and again['lapses']==1
    for _ in range(12): again=schedule_review(again,'again',at)
    assert float(again['ease'])>=1.3
    good=schedule_review(state,'good',at)
    good=schedule_review(good,'good',at)
    assert good['interval_days']==6
    good=schedule_review(good,'good',at)
    assert good['interval_days']==15
    assert float(schedule_review(state,'easy',at)['ease'])==2.6
    assert len(client.get('/api/reviews').json())==1
    assert client.post('/api/reviews/'+n['id'],json={'rating':'good','expected_version':1}).status_code==200
    assert client.post('/api/reviews/'+n['id'],json={'rating':'again','expected_version':1}).status_code==409
    assert client.get('/api/reviews').json()==[]
    assert len(client.get('/api/reviews?due=false').json())==1
    d=client.get('/api/nodes/'+n['id']).json()
    assert len(d['review_history'])==1 and d['review_history'][0]['algorithm']=='sm2-v1'
    assert 'term' in client.get('/api/export/vocabulary').text

def test_backup_restore_independent_workspace(client,bundle,tmp_path):
    r=commit(client,bundle).json()
    pdf=b'%PDF-1.4\nminimal test'
    attachment=client.post('/api/nodes/'+r['nodes']['paper']+'/attachments',files={'file':('source.pdf',pdf)})
    assert attachment.status_code==200
    aid=attachment.json()['id']
    client.post('/api/reviews/'+r['nodes']['posterior'],json={'rating':'hard','expected_version':1})
    ws=client.app.state.workspace
    backup=create_backup(ws)
    result=restore_backup(backup,tmp_path/'restored')
    assert result['files']>=10
    other=create_app(tmp_path/'restored')
    with TestClient(other,base_url='http://127.0.0.1') as c:
        assert c.get('/api/dashboard').json()==client.get('/api/dashboard').json()
        assert c.get('/api/nodes/'+r['nodes']['bptt']).json()==client.get('/api/nodes/'+r['nodes']['bptt']).json()
        assert c.get('/api/attachments/'+aid).content==pdf
        assert len(c.get('/api/nodes/'+r['nodes']['posterior']).json()['review_history'])==1
        assert c.get('/api/nodes?q=BPTT').json()['total']>=5
    other.state.workspace.engine.dispose()
    with pytest.raises(ValueError,match='新目录'): restore_backup(backup,tmp_path/'restored')
    response=client.post('/api/backup')
    assert response.status_code==200 and zipfile.is_zipfile(io.BytesIO(response.content))

def test_corrupt_backup_and_traversal_never_overwrite(client,tmp_path):
    n=create(client,markdown='keep me')
    ws=client.app.state.workspace
    archive=create_backup(ws)
    corrupt=tmp_path/'corrupt.zip'
    with zipfile.ZipFile(archive) as src,zipfile.ZipFile(corrupt,'w') as dst:
        for i in src.infolist(): dst.writestr(i.filename,b'corrupt' if i.filename.endswith('.md') else src.read(i.filename))
    with pytest.raises(ValueError,match='校验失败'): restore_backup(corrupt,tmp_path/'bad-target')
    assert not (tmp_path/'bad-target').exists()
    malicious=tmp_path/'evil.zip'
    with zipfile.ZipFile(malicious,'w') as z: z.writestr('../escape.txt','bad')
    with pytest.raises(ValueError,match='非法路径'): restore_backup(malicious,tmp_path/'evil-target')
    assert not (tmp_path/'escape.txt').exists()
    assert client.get('/api/nodes/'+n['id']).json()['markdown']=='keep me'

def test_missing_files_and_migration_reopen(client,tmp_path):
    n=create(client,markdown='safe')
    ws=client.app.state.workspace
    with ws.Session() as s: path=ws.path(s.get(Node,n['id']).note_path)
    data=path.read_bytes();path.unlink()
    assert client.get('/api/nodes/'+n['id']).status_code==422
    with pytest.raises(ValueError,match='缺失'): create_backup(ws)
    path.write_bytes(data)
    # Re-opening reruns Alembic upgrade(head) without resetting existing material.
    other=create_app(ws.root)
    with TestClient(other,base_url='http://127.0.0.1') as c: assert c.get('/api/nodes/'+n['id']).json()['markdown']=='safe'
    other.state.workspace.engine.dispose()
    with sqlite3.connect(ws.db) as db: assert db.execute('select version_num from alembic_version').fetchone()[0]=='0001'
    with pytest.raises(ValueError,match='非法'): ws.path('../outside')

def test_graph_query_filters_before_limiting(client):
    old=create(client,'mathematics','Older unique target')
    for index in range(4): create(client,'algorithm',f'New node {index}')
    graph=client.get('/api/graph',params={'q':'Older unique','limit':2}).json()
    assert [n['id'] for n in graph['nodes']]==[old['id']]
    limited=client.get('/api/graph?limit=2').json()
    assert len(limited['nodes'])==2 and limited['truncated']

def test_invalid_merge_and_corrupt_restore(client):
    assert client.post('/api/merge',json={}).status_code==422
    response=client.post('/api/backup/restore?name=bad-zip',files={'file':('bad.zip',b'not a zip')})
    assert response.status_code==422

def test_symmetric_edges_and_manual_merge(client):
    a=create(client,'mathematics','A',markdown='original A')
    b=create(client,'mathematics','B',markdown='original B')
    paper=create(client,title='Source')
    for source,target in [(a['id'],paper['id']),(paper['id'],a['id'])]:
        assert client.post('/api/relations',json={'source':source,'target':target,'type':'related_to'}).status_code==200
    assert len(client.get('/api/nodes/'+a['id']).json()['relations'])==1
    merged=client.post('/api/merge',json={'source_id':a['id'],'target_id':b['id'],'source_version':1,'target_version':1})
    assert merged.status_code==200,merged.text
    assert 'original A' in merged.json()['markdown'] and 'original B' in merged.json()['markdown']
    assert client.get('/api/nodes/'+a['id']).status_code==404
    assert client.get('/api/nodes/'+b['id']).json()['relations'][0]['node']['id']==paper['id']

def test_categories_cycles_and_referenced_delete(client):
    a=client.post('/api/categories',json={'kind':'mathematics','name':'Parent'}).json()
    b=client.post('/api/categories',json={'kind':'mathematics','name':'Child','parent_id':a['id']}).json()
    assert client.put('/api/categories/'+a['id'],json={'kind':'mathematics','name':'Cycle','parent_id':b['id']}).status_code==422
    assert client.delete('/api/categories/'+a['id']).status_code==409
    create(client,'mathematics',metadata={'category_ids':[b['id']]})
    assert client.delete('/api/categories/'+b['id']).status_code==409

def test_request_security_and_search_escaping(client):
    assert client.post('/api/nodes',json={'kind':'paper','title':'x'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.get('/api/health',headers={'Host':'evil.example'}).status_code==403
    assert client.post('/api/nodes',json={'kind':'paper','title':'x'},headers={'Content-Length':str(60*1024*1024)}).status_code==413
    create(client,title='100% literal_value 中文')
    assert client.get('/api/nodes',params={'q':'%'}).json()['total']==1
    assert client.get('/api/nodes',params={'q':'" OR *'}).status_code==200
    assert client.get('/api/nodes',params={'q':'中文'}).json()['total']==1
    assert client.post('/api/search/rebuild').status_code==200
    assert client.get('/api/nodes',params={'q':'literal_value'}).json()['total']==1
