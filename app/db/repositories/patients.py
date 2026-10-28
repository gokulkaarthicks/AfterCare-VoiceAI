"""Patient chart reads and writes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.common import age_from_dob, new_id, utcnow
from app.shared.clinical.questionnaire import ensure_appointment_consent
from app.shared.core.logging import get_logger
from app.shared.database.models import DischargeSummary, Patient

logger = get_logger("db_service.patients")


def _earliest(value: Any) -> datetime:
    return value or datetime.min.replace(tzinfo=timezone.utc)


def _has_discharge_payload(discharge: Any) -> bool:
    if not isinstance(discharge, dict):
        return False
    return bool(
        str(discharge.get("raw_text") or "").strip()
        or str(discharge.get("diagnosis") or "").strip()
    )


def _ward_from_appointments(appointments: list[Any]) -> str:
    """The seed data stores ward/bed in the newest appointment notes."""
    if not appointments:
        return "-"
    for appointment in sorted(appointments, key=lambda a: _earliest(a.created_at), reverse=True):
        notes = getattr(appointment, "notes", None)
        if notes and str(notes).strip():
            return str(notes).strip()
    return "-"


async def upsert_patient(session: AsyncSession, payload: dict[str, Any]) -> Patient:
    """Create or refresh the patient row from a `patient_state_upsert` payload."""
    patient_id = payload.get("patient_id") or payload.get("id") or new_id()
    demographics = payload.get("demographics", {})
    discharge = payload.get("discharge_data")
    discharged = _has_discharge_payload(discharge)

    existing = await session.execute(select(Patient).where(Patient.id == patient_id))
    patient = existing.scalar_one_or_none()

    if patient is None:
        patient = Patient(
            id=patient_id,
            name=demographics.get("name", ""),
            phone=demographics.get("phone", ""),
            dob=demographics.get("dob"),
            email=demographics.get("email"),
            status="Discharged" if discharged else "active",
            risk_level=payload.get("risk_level", "low"),
        )
        session.add(patient)
        logger.info("patient.created", patient_id=patient_id)
    else:
        for field in ("name", "phone", "dob", "email"):
            if demographics.get(field):
                setattr(patient, field, demographics[field])
        if payload.get("risk_level"):
            patient.risk_level = payload["risk_level"]
        if discharged:
            patient.status = "Discharged"
        patient.updated_at = utcnow()
        logger.info("patient.updated", patient_id=patient_id)

    await session.flush()
    return patient


async def list_patients(session: AsyncSession) -> list[dict[str, Any]]:
    """Dashboard rows: reason (latest diagnosis), ward (appointment notes), age."""
    result = await session.execute(
        select(Patient)
        .options(selectinload(Patient.discharge_summaries), selectinload(Patient.appointments))
        .order_by(Patient.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for patient in result.scalars().all():
        latest: DischargeSummary | None = (
            max(patient.discharge_summaries, key=lambda d: d.created_at)
            if patient.discharge_summaries
            else None
        )
        rows.append(
            {
                "id": patient.id,
                "name": patient.name,
                "phone": patient.phone,
                "dob": patient.dob,
                "status": patient.status,
                "risk_level": patient.risk_level,
                "created_at": patient.created_at,
                "reason": (latest.diagnosis if latest else None) or "-",
                "ward": _ward_from_appointments(list(patient.appointments)),
                "age": age_from_dob(patient.dob),
            }
        )
    return rows


async def get_patient_detail(session: AsyncSession, patient_id: str) -> dict[str, Any] | None:
    """Full chart: discharge, medications, questionnaire, interactions, alerts, scheduling."""
    result = await session.execute(
        select(Patient)
        .where(Patient.id == patient_id)
        .options(
            selectinload(Patient.discharge_summaries),
            selectinload(Patient.medications),
            selectinload(Patient.questionnaires),
            selectinload(Patient.interactions),
            selectinload(Patient.alerts),
            selectinload(Patient.appointments),
            selectinload(Patient.followup_jobs),
        )
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        return None

    latest_discharge = (
        max(patient.discharge_summaries, key=lambda d: d.created_at)
        if patient.discharge_summaries
        else None
    )
    latest_questionnaire = (
        max(patient.questionnaires, key=lambda q: q.generated_at)
        if patient.questionnaires
        else None
    )

    questionnaire_context: dict[str, Any] | None = None
    if latest_questionnaire:
        questions, injected = ensure_appointment_consent(
            json.loads(latest_questionnaire.questions_json)
        )
        if injected:
            logger.info(
                "questionnaire.consent_injected",
                patient_id=patient.id,
                questionnaire_id=latest_questionnaire.id,
            )
        questionnaire_context = {
            "id": latest_questionnaire.id,
            "questions": questions,
            "diagnosis_context": latest_questionnaire.diagnosis_context,
            "generated_at": latest_questionnaire.generated_at,
        }

    return {
        "id": patient.id,
        "name": patient.name,
        "phone": patient.phone,
        "dob": patient.dob,
        "email": patient.email,
        "status": patient.status,
        "risk_level": patient.risk_level,
        "created_at": patient.created_at,
        "discharge_summary": (
            {
                "id": latest_discharge.id,
                "diagnosis": latest_discharge.diagnosis,
                "procedures": latest_discharge.procedures,
                "discharge_date": latest_discharge.discharge_date,
                "instructions": latest_discharge.instructions,
                "raw_text": latest_discharge.raw_text,
                "created_at": latest_discharge.created_at,
            }
            if latest_discharge
            else None
        ),
        "medications": [
            {
                "id": med.id,
                "name": med.name,
                "dosage": med.dosage,
                "frequency": med.frequency,
                "created_at": med.created_at,
            }
            for med in patient.medications
        ],
        "questionnaire": questionnaire_context,
        "interactions": [
            {
                "id": item.id,
                "interaction_type": item.interaction_type,
                "channel": item.channel,
                "questionnaire_id": item.questionnaire_id,
                "responses": json.loads(item.responses_json) if item.responses_json else None,
                "created_at": item.created_at,
            }
            for item in sorted(patient.interactions, key=lambda x: x.created_at, reverse=True)
        ],
        "alerts": [
            {
                "id": alert.id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "acknowledged": alert.acknowledged,
                "created_at": alert.created_at,
            }
            for alert in sorted(patient.alerts, key=lambda x: x.created_at, reverse=True)
        ],
        "appointments": [
            {
                "id": appointment.id,
                "appointment_type": appointment.appointment_type,
                "scheduled_at": appointment.scheduled_at,
                "status": appointment.status,
                "notes": appointment.notes,
                "created_at": appointment.created_at,
            }
            for appointment in sorted(
                patient.appointments, key=lambda x: x.created_at, reverse=True
            )
        ],
        "followup_jobs": [
            {
                "id": job.id,
                "job_type": job.job_type,
                "scheduled_at": job.scheduled_at,
                "status": job.status,
                "executed_at": job.executed_at,
                "completed_at": job.completed_at,
                "correlation_id": job.correlation_id,
                "created_at": job.created_at,
            }
            for job in sorted(
                patient.followup_jobs,
                key=lambda j: (_earliest(j.scheduled_at), j.created_at),
                reverse=True,
            )
        ],
    }
