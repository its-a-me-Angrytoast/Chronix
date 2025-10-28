"""Minimal runner for Chronix (Phase 1).

This will load settings and create the bot instance. It's intentionally small
so it can be used in early development.
"""
from chronix_bot.config import Settings
from chronix_bot.bot import create_bot


def main() -> None:
    settings = Settings()
    bot = create_bot(settings)
    token = settings.TOKEN
    if not token:
        print("Missing TOKEN in environment or .env. See .env.example")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
