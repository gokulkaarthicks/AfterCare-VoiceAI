"""Questionnaire and follow-up job queries."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.common import new_id, utcnow
from app.shared.clinical.questionnaire import ensure_appointment_consent
from app.shared.core.logging import get_logger
from app.shared.database.models import FollowupJob, Questionnaire

logger = get_logger("db_service.followups")


async def add_followup_job(session: AsyncSession, data: dict[str, Any]) -> FollowupJob:
    scheduled_at = data.get("scheduled_at")
    if isinstance(scheduled_at, str):
        scheduled_at = datetime.fromisoformat(scheduled_at)

    job = FollowupJob(
        id=data.get("id") or new_id(),
        patient_id=data["patient_id"],
        job_type=data.get("job_type", "followup"),
        scheduled_at=scheduled_at,
        status=data.get("status", "pending"),
        correlation_id=data.get("correlation_id"),
        completed_at=data.get("completed_at"),
    )
    session.add(job)
    await session.flush()
    logger.info("followup_job.created", job_id=job.id, patient_id=job.patient_id)
    return job


async def latest_questionnaire(session: AsyncSession, patient_id: str) -> dict[str, Any] | None:
    """The patient's current questionnaire, with the consent item guaranteed."""
    result = await session.execute(
        select(Questionnaire)
        .where(Questionnaire.patient_id == patient_id)
        .order_by(Questionnaire.generated_at.desc())
        .limit(1)
    )
    questionnaire = result.scalar_one_or_none()
    if questionnaire is None:
        return None

    questions, injected = ensure_appointment_consent(json.loads(questionnaire.questions_json))
    if injected:
        logger.info(
            "questionnaire.consent_injected",
            patient_id=patient_id,
            questionnaire_id=questionnaire.id,
        )
    return {
        "id": questionnaire.id,
        "questionnaire_id": questionnaire.id,
        "patient_id": questionnaire.patient_id,
        "questions": questions,
        "diagnosis_context": questionnaire.diagnosis_context,
        "generated_at": questionnaire.generated_at,
    }


async def list_followup_jobs(
    session: AsyncSession, status: str | None = None
) -> list[dict[str, Any]]:
    statement = select(FollowupJob).options(selectinload(FollowupJob.patient))
    if status is not None:
        statement = statement.where(FollowupJob.status == status)
    statement = statement.order_by(FollowupJob.created_at.desc())

    result = await session.execute(statement)
    return [
        {
            "id": job.id,
            "patient_id": job.patient_id,
            "patient_name": job.patient.name if job.patient else None,
            "job_type": job.job_type,
            "scheduled_at": job.scheduled_at,
            "status": job.status,
            "executed_at": job.executed_at,
            "completed_at": job.completed_at,
            "correlation_id": job.correlation_id,
            "created_at": job.created_at,
        }
        for job in result.scalars().all()
    ]


async def update_job_by_correlation(
    session: AsyncSession,
    correlation_id: str,
    *,
    status: str | None = None,
    executed_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> FollowupJob | None:
    """Move a follow-up job forward, filling in timestamps implied by the status."""
    job_id = (correlation_id or "").strip()
    if not job_id:
        return None

    result = await session.execute(
        select(FollowupJob).where(FollowupJob.correlation_id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    now = utcnow()
    if status is not None:
        job.status = status
    if executed_at is not None:
        job.executed_at = executed_at
    elif status == "in_progress" and job.executed_at is None:
        job.executed_at = now
    if completed_at is not None:
        job.completed_at = completed_at
    elif status in ("completed", "failed") and job.completed_at is None:
        job.completed_at = now

    await session.flush()
    logger.info("followup_job.updated", job_id=job.id, status=job.status)
    return job
