"""Simple file-backed music queue persistence for development.

This is intentionally lightweight: stores per-guild queues in
`data/music_queues.json`. Each track is a dict with keys: `title`, `url`,
`requested_by`.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import List, Dict, Any

DATA_DIR = Path.cwd() / "data"
QUEUES_FILE = DATA_DIR / "music_queues.json"
_lock = threading.Lock()


def _load() -> Dict[str, Any]:
    if not QUEUES_FILE.exists():
        return {}
    try:
        return json.loads(QUEUES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    QUEUES_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def list_queue(guild_id: int) -> List[Dict[str, Any]]:
    d = _load()
    return d.get(str(guild_id), [])


def enqueue(guild_id: int, track: Dict[str, Any]) -> None:
    """Enqueue a track. Supports optional 'priority' (int) and will record
    a queued_at timestamp for FIFO ordering within the same priority.
    """
    import time
    with _lock:
        d = _load()
        arr = d.setdefault(str(guild_id), [])
        # normalize fields
        if "priority" not in track:
            track["priority"] = int(track.get("priority", 0) or 0)
        track.setdefault("queued_at", int(time.time()))
        arr.append(track)
        # persist
        _save(d)


def dequeue(guild_id: int):
    """Dequeue the highest priority (largest priority number). Within the
    same priority, earlier queued items are favored (FIFO).
    Returns the removed item or None if empty.
    """
    with _lock:
        d = _load()
        arr = d.get(str(guild_id), [])
        if not arr:
            return None
        # pick best index
        best_idx = 0
        for i in range(1, len(arr)):
            a = arr[i]
            b = arr[best_idx]
            # compare priority then queued_at
            if int(a.get("priority", 0)) > int(b.get("priority", 0)):
                best_idx = i
            elif int(a.get("priority", 0)) == int(b.get("priority", 0)):
                if int(a.get("queued_at", 0)) < int(b.get("queued_at", 0)):
                    best_idx = i
        item = arr.pop(best_idx)
        d[str(guild_id)] = arr
        _save(d)
        return item


def clear_queue(guild_id: int) -> None:
    with _lock:
        d = _load()
        d[str(guild_id)] = []
        _save(d)


# ----- metadata helpers (panel message, volume)
def set_panel_message(guild_id: int, channel_id: int, message_id: int) -> None:
    with _lock:
        d = _load()
        meta = d.setdefault("__meta__", {})
        meta[str(guild_id)] = meta.get(str(guild_id), {})
        meta[str(guild_id)]["panel_channel"] = int(channel_id)
        meta[str(guild_id)]["panel_message"] = int(message_id)
        _save(d)


def get_panel_message(guild_id: int) -> Dict[str, int] | None:
    d = _load()
    meta = d.get("__meta__", {})
    g = meta.get(str(guild_id))
    return g


def set_volume(guild_id: int, volume: int) -> None:
    with _lock:
        d = _load()
        meta = d.setdefault("__meta__", {})
        meta[str(guild_id)] = meta.get(str(guild_id), {})
        meta[str(guild_id)]["volume"] = int(volume)
        _save(d)


def get_volume(guild_id: int) -> int:
    d = _load()
    meta = d.get("__meta__", {})
    g = meta.get(str(guild_id), {})
    return int(g.get("volume", 100))


def list_all_meta() -> Dict[str, Dict[str, int]]:
    """Return the internal __meta__ map (guild_id -> metadata).

    Used for startup reconciliation of panels.
    """
    d = _load()
    return d.get("__meta__", {})
