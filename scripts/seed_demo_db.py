"""Seed an empty SQLite database with the demo fixtures.

Usage (repo root, with the local venv):

    uv run python scripts/seed_demo_db.py

The DB service does this automatically on startup unless SKIP_DEMO_SEED=1.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def _seed() -> None:
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./aftercare.db")

    from app.db.seed.doctors import seed_doctors_and_slots
    from app.db.seed.patients import seed_demo_patients
    from app.shared.database.engine import create_all_tables

    await create_all_tables()
    await seed_demo_patients()
    await seed_doctors_and_slots()
    print("Demo data seeded (existing rows are left untouched).", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(_seed())
