"""Configuration loader for Chronix.

This module provides a small, dependency-light Settings class that reads
environment variables (and a .env file via python-dotenv). It also exposes a
small `validate()` helper to perform automated `.env` checks at startup.
"""
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Minimal settings holder.

    Attributes mirror the earlier Pydantic model used during development.
    """

    TOKEN: Optional[str] = os.getenv("TOKEN")
    DEV_GUILD_ID: Optional[int] = int(os.getenv("DEV_GUILD_ID")) if os.getenv("DEV_GUILD_ID") else None
    OWNER_ID: Optional[int] = int(os.getenv("OWNER_ID")) if os.getenv("OWNER_ID") else None
    FORCE_OWNER_OVERRIDE: bool = os.getenv("FORCE_OWNER_OVERRIDE", "false").lower() in ("1", "true", "yes")
    DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() in ("1", "true", "yes")

    # Database
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "10"))

    # Logging retention settings
    LOG_PRUNE_ENABLED: bool = os.getenv("LOG_PRUNE_ENABLED", "true").lower() in ("1", "true", "yes")
    LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    LOG_PRUNE_INTERVAL_HOURS: int = int(os.getenv("LOG_PRUNE_INTERVAL_HOURS", "24"))
    # Developer/dev-only logging channel (optional)
    DEV_LOG_CHANNEL_ID: Optional[int] = int(os.getenv("DEV_LOG_CHANNEL_ID")) if os.getenv("DEV_LOG_CHANNEL_ID") else None

    # Music request credit configuration
    ENABLE_MUSIC_REQUEST_CREDITS: bool = os.getenv("ENABLE_MUSIC_REQUEST_CREDITS", "false").lower() in ("1", "true", "yes")
    MUSIC_REQUEST_CREDIT_COST: int = int(os.getenv("MUSIC_REQUEST_CREDIT_COST", "10"))
    MUSIC_STATS_ENABLED: bool = os.getenv("MUSIC_STATS_ENABLED", "true").lower() in ("1", "true", "yes")

    def validate(self, required: Optional[List[str]] = None) -> List[str]:
        """Validate required environment variables.

        Args:
            required: list of attribute names to check (e.g. ["TOKEN"]). If
                omitted, defaults to checking at least `TOKEN`.

        Returns:
            A list of missing attribute names (empty if all present).
        """
        if required is None:
            required = ["TOKEN"]

        missing: List[str] = []
        for name in required:
            val = getattr(self, name, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(name)

        return missing

