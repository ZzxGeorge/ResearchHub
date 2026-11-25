import copy
import io
import json
import sqlite3
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import create_app
from app.models import Attachment, SourceAnchor, Node, Revision
from app.backup import restore_backup
from conftest import create, commit


def source_data(client, title='Two-column paper', page=2):
    paper = create(client, 'paper', title, markdown='Original note')
    attachment = client.post('/api/nodes/'+paper['id']+'/attachments', files={'file':('中文论文.pdf', b'%PDF-1.4\npublic-test-fixture')}).json()
    attachment = client.get('/api/nodes/'+paper['id']).json()['attachments'][0]
    return dict(paper_id=paper['id'], attachment_id=attachment['id'], pdf_sha256=attachment['sha256'], page=page,
                raw_text='differen-\ntiable dynamics', cleaned_text='differentiable dynamics', context='A differentiable dynamics model.',
                section='', printed_page='', notes='', rects=[{'page':page, 'rect':[72, 600, 130, 612]}, {'page':page, 'rect':[72, 582, 180, 594]}])


def collect(client, source, **kwargs):
    data = {'anchor':source, 'node':{'kind':'vocabulary', 'title':'dynamics', 'metadata':{'meaning':'动力学', 'priority':5, 'mastery':3}, 'markdown':'My explanation'}, **kwargs}
    response = client.post('/api/reading/capture', json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_capture_provenance_review_and_bidirectional_collection(client):
    source = source_data(client)
    result = collect(client, source, provenance='ai')
    n, anchor = result['node'], result['source']
    assert anchor['rects'] == source['rects'] and anchor['page'] == 2
    assert 'AI 辅助解释' in n['markdown'] and '未经论文作者确认' in n['markdown']
    assert '#source/'+anchor['id'] in n['markdown']
    detail = client.get('/api/nodes/'+n['id']).json()
    assert detail['relations'][0]['node']['id'] == source['paper_id']
    assert [v['id'] for v in client.get('/api/reviews').json()] == [n['id']]
    assert client.get('/api/nodes/'+n['id']+'/sources').json()[0]['id'] == anchor['id']
    collection = client.get('/api/papers/'+source['paper_id']+'/reading').json()
    assert collection['nodes'][0]['id'] == n['id'] and collection['sources'][0]['nodes'][0]['id'] == n['id']
    resolved = client.get('/api/sources/'+anchor['id']).json()
    assert resolved['attachment_id'] == source['attachment_id'] and resolved['available']


def test_duplicate_two_papers_preserves_personal_fields_and_sm2(client):
    first = collect(client, source_data(client, 'First'))
    n = first['node']
    assert client.post('/api/reviews/'+n['id'], json={'rating':'good','expected_version':1}).status_code == 200
    before = client.get('/api/nodes/'+n['id']).json()
    second = source_data(client, 'Second', 4)
    preview = client.post('/api/reading/candidates', json={'kind':'vocabulary','title':'Dynamics','metadata':{'sense':'new context'}}).json()
    assert preview[0]['id'] == n['id'] and preview[0]['review']['repetitions'] == 1
    assert preview[0]['sources'][0]['paper_title'] == 'First'
    added = collect(client, second, mode='append', target_id=n['id'], expected_version=n['version'],
                    node={'kind':'vocabulary','title':'Dynamics','metadata':{'meaning':'新解释','priority':1,'mastery':0},'markdown':'Second application'})
    after = client.get('/api/nodes/'+n['id']).json()
    assert after['metadata']['meaning'] == '动力学' and after['metadata']['priority'] == 5 and after['metadata']['mastery'] == 3
    assert 'My explanation' in after['markdown'] and 'Second application' in after['markdown']
    assert after['review'] == before['review'] and after['review_history'] == before['review_history']
    assert len(client.get('/api/nodes/'+n['id']+'/sources').json()) == 2
    distinct = collect(client, second, node={'kind':'vocabulary','title':'dynamics','metadata':{'sense':'different sense'}})
    assert distinct['node']['id'] != n['id']
    # A stale append must not create an orphan source or a new revision.
    with client.app.state.workspace.Session() as s:
        count = len(s.scalars(select(SourceAnchor)).all())
    failed = client.post('/api/reading/capture', json={'anchor':second,'node':{'kind':'vocabulary','title':'dynamics'},'mode':'append','target_id':n['id'],'expected_version':1})
    assert failed.status_code == 409
    with client.app.state.workspace.Session() as s:
        assert len(s.scalars(select(SourceAnchor)).all()) == count


def test_incomplete_words_stay_out_of_queue_until_completed(client):
    item = collect(client, source_data(client), node={'kind':'vocabulary','title':'pending'})['node']
    assert client.get('/api/reviews?due=false').json() == []
    assert client.get('/api/dashboard').json()['due_vocabulary'] == 0
    assert client.get('/api/reading/incomplete-vocabulary').json()[0]['id'] == item['id']
    assert client.post('/api/reviews/'+item['id'], json={'rating':'good','expected_version':1}).status_code == 422
    update = {k:item[k] for k in ['kind','title','status','tags','metadata','markdown']}
    update['metadata']['contextual_meaning'] = '语境释义'
    assert client.put('/api/nodes/'+item['id'], json={**update,'expected_version':item['version']}).status_code == 200
    assert len(client.get('/api/reviews').json()) == 1
    assert client.get('/api/reading/incomplete-vocabulary').json() == []


def test_highlight_links_delete_rules_optimistic_edit(client):
    data = source_data(client)
    result = collect(client, data)
    source, n = result['source'], result['node']
    math = create(client, 'mathematics', 'Jacobian')
    base = '/api/sources/'+source['id']
    assert client.post(base+'/links', json={'node_id':math['id']}).status_code == 200
    value = {'color':'#b6a0ce','label':'My custom theory','markdown':'$$J=\\frac{\\partial f}{\\partial x}$$','expected_version':0}
    annotation = client.put(base+'/annotation', json=value).json()
    assert annotation['version'] == 1
    assert client.put(base+'/annotation', json=value).status_code == 409
    assert len(client.get(base).json()['nodes']) == 2
    assert client.delete(base+'/annotation?expected_version=1').status_code == 200
    assert client.get(base).json()['annotation'] is None
    assert len(client.get(base).json()['nodes']) == 2
    assert client.put(base+'/annotation', json={**value,'expected_version':2}).status_code == 200
    assert client.delete(base+'?expected_version=1').status_code == 200
    assert client.get(base).status_code == 404
    assert client.get('/api/nodes/'+n['id']).status_code == 200
    assert client.get('/api/nodes/'+math['id']).status_code == 200


def test_changed_missing_and_wrong_paper_pdf_never_apply_old_coordinates(client):
    data = source_data(client)
    anchor = collect(client, data)['source']
    other = source_data(client, 'Other paper')
    assert client.post('/api/sources', json={**data,'paper_id':other['paper_id']}).status_code == 422
    assert client.post('/api/sources', json={**data,'pdf_sha256':'0'*64}).status_code == 409
    ws = client.app.state.workspace
    with ws.Session() as s:
        path = ws.path(s.get(Attachment, data['attachment_id']).path)
    original = path.read_bytes()
    path.write_bytes(b'%PDF-1.4\nreplaced')
    assert client.get('/api/sources/'+anchor['id']).status_code == 409
    assert client.get('/api/attachments/'+data['attachment_id']+'/integrity?sha256='+data['pdf_sha256']).status_code == 409
    path.unlink()
    assert client.get('/api/sources/'+anchor['id']).status_code == 409
    path.write_bytes(original)
    assert client.get('/api/sources/'+anchor['id']).status_code == 200
    assert client.delete('/api/nodes/'+data['paper_id']+'?expected_version=1').status_code == 200
    assert client.get('/api/sources/'+anchor['id']).status_code == 404
    assert client.get('/api/nodes/'+anchor['nodes'][0]['id']+'/sources').json() == []
    assert client.post('/api/nodes/'+data['paper_id']+'/restore').status_code == 200
    assert client.get('/api/sources/'+anchor['id']).status_code == 200


def test_geometry_and_scope_validation(client):
    data = source_data(client)
    for invalid in [dict(page=0),dict(page=3),dict(rects=[]),dict(rects=[{'page':2,'rect':[1,2,1,5]}]),dict(raw_text=' '),dict(rects=[{'page':2,'rect':[0,0,1e50,2]}])]:
        assert client.post('/api/sources', json={**data,**invalid}).status_code == 422
    cross_page = {**data,'rects':data['rects']+[{'page':3,'rect':[72,700,180,712]}]}
    assert client.post('/api/sources', json=cross_page).status_code == 201
    assert client.put('/api/sources/not-found/annotation', json={'color':'url(bad)'}).status_code == 422


def test_all_quick_knowledge_types_and_explicit_edit(client):
    data = source_data(client)
    for kind in ['mathematics','algorithm','idea','question']:
        result = collect(client, data, node={'kind':kind,'title':kind,'metadata':{'next_action':'Check source'},'markdown':'Personal hypothesis'})
        n = result['node']
        assert n['kind'] == kind
        replacement = collect(client, data, node={'kind':kind,'title':kind,'metadata':{'next_action':'Next step'},'markdown':'Explicit edited content'},mode='edit',target_id=n['id'],expected_version=n['version'])['node']
        assert replacement['version'] == 2 and replacement['metadata']['next_action'] == 'Next step'
        assert client.get('/api/nodes/'+n['id']+'/history').json()[0]['markdown']


def test_unlink_paper_keeps_knowledge_annotation_and_review(client):
    data = source_data(client)
    result = collect(client, data, annotation={'color':'#a3c7a0','label':'Conclusion','markdown':'Note'})
    n = result['node']
    before = client.get('/api/nodes/'+n['id']).json()
    assert client.delete('/api/papers/'+data['paper_id']+'/links/'+n['id']).status_code == 200
    collection = client.get('/api/papers/'+data['paper_id']+'/reading').json()
    assert collection['nodes'] == [] and collection['sources'][0]['annotation']['markdown'] == 'Note'
    after = client.get('/api/nodes/'+n['id']).json()
    assert after['markdown'] == before['markdown'] and after['review'] == before['review']
    assert client.post('/api/papers/'+data['paper_id']+'/links', json={'node_id':n['id']}).status_code == 200
    assert client.get('/api/papers/'+data['paper_id']+'/reading').json()['nodes'][0]['id'] == n['id']


def test_reading_workspace_and_full_backup_restore(client,tmp_path):
    data = source_data(client)
    result = collect(client, data, annotation={'markdown':'Personal $x^2$ note'})
    state = {'mode':'split','split_width':62,'panel_tab':'algorithm','selected_anchor':result['source']['id'],'selected_node':result['node']['id'],'attachment_id':data['attachment_id'],'draft':{'raw':'Unfinished AI explanation','selection':data}}
    url = '/api/papers/'+data['paper_id']+'/reading-workspace'
    assert client.put(url,json=state).json() == state
    assert client.put(url,json={**state,'split_width':100}).status_code == 422
    export = client.get('/api/export/json').json()
    assert len(export['source_anchors']) == 1 and len(export['source_links']) == 1 and len(export['annotations']) == 1
    archive = client.post('/api/backup').content
    restore_backup(io.BytesIO(archive),tmp_path/'restored-reading')
    app = create_app(tmp_path/'restored-reading')
    with TestClient(app,base_url='http://127.0.0.1') as restored:
        assert restored.get(url).json() == state
        assert restored.get('/api/sources/'+result['source']['id']).json() == client.get('/api/sources/'+result['source']['id']).json()
    app.state.workspace.engine.dispose()


def test_manual_capture_then_v1_import_preserves_sources_reviews_and_personal_notes(client,bundle):
    data = source_data(client)
    entry = copy.deepcopy(bundle['vocabulary'][0])
    result = collect(client, data, node={k:v for k,v in entry.items() if k not in {'key','match_id'}})
    n = result['node']
    assert client.post('/api/reviews/'+n['id'],json={'rating':'good','expected_version':1}).status_code == 200
    before = client.get('/api/nodes/'+n['id']).json()
    preview = client.post('/api/import/preview',json=bundle).json()
    decisions = {e['key']:{'action':'new'} for e in preview['entries']}
    match = next(e for e in preview['entries'] if e['key'] == entry['key'])
    assert match['candidates'][0]['id'] == n['id']
    decisions[entry['key']] = {'action':'merge','target_id':n['id'],'expected_version':n['version']}
    response = commit(client,bundle,decisions)
    assert response.status_code == 200,response.text
    after = client.get('/api/nodes/'+n['id']).json()
    assert before['markdown'] in after['markdown'] and after['review'] == before['review'] and after['review_history'] == before['review_history']
    assert client.get('/api/nodes/'+n['id']+'/sources').json()[0]['id'] == result['source']['id']
