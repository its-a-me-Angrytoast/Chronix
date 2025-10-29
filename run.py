"""Minimal runner for Chronix (Phase 1).

This will load settings and create the bot instance. It's intentionally small
so it can be used in early development.
"""
from chronix_bot.config import Settings
from chronix_bot.bot import create_bot

import asyncio
import os

from chronix_bot.utils import db as db_utils


def main() -> None:
    settings = Settings()

    # Initialize DB pool and run migrations if DATABASE_URL is provided
    if settings.DATABASE_URL:
        try:
            # Import here to avoid adding asyncpg at module import time unnecessarily
            from scripts.run_migrations import apply_migrations

            async def _init_db_and_run_migs():
                await db_utils.init_pool(settings.DATABASE_URL, min_size=settings.DB_POOL_MIN, max_size=settings.DB_POOL_MAX)
                # Run migrations (best-effort)
                try:
                    await apply_migrations(settings.DATABASE_URL)
                except Exception as e:
                    print("Migration runner encountered an error:", e)

            asyncio.run(_init_db_and_run_migs())
            print("DB pool initialized and migrations applied (if any).")
        except Exception as e:
            print("Failed to initialize DB pool or run migrations:", e)

    bot = create_bot(settings)
    token = settings.TOKEN
    if not token:
        print("Missing TOKEN in environment or .env. See .env.example")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
