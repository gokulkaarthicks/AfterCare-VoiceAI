"""Twilio voice primitives: outbound calls, TwiML helpers, and spoken formatting."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from starlette.responses import Response
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.shared.core.config import get_settings
from app.shared.core.logging import get_logger

logger = get_logger("followup_agent.voice")

# Spoken times are presented in US Eastern; the call script says "Eastern".
CALL_TIMEZONE = ZoneInfo("America/New_York")

GATHER_TIMEOUT_SECONDS = 10
# Integer seconds: Twilio's "auto" speech timeout is unreliable on some accounts.
SPEECH_TIMEOUT_SECONDS = "5"


# --- Outbound calls -----------------------------------------------------------


@lru_cache(maxsize=1)
def _twilio_client() -> TwilioClient:
    settings = get_settings()
    return TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)


async def place_outbound_call(
    to: str,
    twiml_url: str,
    status_callback_url: str | None = None,
) -> str:
    """Place an outbound call and return its SID."""
    settings = get_settings()
    client = _twilio_client()

    def _create() -> str:
        kwargs: dict = {
            "to": to,
            "from_": settings.twilio_phone_number,
            "url": twiml_url,
            # POST is Twilio's default and more reliable for TwiML webhooks than GET.
            "method": "POST",
        }
        if status_callback_url:
            kwargs["status_callback"] = status_callback_url
            kwargs["status_callback_method"] = "POST"
            # Twilio rejects any other event with error 21626.
            kwargs["status_callback_event"] = ["initiated", "ringing", "answered", "completed"]
        return client.calls.create(**kwargs).sid

    call_sid = await asyncio.to_thread(_create)
    logger.info("outbound_call.placed", to=to, call_sid=call_sid)
    return call_sid


# --- TwiML --------------------------------------------------------------------


def twiml_response(response: VoiceResponse) -> Response:
    return Response(content=str(response), media_type="text/xml; charset=utf-8")


def build_gather(action_url: str) -> Gather:
    return Gather(
        input="speech",
        action=action_url,
        method="POST",
        timeout=GATHER_TIMEOUT_SECONDS,
        speech_timeout=SPEECH_TIMEOUT_SECONDS,
        language="en-US",
    )


def speak(element: VoiceResponse | Gather, text: str) -> None:
    """Speak via ElevenLabs <Play> when configured, else fall back to Polly <Say>."""
    from app.agents.followup.speech.tts import tts_play_url

    if get_settings().elevenlabs_api_key:
        element.play(tts_play_url(text))
    else:
        element.say(text, voice="Polly.Joanna")


# --- Spoken formatting --------------------------------------------------------


def to_call_timezone(value: str | datetime) -> datetime:
    """Parse an ISO timestamp (naive means UTC, as SQLite stores it) and convert to Eastern."""
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(CALL_TIMEZONE)


def speakable_datetime(value: str | datetime) -> str:
    """e.g. 'Monday, March 3 at 2 PM Eastern': portable across platforms."""
    try:
        local = to_call_timezone(value)
    except Exception:  # noqa: BLE001 - never break a live call on formatting
        return "the scheduled time"
    day = local.strftime("%A, %B %d").replace(" 0", " ")
    hour = local.strftime("%I").lstrip("0") or "12"
    minute = f":{local.strftime('%M')}" if local.minute else ""
    return f"{day} at {hour}{minute} {local.strftime('%p')} Eastern"


def speakable_slot(slot: dict, index: int) -> str:
    """One numbered option read out during slot selection."""
    doctor = slot.get("doctor_name", "your doctor")
    try:
        when = speakable_datetime(slot["slot_start"])
    except Exception:  # noqa: BLE001
        return f"Option {index + 1}: with {doctor}."
    return f"Option {index + 1}: {when} with {doctor}."


def describe_slots(slots: list[dict]) -> str:
    return " ".join(speakable_slot(slot, index) for index, slot in enumerate(slots))
