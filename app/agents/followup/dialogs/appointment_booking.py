"""Standalone appointment booking call.

Started by the Triage Agent's `appointment_booking_request` event (see
`calls/outbound.py`). The patient hears up to three offered slots, says which
they prefer, and the choice is confirmed against the DB service.
"""

from __future__ import annotations

from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse  # noqa: F401  (re-exported)
from twilio.twiml.voice_response import VoiceResponse

from app.agents.followup import db_client
from app.agents.followup.dialogs.booking import (
    handle_confirmation_result,
    hand_off_to_staff,
    offer_slots,
)
from app.agents.followup.sessions import (
    appointment_session_key,
    drop_session,
    load_session,
    save_session,
)
from app.agents.followup.speech.interpreter import interpret_slot_choice
from app.agents.followup.voice import twiml_response
from app.shared.core.logging import get_logger
logger = get_logger("followup_agent.booking_call")

_SESSION_EXPIRED = "Your session has expired. Goodbye."


async def handle_booking_start(request: Request) -> Response:
    """Read out the available slots for this booking session."""
    params = request.query_params
    key = appointment_session_key(params)
    response = VoiceResponse()

    session = await load_session(key)
    if not session:
        response.say("Sorry, we could not locate your appointment session. Goodbye.", voice="Polly.Joanna")
        response.hangup()
        return twiml_response(response)

    slots = session.get("slots", [])
    name = session.get("patient_name") or "there"

    if not slots:
        response.say(
            f"Hello {name}. Unfortunately we have no available appointment slots at this time. "
            "Your care team will contact you to schedule. Goodbye.",
            voice="Polly.Joanna",
        )
        response.hangup()
        return twiml_response(response)

    plural = "s" if len(slots) != 1 else ""
    offer_slots(
        response,
        session,
        slots,
        f"Hello {name}. This is AfterCare. Based on your recent health check-in, your care team "
        "would like to schedule a follow-up appointment. "
        f"I have {len(slots)} available time{plural} for you.",
    )
    return twiml_response(response)


async def handle_booking_gather(request: Request) -> Response:
    """Interpret the spoken slot choice, then confirm, retry, or hand to staff."""
    params = request.query_params
    key = appointment_session_key(params)
    response = VoiceResponse()

    try:
        form = await request.form()
    except Exception:  # noqa: BLE001
        logger.exception("booking_call.form_parse_failed")
        response.say("We're having a technical issue. Please try again later. Goodbye.", voice="Polly.Joanna")
        response.hangup()
        return twiml_response(response)

    speech = str(form.get("SpeechResult", "")).strip()
    session = await load_session(key)
    if not session:
        response.say(_SESSION_EXPIRED, voice="Polly.Joanna")
        response.hangup()
        return twiml_response(response)

    slots = session.get("slots", [])
    retry_count = session.get("retry_count", 0)
    logger.info(
        "booking_call.choice_received",
        patient_id=session.get("patient_id"),
        speech=speech,
        retry_count=retry_count,
    )

    choice = await interpret_slot_choice(speech, slots)

    if choice.chosen_slot_index is not None and 0 <= choice.chosen_slot_index < len(slots):
        chosen = slots[choice.chosen_slot_index]
        async with httpx.AsyncClient(timeout=10.0) as client:
            result = await db_client.confirm_appointment(
                slot_id=chosen["id"],
                appointment_id=session.get("appointment_id", ""),
                patient_id=session.get("patient_id", ""),
                client=client,
            )
        confirmed = result.json() if result.status_code == 200 else None
        await handle_confirmation_result(
            response,
            session=session,
            session_key=key,
            chosen_slot=chosen,
            status_code=result.status_code,
            confirmed=confirmed,
        )
        return twiml_response(response)

    if choice.preferred_time and retry_count < 1:
        session["retry_count"] = retry_count + 1
        fresh_slots = await db_client.fetch_available_slots(
            urgency=session.get("urgency", "medium")
        )
        session["slots"] = fresh_slots or slots
        await save_session(key, session)
        offer_slots(
            response,
            session,
            session["slots"],
            f"I understand you'd prefer {choice.preferred_time}. "
            "Here are our closest available times:",
        )
        return twiml_response(response)

    if choice.needs_clarification and retry_count < 1:
        session["retry_count"] = retry_count + 1
        await save_session(key, session)
        offer_slots(
            response,
            session,
            slots,
            choice.clarification_question
            or "Could you please repeat which option you'd prefer?",
        )
        return twiml_response(response)

    await hand_off_to_staff(
        response,
        session=session,
        session_key=key,
        preferred_time=choice.preferred_time,
    )
    return twiml_response(response)


