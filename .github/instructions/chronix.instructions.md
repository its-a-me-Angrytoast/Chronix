---
applyTo: '**'
---
# Chronix Instructions
This file contains instructions for the Chronix bot. Please follow these guidelines when interacting with the codebase make reasonable assumptions if something is not clear. Only make production ready code.You are allowed to make suggestions for betterment fo code quality and structure.:

Always update the checklist and the README.md after making changes to the codebase.

Always fix Bugs,errors,or issues in the codebase before adding new features.

Ensure that all code is well-documented and follows best practices.

Fix all problems before moving to next phase.

# Step-by-step Instructions (for Copilot or Devs)
Phase 0 — Repo & Local Dev Bootstrap (foundation)

Goal: Create repository, dev tooling, and minimal runtime so other phases can iterate quickly.

Deliverables

Repo root files:

.env.example (with keys from your spec)

README.md (dev quickstart)

pyproject.toml or requirements.txt

Dockerfile

docker-compose.yml (Postgres + Lavalink + Chronix service)

run.py (entry point that reads env and starts bot)

Remove migrations/ folder — keep schema design notes in docs/schema.md (migrations postponed)

Basic folder skeleton:

chronix/
├─ .env.example
├─ README.md
├─ pyproject.toml
├─ docker-compose.yml
├─ Dockerfile
├─ run.py
├─ chronix_bot/
│  ├─ __init__.py
│  ├─ bot.py
│  ├─ config.py
│  ├─ utils/
│  │   ├─ db.py
│  │   ├─ models.py
│  │   ├─ logger.py
│  │   ├─ perms.py
│  │   ├─ cache.py
│  │   └─ helpers.py
│  ├─ cogs/
│  └─ dashboard/
└─ docs/


Minimal .env.example (include booleans true/false and all keys you listed).

Implementation notes

bot.py exposes a create_bot() function returning a typed commands.Bot (async-ready).

config.py parses .env (pydantic / environs) and exposes typed config object.

utils/db.py should provide an async DB pool factory (use asyncpg or databases wrapper). No migrations created here.

utils/logger.py configures console/file logger and an async db-log writer function (queue log writes to avoid blocking).

run.py does .env check and launches bot with graceful shutdown handlers.

Acceptance checks

python run.py runs, connects (or errors with friendly messages if env missing), prints startup banner and loads no cogs yet.

docker-compose up starts containers (Postgres + Lavalink stub + chronix container that fails gracefully if token missing).

Phase 1 — Core & Bootstrapping Cogs

Goal: Implement startup, cog loader, config reading, hot-reloads, basic health endpoints and minimal core commands (ping, uptime, help), plus owner-only loader utilities.

Deliverables

chronix_bot/cogs/core/core.py

on_ready, cog loader/unloader/reloader commands (owner-only)

hot-reload in dev (watcher or simple chro reload <cog> command)

health check endpoints (simple aiohttp status endpoint for container health)

chronix_bot/cogs/core/health.py — lightweight health cog exposing /health and runtime stats

chronix_bot/bot.py — loads core cog automatically; sets up prefix chro and syncs slash commands to dev guild (if DEV_GUILD_ID set).

chronix_bot/utils/perms.py — is_owner, is_dev, requires_owner_or_dev checks.

chronix_bot/utils/helpers.py — embed builder templates, emoji constants, and common helpers.

Implementation notes

Provide typed functions and docstrings.

Owner-only commands must validate OWNER_ID and DEV_GUILD_ID logic with FORCE_OWNER_OVERRIDE.

Health endpoints should be non-blocking using aiohttp and return JSON with uptime, cog status, DB connection status.

Acceptance checks

chro ping and /ping both respond with latency embed.

Owner can chro load cogs.gameplay.hunt and chro reload works in dev guild.

Phase 2 — Persistence foundation & models (no migrations)

Goal: Implement DB connection layer and Python models used across cogs; do not run migrations yet. Add DB helpers for safe transactions.

Deliverables

chronix_bot/utils/db.py

Async pool creation (asyncpg)

get_pool(), context manager transaction(pool) wrapper, and helper select_for_update(query, *params)

safe_execute_money_transaction(user_id, delta, reason, pool) function (atomic)

chronix_bot/utils/models.py

Typed dataclasses / pydantic models for User, GuildUser, Pet, Weapon, Gem, AutohuntSession, BattleState, Clan, Ticket, Announcement.

JSON (de)serialization helpers for data JSONB fields.

docs/schema.md — canonical DB schema (tables and columns) but no migrations created. This will be used later to produce SQL migration files in final phase.

Implementation notes

Use SELECT ... FOR UPDATE pattern in safe_execute_money_transaction.

Document in comments that migrations are intentionally postponed and that schema in docs/schema.md must be applied by ops later.

Acceptance checks

python -c "from chronix_bot.utils.db import get_pool" imports without errors.

Unit test stubs can import models (actual test generation deferred).

Phase 3 — Economy Cog (chrons) — priority feature

Goal: Implement currency system (chrons), /balance, /pay, /daily, transaction logging via transactions table helper (but actual SQL migration later).

Deliverables

chronix_bot/cogs/economy/economy.py

Prefix commands (chro balance, chro pay, chro daily) and slash equivalents

Transaction logging via utils/db.safe_execute_money_transaction (writes to DB table when available)

Balance embeds (consistent UI)

Cooldowns and anti-abuse checks in utils/perms.py or helpers

chronix_bot/utils/helpers.py add currency formatting helpers and embed templates

Example sample JSON files: assets/tables/daily_rewards.json

Implementation notes

All money ops must be done through safe_execute_money_transaction which uses DB transactions and FOR UPDATE.

Implement SystemRandom() for any reward RNG.

If DB pool not connected (dev mode with SQLite), have an in-memory fallback store for rapid testing.

Acceptance checks

chro balance displays the correct default starting balance (from config).

chro pay transfers atomically (simulate with in-memory store if DB not present).

Phase 4 — Core Gameplay: hunt, crates, gems, pets (single-player)

Goal: Add manual hunt, crates, gear, pets — gameplay loop focused on one-user flows, UIs, and embed-rich responses.

Deliverables

chronix_bot/cogs/gameplay/hunt.py — hunt command & loot generation

chronix_bot/cogs/gameplay/crates.py — crate open flow with confirm modal and reveal embed

chronix_bot/cogs/gameplay/gems.py — gem items, gem inventory commands

chronix_bot/cogs/gameplay/pets.py — pet register, feed, train, show commands

assets/tables/:

loot_tables.yaml (rarity pools)

crate_pools.yaml

pets.yaml (pet base stats)

Live embed behavior (for manual hunts): visually rich result embeds with emojis and small progress/animation via successive message edits (respect rate limits).

Implementation notes

Use SystemRandom for RNG.

Every loot/grant that affects money or inventory should call DB wrappers for atomicity (or in-memory fallback).

Provide clear docstrings for loot formula and where to change rarity weights.

Acceptance checks

chro hunt returns embed with XP, coins, and at least one item.

chro crate open consumes crate and yields items as embed.

Phase 5 — Autohunt scheduler & live embeds (global scheduler)

Goal: Implement autohunt system with a single scheduler loop that batches sessions, performs atomic debits, produces loot, updates live embeds.

Deliverables

chronix_bot/cogs/gameplay/autohunt.py (scheduler + commands)

chro autohunt enable/disable + slash commands

Scheduler task that queries enabled sessions (batching)

process_autohunt_batch() function with transaction semantics (SELECT FOR UPDATE, debit, award)

Live embed creation/updating logic and autohunt_sessions model interaction

DB helper hooks for updating autohunt_sessions.last_run and essence

Logging into logs table via utils/logger.py for significant autohunt events

Implementation notes

Scheduler should batch N users per tick (configurable via AUTOHUNT_BATCH_SIZE) and use exponential backoff on failures.

If insufficient funds, disable session and DM user (respect owner override policies).

Live embeds per session or grouped per N users — start with per-user live embed with option to switch to grouped later (configurable).

Acceptance checks

Enabling autohunt schedules work and process_autohunt_batch logic runs in dev mode (simulate DB with in-memory store if needed).

Live embed updated when autohunt processes.

Phase 6 — Battle Engine, weapons, gems & crafting hooks (PvP & PvE)

Goal: Implement turn-based battles, weapons equip/enhance, gem sockets; persist battle state.

Deliverables

chronix_bot/cogs/gameplay/battles.py

PvP / PvE chro battle command with ephemeral buttons (Attack, Defend, Item, Switch, Surrender)

Turn resolution algorithm with deterministic base damage + RNG (documented)

Timeout handling for actions

Persist battles state through utils/models.BattleState (DB writes deferred until migrations)

chronix_bot/cogs/gameplay/weapons.py — equip/unequip/enhance commands

Forge/empower mechanics in gems.py for gem combining (modal confirm) and weapon socketing

Loot/gem drop integration with battle victories

Implementation notes

Damage formula should be configurable; provide default and explain how to change in docs/balance.md.

Persist battle state after each turn (write to DB when available or to temp file during dev).

Use buttons/views for turn actions and timeouts (60s default).

Acceptance checks

Two players can run a full chro battle @user match to completion in local dev, awarding Chrons and potential gem drops.

Phase 7 — Clans, teams, clan wars & treasury

Goal: Implement clan creation, membership, treasury, and BP/perk system.

Deliverables

chronix_bot/cogs/gameplay/clans.py

chro clan create, join, leave, deposit, withdraw, perk buy

Clan treasury commands and logs

Weekly clan war scheduler scaffolding (event runner)

DB model in utils/models.py for clan and clan_members (no migrations yet)

Implementation notes

Treasury operations are monetary: must call DB transaction functions.

Perk system implemented as modular perks with easy config in assets/tables/clan_perks.yaml.

Acceptance checks

chro clan create consumes Chrons and registers a clan (in-memory or DB fallback).

Deposit/withdraw logs store entries (or print logs).

Phase 8 — Moderation, logging (non-audit) & owner safeguards

Goal: Implement moderation tools + robust logging of non-audit events. Owner-only safety behaviors enforced.

Deliverables

chronix_bot/cogs/moderation/moderation.py

warn, timed mute, massban/masskick filters with confirmation flow

case system and audit embedding

chronix_bot/cogs/logs/logger_cog.py

Listeners for message edits, deletes, role updates, channel updates, voice joins/leaves

Insert logs into logs table (when DB available) and post to configured channels

Command chro create-logs for owner and limited variant for admins

utils/logger.py sends to file, to DB queue, and to log channels

utils/perms.py enforces owner/dev separation including FORCE_OWNER_OVERRIDE logic (owner-only commands in non-dev guild must require dashboard confirmation + log)

Implementation notes

Non-audit logging should be toggled via LOG_NON_AUDIT_EVENTS.

Logging must be non-blocking (enqueue writes).

Mass actions must produce an approval flow (modal or reaction confirm) and rate-limit.

Acceptance checks

Message edit/delete events produce log messages in configured log channel (in dev you can configure a test channel).

chro create-logs (owner) creates channel placeholders (or outputs plan when no server permissions available).

Phase 9 — Tickets & Announcements (panel-based wizards)

Goal: Build ticket and announcement wizards with UI flows, preview, confirm, schedule.

Deliverables

chronix_bot/cogs/tickets/tickets.py

Panel setup wizard (select menus, buttons, modals)

Ticket creation button posting, private channel creation, claim/close/transcript actions

chronix_bot/cogs/announcements/announce.py

Announcement builder wizard: templates, scheduling, preview, and confirmation

Store scheduled announcements in announcements in-memory table (DB later)

utils/helpers.py add common wizard UI helpers and modal flow helpers

Implementation notes

Confirm modals for destructive or scheduled actions.

Transcript creation should compile messages and DM opener on close.

Announcement scheduler uses the same single scheduler loop as autohunt but different interval.

Acceptance checks

Ticket panel config flow succeeds and chro ticket creates a channel with buttons and claim/close works.

Announcement preview shows exactly what will be posted (embed template).

Phase 10 — Music (Wavelink/Lavalink) with DJ role logic

Goal: Integrate Wavelink + Lavalink nodes with queue, live queue embed, and DJ role enforcement.

Deliverables

chronix_bot/cogs/music/music.py

Node connection logic using Lavalink/Wavelink with LAVALINK_* config

Commands: play/search/queue/skip/pause/resume/volume

Live queue embed with buttons for skip/vote skip/pause

utils/perms.py add is_dj check with config MUSIC_DJ_ROLE_REQUIRED

Queue persistence scaffolding (save to DB on add; restore on resume — actual DB persistence postponed)

Implementation notes

Use Wavelink library (async). Provide clear comments on Lavalink config and required jar/source in README.

Save persistent queue to DB only later; for now, maintain in-memory queue with optional dump to disk.

Acceptance checks

chro play <url> enqueues and shows queue embed. (Actual audio requires Lavalink running; otherwise test queue logic locally.)

Phase 11 — Chess integration & feeds (RSS/YouTube)

Goal: Implement local chess play (python-chess) and feed pollers (RSS/YouTube) with polling scheduler.

Deliverables

chronix_bot/cogs/gameplay/chess.py — local chess games with board rendering (unicode or image)

chronix_bot/cogs/feeds/rss.py — feed registration, poller, and post embed

chronix_bot/cogs/feeds/youtube.py — YouTube channel registration scaffolding and poller using YT API (needs key)

assets/templates/chess_board.py (helpers to render board images; image generation optional)

Implementation notes

Chess.com integration placeholders with comments for OAuth scaffolding.

Feeds use the global scheduler — store last_item in rss_feeds or local cache (persisted later).

Acceptance checks

chro chess start @user starts a local chess game and displays the board.

RSS poller can be triggered manually to post latest items (use sample feeds).

Phase 12 — AI hooks (Gemini) & AI client abstraction

Goal: Provide opt-in AI client abstraction for Gemini and simple demos (summarize ticket, flavor text generation).

Deliverables

chronix_bot/cogs/ai/gemini_client.py — AIClient abstraction with generate() and summarize() functions; uses GEMINI_API_KEY if enabled

chronix_bot/cogs/ai/ai_demo.py — simple opt-in commands chro ai generate and chro ai summarize (guild opt-in)

Add privacy opt-in check in utils/config.py and helpers.py.

Implementation notes

Do not store conversation history by default; log only meta (prompt used, timestamp) if AI_LOGGING_ENABLED.

Provide clear comments where API keys go and the opt-in flow.

Acceptance checks

chro ai generate returns a placeholder response if GEMINI_API_KEY missing; actual call works when key present.

Phase 13 — Dashboard scaffolding & dev UX work

Goal: Provide the scaffolding for a local dashboard (optional but useful for owner confirmations).

Deliverables

chronix_bot/dashboard/ skeleton with FastAPI backend endpoints (health, confirm owner actions webhook)

README section with instructions on how to run dashboard locally and connect to bot for confirmations

Implementation notes

Dashboard must implement an owner confirmation endpoint for cross-guild owner actions (owner clicks confirm → bot receives webhook and proceeds).

Use JWT or shared secret for dashboard → bot auth.

Acceptance checks

Owner confirm flow via POST to webhook triggers bot action in dev mode.

Phase 14 — Polish, UX, config, alias mapping, and docs

Goal: Finalize command aliases, consistent embed styling, config knobs, error handling, and developer docs.

Deliverables

Full alias map documented and registered in each cog (prefix chro and slash equivalents).

docs/aliases.md with exhaustive alias list (hunt→h, search; balance→bal, wallet; etc.)

docs/balance.md and docs/configuration.md explaining adjustable formulas and constants.

Standardize embed templates in utils/helpers.py.

Add helpful error handlers (user-friendly messages and logged full tracebacks to error logs).

Implementation notes

Ensure every gameplay command has slash and prefix mapping.

Use typed command signatures and clear docstrings.

Acceptance checks

All primary gameplay commands have slash and prefix forms and aliases per spec.

Phase 15 — Tests, Migrations, CI, and Release (deferred work — final phase)

Goal: Now that features are implemented, produce DB migrations, unit/integration tests, CI, and final Docker images. This phase is explicitly last and contains heavy ops you asked to postpone.

Deliverables

migrations/ folder with Alembic or SQL files to create all tables from docs/schema.md (Postgres syntax + SQLite notes).

Unit tests in tests/ covering:

Loot generation stats (distribution sanity checks)

Battle deterministic core logic

Atomic money transactions (simulate concurrent transactions)

Autohunt batch processing (simulate many sessions)

GitHub Actions workflow .github/workflows/ci.yml to run tests, lint, build docker

Final docker-compose.yml adjustments and README.md deploy steps

Performance/integration scripts to simulate load (optional)

Implementation notes

Migrations are to be built from docs/schema.md — ensure FK, indices, and rename mythcoins → chrons included in migration SQL.

Tests can use a local ephemeral DB container spun via docker-compose or pytest-asyncio with in-memory sqlite where possible (note: some features require Postgres JSONB; use PostgreSQL for full CI).

Acceptance checks

CI pipeline runs tests and builds a Docker image.

Migrations applied successfully create schema and indexes.

Bottom: Step-by-step Instructions (for Copilot or Devs)

Use these as a checklist/automation script hints. Do these steps one file/feature at a time (avoid huge multi-file commits). Keep all code typed, well-documented, and async-first.

Init repo

Create repo skeleton per Phase 0.

Commit with message: chore: repo skeleton and bootstrap.

Implement config & run

chronix_bot/config.py: pydantic settings model; read .env.

run.py: minimal runner calling create_bot(); print helpful env-check messages.

Commit.

DB layer (no migrations)

Implement utils/db.py with asyncpg pool factory and safe_execute_money_transaction.

Implement utils/models.py dataclasses. Create docs/schema.md.

Commit.

Core Cog

Implement cogs/core/core.py and health.py. Add reload commands and owner checks.

Add health endpoint with aiohttp.

Commit and test manually.

Economy Cog

Implement cogs/economy/economy.py using DB wrappers. Ensure SELECT FOR UPDATE usage in money ops.

Add assets/tables/daily_rewards.json.

Commit and test in dev guild.

Gameplay: hunt/crates/gems/pets

Implement hunt.py, crates.py, gems.py, pets.py.

Add asset YAMLs: loot tables, crate pools, pets.

Use random.SystemRandom() for RNG.

Commit and play-test flows.

Autohunt scheduler

Implement scheduler in autohunt.py. Use batch processing and safe DB transactions.

Implement live embed creation/updating functions and store message id in DB model when available.

Commit and run scheduler in dev.

Battle & weapons

Implement battles.py and weapons.py including turn resolution and ephemeral buttons.

Persist battle state to model; write DB save points (migrations will create table later).

Commit.

Clans

Implement clans.py with treasury operations calling safe_execute_money_transaction.

Commit.

Moderation & Logging

Implement moderation.py and logger_cog.py. Hook event listeners and enqueue log writes.

Implement chro create-logs command (owner vs admin variants).

Commit.

Tickets & Announcements

Implement ticket and announcement wizards with modals/selects and preview flows.

Commit.

Music

Implement music.py using Wavelink. Provide clear Lavalink setup steps in README.

Implement live queue embed.

Commit.

Chess & Feeds

Implement chess.py (python-chess local) and feed pollers.

Commit.

AI client

Implement gemini_client.py and simple opt-in demo commands.

Ensure logging and privacy opt-ins are in place.

Commit.

Dashboard scaffolding

Implement minimal FastAPI endpoints and webhook confirm flow for owner actions.

Commit.

Polish

Add alias registry, docs for all aliases, embed standardization, error handling.

Commit.

Final Phase: tests & migrations & CI

Generate migrations from docs/schema.md.

Write unit tests, CI workflows, and finalize Docker Compose.

Commit and release.

Copilot / Automation Hints (do not ask, just implement)

Output one file at a time if automated (commit-per-file). Prefer small commits.

Use asyncpg for Postgres interactions; include a thin databases fallback for SQLite dev.

All monetary ops: open a transaction; SELECT chrons FROM users WHERE id=$1 FOR UPDATE; apply changes; insert into transactions table; commit.

Use random.SystemRandom() for all RNG.

Scheduler pattern: one asyncio.Task created on bot start; use asyncio.sleep() only in the single controller loop; avoid per-user tasks.

Use discord views for buttons/selects and store persistent view state where necessary (message ids).

Provide clear TODO/FIXME comments where external API keys or permissions required.

Cogs must implement async def setup(bot) for load_extension.

Error handling: send sanitized error to user, full trace to error_logs via utils/logger.py.

Use type hints everywhere and docstrings for public functions.

Important: Removed / Deferred Items

migrations/ folder has been removed from early phases — DB migrations, SQL generation, and tests are deferred to Phase 15 (final).

Unit tests and CI configuration are postponed until last (Phase 15) as requested.

Small developer-friendly extras (UX & balance)

Add assets/tables with JSON/YAML for loot, crates, pets, clan perks, and balance constants so balance designers can tweak weights without code changes.

Add docs/balance.md describing default XP and coin formulas and how to change them.

Emoji usage: use 💠 for Chrons, 💎 for gems, 🐾 for pets, ⚔️ for battles in embed templates.