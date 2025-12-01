"""Run smoke tests against the internal FastAPI app using TestClient.

This avoids needing uvicorn in the environment. It imports the create_app
factory and issues a set of GET/POST requests to detect 404s and errors.
"""
import os
from fastapi.testclient import TestClient
from chronix_bot.dashboard.app import create_app
import json

# Ensure middleware allows TestClient access during smoke tests
os.environ.setdefault('DASHBOARD_ALLOW_REMOTE', 'true')

app = create_app()
client = TestClient(app)

checks = [
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/db/status"),
    ("GET", "/docs"),
    ("GET", "/openapi.json"),
    ("GET", "/static/style.css"),
    ("GET", "/static/app.js"),
    ("GET", "/cogs"),
    ("GET", "/cogs/ui"),
    ("GET", "/actions/list"),
    ("GET", "/actions/pending"),
    ("GET", "/api/status"),
    ("GET", "/settings"),
]

results = []
for method, path in checks:
    try:
        r = client.request(method, path)
        status = r.status_code
        # try to parse JSON safely
        content = None
        ctype = r.headers.get('content-type','')
        if 'application/json' in ctype:
            try:
                content = r.json()
            except Exception:
                content = r.text
        else:
            content = r.text[:500]
        results.append((path, status, content))
    except Exception as e:
        results.append((path, 'ERROR', str(e)))

print(json.dumps({"results": results}, indent=2, ensure_ascii=False))
