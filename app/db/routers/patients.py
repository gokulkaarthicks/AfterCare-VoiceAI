"""Patient endpoints: list, detail, timeline, questionnaire, and follow-up scheduling."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SERVICE_NAME
from app.db.repositories import followups as followups_repo
from app.db.repositories import patients as patients_repo
from app.db.schemas import (
    DoctorScheduleFollowupRequest,
    DoctorScheduleFollowupResponse,
)
from app.shared.core.logging import get_logger
from app.shared.database.engine import get_db
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import JobType, ScheduleEvent

logger = get_logger("db_service.routes.patients")
router = APIRouter(prefix="/patients", tags=["patients"])

EASTERN = ZoneInfo("America/New_York")
PAST_GRACE = timedelta(minutes=5)


async def _require_patient(session: AsyncSession, patient_id: str) -> dict[str, Any]:
    detail = await patients_repo.get_patient_detail(session, patient_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return detail


@router.get("")
async def list_patients(session: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return await patients_repo.list_patients(session)


@router.get("/{patient_id}")
async def get_patient(
    patient_id: str, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await _require_patient(session, patient_id)


@router.get("/{patient_id}/timeline")
async def get_timeline(
    patient_id: str, session: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    from app.db.repositories.alerts import patient_timeline

    return await patient_timeline(session, patient_id)


@router.get("/{patient_id}/questionnaire")
async def get_questionnaire(
    patient_id: str, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    questionnaire = await followups_repo.latest_questionnaire(session, patient_id)
    if questionnaire is None:
        raise HTTPException(status_code=404, detail="No questionnaire found")
    return questionnaire


@router.post("/{patient_id}/schedule-followup", response_model=DoctorScheduleFollowupResponse)
async def schedule_doctor_followup(
    patient_id: str,
    body: DoctorScheduleFollowupRequest,
    session: AsyncSession = Depends(get_db),
) -> DoctorScheduleFollowupResponse:
    """Queue a follow-up from the dashboard, through the same schedule_event pipeline."""
    await _require_patient(session, patient_id)

    try:
        local = datetime.strptime(
            f"{body.eastern_date.strip()} {body.eastern_time.strip()}", "%Y-%m-%d %H:%M"
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid eastern_date (YYYY-MM-DD) or eastern_time (HH:MM).",
        ) from exc

    scheduled_at = local.replace(tzinfo=EASTERN).astimezone(timezone.utc)
    if scheduled_at < datetime.now(timezone.utc) - PAST_GRACE:
        raise HTTPException(
            status_code=400,
            detail="Scheduled time cannot be more than 5 minutes in the past.",
        )

    correlation_id = str(uuid.uuid4())
    await event_bus.publish(
        "schedule_event",
        ScheduleEvent(
            patient_id=patient_id,
            correlation_id=correlation_id,
            source_service=SERVICE_NAME,
            job_type=JobType.FOLLOWUP,
            scheduled_at=scheduled_at,
            metadata={"source": "doctor_ui", "from_response_chain": False},
        ),
        correlation_id=correlation_id,
        source_service=SERVICE_NAME,
    )
    logger.info(
        "followup.scheduled_by_doctor",
        patient_id=patient_id,
        correlation_id=correlation_id,
        scheduled_at=scheduled_at.isoformat(),
    )
    return DoctorScheduleFollowupResponse(
        correlation_id=correlation_id, scheduled_at=scheduled_at
    )
