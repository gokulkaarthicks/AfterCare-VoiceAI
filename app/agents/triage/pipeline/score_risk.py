"""Post-discharge clinical risk scoring (low | medium | high | critical)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.triage.pipeline.model import get_pipeline_model
from app.agents.triage.pipeline.state import TriageState
from app.shared.core.llm_json import load_json_object, message_text
from app.shared.core.logging import get_logger

logger = get_logger("triage_agent.score_risk")

RISK_SYSTEM_PROMPT = """\
You are a clinical risk-assessment engine. Given a patient's diagnosis, procedures,
and medications, evaluate the post-discharge risk. Respond ONLY with valid JSON:
{
  "risk_level": "low|medium|high|critical",
  "reasoning": "<brief explanation>",
  "risk_factors": ["factor1", "factor2"]
}
"""

_DEFAULT_RISK: dict[str, Any] = {
    "risk_level": "medium",
    "reasoning": "",
    "risk_factors": [],
}


def score_clinical_risk(state: TriageState) -> dict[str, Any]:
    """Evaluate how closely the patient needs to be watched after discharge."""
    extracted = state.get("extracted_data", {})
    discharge = extracted.get("discharge", {})
    medications = extracted.get("medications", [])

    logger.info("score_clinical_risk.start", patient_id=state.get("patient_id"))

    user_prompt = (
        f"Diagnosis: {discharge.get('diagnosis', 'N/A')}\n"
        f"Procedures: {discharge.get('procedures', 'N/A')}\n"
        f"Medications: {json.dumps(medications)}\n"
        f"Instructions: {discharge.get('instructions', 'N/A')}"
    )

    try:
        reply = get_pipeline_model().invoke(
            [
                SystemMessage(content=RISK_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        risk = load_json_object(message_text(reply.content))
        for key, default in _DEFAULT_RISK.items():
            risk.setdefault(key, default)
    except Exception:  # noqa: BLE001 - default to the cautious tier
        logger.exception("score_clinical_risk.llm_error")
        risk = {
            "risk_level": "medium",
            "reasoning": "Unable to evaluate risk; defaulting to medium.",
            "risk_factors": [],
        }

    return {"risk_evaluation": risk}
