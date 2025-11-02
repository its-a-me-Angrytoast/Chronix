"""Simple file-backed rewards helper (Chrons coins and XP) for development.

Provides award_coins and award_xp with file persistence in `data/accounts.json`.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any

DATA_DIR = Path.cwd() / "data"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"


def _load_accounts() -> Dict[str, Any]:
    if not ACCOUNTS_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ACCOUNTS_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")
        return {}
    try:
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_accounts(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def award_coins(user_id: int, amount: int) -> int:
    data = _load_accounts()
    acct = data.setdefault(str(user_id), {"coins": 0, "xp": 0})
    acct["coins"] = int(acct.get("coins", 0)) + int(amount)
    data[str(user_id)] = acct
    _save_accounts(data)
    return acct["coins"]


def award_xp(user_id: int, amount: int) -> int:
    data = _load_accounts()
    acct = data.setdefault(str(user_id), {"coins": 0, "xp": 0})
    acct["xp"] = int(acct.get("xp", 0)) + int(amount)
    data[str(user_id)] = acct
    _save_accounts(data)
    return acct["xp"]


def get_account(user_id: int) -> Dict[str, Any]:
    return _load_accounts().get(str(user_id), {"coins": 0, "xp": 0})
