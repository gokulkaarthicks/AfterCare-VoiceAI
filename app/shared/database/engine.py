"""Async SQLAlchemy engine and session helpers.

The database is SQLite by default (single writer service). Swap `DATABASE_URL`
for a PostgreSQL DSN to scale horizontally without touching this module.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.shared.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the lazily-created engine for the configured database URL."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory bound to the engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transaction-scoped session."""
    async with get_session_factory()() as session:
        async with session.begin():
            yield session


# Router-facing alias: the name is shorter at every call site.
get_db = get_db_session


async def enable_sqlite_wal() -> None:
    """Turn on write-ahead logging so readers never block the single writer."""
    async with get_engine().begin() as connection:
        await connection.execute(text("PRAGMA journal_mode=WAL"))


async def create_all_tables() -> None:
    """Create any missing tables from the ORM metadata (used outside Alembic)."""
    from app.shared.database.models import Base

    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def prepare_database() -> None:
    """Startup hook: validate the database URL and turn on WAL for SQLite."""
    get_settings()
    await enable_sqlite_wal()
