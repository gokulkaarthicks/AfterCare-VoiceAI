"""Chat-model factory for every LLM call in AfterCare.

Only two services reason with an LLM: the Triage Agent (clinical pipeline and
Care Act tool loop) and the Follow-up Agent (speech interpretation). Both
obtain their client here so provider, model, and credentials stay in one place.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.shared.core.config import get_settings


def build_chat_model(
    *,
    temperature: float = 0,
    max_tokens: int = 4096,
    timeout: float | None = None,
) -> ChatOpenAI:
    """Build an OpenRouter-backed chat model for the given generation limits."""
    settings = get_settings()
    options: dict = {
        "model": settings.openrouter_model,
        "api_key": settings.openrouter_api_key,
        "base_url": settings.openrouter_base_url,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if timeout is not None:
        options["timeout"] = timeout
    return ChatOpenAI(**options)
