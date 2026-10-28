"""Outbound call initiation: build the Redis session, then dial via Twilio.

`start_followup_call`: the scheduled post-discharge check-in.
`start_booking_call`: an appointment booking call requested by the Triage Agent.

Both are also exposed over HTTP so scripts and demos can trigger them directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.agents.followup import db_client
from app.agents.followup.dialogs.booking import create_booking_session
from app.agents.followup.sessions import (
    VOICE_SESSION_PREFIX,
    new_voice_session_id,
    save_session,
    webhook_url,
)
from app.agents.followup.voice import place_outbound_call
from app.shared.core.config import get_settings
from app.shared.core.logging import get_logger

logger = get_logger("followup_agent.outbound")


class CallRequestError(RuntimeError):
    """The call cannot be placed (missing phone number, no questionnaire, ...)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def _load_patient_and_questions(
    patient_id: str, triage_agent_url: str
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        patient_response = await client.get(f"{settings.db_service_url}/patients/{patient_id}")
        questions_response = await client.get(f"{triage_agent_url}/patients/{patient_id}/questions")

    if patient_response.status_code != 200:
        raise CallRequestError(
            f"Failed to fetch patient from DB service: {patient_response.text}", 502
        )
    if questions_response.status_code != 200:
        raise CallRequestError(
            f"Failed to fetch questions from Triage Agent: {questions_response.text}", 502
        )

    patient = patient_response.json()
    questions_payload = questions_response.json()
    questions = questions_payload.get(
        "questions", questions_payload if isinstance(questions_payload, list) else []
    )
    return patient, questions, questions_payload.get("questionnaire_id")


async def start_followup_call(
    *,
    patient_id: str,
    schedule_correlation_id: str | None = None,
) -> dict[str, Any]:
    """Place the post-discharge follow-up call and return its identifiers."""
    settings = get_settings()
    logger.info("followup_call.initiate", patient_id=patient_id)

    patient, questions, questionnaire_id = await _load_patient_and_questions(
        patient_id, settings.triage_agent_url
    )
    phone = patient.get("phone", "")
    name = patient.get("name", "")
    diagnosis = (patient.get("discharge_summary") or {}).get("diagnosis", "Unknown")

    if not phone:
        raise CallRequestError("Patient has no phone number on file.")
    if not questions:
        raise CallRequestError(
            "No questions generated for this patient yet. Run the discharge intake first."
        )

    from app.agents.followup.sessions import new_voice_session_id

    session_id = new_voice_session_id()
    session_key = f"{VOICE_SESSION_PREFIX}{session_id}"
    session = {
        "voice_session_id": session_id,
        "patient_id": patient_id,
        "patient_phone": phone,
        "patient_name": name,
        "diagnosis": diagnosis,
        "questionnaire_id": questionnaire_id,
        "schedule_correlation_id": schedule_correlation_id,
        "questions": [
            {
                "id": question.get("id", str(index)),
                "text": question["text"],
                "question_type": question.get("question_type", "open"),
            }
            for index, question in enumerate(questions)
        ],
        "current_index": 0,
        "responses": [],
        "channel": "voice",
    }
    await save_session(session_key, session)

    call_sid = await place_outbound_call(
        to=phone,
        twiml_url=webhook_url("/webhooks/voice/start", voice_session_id=session_id),
        status_callback_url=webhook_url("/webhooks/voice/status"),
    )

    session["call_sid"] = call_sid
    await save_session(session_key, session)

    if schedule_correlation_id:
        await db_client.update_followup_job(
            schedule_correlation_id,
            "in_progress",
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

    logger.info("followup_call.initiated", patient_id=patient_id, call_sid=call_sid, phone=phone)
    return {
        "status": "initiated",
        "channel": "voice",
        "patient_id": patient_id,
        "voice_session_id": session_id,
        "call_sid": call_sid,
    }


async def start_booking_call(
    *,
    patient_id: str,
    urgency: str = "medium",
    reason: str = "",
    correlation_id: str = "",
) -> dict[str, Any] | None:
    """Offer available slots to the patient over the phone."""
    logger.info(
        "booking_call.initiate", patient_id=patient_id, urgency=urgency, correlation_id=correlation_id
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        patient = await db_client.fetch_patient(patient_id, client=client)
        if not patient:
            logger.error("booking_call.patient_unavailable", patient_id=patient_id)
            return None

        phone = patient.get("phone", "")
        name = patient.get("name", "")
        if not phone:
            logger.error("booking_call.no_phone", patient_id=patient_id)
            return None

        slots = await db_client.fetch_available_slots(urgency=urgency, client=client)
        if not slots:
            logger.warning("booking_call.no_slots", patient_id=patient_id, urgency=urgency)
            return None

        appointment_id = await db_client.create_pending_appointment(
            patient_id=patient_id, notes=reason, client=client
        )

    session_id = await create_booking_session(
        patient_id=patient_id,
        patient_name=name,
        appointment_id=appointment_id,
        slots=slots,
        urgency=urgency,
        reason=reason,
        correlation_id=correlation_id,
    )

    try:
        call_sid = await place_outbound_call(
            to=phone,
            twiml_url=webhook_url("/webhooks/voice/appointment/start", voice_session_id=session_id),
            status_callback_url=webhook_url("/webhooks/voice/status"),
        )
    except Exception:  # noqa: BLE001
        logger.exception("booking_call.dial_failed", patient_id=patient_id)
        return None

    logger.info(
        "booking_call.initiated",
        patient_id=patient_id,
        call_sid=call_sid,
        appointment_id=appointment_id,
        slots_offered=len(slots),
    )
    return {
        "status": "initiated",
        "channel": "voice",
        "patient_id": patient_id,
        "appointment_id": appointment_id,
        "voice_session_id": session_id,
        "call_sid": call_sid,
    }


async def handle_appointment_booking_request(envelope: dict[str, Any]) -> None:
    """Consume `appointment_booking_request` from the Triage Agent and dial the patient."""
    payload = envelope.get("payload", {})
    await start_booking_call(
        patient_id=payload.get("patient_id", ""),
        urgency=payload.get("urgency", "medium"),
        reason=payload.get("reason", ""),
        correlation_id=envelope.get("correlation_id", ""),
    )


__all__ = [
    "CallRequestError",
    "handle_appointment_booking_request",
    "start_booking_call",
    "start_followup_call",
]
