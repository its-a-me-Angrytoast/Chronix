-- Chronix canonical schema (Phase 2)

-- NOTE: These SQL statements are reference-only. Migrations will be produced
-- in Phase 15. Apply manually in dev/prod as needed.

-- Users table: stores balances and basic metadata
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    balance BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Transactions table: logs monetary changes
CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    delta BIGINT NOT NULL,
    reason TEXT,
    balance_after BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Autohunt sessions: example table for Phase 5 scheduling
CREATE TABLE IF NOT EXISTS autohunt_sessions (
    session_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_run TIMESTAMPTZ,
    config JSONB DEFAULT '{}'::jsonb
);

-- Battle state: persisted battle information
CREATE TABLE IF NOT EXISTS battle_states (
    battle_id BIGSERIAL PRIMARY KEY,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Clans (example)
CREATE TABLE IF NOT EXISTS clans (
    clan_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id BIGINT NOT NULL,
    treasury BIGINT NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Additional tables (pets, weapons, gems, tickets, announcements) should be
-- added later in docs/schema.md as the models stabilise.
