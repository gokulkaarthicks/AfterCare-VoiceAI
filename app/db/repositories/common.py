"""Primitives every repository shares.

Ids are UUID strings and every timestamp is UTC-aware, so the repositories
never disagree on either.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.core.logging import get_logger
from app.shared.database.models import AuditLog, EventStore

logger = get_logger("db_service.common")


def new_id() -> str:
    """A fresh UUID primary key, stored as text."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def age_from_dob(dob: str | None) -> int | None:
    """Age in whole years from an ISO date string (YYYY-MM-DD)."""
    if not dob or len(dob) < 10:
        return None
    try:
        born = date.fromisoformat(dob[:10])
    except ValueError:
        return None
    today = date.today()
    return max(0, today.year - born.year - ((today.month, today.day) < (born.month, born.day)))


async def add_audit_log(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    changes: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        id=new_id(),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes_json=json.dumps(changes) if changes else None,
        correlation_id=correlation_id,
    )
    session.add(entry)
    await session.flush()
    return entry


async def record_event(
    session: AsyncSession,
    *,
    event_type: str,
    payload_json: str,
    correlation_id: str | None = None,
    source_service: str | None = None,
) -> EventStore | None:
    """Append the raw event; returns None when this correlation_id was already seen."""
    if correlation_id:
        existing = await session.execute(
            select(EventStore).where(
                EventStore.correlation_id == correlation_id,
                EventStore.event_type == event_type,
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(
                "event.duplicate_skipped",
                event_type=event_type,
                correlation_id=correlation_id,
            )
            return None

    event = EventStore(
        id=new_id(),
        event_type=event_type,
        payload_json=payload_json,
        correlation_id=correlation_id,
        source_service=source_service,
    )
    session.add(event)
    await session.flush()
    return event
