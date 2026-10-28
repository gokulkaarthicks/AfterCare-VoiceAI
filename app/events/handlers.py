"""Handlers for every event the DB service consumes.

Each handler follows the same shape:
  1. append the raw event (duplicate correlation ids are dropped),
  2. write the domain rows inside one transaction,
  3. publish `patient_record_updated` so the dashboard can refresh.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from app.db import SERVICE_NAME
from app.db.repositories import alerts as alerts_repo
from app.db.repositories import appointments as appointments_repo
from app.db.repositories import charts
from app.db.repositories import common
from app.db.repositories import followups as followups_repo
from app.db.repositories import patients as patients_repo
from app.shared.core.logging import get_logger
from app.shared.database.engine import get_session_factory
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import PatientRecordUpdated

logger = get_logger("db_service.event_handlers")


@asynccontextmanager
async def _transaction():
    async with get_session_factory()() as session:
        async with session.begin():
            yield session


async def _announce_update(
    patient_id: str, updated_fields: list[str], correlation_id: str
) -> None:
    await event_bus.publish(
        "patient_record_updated",
        PatientRecordUpdated(
            patient_id=patient_id,
            updated_fields=updated_fields,
            correlation_id=correlation_id,
            source_service=SERVICE_NAME,
        ),
        correlation_id=correlation_id,
        source_service=SERVICE_NAME,
    )


async def _append_event(
    session, event_type: str, payload: dict[str, Any], correlation_id: str, source: str
) -> bool:
    """Record the raw event; False means this correlation id was already handled."""
    stored = await common.record_event(
        session,
        event_type=event_type,
        payload_json=json.dumps(payload),
        correlation_id=correlation_id,
        source_service=source,
    )
    if stored is None:
        logger.info("event.duplicate_ignored", event_type=event_type, correlation_id=correlation_id)
        return False
    return True


# --- patient_state_upsert -----------------------------------------------------


async def handle_patient_state_upsert(envelope: dict[str, Any]) -> None:
    """Store a parsed discharge: demographics, chart, medications, questionnaire."""
    payload = envelope.get("payload", {})
    correlation_id = envelope.get("correlation_id", "")
    source = envelope.get("source_service", "unknown")

    logger.info(
        "patient_state_upsert.received",
        patient_id=payload.get("patient_id"),
        correlation_id=correlation_id,
    )

    async with _transaction() as session:
        if not await _append_event(session, "patient_state_upsert", payload, correlation_id, source):
            return

        patient = await patients_repo.upsert_patient(session, payload)
        patient_id = patient.id
        updated_fields = ["patient"]

        discharge = payload.get("discharge_data")
        if discharge:
            await charts.add_discharge_summary(session, patient_id, discharge)
            updated_fields.append("discharge_summary")

        medications = payload.get("medications") or []
        if medications:
            await charts.add_medications(session, patient_id, medications)
            updated_fields.append("medications")

        questions = payload.get("generated_questions") or []
        if questions:
            await charts.add_questionnaire(
                session,
                patient_id,
                questions,
                (discharge or {}).get("diagnosis", ""),
            )
            updated_fields.append("questionnaire")

        await common.add_audit_log(
            session,
            entity_type="patient",
            entity_id=patient_id,
            action="upsert",
            changes={"updated_fields": updated_fields},
            correlation_id=correlation_id,
        )

    await _announce_update(patient_id, updated_fields, correlation_id)
    logger.info("patient_state_upsert.stored", patient_id=patient_id, fields=updated_fields)


# --- alert_event --------------------------------------------------------------


async def handle_alert_event(envelope: dict[str, Any]) -> None:
    """Create a dashboard alert for the care team."""
    payload = envelope.get("payload", {})
    correlation_id = envelope.get("correlation_id", "")
    source = envelope.get("source_service", "unknown")

    logger.info("alert_event.received", patient_id=payload.get("patient_id"))

    async with _transaction() as session:
        if not await _append_event(session, "alert_event", payload, correlation_id, source):
            return

        alert = await alerts_repo.add_alert(session, payload)
        await common.add_audit_log(
            session,
            entity_type="alert",
            entity_id=alert.id,
            action="created",
            changes={"alert_type": alert.alert_type, "severity": alert.severity},
            correlation_id=correlation_id,
        )

    await _announce_update(payload.get("patient_id", ""), ["alert"], correlation_id)
    logger.info("alert_event.stored", alert_id=alert.id)


# --- patient_response_event ---------------------------------------------------


async def handle_patient_response_event(envelope: dict[str, Any]) -> None:
    """Store the Q&A from a finished call as a patient interaction."""
    payload = envelope.get("payload", {})
    correlation_id = envelope.get("correlation_id", "")
    source = envelope.get("source_service", "unknown")
    patient_id = payload.get("patient_id", "")
    responses = payload.get("responses", [])

    logger.info("patient_response_event.received", patient_id=patient_id)

    async with _transaction() as session:
        if not await _append_event(session, "patient_response_event", payload, correlation_id, source):
            return

        transcript = [
            {
                "question_id": item.get("question_id"),
                "question": item.get("question_text"),
                "answer": item.get("answer"),
                "normalized": item.get("normalized"),
            }
            for item in responses
        ]
        interaction = await charts.add_interaction(
            session,
            {
                "patient_id": patient_id,
                "interaction_type": "followup",
                "channel": payload.get("channel", "voice"),
                "questionnaire_id": payload.get("questionnaire_id"),
                "questions_json": json.dumps(
                    [{"id": item.get("question_id"), "text": item.get("question_text")} for item in responses]
                ),
                "responses_json": json.dumps(transcript),
                "twilio_sid": payload.get("twilio_sid"),
            },
        )
        await common.add_audit_log(
            session,
            entity_type="patient_interaction",
            entity_id=interaction.id,
            action="created",
            changes={"response_count": len(responses), "channel": "voice"},
            correlation_id=correlation_id,
        )

    await _announce_update(patient_id, ["interaction"], correlation_id)
    logger.info(
        "patient_response_event.stored",
        patient_id=patient_id,
        interaction_id=interaction.id,
        response_count=len(responses),
    )


# --- schedule_event -----------------------------------------------------------


async def handle_schedule_event(envelope: dict[str, Any]) -> None:
    """Queue work for the Scheduler: a voice follow-up, or an appointment request."""
    payload = envelope.get("payload", {})
    correlation_id = envelope.get("correlation_id", "")
    source = envelope.get("source_service", "unknown")
    job_type = payload.get("job_type", "followup")
    metadata = payload.get("metadata", {})

    logger.info(
        "schedule_event.received",
        patient_id=payload.get("patient_id"),
        job_type=job_type,
    )

    async with _transaction() as session:
        if not await _append_event(session, "schedule_event", payload, correlation_id, source):
            return

        if job_type == "appointment":
            appointment = await appointments_repo.add_appointment(
                session,
                {
                    "patient_id": payload["patient_id"],
                    "appointment_type": metadata.get("appointment_type", "followup"),
                    "scheduled_at": payload.get("scheduled_at"),
                    "notes": metadata.get("notes"),
                },
            )
            entity_type, entity_id = "appointment", appointment.id
        else:
            job = await followups_repo.add_followup_job(
                session,
                {
                    "patient_id": payload["patient_id"],
                    "job_type": job_type,
                    "scheduled_at": payload.get("scheduled_at"),
                    "correlation_id": correlation_id or None,
                },
            )
            entity_type, entity_id = "followup_job", job.id

        await common.add_audit_log(
            session,
            entity_type=entity_type,
            entity_id=entity_id,
            action="created",
            changes={"job_type": job_type},
            correlation_id=correlation_id,
        )

    await _announce_update(payload.get("patient_id", ""), [entity_type], correlation_id)
    logger.info("schedule_event.stored", entity_type=entity_type, entity_id=entity_id)


__all__ = [
    "handle_alert_event",
    "handle_patient_response_event",
    "handle_patient_state_upsert",
    "handle_schedule_event",
]
