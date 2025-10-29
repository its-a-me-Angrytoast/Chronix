from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import json

from chronix_bot.utils import db

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BANK_FILE = DATA_DIR / "banks.json"
_lock = asyncio.Lock()


async def _read_banks() -> dict:
    if not BANK_FILE.exists():
        return {}
    def _load():
        with BANK_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    import asyncio
    return await asyncio.to_thread(_load)


async def _write_banks(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    def _dump():
        with BANK_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    import asyncio
    await asyncio.to_thread(_dump)


async def apply_interest(rate_percent: float = 0.1) -> int:
    """Apply interest to all bank balances (rate_percent expressed as percent).

    Returns number of accounts credited.
    """
    pool = db.get_pool()
    if pool is not None:
        # DB-backed: update user_banks balances
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, balance FROM user_banks WHERE balance > 0 FOR UPDATE")
            updated = 0
            for r in rows:
                bal = int(r["balance"])
                credit = int((rate_percent / 100.0) * bal)
                if credit <= 0:
                    continue
                await conn.execute("UPDATE user_banks SET balance = balance + $1 WHERE user_id = $2", credit, r["user_id"])
                updated += 1
        return updated

    async with _lock:
        banks = await _read_banks()
        updated = 0
        for uid_str, bal in list(banks.items()):
            if bal <= 0:
                continue
            credit = int((rate_percent / 100.0) * bal)
            if credit <= 0:
                continue
            banks[uid_str] = bal + credit
            updated += 1
        await _write_banks(banks)
    return updated
