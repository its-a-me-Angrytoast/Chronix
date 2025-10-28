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

Phases

See `Checklist` for the chronological phase plan. Phase 0 and Phase 1 implement
the bootstrap and core cogs.
