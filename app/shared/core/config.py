"""Environment-backed application settings shared by every AfterCare service.

All values are read from the process environment, falling back to the optional
`.env` file at the repository root. Field names map to upper-case environment
variables (for example `rabbitmq_url` <- `RABBITMQ_URL`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view over the AfterCare environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM provider (OpenRouter exposes an OpenAI-compatible chat API) --------
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-v4-flash"

    # --- Optional ElevenLabs narration; falls back to Twilio Polly when empty ---
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "gJx1vCzNCD1EQHT212Ls"

    # --- Twilio programmable voice --------------------------------------------
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    twilio_webhook_base_url: str = "http://localhost:8002"

    # --- Shared infrastructure -------------------------------------------------
    rabbitmq_url: str = "amqp://guest:guest@localhost/"
    redis_url: str = "redis://localhost:6379"
    redis_session_ttl_seconds: int = 3600
    database_url: str = "sqlite+aiosqlite:///./aftercare.db"

    # --- Runtime behaviour -----------------------------------------------------
    demo_mode: bool = True
    # Demo only: gap between a discharge intake and its first outbound call, used
    # when the Triage Agent did not supply an explicit `scheduled_at`.
    demo_followup_delay_seconds: int = 240
    # Demo only: Care Act follow-up spacing per urgency tier (minutes from now).
    demo_followup_minutes_low: int = 1
    demo_followup_minutes_medium: int = 2
    demo_followup_minutes_high: int = 3
    demo_followup_minutes_critical: int = 4

    # --- Inter-service HTTP base URLs -----------------------------------------
    triage_agent_url: str = "http://localhost:8001"
    followup_agent_url: str = "http://localhost:8002"
    db_service_url: str = "http://localhost:8003"
    scheduler_url: str = "http://localhost:8004"

    @field_validator("*", mode="before")
    @classmethod
    def strip_padded_strings(cls, value: Any) -> Any:
        """Trim whitespace that sneaks in from hand-edited `.env` files."""
        return value.strip() if isinstance(value, str) else value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton (built on first use)."""
    return Settings()
