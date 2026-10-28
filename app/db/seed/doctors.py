"""Keep the fictional doctor roster and appointment availability fresh at startup.

1. Upsert `shared.fixtures.doctors.DEMO_DOCTORS`, propagating any display-name
   change to slots that are still open.
2. Delete expired open slots and top up three weeks of Mon-Fri hourly
   availability from next Monday, so voice booking keeps working after seeded
   timestamps pass.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.core.logging import get_logger
from app.shared.database.engine import get_session_factory
from app.shared.database.models import Doctor, DoctorSchedule
from app.shared.fixtures.doctors import DEMO_DOCTORS

logger = get_logger("db_service.seed.doctors")

MIN_FUTURE_AVAILABLE_SLOTS = 12
BOOKING_HOURS = range(9, 17)  # 09:00-17:00 UTC hourly
WEEKS_AHEAD = 3


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _future_slot_times(now: datetime) -> list[tuple[datetime, datetime]]:
    """Hourly weekday slots starting next Monday."""
    days_until_monday = (7 - now.weekday()) % 7 or 7
    first_monday = (now + timedelta(days=days_until_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    slots: list[tuple[datetime, datetime]] = []
    for week in range(WEEKS_AHEAD):
        for day in range(5):
            date = first_monday + timedelta(weeks=week, days=day)
            for hour in BOOKING_HOURS:
                start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                slots.append((start, start + timedelta(hours=1)))
    return slots


async def _sync_doctors(session: AsyncSession) -> None:
    for doctor in DEMO_DOCTORS:
        existing = await session.get(Doctor, doctor["id"])
        if existing is None:
            session.add(
                Doctor(id=doctor["id"], name=doctor["name"], specialty=doctor["specialty"])
            )
        else:
            existing.name = doctor["name"]
            existing.specialty = doctor["specialty"]

        # Slots denormalise the doctor name for read performance.
        await session.execute(
            update(DoctorSchedule)
            .where(
                DoctorSchedule.doctor_id == doctor["id"],
                DoctorSchedule.status == "available",
            )
            .values(doctor_name=doctor["name"])
        )

    logger.info("doctors.synced", count=len(DEMO_DOCTORS))


async def _refresh_open_slots(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        delete(DoctorSchedule).where(
            DoctorSchedule.status == "available",
            DoctorSchedule.slot_start < now,
        )
    )

    horizon = now + timedelta(days=21)
    count_result = await session.execute(
        select(func.count())
        .select_from(DoctorSchedule)
        .where(
            DoctorSchedule.status == "available",
            DoctorSchedule.slot_start >= now,
            DoctorSchedule.slot_start <= horizon,
        )
    )
    future_open = int(count_result.scalar_one() or 0)
    if future_open >= MIN_FUTURE_AVAILABLE_SLOTS:
        logger.info("doctor_slots.sufficient", future_open=future_open)
        return

    created = 0
    for doctor in DEMO_DOCTORS:
        taken = await session.execute(
            select(DoctorSchedule.slot_start).where(DoctorSchedule.doctor_id == doctor["id"])
        )
        taken_starts = {_as_utc(start) for start in taken.scalars().all()}

        for slot_start, slot_end in _future_slot_times(now):
            start = _as_utc(slot_start)
            if start < now or start in taken_starts:
                continue
            session.add(
                DoctorSchedule(
                    id=str(uuid.uuid4()),
                    doctor_id=doctor["id"],
                    doctor_name=doctor["name"],
                    slot_start=start,
                    slot_end=_as_utc(slot_end),
                    status="available",
                    patient_id=None,
                    created_at=now,
                )
            )
            taken_starts.add(start)
            created += 1

    logger.info("doctor_slots.refreshed", created=created, previous_future_open=future_open)


async def seed_doctors_and_slots() -> None:
    """Startup hook: sync the roster, then guarantee bookable availability."""
    async with get_session_factory()() as session:
        async with session.begin():
            await _sync_doctors(session)
            await _refresh_open_slots(session)
