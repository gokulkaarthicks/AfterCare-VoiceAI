"""Appointment reads, updates, and optimistic slot confirmation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.common import new_id, utcnow
from app.shared.core.logging import get_logger
from app.shared.database.models import Appointment

logger = get_logger("db_service.appointments")

EDITABLE_FIELDS = {
    "status",
    "notes",
    "scheduled_at",
    "doctor_id",
    "doctor_name",
    "appointment_type",
}


async def add_appointment(session: AsyncSession, data: dict[str, Any]) -> Appointment:
    scheduled_at = data.get("scheduled_at")
    if isinstance(scheduled_at, str):
        scheduled_at = datetime.fromisoformat(scheduled_at)

    appointment = Appointment(
        id=data.get("id") or new_id(),
        patient_id=data["patient_id"],
        appointment_type=data.get("appointment_type", "followup"),
        scheduled_at=scheduled_at,
        status=data.get("status", "scheduled"),
        notes=data.get("notes"),
        doctor_id=data.get("doctor_id"),
        doctor_name=data.get("doctor_name"),
    )
    session.add(appointment)
    await session.flush()
    logger.info("appointment.created", appointment_id=appointment.id, patient_id=appointment.patient_id)
    return appointment


async def list_appointments(
    session: AsyncSession, doctor_id: str | None = None
) -> list[dict[str, Any]]:
    statement = select(Appointment).options(selectinload(Appointment.patient))
    if doctor_id:
        statement = statement.where(Appointment.doctor_id == doctor_id)
    statement = statement.order_by(Appointment.created_at.desc())

    result = await session.execute(statement)
    return [
        {
            "id": appointment.id,
            "patient_id": appointment.patient_id,
            "patient_name": appointment.patient.name if appointment.patient else None,
            "appointment_type": appointment.appointment_type,
            "scheduled_at": appointment.scheduled_at,
            "status": appointment.status,
            "notes": appointment.notes,
            "doctor_name": appointment.doctor_name,
            "created_at": appointment.created_at,
        }
        for appointment in result.scalars().all()
    ]


async def update_appointment(
    session: AsyncSession, appointment_id: str, updates: dict[str, Any]
) -> Appointment | None:
    result = await session.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return None

    for field, value in updates.items():
        if field not in EDITABLE_FIELDS:
            continue
        if field == "scheduled_at" and isinstance(value, str):
            value = datetime.fromisoformat(value)
        setattr(appointment, field, value)

    await session.flush()
    logger.info("appointment.updated", appointment_id=appointment.id, fields=list(updates))
    return appointment


async def confirm_slot(
    session: AsyncSession,
    *,
    slot_id: str,
    appointment_id: str,
    patient_id: str,
) -> dict[str, Any] | None:
    """Book a slot only if it is still free; None means someone else took it."""
    from app.shared.database.models import DoctorSchedule

    slot_result = await session.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.id == slot_id,
            DoctorSchedule.status == "available",
        )
    )
    slot = slot_result.scalar_one_or_none()
    if slot is None:
        logger.warning("slot.taken", slot_id=slot_id)
        return None

    slot.status = "booked"
    slot.patient_id = patient_id
    await session.flush()

    appt_result = await session.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = appt_result.scalar_one_or_none()
    if appointment is None:
        logger.error("slot.appointment_missing", appointment_id=appointment_id)
        return None

    appointment.scheduled_at = slot.slot_start
    appointment.doctor_id = slot.doctor_id
    appointment.doctor_name = slot.doctor_name
    appointment.status = "confirmed"
    await session.flush()

    logger.info(
        "appointment.confirmed",
        appointment_id=appointment_id,
        slot_id=slot_id,
        scheduled_at=slot.slot_start.isoformat(),
    )
    return {
        "appointment_id": appointment.id,
        "patient_id": appointment.patient_id,
        "scheduled_at": appointment.scheduled_at.isoformat(),
        "doctor_id": appointment.doctor_id,
        "doctor_name": appointment.doctor_name,
        "status": appointment.status,
    }


def now_utc() -> datetime:
    return utcnow()
