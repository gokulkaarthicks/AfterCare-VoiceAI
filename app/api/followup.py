"""Follow-up Agent HTTP API.

Twilio webhooks (all under /webhooks/voice) drive the two phone flows; the rest
of the API lets scripts and the Scheduler start calls.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from twilio.twiml.voice_response import VoiceResponse

from app.agents.followup import SERVICE_NAME, SERVICE_PORT
from app.agents.followup.dialogs.appointment_booking import (
    handle_booking_gather,
    handle_booking_start,
)
from app.agents.followup.dialogs.dialer import (
    CallRequestError,
    handle_appointment_booking_request,
    start_followup_call,
)
from app.agents.followup.dialogs.questionnaire import (
    handle_voice_complete,
    handle_voice_gather,
    handle_voice_start,
    handle_voice_status,
)
from app.agents.followup.schemas import ActiveSession, InitiateCallRequest
from app.agents.followup.sessions import VOICE_SESSION_PREFIX
from app.agents.followup.speech.tts import router as tts_router
from app.agents.followup.voice import speak, twiml_response
from app.shared.cache.redis_json import cache
from app.shared.core.config import get_settings
from app.shared.core.logging import CorrelationIdMiddleware, configure_logging, get_logger
from app.shared.messaging.bus import event_bus

configure_logging()
logger = get_logger(SERVICE_NAME)


class TwilioWebhookLogger(BaseHTTPMiddleware):
    """Log every Twilio request: if these never appear Twilio cannot reach the app."""

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/webhooks/voice"):
            return await call_next(request)

        started = time.perf_counter()
        logger.info(
            "twilio.request",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params),
        )
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            logger.exception("twilio.request_failed", path=request.url.path)
            raise

        logger.info(
            "twilio.response",
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    public_url = get_settings().twilio_webhook_base_url.strip().rstrip("/")
    logger.info("followup_agent.starting", port=SERVICE_PORT, webhook_base=public_url[:60])
    if "localhost" in public_url or "127.0.0.1" in public_url:
        logger.warning(
            "twilio_webhook_base_url points at localhost: Twilio cannot reach it. "
            "Set it to your public HTTPS tunnel URL in .env and restart."
        )

    await event_bus.connect()
    await cache.connect()
    await event_bus.subscribe(
        "appointment_booking_request",
        handle_appointment_booking_request,
        queue_name="followup_agent.appointment_booking_request",
    )
    yield
    await cache.disconnect()
    await event_bus.disconnect()
    logger.info("followup_agent.stopped")


app = FastAPI(title="AfterCare · Follow-up Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(TwilioWebhookLogger)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tts_router)


# --- Operator API -------------------------------------------------------------


@app.post("/initiate-call")
async def initiate_call(body: InitiateCallRequest) -> dict[str, Any]:
    """Dial a patient for their post-discharge follow-up call."""
    try:
        return await start_followup_call(
            patient_id=body.patient_id,
            schedule_correlation_id=body.schedule_correlation_id,
        )
    except CallRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/active-sessions", response_model=list[ActiveSession])
async def active_sessions() -> list[ActiveSession]:
    """Voice calls currently in progress (useful when debugging a demo)."""
    sessions: list[ActiveSession] = []
    for key in await cache.scan_keys(f"{VOICE_SESSION_PREFIX}*"):
        session = await cache.get_json(key)
        if not session:
            continue
        sessions.append(
            ActiveSession(
                session_key=key,
                patient_id=session.get("patient_id"),
                patient_name=session.get("patient_name"),
                diagnosis=session.get("diagnosis"),
                current_index=session.get("current_index"),
                total_questions=len(session.get("questions", [])),
                call_sid=session.get("call_sid"),
            )
        )
    return sessions


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": SERVICE_NAME}


# --- Twilio webhooks ----------------------------------------------------------


@app.get("/webhooks/voice/start")
@app.post("/webhooks/voice/start")
async def voice_start(request: Request) -> Response:
    """Greeting + first questionnaire item."""
    return await handle_voice_start(request)


@app.post("/webhooks/voice/gather")
async def voice_gather(request: Request) -> Response:
    """Interpret one spoken answer."""
    return await handle_voice_gather(request)


@app.get("/webhooks/voice/complete")
@app.post("/webhooks/voice/complete")
async def voice_complete(request: Request) -> Response:
    """Fallback redirect target used when a gather times out."""
    return await handle_voice_complete(request)


@app.post("/webhooks/voice/status")
async def voice_status(request: Request) -> Response:
    """Twilio call-status callback."""
    return await handle_voice_status(request)


@app.get("/webhooks/voice/appointment/start")
@app.post("/webhooks/voice/appointment/start")
async def appointment_voice_start(request: Request) -> Response:
    """Read out appointment slots."""
    return await handle_booking_start(request)


@app.post("/webhooks/voice/appointment/gather")
async def appointment_voice_gather(request: Request) -> Response:
    """Interpret the spoken slot choice."""
    return await handle_booking_gather(request)


@app.get("/webhooks/voice/twiml-smoke")
async def twiml_smoke() -> Response:
    """Minimal TwiML with no Redis. Use it to confirm a tunnel reaches this app.

        curl -sS 'BASE/webhooks/voice/twiml-smoke' | head -1
    """
    response = VoiceResponse()
    speak(response, "AfterCare webhook smoke test. If you hear this, your tunnel works.")
    response.hangup()
    return twiml_response(response)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
