from fastapi.testclient import TestClient
from chronix_bot.dashboard.app import create_app


def test_basic_endpoints():
    app = create_app()
    client = TestClient(app)
    r = client.get('/health')
    assert r.status_code == 200
    r = client.get('/settings')
    assert r.status_code == 200
    r = client.get('/api/status')
    assert r.status_code == 200
