"""Appointment, doctor availability, and follow-up job endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SERVICE_NAME
from app.db.repositories import appointments as appointments_repo
from app.db.repositories import doctors as doctors_repo
from app.db.repositories import followups as followups_repo
from app.db.repositories import appointments as appointments_repo
from app.db.schemas import (
    ConfirmAppointmentRequest,
    CreateAppointmentRequest,
    FollowupJobStatusPatch,
    UpdateAppointmentRequest,
)
from app.shared.database.engine import get_db
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import AppointmentConfirmed

router = APIRouter(tags=["scheduling"])


# --- Appointments -------------------------------------------------------------


@router.get("/appointments")
async def list_appointments(
    doctor_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await appointments_repo.list_appointments(session, doctor_id=doctor_id)


@router.post("/appointments")
async def create_appointment(
    body: CreateAppointmentRequest, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    appointment = await appointments_repo.add_appointment(session, body.model_dump())
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "status": appointment.status,
        "appointment_type": appointment.appointment_type,
    }


@router.post("/appointments/confirm")
async def confirm_appointment(
    body: ConfirmAppointmentRequest, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Book a slot; 409 means another call took it first."""
    confirmed = await appointments_repo.confirm_slot(
        session,
        slot_id=body.slot_id,
        appointment_id=body.appointment_id,
        patient_id=body.patient_id,
    )
    if confirmed is None:
        raise HTTPException(status_code=409, detail="Slot already booked: please choose another.")

    await event_bus.publish(
        "appointment_confirmed",
        AppointmentConfirmed(
            patient_id=confirmed["patient_id"],
            appointment_id=confirmed["appointment_id"],
            scheduled_at=confirmed["scheduled_at"],
            doctor_name=confirmed["doctor_name"] or "",
            source_service=SERVICE_NAME,
        ),
    )
    return confirmed


@router.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    body: UpdateAppointmentRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    updates = {key: value for key, value in body.model_dump().items() if value is not None}
    appointment = await appointments_repo.update_appointment(session, appointment_id, updates)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "status": appointment.status,
        "notes": appointment.notes,
        "doctor_name": appointment.doctor_name,
        "scheduled_at": appointment.scheduled_at.isoformat() if appointment.scheduled_at else None,
    }


# --- Doctors ------------------------------------------------------------------


@router.get("/doctors")
async def list_doctors(session: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return await doctors_repo.list_doctors(session)


@router.get("/doctors/availability")
async def get_doctor_availability(
    urgency: str = Query(default="medium"),
    limit: int = Query(default=3, ge=1, le=10),
    doctor_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await doctors_repo.available_slots(
        session, urgency=urgency, limit=limit, doctor_id=doctor_id
    )


# --- Follow-up jobs -----------------------------------------------------------


@router.get("/followup-jobs")
async def list_followup_jobs(
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await followups_repo.list_followup_jobs(session, status=status)


@router.patch("/followup-jobs/by-correlation/{correlation_id}")
async def patch_followup_job(
    correlation_id: str,
    body: FollowupJobStatusPatch,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = await followups_repo.update_job_by_correlation(
        session,
        correlation_id,
        status=body.status,
        executed_at=body.executed_at,
        completed_at=body.completed_at,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Follow-up job not found")
    return {
        "id": job.id,
        "patient_id": job.patient_id,
        "status": job.status,
        "executed_at": job.executed_at,
        "completed_at": job.completed_at,
    }
