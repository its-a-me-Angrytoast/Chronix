"""Background worker helpers for the Chronix dashboard.

This file exposes a small consumer that the bot can run to pick up admin
actions recorded by the dashboard in `data/dashboard_actions.json` and apply
them (enable/disable cogs, etc.).

The worker intentionally does not automatically alter the bot; instead it
provides a small API the bot process can call to consume pending actions.
"""
from pathlib import Path
import json
from typing import List, Dict, Optional
from datetime import datetime

ACTIONS_FILE = Path(__file__).parents[2] / "data" / "dashboard_actions.json"


def read_pending_actions() -> List[Dict]:
    if not ACTIONS_FILE.exists():
        return []
    try:
        data = json.loads(ACTIONS_FILE.read_text(encoding="utf-8") or "{}")
        actions = data.get("actions", [])
        # filter out actions that are already processed -> move to processed list
        pending = [a for a in actions if not a.get("processed")]
        return pending
    except Exception:
        return []


def clear_actions():
    try:
        ACTIONS_FILE.write_text(json.dumps({"actions": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def mark_action_processed(action: Dict, result: Optional[Dict] = None) -> None:
    """Mark the given action as processed and append a result entry.

    This updates the actions file in-place and keeps a processed list for auditing.
    """
    try:
        data = {}
        if ACTIONS_FILE.exists():
            data = json.loads(ACTIONS_FILE.read_text(encoding="utf-8") or "{}")
        actions = data.get("actions", [])
        for a in actions:
            if a.get("op") == action.get("op") and a.get("cog") == action.get("cog") and not a.get("processed"):
                a["processed"] = True
                a.setdefault("result", result or {"status": "ok"})
                a["processed_at"] = datetime.utcnow().isoformat() + 'Z'
                break
        data["actions"] = actions
        ACTIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

