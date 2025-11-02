from __future__ import annotations

from typing import Optional, Dict, Any
from pathlib import Path
import json
import time

from chronix_bot.utils import db as db_utils

DATA_DIR = Path.cwd() / "data"
CRATE_OPENINGS_FILE = DATA_DIR / "crate_openings.jsonl"


async def get_crate_opening_stats(guild_id: Optional[int] = None) -> Dict[str, Any]:
    """Return aggregate stats for crate openings.

    If DB pool is configured, query `crate_openings`. Otherwise read the
    file-backed JSONL log and compute simple aggregates.
    """
    pool = db_utils.get_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            if guild_id is None:
                rows = await conn.fetch("SELECT crate_type, count(*) as cnt, sum(coins) as coins FROM crate_openings GROUP BY crate_type")
            else:
                rows = await conn.fetch("SELECT crate_type, count(*) as cnt, sum(coins) as coins FROM crate_openings WHERE guild_id = $1 GROUP BY crate_type", guild_id)
            return {r["crate_type"]: {"count": int(r["cnt"]), "coins": int(r["coins"] or 0)} for r in rows}

    # file-backed fallback
    if not CRATE_OPENINGS_FILE.exists():
        return {}

    totals: Dict[str, Dict[str, int]] = {}
    with open(CRATE_OPENINGS_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if guild_id is not None and entry.get("guild_id") != guild_id:
                continue
            ctype = entry.get("crate_type")
            coins = int(entry.get("coins", 0))
            rec = totals.setdefault(ctype, {"count": 0, "coins": 0})
            rec["count"] += 1
            rec["coins"] += coins

    return totals
