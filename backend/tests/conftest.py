import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path/'workspace')
    with TestClient(app,raise_server_exceptions=False,base_url='http://127.0.0.1') as c:
        yield c
    app.state.workspace.engine.dispose()

@pytest.fixture
def bundle():
    return json.loads((Path(__file__).resolve().parents[2]/'examples/reading_summary.json').read_text(encoding='utf-8'))

def create(client,kind='paper',title='Example',**kwargs):
    response=client.post('/api/nodes',json={'kind':kind,'title':title,**kwargs})
    assert response.status_code==201,response.text
    return response.json()

def commit(client,bundle,decisions=None):
    if decisions is None:
        preview=client.post('/api/import/preview',json=bundle)
        assert preview.status_code==200,preview.text
        decisions={e['key']:{'action':'new'} for e in preview.json()['entries']}
    return client.post('/api/import/commit',json={'bundle':bundle,'decisions':decisions})
