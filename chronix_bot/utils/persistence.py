"""Scaffold for DB-backed persistence to replace file-backed reminders and inventory.

This module provides placeholder async functions and an adapter interface. The
current project uses file-backed stores during early phases. When ready, implement
these functions to use `chronix_bot.utils.db` asyncpg pool and the models in
`chronix_bot.utils.models`.

Usage:
- Import `Persistence` and call `Persistence.enable_db(pool)` to switch to DB mode.
- Current functions will raise NotImplementedError when the DB backend is enabled.
"""
from __future__ import annotations

from typing import Optional, Dict, Any

_db_enabled = False
_db_pool = None


def enable_db(pool) -> None:
    """Enable DB-backed persistence and provide an asyncpg pool or connection.

    For now this is a toggle; the actual DB methods are TODO and should be
    implemented when migrations and schema are available.
    """
    global _db_enabled, _db_pool
    _db_enabled = True
    _db_pool = pool


def is_db_enabled() -> bool:
    return _db_enabled


# Reminder interface (mirror of chronix_bot.utils.reminders)
async def add_reminder_db(user_id: int, when_ts: int, message: str, guild_id: Optional[int] = None) -> Dict[str, Any]:
    """Add reminder to DB-backed store. TODO: implement.

    Raises NotImplementedError until DB persistence is implemented.
    """
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed persistence for reminders is not implemented yet")


async def remove_reminder_db(reminder_id: str) -> bool:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed persistence for reminders is not implemented yet")


async def list_reminders_db() -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed persistence for reminders is not implemented yet")


# Inventory interface (mirror of chronix_bot.utils.inventory)
async def add_gem_db(user_id: int, gem_type: str, power: int = 1) -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed inventory not implemented yet")

async def merge_gems_db(user_id: int, gem_type: str, count: int = 2) -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed inventory not implemented yet")


async def add_pet_db(user_id: int, species: str) -> Dict[str, Any]:
    if not _db_enabled:
        raise RuntimeError("DB persistence not enabled")
    raise NotImplementedError("DB-backed inventory not implemented yet")
