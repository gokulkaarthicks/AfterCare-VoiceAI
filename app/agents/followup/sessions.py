"""Voice session persistence and TwiML URL construction.

Twilio webhooks are stateless, so every in-progress call lives in Redis under
`voice_session:{id}` (follow-up call) or `appt_session:{id}` (appointment
booking). This module owns those keys and the absolute URLs TwiML must return.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlencode

from app.shared.cache.redis_json import cache
from app.shared.core.config import get_settings

VOICE_SESSION_PREFIX = "voice_session:"
APPOINTMENT_SESSION_PREFIX = "appt_session:"


# --- Keys and lookups ---------------------------------------------------------


def voice_session_key(session: dict[str, Any], params: Any) -> str | None:
    """Redis key for the call identified by the session, falling back to the URL params."""
    session_id = (session.get("voice_session_id") or "").strip()
    if not session_id:
        session_id = (params.get("voice_session_id") or params.get("patient_id") or "").strip()
    return f"{VOICE_SESSION_PREFIX}{session_id}" if session_id else None


def appointment_session_key(params: Any) -> str | None:
    session_id = (params.get("voice_session_id") or "").strip()
    return f"{APPOINTMENT_SESSION_PREFIX}{session_id}" if session_id else None


async def load_session(key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    return await cache.get_json(key)


async def save_session(key: str, session: dict[str, Any]) -> None:
    await cache.set_json(
        key, session, ttl_seconds=get_settings().redis_session_ttl_seconds
    )


async def drop_session(key: str) -> None:
    await cache.delete(key)


def new_voice_session_id() -> str:
    return str(uuid.uuid4())


# --- TwiML URLs ---------------------------------------------------------------


def public_base_url() -> str:
    return get_settings().twilio_webhook_base_url.strip().rstrip("/")


def ngrok_free_skip_warning_params(base_url: str) -> dict[str, str]:
    """Extra query params that stop ngrok-free tunnels from serving an HTML warning page.

    Twilio cannot send custom headers on webhook fetches, so the token goes in the
    query string instead; without it Twilio receives HTML and reports an
    application error.
    """
    if "ngrok-free." in (base_url or "").lower():
        return {"ngrok-skip-browser-warning": "1"}
    return {}


def webhook_url(path: str, **params: str) -> str:
    """Absolute webhook URL for the current public tunnel."""
    base = public_base_url()
    query = {**ngrok_free_skip_warning_params(base), **{k: v for k, v in params.items() if v}}
    return f"{base}{path}?{urlencode(query)}" if query else f"{base}{path}"


def session_webhook_url(
    path: str,
    session: dict[str, Any],
    params: Any,
    extra: dict[str, str] | None = None,
) -> str:
    """Webhook URL that keeps the current call's session identifier attached."""
    identity = (session.get("voice_session_id") or params.get("voice_session_id") or "").strip()
    if not identity:
        identity = (params.get("patient_id") or session.get("patient_id") or "").strip()
    return webhook_url(path, voice_session_id=identity, **(extra or {}))
