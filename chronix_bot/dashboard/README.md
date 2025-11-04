# Chronix Dashboard (Phase 18 - Base)

This folder contains a minimal FastAPI-based dashboard skeleton used to begin
Phase 18 work. It intentionally keeps functionality small: health/readiness
endpoints and an OAuth placeholder for future Discord login support.

Quick start (dev):

1. Install dependencies for the dashboard (recommended in a venv):

```bash
pip install fastapi uvicorn
```

2. Run the app:

```bash
uvicorn chronix_bot.dashboard.app:create_app --host 127.0.0.1 --port 8080
```

3. Visit http://127.0.0.1:8080/health and /ready to see probes.

Notes and next steps:
- Implement OAuth with `authlib` or FastAPI's OAuth integrations.
- Add session management and RBAC (Admin/Owner/Developer) driving what the
  dashboard shows for a given logged-in user.
- Add CI job that spins up the app and probes `/health` as a smoke test.
