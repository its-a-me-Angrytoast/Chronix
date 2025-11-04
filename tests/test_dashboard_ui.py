from fastapi.testclient import TestClient
from chronix_bot.dashboard.app import create_app


def test_cogs_ui_page():
    app = create_app()
    client = TestClient(app)
    r = client.get('/cogs/ui')
    assert r.status_code == 200


def test_configs_ui_page():
    app = create_app()
    client = TestClient(app)
    r = client.get('/configs/ui')
    assert r.status_code == 200
