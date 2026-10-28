"""Chat-model access for the Triage Agent's deterministic pipeline stages."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.shared.core.llm import build_chat_model


def get_pipeline_model() -> ChatOpenAI:
    """Deterministic (temperature 0) model used for clinical extraction."""
    return build_chat_model(temperature=0, max_tokens=4096)
