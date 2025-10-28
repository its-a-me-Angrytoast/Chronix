# Chronix (development)

Chronix is a Discord bot project developed in phases. This repository contains
an async-first Discord bot with game/economy features planned over multiple
phases. The codebase intentionally defers DB migrations and heavy ops until
later phases.

Quickstart (dev)

1. Copy the example env and set your bot token:

```bash
cp .env.example .env
# edit .env and set TOKEN and OWNER_ID
```

2. Install dependencies (recommended in a venv):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run the bot (local dev):

```bash
python run.py
```

This will start the bot and a small health HTTP endpoint at `http://0.0.0.0:8080/health`.

Docker (dev compose)

There is a `docker-compose.yml` that sets up Postgres and a Lavalink stub. Use it to
quickly spin up dependencies for later phases.

Environment variables

Add these to `.env` (see `.env.example`):

- TOKEN: Discord bot token (required for running the bot)
- OWNER_ID: numeric Discord user id for owner-only commands
- DATABASE_DSN: Postgres DSN, e.g. `postgres://chronix:chronixpass@postgres:5432/chronix`
- POSTGRES_*: individual Postgres connection pieces (host, port, db, user, password)
- LAVALINK_HOST / LAVALINK_PORT: Lavalink node settings (optional)

Initialize DB (dev)

The repository includes a reference schema in `docs/schema.md`. For quick local
testing using the included `docker-compose.yml`:

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


Phases

See `Checklist` for the chronological phase plan. Phase 0 and Phase 1 implement
the bootstrap and core cogs.
