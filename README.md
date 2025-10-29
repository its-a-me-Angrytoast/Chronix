# Chronix — Discord Bot# Chronix (development)



Chronix is an async, modular Discord bot built with discord.py v2.x. This repository contains an in-development implementation focusing on gameplay (economy, crates, pets), moderation, utilities, and more.Chronix is a Discord bot project developed in phases. This repository contains

an async-first Discord bot with game/economy features planned over multiple

## Quickstart (development)phases. The codebase intentionally defers DB migrations and heavy ops until

later phases.

Requirements:

- Python 3.10+ (3.11 recommended)Quickstart (dev)

- Git

- Optional: Docker + docker-compose for Postgres + Lavalink for music1. Copy the example env and set your bot token:



1. Create a virtual environment and install dependencies:```bash

cp .env.example .env

```bash# edit .env and set TOKEN and OWNER_ID

python -m venv .venv```

source .venv/bin/activate

pip install -r requirements.txt2. Install dependencies (recommended in a venv):

```

```bash

2. Copy the example env and fill values:python -m venv .venv

source .venv/bin/activate

```bashpip install -r requirements.txt

cp .env.example .env```

# Edit .env and set DISCORD_TOKEN, OWNER_ID, DATABASE_URL (optional)

```3. Run the bot (local dev):



3. Run migrations (if using a DB) — placeholder:```bash

python run.py

```bash```

# migrations are SQL files in migrations/; apply them to your Postgres instance

# Example:This will start the bot and a small health HTTP endpoint at `http://0.0.0.0:8080/health`.

# psql $DATABASE_URL -f migrations/0001_phase8.sql

```Phase 4

-------

4. Start the bot:Development has entered Phase 4 (gameplay). Current work items include gems, pet systems,

and socketing mechanics. The repo contains a `gems.py` scaffold and crate/hunt flows.

```bashUse the `Checklist` file at the repo root to track progress; update it whenever you

python run.pycomplete a task. Create `.env` from `.env.example` and do not commit secrets.

```

Docker (dev compose)

## Development notes

- The project defaults to file-backed storage in `data/` for development (inventories.json, loot tables, etc.).There is a `docker-compose.yml` that sets up Postgres and a Lavalink stub. Use it to

- To enable DB-backed features, set `DATABASE_URL` in `.env` and run the SQL migrations.quickly spin up dependencies for later phases.

- Cogs live under `chronix_bot/cogs/` and are hot-reloadable.

Environment variables

## Tests

Run unit tests with pytest:Add these to `.env` (see `.env.example`):



```bash- TOKEN: Discord bot token (required for running the bot)

pip install -r requirements.txt- OWNER_ID: numeric Discord user id for owner-only commands

pytest -q- DATABASE_DSN: Postgres DSN, e.g. `postgres://chronix:chronixpass@postgres:5432/chronix`

```- POSTGRES_*: individual Postgres connection pieces (host, port, db, user, password)

- LAVALINK_HOST / LAVALINK_PORT: Lavalink node settings (optional)

## Contributing

- Follow the Checklist file for roadmap and phases.Initialize DB (dev)

- Keep changes small and focused. Add tests for new logic.

The repository includes a reference schema in `docs/schema.md`. For quick local

## Contacttesting using the included `docker-compose.yml`:

For owner/dev contact, see the `OWNER_ID` in `.env.example` (used by owner-only commands).

```bash
docker compose up -d postgres
# Then create the tables (psql example):
docker compose exec postgres psql -U chronix -d chronix -c "$(sed -n '1,200p' docs/schema.md)"
```

Start everything with Docker Compose

This will bring up Postgres, Lavalink, and the Chronix service (Chronix may
fail gracefully if TOKEN isn't set):

```bash
docker compose up --build
```

Notes

- Migrations are intentionally postponed until Phase 15. `docs/schema.md` is
	the canonical schema reference used during development.
- For development without Postgres, the bot will run but DB-backed features will
	raise runtime errors if you try to use them; consider creating a local
	Postgres instance for full testing.

Integration test

There's a small integration harness that will bring up Postgres (docker compose),
apply the schema, and run the DB-backed integration test:

```bash
./scripts/run_integration_db_test.sh
```

This requires Docker and Docker Compose to be installed and the project's
virtualenv to be prepared (`python -m venv chronix.venv && ./chronix.venv/bin/pip install -r requirements.txt`).


Phases

See `Checklist` for the chronological phase plan. Phase 0 and Phase 1 implement
the bootstrap and core cogs.
