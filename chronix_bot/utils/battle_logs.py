"""Battle log persistence and replay helper.

Appends battle events to data/battle_logs.jsonl and can load/replay logs.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any, List, Optional

DATA_DIR = Path.cwd() / "data"
LOG_FILE = DATA_DIR / "battle_logs.jsonl"


def append_battle_log(entry: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def read_all_logs(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    out: List[Dict[str, Any]] = []
    with LOG_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    if limit is not None:
        return out[-limit:]
    return out


def get_log_by_id(battle_id: str) -> Optional[Dict[str, Any]]:
    for entry in read_all_logs(limit=None):
        if str(entry.get("battle_id")) == str(battle_id):
            return entry
    return None
