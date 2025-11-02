"""Lightweight command telemetry (file-backed).

Records command usage counts and execution durations to `data/telemetry.json`.
This is intentionally minimal and used for Phase 1–4 telemetry requirements.
"""
from __future__ import annotations

from pathlib import Path
import json
import time
from typing import Dict, Any

DATA_DIR = Path.cwd() / "data"
TELEMETRY_FILE = DATA_DIR / "telemetry.json"


def _load() -> Dict[str, Any]:
    if not TELEMETRY_FILE.exists():
        return {"commands": {}}
    try:
        return json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"commands": {}}


def _save(d: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TELEMETRY_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def record_command_start(ctx) -> None:
    data = _load()
    cmd = getattr(ctx.command, "qualified_name", None) or getattr(ctx, "command", None) or "unknown"
    entry = data.setdefault("commands", {}).setdefault(cmd, {"count": 0, "total_time_ms": 0})
    # store a temporary start timestamp on the context to be used later
    try:
        setattr(ctx, "_telemetry_start", time.time())
    except Exception:
        pass
    _save(data)


def record_command_end(ctx) -> None:
    data = _load()
    cmd = getattr(ctx.command, "qualified_name", None) or getattr(ctx, "command", None) or "unknown"
    start = getattr(ctx, "_telemetry_start", None)
    elapsed_ms = 0
    if start is not None:
        elapsed_ms = int((time.time() - start) * 1000)
    entry = data.setdefault("commands", {}).setdefault(cmd, {"count": 0, "total_time_ms": 0})
    entry["count"] = entry.get("count", 0) + 1
    entry["total_time_ms"] = entry.get("total_time_ms", 0) + elapsed_ms
    _save(data)


def get_snapshot() -> Dict[str, Any]:
    return _load()
