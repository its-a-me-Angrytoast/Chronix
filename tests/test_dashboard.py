import os
import json
from fastapi.testclient import TestClient

from chronix_bot.dashboard.app import create_app


def test_health_ready_and_version():
    app = create_app()
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200 and r.json().get("status") == "ok"
    r = client.get("/ready")
    assert r.status_code == 200 and r.json().get("status") == "ready"
    r = client.get("/version")
    assert r.status_code == 200


def test_admin_endpoints_require_api_key(monkeypatch, tmp_path):
    # ensure API key is set
    monkeypatch.setenv("CHRONIX_DASHBOARD_API_KEY", "secret123")
    app = create_app()
    client = TestClient(app)
    r = client.get("/cogs")
    assert r.status_code == 401
    r = client.get("/cogs", headers={"X-API-Key": "secret123"})
    assert r.status_code == 200

    # test record action file written
    data_dir = tmp_path / "data"
    monkeypatch.setenv("CHRONIX_DATA_DIR", str(data_dir))
    app2 = create_app()
    client2 = TestClient(app2)
    r = client2.post("/cogs/testcog/enable", headers={"X-API-Key": "secret123"})
    assert r.status_code == 200
    actions = json.loads((data_dir / "dashboard_actions.json").read_text())
    assert any(a.get("op") == "enable" and a.get("cog") == "testcog" for a in actions.get("actions", []))


def test_guild_config_put_and_get(monkeypatch, tmp_path):
    monkeypatch.delenv("CHRONIX_DASHBOARD_API_KEY", raising=False)
    monkeypatch.setenv("CHRONIX_DATA_DIR", str(tmp_path / "data"))
    app = create_app()
    client = TestClient(app)
    payload = {"welcome_channel": 12345, "enabled": True}
    r = client.put("/configs/guild/42", json=payload)
    assert r.status_code == 200
    r = client.get("/configs/guild/42")
    assert r.status_code == 200 and r.json().get("config") == payload
