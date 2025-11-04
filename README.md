# Chronix — Discord Bot# Chronix (development)



Chronix is an async, modular Discord bot built with discord.py v2.x. This repository contains an in-development implementation focusing on gameplay (economy, crates, pets), moderation, utilities, and more.Chronix is a Discord bot project developed in phases. This repository contains

an async-first Discord bot with game/economy features planned over multiple

## Quickstart (development)phases. The codebase intentionally defers DB migrations and heavy ops until

later phases.

Requirements:

- Python 3.10+ (3.11 recommended)Quickstart (dev)

fail gracefully if TOKEN isn't set):
	the canonical schema reference used during development.

# Chronix — Modular Discord Bot

Chronix is an async-first, modular Discord bot built with discord.py v2.x. It focuses on gameplay (economy, loot/crates, pets, weapons, battles), moderation utilities, music (Lavalink/Wavelink), and optional AI integrations. The project is developed in phases — consult the `Checklist` file for status on each feature.

This repository is aimed at being production-ready (typed, tested, DB-first) while still supporting a lightweight, file-backed development mode.

Key features
- Gameplay: hunt, autohunt, crates, gems, pets, weapons, PvP/PvE battles
- Economy: global and per-guild balances, transactions, daily rewards
- Music: Lavalink/Wavelink integration (optional)
- AI: pluggable providers (Gemini/OpenAI) via an async client (opt-in)
- Moderation: warnings, timed-mutes, logs
- Tickets & announcements: panel-driven flows

Table of contents
- Quickstart (dev)
- Docker (dev)
- Environment variables (.env.example)
- Tests
- Contributing

## Quickstart (development)

1. Copy the example environment and set the minimal variables:

	cp .env.example .env
	# edit .env and set DISCORD_TOKEN and OWNER_ID

2. Create and activate a virtual environment, then install Python deps:

	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt

3. Run the bot:

	python run.py

The bot starts a small health endpoint at `http://0.0.0.0:8080/health`.

Development notes
- The repository supports file-backed storage under `data/` for development (inventories.json, loot tables, etc.).
- To enable DB-backed features, set `DATABASE_DSN` (or the `POSTGRES_*` variables) and run the SQL migrations in `migrations/` against your Postgres instance.
- Cogs live under `chronix_bot/cogs/` and are hot-reloadable during development.

## Docker (development)

The included `docker-compose.yml` brings up a Postgres and Lavalink service. Example:

	docker compose up --build

The `chronix` service builds the project image and mounts `./data` into the container for easy debugging and persistent file-backed state.

## Environment variables

See `.env.example` for a comprehensive list. Minimal variables to run locally:
- DISCORD_TOKEN — Discord bot token (required)
- OWNER_ID — Owner's Discord ID (numeric)

Optional and advanced variables (DB, AI, Lavalink) are documented in `.env.example`.

## Tests

Unit tests use `pytest` and `pytest-asyncio`. Run them from the repository root (inside a venv):

	pytest -q

Note: the test suite includes deterministic tests for the battle engine, weapons, and AI client. Some tests require optional dependencies (see `requirements.txt`).

## Contributing

- Follow the `Checklist` file to see planned features/phases.
- Keep changes small and include tests for new logic.

## Migrations

SQL migrations are in `migrations/`; apply them to your Postgres instance when ready. For quick testing you can use the bundled `docker-compose.yml` Postgres service and run:

	docker compose exec postgres psql -U chronix -d chronix -f /path/to/migrations/0001_phase8.sql

## Troubleshooting

- If the bot fails to start due to missing DB: ensure `DATABASE_DSN` or `POSTGRES_*` are set and Postgres is reachable.
- If AI features are enabled, install `aiohttp` and set provider keys (Gemini/OpenAI).

## License

This project is provided under the LICENSE in the repository root.

---



