"""Minimal FastAPI dashboard skeleton for Chronix.

Provides `/health` and `/ready` endpoints and a small set of admin APIs.
This module intentionally keeps dependencies minimal and is safe to import
in environments that don't run the dashboard (it raises ImportError when
FastAPI is not installed).
"""

import os
import json
import time
from pathlib import Path
from typing import Callable


def _data_dir() -> Path:
    p = Path(os.environ.get("CHRONIX_DATA_DIR", Path(__file__).parents[2] / "data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_app() -> "FastAPI":
    try:
        from fastapi import FastAPI, Depends, HTTPException, status
        from fastapi.responses import JSONResponse
        from fastapi.security import APIKeyHeader
    except Exception as e:
        raise ImportError(
            "FastAPI is not installed. Install `fastapi[all]` to run the dashboard"
        ) from e

    app = FastAPI(title="Chronix Dashboard", version="0.1.0")
    # record start time for uptime display
    app.state.start_time = time.time()
    # import Request type for typed endpoints
    from starlette.requests import Request
    from typing import Optional

    # Template rendering and static files
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

    # Simple API key auth for admin actions. Production should use Discord OAuth.
    API_KEY = os.environ.get("CHRONIX_DASHBOARD_API_KEY")
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    # Optional async HTTP client to call the bot RPC for immediate apply
    try:
        import httpx
    except Exception:
        httpx = None

    async def _trigger_rpc_consume() -> bool:
        """Try to trigger the bot RPC server to consume pending actions immediately.
        Returns True if the RPC call succeeded (HTTP 200), False otherwise.
        """
        # determine RPC port from settings file or env
        rpc_port = None
        try:
            cfg = {}
            if SETTINGS_FILE.exists():
                cfg = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
            rpc_port = cfg.get('rpc_port') or int(os.environ.get('CHRONIX_DASHBOARD_RPC_PORT', 9091))
        except Exception:
            try:
                rpc_port = int(os.environ.get('CHRONIX_DASHBOARD_RPC_PORT', 9091))
            except Exception:
                rpc_port = 9091

        # If no httpx available we can't call the RPC directly
        if httpx is None:
            return False

        url = f'http://127.0.0.1:{int(rpc_port)}/rpc/consume'
        headers = {'content-type': 'application/json'}
        if API_KEY:
            headers['X-API-Key'] = API_KEY
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                if actions is None:
                    r = await client.post(url, headers=headers)
                else:
                    # post the action(s) directly for immediate-apply
                    body = { 'actions': actions }
                    r = await client.post(url, headers=headers, json=body)
                return r.status_code == 200
        except Exception:
            return False


    # Restrict dashboard to localhost by default. If a non-local request is made,
    # require a valid API key. This keeps the dashboard safe for local-only use.
    async def require_api_key(header: str = Depends(api_key_header), request: Request = None):
        API_KEY_VAL = API_KEY
        # determine client host
        client_host = None
        try:
            client_host = request.client.host if request and request.client else None
        except Exception:
            client_host = None

        local_hosts = ("127.0.0.1", "::1", "localhost")
        test_hosts = ("testclient", "testserver")

        # allow if request is from an actual localhost address
        if client_host in local_hosts:
            return True

        # if an API key is configured, enforce it for non-local clients
        if API_KEY_VAL:
            if header and header == API_KEY_VAL:
                return True
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key or access not allowed")

        # no API key configured: allow requests from test client or when client_host is absent
        if client_host is None or client_host in test_hosts:
            return True

        # otherwise deny
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key or access not allowed")


    @app.get("/health")
    async def health(request: Request):
        """Simple liveness probe. Renders a small HTML page when requested from a browser."""
        accept = request.headers.get('accept', '')
        if 'text/html' in accept:
            start_time = getattr(app.state, 'start_time', None)
            return templates.TemplateResponse(request, 'health.html', {'status': 'ok', 'start_time': start_time})
        return JSONResponse({"status": "ok"})


    @app.get("/ready")
    async def ready():
        """Readiness probe - in a fuller implementation this should check DB
        connectivity, Lavalink state, and any required external services.
        """
        # Lightweight readiness: check for optional env markers
        db_url = os.environ.get("DATABASE_URL")
        readiness = {"services": {"database_configured": bool(db_url)}}
        return JSONResponse({"status": "ready", "readiness": readiness})


    # Info endpoint (renamed from /version -> /info). Keep /version as a lightweight alias.
    @app.get("/info")
    async def info(request: Request):
        accept = request.headers.get('accept', '')
        if 'text/html' in accept:
            start_time = getattr(app.state, 'start_time', None)
            return templates.TemplateResponse(request, 'info.html', {'version': '0.1.0', 'start_time': start_time})
        return JSONResponse({"version": "0.1.0"})

    @app.get("/version")
    async def version_alias():
        # keep a stable JSON-friendly /version for scripts; prefer /info for human UI
        return JSONResponse({"version": "0.1.0", "info": "/info"})


    @app.post('/instance/{op}')
    async def instance_op(op: str, auth=Depends(require_api_key)):
        if op not in ('start', 'stop', 'restart'):
            return JSONResponse({'status':'error','reason':'invalid_op'}, status_code=400)
        _record_action({'op': 'instance.'+op, 'ts': time.time()})
        return JSONResponse({'status':'queued','op':op})


    @app.get("/")
    async def index(request: Request):
        # Local-only dashboard index. Show owner info if configured.
        owner = os.environ.get("CHRONIX_OWNER_ID")
        server_count = os.environ.get("CHRONIX_SERVER_COUNT")
        # pass start_time for uptime display
        start_time = getattr(app.state, 'start_time', None)
        data_dir = os.environ.get('CHRONIX_DATA_DIR', str(_data_dir()))
        import platform
        py_ver = platform.python_version()
        return templates.TemplateResponse(request, "index.html", {"owner_id": owner, "start_time": start_time, "server_count": server_count, 'data_dir': data_dir, 'py_ver': py_ver})


    # OAuth removed: dashboard is local-only and owner-only; OAuth flow intentionally disabled.


    # Dashboard admin endpoints
    @app.get("/cogs")
    async def list_cogs(auth=Depends(require_api_key)):
        """List available cogs by scanning `chronix_bot/cogs` directory."""
        root = Path(__file__).parents[2] / "chronix_bot" / "cogs"
        cogs = []
        if root.exists():
            for entry in root.iterdir():
                if entry.is_dir():
                    cogs.append(entry.name)
                elif entry.suffix == ".py":
                    cogs.append(entry.stem)
        return JSONResponse({"cogs": sorted(cogs)})


    @app.get('/cogs/meta')
    async def cogs_meta(auth=Depends(require_api_key)):
        """Return per-cog metadata (title, description) from data files if present."""
        cfg_dir = _data_dir() / 'dashboard_cogs'
        meta = {}
        for f in cfg_dir.glob('*.json'):
            try:
                name = f.stem
                data = json.loads(f.read_text(encoding='utf-8') or '{}')
                meta[name] = {'title': data.get('title') or data.get('name'), 'description': data.get('description')}
            except Exception:
                continue
        return JSONResponse({'meta': meta})


    # expose a lightweight pending actions count for the UI
    try:
        from chronix_bot.dashboard import worker as _dash_worker
    except Exception:
        _dash_worker = None

    @app.get('/actions/pending')
    async def actions_pending(auth=Depends(require_api_key)):
        if _dash_worker is None:
            return JSONResponse({'pending': 0})
        try:
            pending = _dash_worker.read_pending_actions() or []
            return JSONResponse({'pending': len(pending)})
        except Exception:
            return JSONResponse({'pending': 0})


    @app.get('/actions/list')
    async def actions_list(page: int = 1, per_page: int = 50, op: str = None, cog: str = None, auth=Depends(require_api_key)):
        """Return a paginated list of recorded actions with optional filtering.
        Query params: page (1-based), per_page, op (filter by operation), cog (filter by cog name).
        """
        try:
            if not ACTIONS_FILE.exists():
                return JSONResponse({'actions': [], 'total': 0, 'page': page, 'per_page': per_page})
            data = json.loads(ACTIONS_FILE.read_text(encoding='utf-8') or '{}')
            actions = data.get('actions', [])
            # optional filtering
            if op:
                actions = [a for a in actions if a.get('op') == op]
            if cog:
                actions = [a for a in actions if a.get('cog') == cog]
            total = len(actions)
            # clamp pagination
            if per_page <= 0:
                per_page = 50
            if page <= 0:
                page = 1
            start = (page - 1) * per_page
            end = start + per_page
            page_items = actions[start:end]
            return JSONResponse({'actions': page_items, 'total': total, 'page': page, 'per_page': per_page})
        except Exception:
            return JSONResponse({'actions': [], 'total': 0, 'page': page, 'per_page': per_page}, status_code=500)


    @app.get('/actions/ui')
    async def actions_ui(request: Request, auth=Depends(require_api_key)):
        """Render the actions UI page (client will fetch paginated data)."""
        return templates.TemplateResponse(request, 'actions.html', {})


    @app.post('/actions/apply_now')
    async def actions_apply_now(auth=Depends(require_api_key)):
        """Owner action: request immediate application of pending actions.
        This records a special action that the bot consumer will observe and
        attempt to apply pending actions. It is a best-effort trigger.
        """
        try:
            _record_action({'op': 'consume_now', 'ts': time.time()})
            # attempt to call RPC directly to speed up processing
            try:
                ok = await _trigger_rpc_consume()
            except Exception:
                ok = False
            # also write a lightweight trigger file as a fallback so a co-located bot can react
            try:
                t = _data_dir() / 'dashboard_trigger'
                t.write_text(str(time.time()), encoding='utf-8')
            except Exception:
                pass
            return JSONResponse({'status': 'queued', 'op': 'consume_now', 'rpc_called': bool(ok)})
        except Exception:
            return JSONResponse({'status': 'error'}, status_code=500)


    @app.post('/actions/clear')
    async def actions_clear(auth=Depends(require_api_key)):
        try:
            # clear the actions file
            try:
                ACTIONS_FILE.write_text(json.dumps({'actions': []}, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass
            return JSONResponse({'status': 'ok'})
        except Exception:
            return JSONResponse({'status': 'error'}, status_code=500)


    @app.get('/users/{user_id}')
    async def get_user_profile(user_id: int, auth=Depends(require_api_key)):
        dirp = _data_dir() / 'dashboard_users'
        dirp.mkdir(parents=True, exist_ok=True)
        f = dirp / f"{user_id}.json"
        if not f.exists():
            return JSONResponse({'user_id': user_id, 'profile': {} })
        try:
            data = json.loads(f.read_text(encoding='utf-8') or '{}')
            return JSONResponse({'user_id': user_id, 'profile': data})
        except Exception:
            return JSONResponse({'user_id': user_id, 'profile': {}}, status_code=500)


    @app.put('/users/{user_id}')
    async def put_user_profile(user_id: int, payload: dict, auth=Depends(require_api_key)):
        dirp = _data_dir() / 'dashboard_users'
        dirp.mkdir(parents=True, exist_ok=True)
        f = dirp / f"{user_id}.json"
        try:
            f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            return JSONResponse({'status':'ok'})
        except Exception:
            return JSONResponse({'status':'error'}, status_code=500)


    @app.get('/users/{user_id}/ui')
    async def user_profile_ui(user_id: int, request: Request, auth=Depends(require_api_key)):
        dirp = _data_dir() / 'dashboard_users'
        dirp.mkdir(parents=True, exist_ok=True)
        f = dirp / f"{user_id}.json"
        data = {}
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding='utf-8') or '{}')
            except Exception:
                data = {}
        return templates.TemplateResponse(request, 'user_profile.html', {'user_id': user_id, 'profile': data})


    @app.get("/cogs/ui")
    async def cogs_ui(request: Request, auth=Depends(require_api_key)):
        # render the cogs management UI
        return templates.TemplateResponse(request, "cogs.html", {})

    @app.get('/settings')
    async def get_settings(auth=Depends(require_api_key)):
        cfg = _data_dir() / 'dashboard_settings.json'
        if not cfg.exists():
            return JSONResponse({'settings': {}})
        try:
            data = json.loads(cfg.read_text(encoding='utf-8') or '{}')
            return JSONResponse({'settings': data})
        except Exception:
            return JSONResponse({'settings': {}}, status_code=500)


    @app.put('/settings')
    async def put_settings(payload: dict, auth=Depends(require_api_key)):
        cfg = _data_dir() / 'dashboard_settings.json'
        try:
            cfg.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            return JSONResponse({'status': 'ok'})
        except Exception:
            return JSONResponse({'status': 'error'}, status_code=500)


    @app.get('/owner')
    async def owner_panel(request: Request, auth=Depends(require_api_key)):
        return templates.TemplateResponse(request, 'owner.html', {})


    @app.post('/owner/rebuild_caches')
    async def owner_rebuild_caches(auth=Depends(require_api_key)):
        act = {'op': 'owner.rebuild_caches', 'ts': time.time()}
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            settings = {}
        if settings.get('apply_immediately', True):
            try:
                ok = await _trigger_rpc_consume([act])
                if ok:
                    act['applied_via_rpc'] = True
            except Exception:
                pass
        _record_action(act)
        return JSONResponse({'status': 'queued', 'op': act.get('op'), 'applied_via_rpc': act.get('applied_via_rpc', False)})


    @app.post('/owner/force_reload_all')
    async def owner_force_reload_all(auth=Depends(require_api_key)):
        act = {'op': 'owner.force_reload_all', 'ts': time.time()}
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            settings = {}
        if settings.get('apply_immediately', True):
            try:
                ok = await _trigger_rpc_consume([act])
                if ok:
                    act['applied_via_rpc'] = True
            except Exception:
                pass
        _record_action(act)
        return JSONResponse({'status': 'queued', 'op': act.get('op'), 'applied_via_rpc': act.get('applied_via_rpc', False)})


    @app.get('/dev')
    async def dev_panel(request: Request, auth=Depends(require_api_key)):
        return templates.TemplateResponse(request, 'dev.html', {})

    @app.get('/console/ui')
    async def console_ui(request: Request, auth=Depends(require_api_key)):
        return templates.TemplateResponse(request, 'console.html', {})

    @app.get('/console/logs')
    async def console_logs(auth=Depends(require_api_key)):
        # return last N lines from data/logs.jsonl
        data_dir = _data_dir()
        f = data_dir / 'logs.jsonl'
        if not f.exists():
            return JSONResponse([])
        try:
            lines = f.read_text(encoding='utf-8').splitlines()
            tail = lines[-200:]
            # pretty-print JSON entries as single-line strings
            out = []
            for l in tail:
                out.append(l)
            return JSONResponse(out)
        except Exception:
            return JSONResponse([], status_code=500)


    @app.get('/console/download')
    async def console_download(auth=Depends(require_api_key)):
        data_dir = _data_dir()
        f = data_dir / 'logs.jsonl'
        if not f.exists():
            return JSONResponse({'status': 'no_logs'})
        try:
            text = f.read_text(encoding='utf-8')
            # return as plain text attachment
            from fastapi.responses import PlainTextResponse
            headers = {"Content-Disposition": "attachment; filename=logs.jsonl"}
            return PlainTextResponse(text, headers=headers)
        except Exception:
            return JSONResponse({'status': 'error'}, status_code=500)


    @app.get('/moderation/ui')
    async def moderation_ui(request: Request, auth=Depends(require_api_key)):
        return templates.TemplateResponse(request, 'moderation.html', {})


    @app.get('/moderation/logs')
    async def moderation_logs(auth=Depends(require_api_key)):
        # scan logs.jsonl for entries containing moderation-related tags
        data_dir = _data_dir()
        f = data_dir / 'logs.jsonl'
        if not f.exists():
            return JSONResponse({'logs': []})
        out = []
        try:
            for l in f.read_text(encoding='utf-8').splitlines():
                try:
                    j = json.loads(l)
                except Exception:
                    continue
                # simple heuristic: moderation logs have a 'type' field == 'moderation' or contain 'moderation' in tags
                if j.get('type') == 'moderation' or ('tags' in j and 'moderation' in j.get('tags', [])):
                    out.append(j)
            return JSONResponse({'logs': out})
        except Exception:
            return JSONResponse({'logs': []}, status_code=500)


    @app.get('/announcements/ui')
    async def announcements_ui(request: Request, auth=Depends(require_api_key)):
        return templates.TemplateResponse(request, 'announcement.html', {})


    @app.post('/announcements/create')
    async def announcements_create(payload: dict, auth=Depends(require_api_key)):
        # append announcement to a queue file for later posting
        data_dir = _data_dir()
        q = data_dir / 'announcements.json'
        try:
            cur = []
            if q.exists():
                cur = json.loads(q.read_text(encoding='utf-8') or '[]')
            payload.setdefault('ts', int(time.time()))
            cur.append(payload)
            q.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding='utf-8')
            return JSONResponse({'status': 'ok'})
        except Exception:
            return JSONResponse({'status': 'error'}, status_code=500)


    @app.get('/metrics/db')
    async def metrics_db(auth=Depends(require_api_key)):
        # provide a minimal DB health summary
        try:
            from chronix_bot.utils import db as db_utils
            pool = db_utils.get_pool()
            return JSONResponse({'db_pool_initialized': pool is not None})
        except Exception:
            return JSONResponse({'db_pool_initialized': False}, status_code=500)


    @app.get('/metrics/server_count')
    async def metrics_server_count(auth=Depends(require_api_key)):
        # try to read the bot-written stats file
        stats = _data_dir() / 'dashboard_stats.json'
        if not stats.exists():
            # fallback to env value
            sc = os.environ.get('CHRONIX_SERVER_COUNT')
            try:
                val = int(sc) if sc else None
            except Exception:
                val = None
            return JSONResponse({'server_count': val})
        try:
            data = json.loads(stats.read_text(encoding='utf-8') or '{}')
            return JSONResponse({'server_count': data.get('server_count'), 'ts': data.get('ts')})
        except Exception:
            return JSONResponse({'server_count': None}, status_code=500)


    @app.get('/metrics/stats')
    async def metrics_stats(auth=Depends(require_api_key)):
        stats = _data_dir() / 'dashboard_stats.json'
        if not stats.exists():
            return JSONResponse({'stats': {}})
        try:
            data = json.loads(stats.read_text(encoding='utf-8') or '{}')
            return JSONResponse({'stats': data})
        except Exception:
            return JSONResponse({'stats': {}}, status_code=500)

    @app.get('/owner/users')
    async def owner_users(request: Request, auth=Depends(require_api_key)):
        # simple index of saved dashboard users
        dirp = _data_dir() / 'dashboard_users'
        dirp.mkdir(parents=True, exist_ok=True)
        entries = []
        for f in dirp.iterdir():
            if f.is_file() and f.suffix == '.json':
                entries.append(f.stem)
        return templates.TemplateResponse(request, 'owner_users.html', {'users': sorted(entries)})


    ACTIONS_FILE = _data_dir() / "dashboard_actions.json"
    COG_STATUS_FILE = _data_dir() / "dashboard_cogs_status.json"
    SETTINGS_FILE = _data_dir() / "dashboard_settings.json"
    COG_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # initialize settings file with sensible defaults from env if missing
    if not SETTINGS_FILE.exists():
        defaults = {
            "default_theme": os.environ.get('CHRONIX_THEME_DEFAULT', 'green'),
            "allow_self_restart": os.environ.get('CHRONIX_ALLOW_SELF_RESTART', 'false').lower() in ('1','true','yes'),
            "dashboard_poll_interval": int(os.environ.get('CHRONIX_DASHBOARD_POLL_INTERVAL', '6')),
            # optional RPC settings for owner convenience
            "rpc_port": int(os.environ.get('CHRONIX_DASHBOARD_RPC_PORT', '9091')),
            # whether the dashboard should attempt to apply changes immediately by calling the bot RPC
            # When true the dashboard will POST the action payload to the bot RPC; the action is still
            # recorded for audit but marked when applied via RPC.
            "apply_immediately": True
        }
        try:
            SETTINGS_FILE.write_text(json.dumps(defaults, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
    # ensure file exists
    if not COG_STATUS_FILE.exists():
        # initialize status file: mark all discovered cogs as enabled by default
        root = Path(__file__).parents[2] / "chronix_bot" / "cogs"
        st = {}
        if root.exists():
            for entry in root.iterdir():
                if entry.is_dir() or entry.suffix == '.py':
                    name = entry.name if entry.is_dir() else entry.stem
                    st[name] = True
        COG_STATUS_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


    def _record_action(payload: dict):
        try:
            cur = {}
            if ACTIONS_FILE.exists():
                cur = json.loads(ACTIONS_FILE.read_text(encoding="utf-8") or "{}")
            cur.setdefault("actions", []).append(payload)
            ACTIONS_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # best-effort logging; if write fails, ignore
            pass


    @app.post("/cogs/{cog_name}/enable")
    async def enable_cog(cog_name: str, auth=Depends(require_api_key)):
        # optimistic status update
        try:
            st = json.loads(COG_STATUS_FILE.read_text(encoding="utf-8") or "{}")
        except Exception:
            st = {}
        st[cog_name] = True
        try:
            COG_STATUS_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        act = {"op": "enable", "cog": cog_name, "ts": time.time()}
        # Attempt immediate apply if enabled in settings
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            settings = {}
        if settings.get('apply_immediately', True):
            try:
                ok = await _trigger_rpc_consume([act])
                if ok:
                    act['applied_via_rpc'] = True
            except Exception:
                pass
        _record_action(act)
        return JSONResponse({"status": "queued", "op": "enable", "cog": cog_name, "applied_via_rpc": act.get('applied_via_rpc', False)})


    @app.post("/cogs/{cog_name}/disable")
    async def disable_cog(cog_name: str, auth=Depends(require_api_key)):
        try:
            st = json.loads(COG_STATUS_FILE.read_text(encoding="utf-8") or "{}")
        except Exception:
            st = {}
        st[cog_name] = False
        try:
            COG_STATUS_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        act = {"op": "disable", "cog": cog_name, "ts": time.time()}
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            settings = {}
        if settings.get('apply_immediately', True):
            try:
                ok = await _trigger_rpc_consume([act])
                if ok:
                    act['applied_via_rpc'] = True
            except Exception:
                pass
        _record_action(act)
        return JSONResponse({"status": "queued", "op": "disable", "cog": cog_name, "applied_via_rpc": act.get('applied_via_rpc', False)})


    @app.post("/cogs/{cog_name}/reload")
    async def reload_cog(cog_name: str, auth=Depends(require_api_key)):
        act = {"op": "reload", "cog": cog_name, "ts": time.time()}
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            settings = {}
        if settings.get('apply_immediately', True):
            try:
                ok = await _trigger_rpc_consume([act])
                if ok:
                    act['applied_via_rpc'] = True
            except Exception:
                pass
        _record_action(act)
        return JSONResponse({"status": "queued", "op": "reload", "cog": cog_name, "applied_via_rpc": act.get('applied_via_rpc', False)})


    @app.post('/cogs/hot_reload')
    async def cogs_hot_reload(auth=Depends(require_api_key)):
        act = {"op": "hot_reload", "ts": time.time()}
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            settings = {}
        if settings.get('apply_immediately', True):
            try:
                ok = await _trigger_rpc_consume([act])
                if ok:
                    act['applied_via_rpc'] = True
            except Exception:
                pass
        _record_action(act)
        return JSONResponse({"status": "queued", "op": "hot_reload", "applied_via_rpc": act.get('applied_via_rpc', False)})


    # Simple per-guild config storage for the dashboard to manage
    CONFIG_DIR = _data_dir() / "dashboard_configs"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


    @app.get("/configs/guild/{guild_id}")
    async def get_guild_config(guild_id: int, auth=Depends(require_api_key)):
        cfg_file = CONFIG_DIR / f"{guild_id}.json"
        if not cfg_file.exists():
            return JSONResponse({"guild_id": guild_id, "config": {}})
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8") or "{}")
            # if request prefers html (browser) we still return JSON but the UI route below will render templates
            return JSONResponse({"guild_id": guild_id, "config": data})
        except Exception:
            return JSONResponse({"guild_id": guild_id, "config": {}}, status_code=500)


    @app.get('/ping')
    async def ping():
        """Simple ping endpoint used by the UI to measure round-trip latency."""
        return JSONResponse({"ts": time.time()})


    @app.put("/configs/guild/{guild_id}")
    async def put_guild_config(guild_id: int, payload: dict, auth=Depends(require_api_key)):
        cfg_file = CONFIG_DIR / f"{guild_id}.json"
        try:
            cfg_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return JSONResponse({"status": "ok", "guild_id": guild_id})
        except Exception:
            return JSONResponse({"status": "error"}, status_code=500)


    @app.get('/configs/ui')
    async def configs_index(request: Request, auth=Depends(require_api_key)):
        return templates.TemplateResponse(request, 'configs_index.html', {})


    @app.get('/configs/list')
    async def configs_list(auth=Depends(require_api_key)):
        files = []
        for f in CONFIG_DIR.iterdir():
            if f.is_file() and f.suffix == '.json':
                files.append(f.stem)
        return JSONResponse({"configs": sorted(files)})


    @app.put('/cogs/config/{cog_name}')
    async def put_cog_config(cog_name: str, payload: dict, auth=Depends(require_api_key)):
        cfg_dir = _data_dir() / 'dashboard_cogs'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / f"{cog_name}.json"
        try:
            cfg_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            # record a config action so the bot consumer applies it. Optionally attempt immediate apply.
            act = {'op': 'config', 'cog': cog_name, 'ts': time.time()}
            try:
                settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
            except Exception:
                settings = {}
            if settings.get('apply_immediately', True):
                try:
                    ok = await _trigger_rpc_consume([act])
                    if ok:
                        act['applied_via_rpc'] = True
                except Exception:
                    pass
            _record_action(act)
            return JSONResponse({'status':'ok', 'applied_via_rpc': act.get('applied_via_rpc', False)})
        except Exception:
            return JSONResponse({'status':'error'}, status_code=500)


    @app.post('/cogs/{cog_name}/action/{action_name}')
    async def cog_action(cog_name: str, action_name: str, payload: dict = None, auth=Depends(require_api_key)):
        try:
            payload = payload or {}
            act = {'op': 'action', 'cog': cog_name, 'action': action_name, 'payload': payload, 'ts': time.time()}
            try:
                settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8') or '{}')
            except Exception:
                settings = {}
            if settings.get('apply_immediately', True):
                try:
                    ok = await _trigger_rpc_consume([act])
                    if ok:
                        act['applied_via_rpc'] = True
                except Exception:
                    pass
            _record_action(act)
            return JSONResponse({'status': 'queued', 'applied_via_rpc': act.get('applied_via_rpc', False)})
        except Exception:
            return JSONResponse({'status': 'error'}, status_code=500)


    @app.get('/cogs/status')
    async def cogs_status(auth=Depends(require_api_key)):
        try:
            st = json.loads(COG_STATUS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            st = {}
        return JSONResponse({'status': st})


    @app.get('/cogs/{cog_name}')
    async def cog_detail_page(cog_name: str, request: Request, auth=Depends(require_api_key)):
        # load status and config for this cog
        try:
            st = json.loads(COG_STATUS_FILE.read_text(encoding='utf-8') or '{}')
        except Exception:
            st = {}
        enabled = bool(st.get(cog_name, False))
        # per-cog config file
        cfg_dir = _data_dir() / 'dashboard_cogs'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / f"{cog_name}.json"
        cfg = {}
        if cfg_file.exists():
            try:
                cfg = json.loads(cfg_file.read_text(encoding='utf-8') or '{}')
            except Exception:
                cfg = {}
        # optional JSON schema for typed settings
        schema_file = cfg_dir / f"{cog_name}.schema.json"
        schema = None
        if schema_file.exists():
            try:
                schema = json.loads(schema_file.read_text(encoding='utf-8') or '{}')
            except Exception:
                schema = None
        # human-friendly title (always compute, use config title if present)
        title = cfg.get('title') or cfg.get('name') or ' '.join(part.capitalize() for part in cog_name.replace('-', ' ').replace('_', ' ').split())
        return templates.TemplateResponse(request, 'cog_detail.html', {'cog': cog_name, 'enabled': enabled, 'config': cfg, 'title': title, 'schema': schema})


    return app
