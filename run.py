"""Main entry point for Chronix bot.

Handles bot initialization, database setup, and dashboard startup.
"""
from chronix_bot.config import Settings
from chronix_bot.bot import create_bot

import asyncio
import os

from chronix_bot.utils import db as db_utils


def main() -> None:
    settings = Settings()

    # Developer startup banner and FAST_SYNC support
    FAST_SYNC = os.getenv("FAST_SYNC", "false").lower() in ("1", "true", "yes")
    if settings.DEV_MODE:
        banner = r"""
  ____ _                   _
 / ___| |__   __ _ _ __ __| | ___ _ __
| |   | '_ \ / _` | '__/ _` |/ _ \ '__|
| |___| | | | (_| | | | (_| |  __/ |
 \____|_| |_|\__,_|_|  \__,_|\___|_|

 Chronix - dev mode: fast sync=%s
""" % (FAST_SYNC,)
        print(banner)

    # Initialize DB pool and run migrations if DATABASE_URL is provided
    if settings.DATABASE_URL and not FAST_SYNC:
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
            print(f"Chronix bot started")
            print("DB pool initialized and migrations applied (if any).")
        except Exception as e:
            print("Failed to initialize DB pool or run migrations:", e)
    else:
        if FAST_SYNC:
            print("FAST_SYNC enabled: skipping DB initialization and migrations.")

    # Create and start the bot
    bot = create_bot(settings)
    token = settings.TOKEN
    if not token:
        print("Missing TOKEN in environment or .env. See .env.example")
        return

    # Run the bot
    bot.run(token)


if __name__ == "__main__":
    main()
