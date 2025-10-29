---
applyTo: '**'
---
# Chronix Instructions
- This file contains instructions for the Chronix bot. Please follow these guidelines when interacting with the codebase make reasonable assumptions if something is not clear. Only make production ready code.You are allowed to make suggestions for betterment fo code quality and structure.:
- Always update the checklist and the README.md after making changes to the codebase.
- Always fix Bugs,errors,or issues in the codebase before adding new features.
- Ensure that all code is well-documented and follows best practices.
- Fix all problems before moving to next phase.
- Do not make scaffold code only make final production ready code.
# CHRONIX — IMPLEMENTATION FOR COPILOT

TODO: Make each point(marked by '-') into a todo task
-----------------------------------------------
*** Purpose ***: Generate a production-ready Discord bot named Chronix. Build it as a modular, scalable, async Python application using discord.py v2.x. Implement all features discussed and the full roadmap: gameplay (global), utility & moderation (server-specific), owner/dev controls, panels, logging (including non-audit events), music (Wavelink), chess, AI hooks (Gemini), RSS/YouTube feeds, and advanced announcement/ticket panels. Use prefix chro for CLI-style commands and also register equivalent slash commands. Use PostgreSQL (or SQLite for dev) for persistence. Provide tests, CI, Docker compose, and clear, sectioned code with comments.
*** Tone & goals for generated code: ***
-----------------------------------------------
- Production quality: typed, well-commented, modular.
- Async-first: avoid blocking operations.
- Secure: DB transactions for all money/loot ops, audit logs for critical actions, owner confirmations for destructive ops.
- UX-first: embed-based responses, panels, buttons, dropdowns, and live embed updates.
- Developer-friendly: clear folder structure, hot-reloadable cogs, debug utilities.
- Owner/dev separation: owner-only features limited to OWNER_ID in .env and only enabled on DEV_GUILD_ID or via FORCE_OWNER_OVERRIDE with explicit logging.
*** I — Project layout (generate these files & folders).If required create additional files (this is not the final layout) ***
-----------------------------------------------------------
chronix/
├─ .env.example
├─ README.md
├─ pyproject.toml / requirements.txt
├─ docker-compose.yml
├─ Dockerfile
├─ run.py
├─ migrations/
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
│  │   ├─ core/
│  │   │  ├─ core.py
│  │   │  └─ health.py
│  │   ├─ economy/
│  │   │  └─ economy.py
│  │   ├─ gameplay/
│  │   │  ├─ hunt.py
│  │   │  ├─ autohunt.py
│  │   │  ├─ pets.py
│  │   │  ├─ crates.py
│  │   │  ├─ gems.py
│  │   │  ├─ weapons.py
│  │   │  ├─ battles.py
│  │   │  ├─ clans.py
│  │   │  └─ chess.py
│  │   ├─ moderation/
│  │   │  └─ moderation.py
│  │   ├─ music/
│  │   │  └─ music.py
│  │   ├─ tickets/
│  │   │  └─ tickets.py
│  │   ├─ logs/
│  │   │  └─ logger_cog.py
│  │   ├─ announcements/
│  │   │  └─ announce.py
│  │   ├─ feeds/
│  │   │  ├─ rss.py
│  │   │  └─ youtube.py
│  │   ├─ ai/
│  │   │  └─ gemini_client.py
│  │   └─ owner/
│  │      └─ owner_tools.py
│  └─ dashboard/ 
└─ docs/
*** II — .env specification (create .env.example) ***
-----------------------------------------------------------
- Include keys, default types, and purpose. Ensure booleans use true/false.
Any more sensitive booleans,variables should also be in .env
DISCORD_TOKEN=...
OWNER_ID=123456789012345678
DEV_GUILD_ID=123456789012345678
DEV_IDS=1234567890,2345678901
PREFIX=chro
DATABASE_URL=postgres://user:pass@db:5432/chronix
LAVALINK_HOST=127.0.0.1
LAVALINK_PORT=2333
LAVALINK_AUTH=changeme
ENABLE_ECONOMY=true
ENABLE_GAMEPLAY=true
ENABLE_MODERATION=true
ENABLE_MUSIC=true
ENABLE_TICKETS=true
ENABLE_LOGGING=true
ENABLE_AI=false
GEMINI_API_KEY=
YOUTUBE_API_KEY=
RSS_POLL_INTERVAL=300
CRATE_DEFAULTS=basic,advanced,mythic
FORCE_OWNER_OVERRIDE=false
LOG_NON_AUDIT_EVENTS=true
PREFIX_SHORT=chro
*** III — Database schema (generate migration scripts) ***
-----------------------------------------------------------
- Create SQL migrations to add these tables. Provide proper indices and foreign keys. Use PostgreSQL syntax; include SQLite compatibility notes.
- Tables to create (primary fields only — include timestamps everywhere):
 - users (id BIGINT PK, chrons BIGINT, global_xp BIGINT, global_level INT, created_at)
 - guild_users (guild_id BIGINT, user_id BIGINT, xp BIGINT, level INT, balance BIGINT, last_message TIMESTAMP)
 - transactions (id SERIAL PK, user_id BIGINT, guild_id BIGINT NULL, change BIGINT, balance_after BIGINT, reason TEXT, created_at)
 - pets (id PK, owner_id, pet_type, name, rarity, level, xp, stamina, affinity, active BOOL, prestige INT)
 - weapons (id, owner_id, name, type, rarity, attack, crit_rate, slots, gems JSONB)
 - gems (id, owner_id, gem_type, rarity, power, created_at)
 - crates (id, owner_id, crate_type, created_at)
 - autohunt_sessions (user_id PK, enabled BOOL, last_run TIMESTAMP, essence BIGINT, level INT, cost BIGINT)
 - battles (id, battle_type, data JSONB, status, winner_id NULL, created_at)
 - clans (id, name UNIQUE, owner_id, level, treasury, bp INT, created_at)
 - clan_members (clan_id, user_id, role, joined_at)
 - announcements (id, guild_id, author_id, channel_id, payload JSONB, scheduled_at NULL, created_at)
 - logs (id, guild_id, log_type, payload JSONB, created_at)
 - rss_feeds (id, guild_id, url, channel_id, last_item TEXT)
 - youtube_channels (id, guild_id, channel_id, yt_channel_id, last_video_id)
 - tickets (id, guild_id, opener_id, channel_id, panel_id, status, created_at)
 - user_items (id, owner_id, item_type, item_data JSONB)
 - cooldowns (id, user_id, command, expires_at)
 - leaderboards (views, caching table as needed)
Include migrations to rename mythcoins → chrons if migrating.
*** IV — Coding & behavioral rules for the LLM to follow ***
-----------------------------------------------------------
- Async everywhere — use asyncpg or databases for DB calls and avoid blocking IO.
- DB transactions for any monetary or loot change: always lock rows (FOR UPDATE) or use transactions to avoid race conditions.
- Secure RNG — use random.SystemRandom() for game RNG.
- Single scheduler loop — don't create per-user loops; create a single periodic scheduler that queries eligible autohunt sessions in batches.
- Live embeds — for autohunt, battles, and music panels, use message edit patterns (store message IDs in DB).
- Command parity — every gameplay command should have a slash command and a prefix alias (prefix is chro).
- Permissions — use custom checks (is_owner, is_dev, has_guild_admin, is_dj) stored in utils/perms.py.
- Owner/dev features — any absolute or dangerous command must require: (a) the command issuer matches OWNER_ID, (b) if run outside DEV_GUILD_ID, require dashboard confirmation & log to owner DM.
- Panels & UI — use Discord components (buttons, select menus, modals) to implement setup wizards. Panel flows must support preview and confirm steps.
- Logging — central utils/logger.py writes to file and inserts into logs table. Non-audit events (message edits/deletes, role changes, VC joins/leaves) are logged if LOG_NON_AUDIT_EVENTS=true.
- Testing hooks — each cog should include a setup function compatible with bot.load_extension.
*** V — Initial core modules to generate (priority order) ***
-----------------------------------------------------------
- Generate code for these cogs first, fully implemented and tested:
 - cogs/core/core.py — Bot startup, cog loader, config reader, graceful shutdown, basic health endpoints.
 - cogs/economy/economy.py — Chrons, /balance, /pay, /daily, transaction logging; DB transactions and tests.
 - cogs/gameplay/hunt.py and cogs/gameplay/autohunt.py — manual hunts, loot tables, autohunt scheduler with essence, live embed updates.
 - cogs/gameplay/gems.py and cogs/gameplay/crates.py — gem items, crate open flow, forge/empower endpoints.
 - cogs/gameplay/pets.py — pets CRUD, train/feed/prestige.
 - cogs/gameplay/battles.py — PvP and PvE turn-based battles (buttons), reward distribution, DB persistence.
 - cogs/gameplay/weapons.py — weapons equip/unequip/enhance.
 - cogs/gameplay/clans.py — clan creation, join/leave, treasury, BP system.
 - cogs/moderation/moderation.py — warnings, timed mutes, massban/masskick filters; audit logging/case system.
 - cogs/tickets/tickets.py — panel-based ticket setup, creation, claim, close, transcript.
 - cogs/announcements/announce.py — wizard, preview, schedule, templates.
 - cogs/logs/logger_cog.py — central listener for non-audit events; per-guild log channels creation with emoji prefix.
 - cogs/music/music.py — wavelink integration, queue commands, DJ role enforcement.
 - cogs/gameplay/chess.py — local chess play with python-chess and optional chess.com hooks.
 - cogs/feeds/rss.py & cogs/feeds/youtube.py — feed polling and embed posting.
 - cogs/ai/gemini_client.py — abstraction for AI features; opt-in per guild.
- Each cog must:
 - Register slash commands (app_commands) and prefix equivalents with aliases (e.g., hunt aliases h).
 - Use typed function signatures and detailed docstrings.
 - Include permission checks and proper error handling.
 - Use embed templates consistent across cogs (utils/helpers.py contains embed builders).
 - Include unit tests for core logic (loot generation, battle resolution, empower flow).
*** VI — Command naming & alias mapping (prefix chro) ***
-----------------------------------------------------------
- Implement prefix chro and alias sets. For every slash command below, create prefix equivalents and common aliases:
- Examples (full list generation required by LLM):
 - hunt — aliases: h, search
 - autohunt enable/disable — aliases: ah on/off, autoh
 - balance — aliases: bal, wallet
 - pay — aliases: give, transfer
 - pets — aliases: p, mypets
 - pet train — aliases: train, pt
 - battle — aliases: fight, duel
 - clan create — aliases: clan new, clan make
 - crate open — aliases: openbox, opencrate
 - gem empower — aliases: empower, socket
 - announce setup — aliases: announce, ann
 - ticket setup — aliases: ticket, tickets
 - music play — aliases: play, p
 - chess start — aliases: chess play, cstart
- Exact alias list: LLM should create aliases for all gameplay commands and reasonable shortcuts for admin/utility commands.
*** VII — Autohunt specifics & live embed behavior ***
-----------------------------------------------------------
- Single scheduler task obtains autohunt_sessions where enabled = true and last_run + interval <= now.
- batch process up to N users per tick to avoid rate-limits.
- Compute per-session cost from session level and apply atomic DB debit:
 - Begin transaction
 - SELECT chrons FROM users WHERE id = $1 FOR UPDATE
 - If insufficient, disable session and optionally DM user
 - Deduct cost, compute loot via random.SystemRandom, insert user items, award XP
 - Update autohunt_sessions.last_run and essence
 - Commit transaction
- Keep a live_message_id per session (or per user) to update status; if missing, post new message and store id in DB.
- The live embed displays:
 - status: enabled/disabled
 - last loot (icons)
 - total essence
 - coins spent/earned this cycle
 - active pets and stamina
 - upgrade suggestions (spend essence to upgrade)
*** VIII — Battle engine specifics ***
-----------------------------------------------------------
- Represent combatants by a normalized JSON structure:
{
  "user_id": 123,
  "team": [pet1, pet2],
  "weapon": { id, attack, crit },
  "hp": 100,
  "stats": {...},
  "affinity": 1.0
}
- Turn resolution algorithm:

 - Use deterministic base damage + RNG-based crit
 - Consider weapon attack, pet power, gem boosts, affinity multiplier
 - Example formula: damage = floor((weapon.attack + pet.power) * (1 + gem_bonus) * affinity * (1 + rand(0,0.2)))
 - Use ephemeral buttons for actions: Attack, Defend, Use Item, Switch Pet, Surrender.
 - Ensure timeouts: if a player doesn’t act in 60s, auto-skip or surrender after X warnings.
 - Persist battle state to battles table on each turn.
 - On win: award Chrons, XP, chance for gem drop; update battle logs.
*** IX — Gems, weapons, crates, and crafting ***
-----------------------------------------------------
- Gems have gem_type and rarity. Generate gem drop tables per crate rarity.
- Weapons have gem slots; each gem applied increases specific stats.
- Crates: crate_type determines pool. Opening a crate consumes crate item and yields items.
- Forge endpoint: /forge gem to combine multiple gems into a higher-rarity gem (with success chance), consume resources.
- UI: confirm modals before forging or empowering items; show before/after stats.
*** X — Clan & Team details ***
-----------------------------------------------------
- Clan creation costs Chrons; owner gets initial BP to spend on perks.
- Clan perks: XP boost, hunt rate bonus, clan shop discounts.
- Weekly clan wars: scheduled events run with aggregated battle outcomes.
- Clan treasury: members with manage_clan role can deposit/withdraw with logs.
- Teams: lightweight ephemeral groupings for group hunts/battles.
 - /team create/join/leave/invite commands.
 - Team hunts/battles share loot and XP among members.
*** XI — Tickets & Announcements (panel-based) ***
-----------------------------------------------------
- Ticket Setup wizard:
 - Steps: Select category → Set staff roles → Choose ping roles → Customize initial message → Confirm.
 - Store panel config to tickets table.
 - Ticket creation posts a message with button. When clicked, bot creates a private channel with overwrites and an embed with action buttons: Claim, Close, Transcript, Lock.
 - On close: compile transcript, post to logs channel, DM transcript to opener, mark ticket closed.
- Announcements wizard:
 - Steps: Choose channels → Template → Title/Description → Thumbnail/Image → Buttons/Links → Ping roles → Schedule → Preview → Confirm.
 - Store announcements in announcements table; scheduler posts scheduled announcements.
 - Support recurring announcements: daily/weekly/custom cron expression.
*** XII — Logging & non-audit events ***
-----------------------------------------------------
- Implement listeners for:
 - on_message_edit — log before/after
 - on_message_delete — content + author
 - on_guild_role_update — before/after role attributes
 - on_guild_channel_update — before/after channel attributes
 - on_voice_state_update — join/leave/move
 - on_invite_create — invite code + channel
 - on_invite_delete — invite code + channel
 - on_member_update — nickname changes, roles changes (record both)
 - Store logs in logs table and post to respective channel with emoji prefix naming convention: "🔒 | mod-logs", "🧭 | invite-logs", "🎮 | gameplay-logs".
- Log channel creation command:
 - chro create-logs for owner: creates full suite of log channels with emoji prefixes.
 - If run by server admin (non-owner), create only non-gameplay logs.
*** XIII — Music & DJ logic ***
--------------------------------------------
- Wavelink node(s) connection with auth from .env.
- Commands: play/search/queue/skip/pause/resume/volume.
- Optional DJ role enforcement: if MUSIC_DJ_ROLE_REQUIRED=true, enforce dj role for music control.
- Live queue embed with buttons for skip/vote skip/pause/resume.
- Persistent queue per guild saved in DB (so restarting bot restores queue).
*** XIV — Chess integration ***
-------------------------------------
- Use python-chess for local play with board rendering (unicode or image via Pillow).
- Slash/prefix commands: chro chess start @user, chro chess move e2e4.
- For chess.com integration: scaffolding for OAuth and polling public game feed; accept that full remote play requires chess.com API allowances — provide placeholders and config keys.
*** XV — Feeds & AI ***
-------------------------------------
- RSS:
 - Poll feeds per guild at interval. On new item, post embed with title/summary/image. Track last_item to avoid duplicates.
- YouTube:
 - Use YouTube Data API v3 to check new uploads; post embed to configured channel.
- AI (Gemini):
 - Provide an abstraction ai_client.generate(prompt, options) that is opt-in per guild. Use for:
 - Event generator
 - Ticket summarization
 - Moderation suggestion (human-in-the-loop)
 - NPC/gameplay flavor responses
 - Keep message privacy options in UI.
*** XVI — Tests, CI, and Docker ***
--------------------------------------
- Unit tests for:
 - Loot generator distribution (statistical checks)
 - Battle engine deterministic outcomes
 - DB transaction atomicity for place_bet, empower_item
 - Autohunt loop candidate selection and process_autohunt function
 - Integration/perf tests for autohunt under load (simulate many sessions).
 - GitHub Actions config to run tests, lint, and build Docker image.
 - docker-compose.yml for local dev: service db (Postgres), lavalink (Lavalink node), chronix (bot).
 - Health checks and logs via files and container logs.
*** XVII — Security & audit ***
-------------------------------
- Owner-only actions must:
 - Validate ctx.author.id == OWNER_ID
 - If FORCE_OWNER_OVERRIDE=false and the command affects remote guilds, require confirmation via dashboard button (owner must click).
 - Log action to owner DM webhook with server invite if unban owner is performed.
 - Use DB transactions for monetary ops and SELECT FOR UPDATE where needed.
 - Rate-limit expensive ops (massban, masskick).
 - Input sanitization for templates and embed fields.
*** XVIII — Developer outputs to produce ***
--------------------------------------------
- When generating code, create:
 - Fully implemented cogs with typed function signatures and PEP8 compliance.
 - README.md with setup steps (env, migrations, Lavalink).
 - docker-compose.yml and Dockerfile.
 - Alembic migrations or SQL files to create all tables listed.
 - Unit tests in tests/ for core systems.
 - Example data files: loot tables, crate pools, pet stat definitions (YAML/JSON in assets/tables).
 - Example .env.example.
*** XIX — Acceptance checklist (automated tests + manual checks) ***
-------------------------------------------------------------
- For each generated feature, include tests or manual verification steps:
 - chro hunt returns embed with XP, coins, loot.
 - chro autohunt enable starts recurring cycle and updates live embed.
 - chro balance displays Chrons (💠).
 - chro crate open shows animated reveal and awards items.
 - chro gem empower applies gem and updates stats.
 - chro battle @user runs a full match, awarding rewards and logging battle.
 - chro clan create registers a clan, treasury works.
 - chro ticket wizard creates channel, claim and close work, transcript is delivered.
 - chro announce setup builds a scheduled announcement and posts at scheduled time.
 - chro music play queues track and music plays via Lavalink.
 - chro log channels record message edits/deletes and role changes.
- Owner-only commands are present only on DEV_GUILD_ID and require confirmations if run elsewhere.
*** XX — Deliver final artifacts ***
-------------------------------------------
- Produce:
 - Full repository code (files above) ready to run after .env and DB migration.
 - SQL migration files.
 - Docker compose + instructions to run Lavalink + Postgres.
 - Unit tests and integration test scripts.
 - README.md with step-by-step run/deploy/test.
 - Sample assets (embed templates, loot tables, crate definitions).
 - Comments in code for maintainability & DX.
*** Final instructions to Copilot ***
---------------------------------
- Implement features exactly as specified. Where external APIs require keys or restrictions (e.g., Chess.com play, Gemini), provide scaffolding and clear comments describing required credentials and limitations.
- Use secure, production-ready patterns for DB and async code. Prefer asyncpg or databases with transactions.
- Provide comprehensive inline comments, type hints, and docstrings.
- Generate unit tests for key logic (loot, battle, transactions).
- Generate Docker and CI configs.
- Output one file at a time if necessary; otherwise create the full repo tree at once.
- Do not ask for confirmation keep continuing with the process. There is no phased development sequence
- When a choice is ambiguous (e.g., exact XP formula), implement a configurable default and document how to change it.
- Respect privacy: default AI features are opt-in and do not store conversation history unless explicitly enabled.
- skip tests and related work and do them at last
- use emojis in appropriate places in gameplay features
- Do not go in circles if something is not clear make a reasonable assumption and continue
