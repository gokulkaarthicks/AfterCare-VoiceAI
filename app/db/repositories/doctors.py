"""Doctor directory and slot availability."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.models import DoctorSchedule

# How far ahead a slot may be for each urgency. "medium" deliberately exceeds
# seven days: seeded slots begin the next Monday, and early-Monday UTC can push
# the first slot just past a naive 7-day cutoff.
URGENCY_WINDOWS: dict[str, timedelta] = {
    "high": timedelta(hours=48),
    "medium": timedelta(days=10),
    "low": timedelta(days=14),
}
DEFAULT_URGENCY = "medium"


async def list_doctors(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        text("SELECT id, name, specialty FROM doctors ORDER BY name")
    )
    return [{"id": row[0], "name": row[1], "specialty": row[2]} for row in result]


async def available_slots(
    session: AsyncSession,
    *,
    urgency: str = DEFAULT_URGENCY,
    limit: int = 3,
    doctor_id: str | None = None,
) -> list[dict[str, Any]]:
    """The next `limit` free slots inside the urgency window."""
    now = datetime.now(timezone.utc)
    cutoff = now + URGENCY_WINDOWS.get(urgency, URGENCY_WINDOWS[DEFAULT_URGENCY])

    conditions = [
        DoctorSchedule.status == "available",
        DoctorSchedule.slot_start >= now,
        DoctorSchedule.slot_start <= cutoff,
    ]
    if doctor_id:
        conditions.append(DoctorSchedule.doctor_id == doctor_id)

    result = await session.execute(
        select(DoctorSchedule)
        .where(*conditions)
        .order_by(DoctorSchedule.slot_start)
        .limit(limit)
    )
    return [
        {
            "id": slot.id,
            "doctor_id": slot.doctor_id,
            "doctor_name": slot.doctor_name,
            "slot_start": slot.slot_start.isoformat(),
            "slot_end": slot.slot_end.isoformat(),
            "status": slot.status,
        }
        for slot in result.scalars().all()
    ]
