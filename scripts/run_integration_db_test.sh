#!/usr/bin/env bash
set -euo pipefail

# Bring up Postgres service defined in docker-compose.yml, apply schema, and run the Python integration test.
# Usage: ./scripts/run_integration_db_test.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
  echo "Starting Postgres via docker compose..."
  docker compose up -d postgres

  echo "Waiting for Postgres to be ready..."
  for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U chronix -d chronix >/dev/null 2>&1; then
      echo "Postgres is ready"
      break
    fi
    echo "Postgres not ready yet, sleeping... ($i)"
    sleep 1
  done

  echo "Applying schema from docs/schema.md"
  docker compose exec -T postgres psql -U chronix -d chronix < docs/schema.md

  export DATABASE_DSN="postgres://chronix:chronixpass@postgres:5432/chronix"

  echo "Running integration test script"
  ./chronix.venv/bin/python scripts/integration_test_postgres.py

  echo "Integration test finished. You can keep Postgres running or tear down with: docker compose down -v"
else
  echo "Docker/Docker Compose not found in PATH. Falling back to external DATABASE_DSN if provided."
  if [ -z "${DATABASE_DSN:-}" ]; then
    echo "ERROR: DATABASE_DSN not set. Install Docker or provide DATABASE_DSN to run integration test."
    exit 2
  fi

  echo "Using external DATABASE_DSN=${DATABASE_DSN}. Running integration test script..."
  ./chronix.venv/bin/python scripts/integration_test_postgres.py
  echo "Integration test finished against external DSN: ${DATABASE_DSN}"
fi
