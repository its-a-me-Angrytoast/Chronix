from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings read from environment or .env file."""

    TOKEN: Optional[str] = None
    DEV_GUILD_ID: Optional[int] = None
    OWNER_ID: Optional[int] = None
    FORCE_OWNER_OVERRIDE: bool = False
    DEV_MODE: bool = True

    class Config:
        env_file = ".env"
