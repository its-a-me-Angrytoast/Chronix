"""Configuration loader for Chronix.

This module provides a small, dependency-light Settings class that reads
environment variables (and a .env file via python-dotenv). We avoid a hard
dependency on pydantic-settings in order to keep the bootstrap simple.
"""
from typing import Optional
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

