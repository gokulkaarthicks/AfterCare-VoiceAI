"""ElevenLabs text-to-speech: TwiML <Play> URLs plus the streaming audio endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.followup.sessions import webhook_url
from app.shared.core.config import get_settings
from app.shared.core.logging import get_logger

logger = get_logger("followup_agent.tts")

# eleven_turbo_v2_5 gives the lowest latency (~300 ms to first byte).
TTS_MODEL = "eleven_turbo_v2_5"

router = APIRouter()


def tts_play_url(text: str) -> str:
    """Public HTTPS URL Twilio should <Play> to speak `text`."""
    return webhook_url("/voice/tts", text=text)


@router.get("/voice/tts")
async def stream_tts(text: str = "") -> StreamingResponse:
    """Stream ElevenLabs audio as audio/mpeg so Twilio starts playback immediately.

    Any ElevenLabs failure returns an empty 200 with the correct content type, so
    Twilio skips the prompt instead of erroring the whole call.
    """
    settings = get_settings()
    if not text or not settings.elevenlabs_api_key:
        if text:
            logger.warning("tts.missing_api_key")
        return StreamingResponse(iter([]), media_type="audio/mpeg")

    try:
        from elevenlabs import AsyncElevenLabs

        client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        # .stream() returns an async generator: do not await it.
        audio_chunks = client.text_to_speech.stream(
            text=text,
            voice_id=settings.elevenlabs_voice_id,
            model_id=TTS_MODEL,
        )

        async def _audio():
            async for chunk in audio_chunks:
                if chunk:
                    yield chunk

        return StreamingResponse(_audio(), media_type="audio/mpeg")
    except Exception:  # noqa: BLE001
        logger.exception("tts.stream_failed", text_len=len(text))
        return StreamingResponse(iter([]), media_type="audio/mpeg")
