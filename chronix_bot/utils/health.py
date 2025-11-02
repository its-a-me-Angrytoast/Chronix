"""Minimal health HTTP endpoints for Chronix.

Provides `/health` and `/ready` endpoints using aiohttp. The server is
intentionally tiny and runs in the bot's event loop when started from
`ChronixBot.setup_hook`.
"""
from typing import Optional
import asyncio
import os
import time
from aiohttp import web
try:
    import psutil  # optional dependency for memory metrics
except Exception:
    psutil = None


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _ready(request: web.Request) -> web.Response:
    # For now treat ready the same as health; in future can probe DB, cache
    return web.json_response({"ready": True})


async def _metrics(request: web.Request) -> web.Response:
    # uptime, pid, memory (if psutil available)
    now = time.time()
    uptime = now - start_time if "start_time" in globals() else None
    pid = os.getpid()
    mem = None
    if psutil is not None:
        try:
            p = psutil.Process(pid)
            mem = p.memory_info().rss
        except Exception:
            mem = None
    return web.json_response({"uptime": uptime, "pid": pid, "memory_rss": mem})


async def start_health_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start an aiohttp server exposing /health and /ready.

    This function sets up the server and returns once the server is started.
    It is safe to call from `asyncio.create_task()` so it won't block the
    caller.
    """
    app = web.Application()
    app.router.add_get("/health", _health)
    app.router.add_get("/ready", _ready)
    app.router.add_get("/metrics", _metrics)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    # record startup time for /metrics
    global start_time
    start_time = time.time()
    await site.start()

    print(f"Health server started at http://{host}:{port} (endpoints: /health /ready)")

    # Keep runner alive until cancelled. We wait on an Event that is never
    # set; cancellation of the task will stop the server when the loop stops.
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
