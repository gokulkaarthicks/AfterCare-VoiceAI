"""Shared booking steps used by both phone flows.

Slot selection inside a follow-up call and the standalone booking call need the
same pieces: reading options aloud, storing an `appt_session`, and handing the
appointment back to staff when automation cannot finish it.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from twilio.twiml.voice_response import VoiceResponse

from app.agents.followup import db_client
from app.agents.followup.sessions import (
    APPOINTMENT_SESSION_PREFIX,
    drop_session,
    save_session,
    webhook_url,
)
from app.agents.followup.voice import (
    build_gather,
    describe_slots,
    speak,
    speakable_datetime,
)
from app.shared.core.logging import get_logger

logger = get_logger("followup_agent.booking")

MANUAL_SCHEDULING_NOTE = (
    "Manual scheduling required: automated booking unsuccessful. "
    "Please call the patient to confirm a suitable time."
)


def appointment_gather_url(session_id: str) -> str:
    return webhook_url("/webhooks/voice/appointment/gather", voice_session_id=session_id)


def appointment_start_url(session_id: str) -> str:
    return webhook_url("/webhooks/voice/appointment/start", voice_session_id=session_id)


async def create_booking_session(
    *,
    patient_id: str,
    patient_name: str,
    appointment_id: str,
    slots: list[dict[str, Any]],
    urgency: str,
    reason: str = "",
    correlation_id: str = "",
    session_id: str | None = None,
) -> str:
    """Persist an appointment session in Redis and return its id."""
    session_id = session_id or str(uuid.uuid4())
    await save_session(
        f"{APPOINTMENT_SESSION_PREFIX}{session_id}",
        {
            "voice_session_id": session_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "appointment_id": appointment_id,
            "slots": slots,
            "urgency": urgency,
            "reason": reason,
            "correlation_id": correlation_id,
            "retry_count": 0,
        },
    )
    return session_id


def offer_slots(
    response: VoiceResponse,
    session: dict[str, Any],
    slots: list[dict[str, Any]],
    prompt: str,
) -> None:
    """Append a spoken slot list plus a speech gather to the TwiML response."""
    session_id = session["voice_session_id"]
    gather = build_gather(appointment_gather_url(session_id))
    speak(gather, f"{prompt} {describe_slots(slots)} Which option works best for you?")
    response.append(gather)
    speak(response, "I didn't hear a response. Let me repeat the options.")
    response.redirect(appointment_start_url(session_id), method="GET")


async def handle_confirmation_result(
    response: VoiceResponse,
    *,
    session: dict[str, Any],
    session_key: str,
    chosen_slot: dict[str, Any],
    status_code: int,
    confirmed: dict[str, Any] | None,
) -> None:
    """Speak the outcome of an appointment confirmation attempt."""
    appointment_id = session.get("appointment_id", "")
    session_id = session["voice_session_id"]

    if status_code == 200 and confirmed:
        doctor = confirmed.get("doctor_name", chosen_slot.get("doctor_name", "your doctor"))
        when = speakable_datetime(confirmed.get("scheduled_at", ""))
        speak(
            response,
            f"Perfect. Your appointment has been confirmed for {when} with {doctor}. "
            "Your care team will send you a reminder. Take care and goodbye!",
        )
        response.hangup()
        await drop_session(session_key)
        logger.info(
            "appointment.confirmed",
            patient_id=session.get("patient_id"),
            appointment_id=appointment_id,
            scheduled_at=confirmed.get("scheduled_at"),
        )
        return

    if status_code == 409:
        # Another call booked this slot first: offer whatever is left.
        remaining = [slot for slot in session.get("slots", []) if slot["id"] != chosen_slot["id"]]
        if remaining:
            session["slots"] = remaining
            await save_session(session_key, session)
            offer_slots(
                response,
                {**session, "voice_session_id": session_id},
                remaining,
                "I'm sorry, that slot was just taken. Here are the remaining options:",
            )
            return

        await db_client.mark_appointment_for_manual_scheduling(appointment_id, MANUAL_SCHEDULING_NOTE)
        speak(
            response,
            "I'm sorry, all available slots have just been taken. "
            "Your care team will call you to schedule. Goodbye.",
        )
        response.hangup()
        await drop_session(session_key)
        return

    await db_client.mark_appointment_for_manual_scheduling(
        appointment_id,
        "Booking confirmation failed due to a system error. Manual scheduling required.",
    )
    speak(
        response,
        "There was a problem confirming your appointment. Your care team will follow up. Goodbye.",
    )
    response.hangup()
    await drop_session(session_key)


async def hand_off_to_staff(
    response: VoiceResponse,
    *,
    session: dict[str, Any],
    session_key: str,
    preferred_time: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Mark the appointment as needing a human and close the call politely."""
    note = MANUAL_SCHEDULING_NOTE
    if preferred_time:
        note = (
            f"Manual scheduling required: patient requested {preferred_time}. "
            "Please call to confirm a suitable time."
        )
    await db_client.mark_appointment_for_manual_scheduling(
        session.get("appointment_id", ""), note, client=client
    )
    speak(
        response,
        "We were unable to schedule your appointment automatically. "
        "Your care team will call you directly to find a suitable time. Goodbye.",
    )
    response.hangup()
    await drop_session(session_key)
    logger.info(
        "appointment.pending_manual",
        patient_id=session.get("patient_id"),
        appointment_id=session.get("appointment_id"),
        preferred_time=preferred_time,
    )
