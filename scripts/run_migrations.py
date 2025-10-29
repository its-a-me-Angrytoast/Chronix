from __future__ import annotations

import asyncio
from pathlib import Path
import asyncpg


async def apply_migrations(dsn: str, migrations_dir: str = "migrations") -> None:
    """Apply .sql migration files (ordered by filename) to the given Postgres DSN.

    This is intentionally simple: it reads each .sql file and executes it in
    order. Use with care in production; consider switching to Alembic for
    complex schema migrations.
    """
    mig_path = Path(migrations_dir)
    if not mig_path.exists():
        print("No migrations directory found, skipping migrations.")
        return

    files = sorted([p for p in mig_path.iterdir() if p.suffix == ".sql"])
    if not files:
        print("No SQL migration files found, skipping.")
        return

    conn = await asyncpg.connect(dsn)
    try:
        for f in files:
            print(f"Applying migration: {f.name}")
            sql = f.read_text(encoding="utf-8")
            await conn.execute(sql)
    finally:
        await conn.close()


if __name__ == "__main__":
    import os
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set; cannot run migrations.")
    else:
        asyncio.run(apply_migrations(dsn))
