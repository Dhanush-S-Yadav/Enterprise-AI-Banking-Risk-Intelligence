from fastapi.testclient import TestClient
from app import security
from app.main import app

def test_auth_rbac_health(local_store):
    with TestClient(app) as client:
        health=client.get('/api/health')
        assert health.status_code==200
        bad=client.get('/api/admin/users')
        assert bad.status_code==401
        login=client.post('/api/auth/login',json={'username':'service','password':'Demo@12345'})
        assert login.status_code==200
        hdr={'Authorization':'Bearer '+login.json()['access_token']}
        assert client.get('/api/auth/me',headers=hdr).status_code==200
        assert client.get('/api/admin/users',headers=hdr).status_code==403
        assert client.get('/api/documents',headers=hdr).status_code==200
        assert client.get('/api/dashboard',headers=hdr).status_code==200
