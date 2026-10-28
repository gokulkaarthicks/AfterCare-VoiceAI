"""Discharge-note parsing: one LLM call returning structured chart fields."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.triage.pipeline.model import get_pipeline_model
from app.agents.triage.pipeline.state import TriageState
from app.shared.core.llm_json import load_json_object, load_json_value, message_text
from app.shared.core.logging import get_logger

logger = get_logger("triage_agent.parse_discharge")

PARSE_SYSTEM_PROMPT = """\
You are a clinical NLP system. Parse the following hospital discharge summary and
extract structured information. Respond ONLY with valid JSON (no markdown fences,
no commentary). Use this exact schema:
{
  "diagnosis": "<primary diagnosis>",
  "procedures": "<procedures performed, or null>",
  "medications": [{"name": "...", "dosage": "...", "frequency": "..."}],
  "discharge_date": "<YYYY-MM-DD or null>",
  "instructions": "<discharge instructions>",
  "demographics": {"name": "<if found or null>", "dob": "<if found or null>",
                   "phone": "<if found or null>", "email": "<if found or null>"}
}
"""


def _fallback_summary(raw_text: str) -> dict[str, Any]:
    """Keep the pipeline alive when the model is unavailable."""
    return {
        "diagnosis": "Unable to parse",
        "procedures": None,
        "medications": [],
        "discharge_date": None,
        "instructions": raw_text[:500],
        "demographics": {},
    }


def parse_discharge_summary(state: TriageState) -> dict[str, Any]:
    """Extract diagnosis, procedures, medications, and instructions from the note."""
    raw_text = state.get("raw_text", "")
    logger.info("parse_discharge_summary.start", patient_id=state.get("patient_id"))

    try:
        reply = get_pipeline_model().invoke(
            [
                SystemMessage(content=PARSE_SYSTEM_PROMPT),
                HumanMessage(content=raw_text),
            ]
        )
        summary = load_json_object(message_text(reply.content))
    except Exception:  # noqa: BLE001 - a failed parse must not drop the intake
        logger.exception("parse_discharge_summary.llm_error")
        summary = _fallback_summary(raw_text)

    return {"parsed_summary": summary}
