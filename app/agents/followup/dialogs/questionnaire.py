"""Post-discharge follow-up call: ask the questionnaire, then possibly book.

Flow:
    /webhooks/voice/start   greeting + question 1            → /gather?q_index=0
    /webhooks/voice/gather  interpret answer, repeat or move  → /gather?q_index=n
    /webhooks/voice/complete  gather fallback when speech is missed
    last question is the appointment-consent item:
        yes → book a slot inline on the same call (calls/booking.py)
        no  → thank the patient, publish responses, hang up
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import Response
from twilio.twiml.voice_response import VoiceResponse

from app.agents.followup import db_client
from app.agents.followup.dialogs.booking import create_booking_session, offer_slots
from app.agents.followup.sessions import (
    APPOINTMENT_SESSION_PREFIX,
    VOICE_SESSION_PREFIX,
    drop_session,
    load_session,
    save_session,
    session_webhook_url,
    voice_session_key,
)
from app.agents.followup.speech.interpreter import interpret_answer
from app.agents.followup.voice import build_gather, speak, twiml_response
from app.shared.clinical.questionnaire import APPOINTMENT_CONSENT_QUESTION_ID
from app.shared.core.logging import get_logger
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import PatientResponseEvent, ResponseItem

logger = get_logger("followup_agent.followup_call")

MAX_CLARIFICATION_RETRIES = 2

_ACK_BY_NORMALIZED = {"yes": "Got it. ", "no": "Understood. "}
_SESSION_EXPIRED = "Your session has expired. Goodbye."
_TECHNICAL_ISSUE = "We're having a technical issue. Please try again later. Goodbye."


# --- Publishing results -------------------------------------------------------


def _response_items(session: dict[str, Any]) -> list[ResponseItem]:
    return [
        ResponseItem(
            question_id=entry["question_id"],
            question_text=entry["question_text"],
            answer=entry["answer"],
            normalized=entry.get("normalized"),
            clinical_flags=entry.get("clinical_flags", []),
        )
        for entry in session.get("responses", [])
    ]


async def publish_responses(session: dict[str, Any], call_sid: str | None = None) -> None:
    """Hand the finished questionnaire to the Triage Agent."""
    event = PatientResponseEvent(
        patient_id=session["patient_id"],
        interaction_id=str(uuid.uuid4()),
        questionnaire_id=session.get("questionnaire_id"),
        responses=_response_items(session),
        channel="voice",
        twilio_sid=call_sid,
    )
    await event_bus.publish("patient_response_event", event, source_service="followup_agent")
    logger.info(
        "followup_call.responses_published",
        patient_id=session["patient_id"],
        response_count=len(session.get("responses", [])),
        clinical_flags=[
            flag for entry in session.get("responses", []) for flag in entry.get("clinical_flags", [])
        ],
    )


# --- Webhook handlers ---------------------------------------------------------


async def handle_voice_start(request: Request) -> Response:
    """Greet the patient and ask the first question."""
    params = request.query_params
    key = voice_session_key({}, params)
    response = VoiceResponse()

    logger.info("followup_call.start", session_key=key)
    session = await load_session(key)

    if not session or not session.get("questions"):
        speak(response, "Sorry, we could not locate your follow-up questionnaire. Goodbye.")
        response.hangup()
        return twiml_response(response)

    questions = session["questions"]
    name = session.get("patient_name") or "there"
    first_question = questions[0].get("text") or "your first question"
    plural = "s" if len(questions) != 1 else ""

    greeting = (
        f"Hello {name}. This is AfterCare, calling for your post-discharge health check-in. "
        f"I have {len(questions)} question{plural} for you. "
        "Please speak your answer clearly after each question. "
        f"First question: {first_question}"
    )

    gather = build_gather(session_webhook_url("/webhooks/voice/gather", session, params, {"q_index": "0"}))
    speak(gather, greeting)
    response.append(gather)

    speak(response, "I didn't hear a response. Let me repeat the question.")
    response.redirect(session_webhook_url("/webhooks/voice/start", session, params), method="GET")
    return twiml_response(response)


async def handle_voice_gather(request: Request) -> Response:
    """Interpret one spoken answer, then advance, clarify, or finish."""
    params = request.query_params
    key = voice_session_key({}, params)
    question_index = int(params.get("q_index", "0"))
    is_clarification = params.get("is_clarification", "false").lower() == "true"

    try:
        form = await request.form()
    except Exception:  # noqa: BLE001
        logger.exception("followup_call.form_parse_failed", session_key=key)
        return _technical_issue_response()

    speech = str(form.get("SpeechResult", "")).strip()
    call_sid = str(form.get("CallSid", ""))
    logger.info(
        "followup_call.answer_received",
        session_key=key,
        question_index=question_index,
        is_clarification=is_clarification,
        speech=speech,
    )

    response = VoiceResponse()
    session = await load_session(key)
    if not session:
        speak(response, _SESSION_EXPIRED)
        response.hangup()
        return twiml_response(response)

    questions = session["questions"]
    if question_index >= len(questions):
        await finish_call(response, session, call_sid, key)
        return twiml_response(response)

    question = questions[question_index]
    interpreted = await interpret_answer(
        question_text=question.get("text", ""),
        question_type=question.get("question_type", "open"),
        speech_result=speech,
        diagnosis=session.get("diagnosis", "Unknown"),
    )

    if interpreted.needs_clarification:
        retry_count = session.get(f"retry_{question_index}", 0)
        if retry_count < MAX_CLARIFICATION_RETRIES:
            session[f"retry_{question_index}"] = retry_count + 1
            await save_session(key, session)
            logger.info(
                "followup_call.clarification",
                patient_id=session.get("patient_id"),
                question_index=question_index,
                attempt=retry_count + 1,
            )
            _ask_again(response, session, params, question_index, interpreted.clarification_question)
            return twiml_response(response)

        logger.warning(
            "followup_call.clarification_exhausted",
            patient_id=session.get("patient_id"),
            question_index=question_index,
        )
        interpreted.interpreted_answer = (
            interpreted.interpreted_answer
            or f"[Unclear response after {MAX_CLARIFICATION_RETRIES} attempts]"
        )

    session["responses"].append(
        {
            "question_id": question.get("id", str(question_index)),
            "question_text": question.get("text", ""),
            "answer": interpreted.interpreted_answer,
            "normalized": interpreted.normalized,
            "clinical_flags": interpreted.clinical_flags,
            "raw_speech": interpreted.raw_speech,
        }
    )
    session["current_index"] = question_index + 1
    session.pop(f"retry_{question_index}", None)

    if question.get("id") == APPOINTMENT_CONSENT_QUESTION_ID:
        if _patient_consented(interpreted.interpreted_answer, interpreted.normalized):
            await save_session(key, session)
            await _book_inline_on_same_call(response, session, key, call_sid)
        else:
            speak(response, "No problem. Your care team has been notified. Take care, goodbye!")
            response.hangup()
            await publish_responses(session, call_sid=call_sid)
            await drop_session(key)
        return twiml_response(response)

    next_index = question_index + 1
    if next_index < len(questions):
        acknowledgement = _ACK_BY_NORMALIZED.get(
            (interpreted.normalized or "").lower(), "Thank you. "
        )
        next_prompt = f"{acknowledgement}Next question: {questions[next_index].get('text') or 'the next question'}"
        await save_session(key, session)

        gather = build_gather(
            session_webhook_url("/webhooks/voice/gather", session, params, {"q_index": str(next_index)})
        )
        speak(gather, next_prompt)
        response.append(gather)

        speak(response, "I didn't hear a response. Let me repeat.")
        response.redirect(
            session_webhook_url("/webhooks/voice/gather", session, params, {"q_index": str(next_index)}),
            method="POST",
        )
    else:
        await save_session(key, session)
        await finish_call(response, session, call_sid, key)

    return twiml_response(response)


async def handle_voice_complete(request: Request) -> Response:
    """Close the call when the gather fallback redirect fires (e.g. silence on the last question)."""
    params = request.query_params
    call_sid = params.get("call_sid", "")
    if request.method == "POST":
        form = await request.form()
        call_sid = str(form.get("CallSid", "") or call_sid)

    key = voice_session_key({}, params)
    logger.info("followup_call.complete", session_key=key, call_sid=call_sid)

    response = VoiceResponse()
    session = await load_session(key)
    if not session:
        speak(response, "Your session has ended. Goodbye.")
        response.hangup()
        return twiml_response(response)

    await finish_call(response, session, call_sid, key)
    return twiml_response(response)


async def handle_voice_status(request: Request) -> Response:
    """Twilio status callback: cleans up sessions for calls that never connected."""
    try:
        form = await request.form()
        call_sid = str(form.get("CallSid", ""))
        call_status = str(form.get("CallStatus", ""))
        logger.info("followup_call.status", call_sid=call_sid, call_status=call_status)

        if call_status in ("no-answer", "busy", "failed", "canceled"):
            await _cleanup_abandoned_call(call_sid, call_status)
    except Exception:  # noqa: BLE001
        logger.exception("followup_call.status_failed")

    return Response(content="", status_code=200)


async def _cleanup_abandoned_call(call_sid: str, call_status: str) -> None:
    """Drop whichever Redis session belongs to this call and mark its job failed."""
    for prefix in (VOICE_SESSION_PREFIX, APPOINTMENT_SESSION_PREFIX):
        for key in await cache.scan_keys(f"{prefix}*"):
            session = await load_session(key)
            if not (session and session.get("call_sid") == call_sid):
                continue
            job_id = session.get("schedule_correlation_id")
            if prefix == VOICE_SESSION_PREFIX and job_id:
                await db_client.update_followup_job(
                    str(job_id), "failed", completed_at=datetime.now(timezone.utc).isoformat()
                )
            await drop_session(key)
            logger.info("followup_call.session_cleaned", key=key, call_status=call_status)
            return


# --- Interaction helpers ------------------------------------------------------


def _technical_issue_response() -> Response:
    response = VoiceResponse()
    speak(response, _TECHNICAL_ISSUE)
    response.hangup()
    return twiml_response(response)


def _ask_again(
    response: VoiceResponse,
    session: dict[str, Any],
    params: Any,
    question_index: int,
    clarification: str | None,
) -> None:
    prompt = clarification or "Could you please repeat or clarify your answer?"
    gather = build_gather(
        session_webhook_url(
            "/webhooks/voice/gather",
            session,
            params,
            {"q_index": str(question_index), "is_clarification": "true"},
        )
    )
    speak(gather, prompt)
    response.append(gather)

    next_index = question_index + 1
    speak(response, "I didn't hear a response. Moving to the next question.")
    if next_index < len(session["questions"]):
        response.redirect(
            session_webhook_url("/webhooks/voice/gather", session, params, {"q_index": str(next_index)}),
            method="POST",
        )
    else:
        response.redirect(session_webhook_url("/webhooks/voice/complete", session, params), method="POST")


async def _book_inline_on_same_call(
    response: VoiceResponse,
    session: dict[str, Any],
    key: str,
    call_sid: str,
) -> None:
    """Consent given: publish the clinical answers and continue into slot selection."""
    patient_id = session.get("patient_id", "")
    patient_name = session.get("patient_name") or "there"

    try:
        await publish_responses(session, call_sid=call_sid)
    except Exception:  # noqa: BLE001 - booking still proceeds
        logger.exception("followup_call.publish_failed", patient_id=patient_id)

    await drop_session(key)

    try:
        slots = await db_client.fetch_available_slots(urgency="medium")
    except Exception:  # noqa: BLE001
        logger.exception("followup_call.slots_fetch_failed", patient_id=patient_id)
        slots = []

    if not slots:
        speak(
            response,
            "I'd like to schedule an appointment for you, but there are no available slots right now. "
            "Your care team will call you to arrange a time. Take care, goodbye!",
        )
        response.hangup()
        logger.warning("followup_call.no_slots", patient_id=patient_id)
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            appointment_id = await db_client.create_pending_appointment(
                patient_id=patient_id,
                notes="Patient requested appointment during follow-up call.",
                client=client,
            )
    except Exception:  # noqa: BLE001
        logger.exception("followup_call.appointment_create_failed", patient_id=patient_id)
        speak(
            response,
            "I'd like to schedule an appointment, but we're having a technical issue. "
            "Your care team will call you to arrange a time. Goodbye!",
        )
        response.hangup()
        return

    session_id = await create_booking_session(
        patient_id=patient_id,
        patient_name=patient_name,
        appointment_id=appointment_id,
        slots=slots,
        urgency="medium",
    )
    booking_session = {"voice_session_id": session_id}

    plural = "s" if len(slots) != 1 else ""
    offer_slots(
        response,
        booking_session,
        slots,
        "Great! Let me check available appointment slots for you. "
        f"I have {len(slots)} available time{plural} with your doctor.",
    )
    logger.info(
        "followup_call.booking_started",
        patient_id=patient_id,
        appointment_id=appointment_id,
        slots_offered=len(slots),
        booking_session_id=session_id,
    )


_POSITIVE_PHRASES = (
    "yes", "yeah", "yep", "yup", "sure", "please", "definitely", "absolutely",
    "of course", "i would", "i'd like", "i want", "would like", "sounds good",
    "that would", "go ahead", "requests to schedule", "wants to schedule",
    "would like to schedule", "requests an appointment", "wants an appointment",
    "asking to schedule", "wishes to schedule", "has requested", "patient requests",
    "patient wants", "consents to", "agrees to", "would like to book",
    "wants to book", "has consented", "given consent", "willing to",
)
_NEGATIVE_PHRASES = (
    "no ", "nope", "no,", "no.", "not ", "don't", "do not", "declines", "decline",
    "doesn't want", "does not want", "not interested", "no thank", "not at this",
)


def _patient_consented(answer: str, normalized: str = "") -> bool:
    """True when the spoken consent answer is affirmative.

    `normalized` is trusted first; negative phrasing is matched before positive so
    an explicit decline always wins.
    """
    if normalized:
        normalized = normalized.lower().strip()
        if normalized == "no":
            return False
        if normalized == "yes":
            return True

    text = (answer or "").lower().strip()
    if not text:
        return False
    if any(phrase in text for phrase in _NEGATIVE_PHRASES):
        return False
    return any(phrase in text for phrase in _POSITIVE_PHRASES)


async def finish_call(
    response: VoiceResponse,
    session: dict[str, Any],
    call_sid: str,
    session_key: str,
) -> None:
    """Say goodbye, publish responses, and close out the follow-up job."""
    speak(
        response,
        "Thank you for completing your follow-up check-in. Your care team has been notified. "
        "Please do not hesitate to call us if you have any concerns. Take care and goodbye!",
    )
    response.hangup()

    sid = call_sid.strip() or None
    try:
        await publish_responses(session, call_sid=sid)
    except Exception:  # noqa: BLE001
        logger.exception("followup_call.publish_failed", patient_id=session.get("patient_id"))

    job_id = session.get("schedule_correlation_id")
    await drop_session(session_key)
    logger.info(
        "followup_call.finished",
        patient_id=session.get("patient_id"),
        total_responses=len(session.get("responses", [])),
    )

    if job_id:
        await db_client.update_followup_job(
            str(job_id), "completed", completed_at=datetime.now(timezone.utc).isoformat()
        )
