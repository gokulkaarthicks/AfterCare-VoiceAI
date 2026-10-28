"""Interpret the answers collected during an outbound follow-up call."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.triage.pipeline.model import get_pipeline_model
from app.agents.triage.pipeline.state import TriageState
from app.shared.clinical.questionnaire import APPOINTMENT_CONSENT_QUESTION_ID
from app.shared.core.llm_json import load_json_object, message_text
from app.shared.core.logging import get_logger

logger = get_logger("triage_agent.analyse_responses")

ANALYSIS_SYSTEM_PROMPT = """\
You are a clinical response-analysis engine. A patient has answered post-discharge
follow-up questions. Analyze each response for clinical significance given the
patient's diagnosis.

MANDATORY CLINICAL RULES: these override all other reasoning.
- chest pain / pressure / nitroglycerin use in ANY cardiac patient = 'high'
- shortness of breath / dyspnea in post-cardiac patient = 'high'
- missed cardiac medications (aspirin, clopidogrel, beta-blockers) = 'high'
- fever > 38C / signs of infection post-surgery = 'high'
- bleeding on anticoagulants (blood in stool, urine, unusual bruising) = 'high'
- new leg/ankle swelling post-cardiac = 'medium'
- reduced energy/fatigue scale <= 5 = 'medium'
- all clear / no symptoms = 'low'

Also check the 'clinical_flags' field per response: these are pre-flagged symptoms
already detected during the call. If clinical_flags is non-empty, the concern_level
must be at least 'medium'.

Respond ONLY with valid JSON:
{
  "analysis": [
    {"question_id": "...", "concern_level": "low|medium|high",
     "interpretation": "one concise sentence"}
  ],
  "overall_concern": "low|medium|high",
  "flags": ["specific symptom detected, e.g. chest_pain, shortness_of_breath"]
}
"""


def _format_responses(responses: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"Q ({item.get('question_id', '?')}): {item.get('question_text', '?')}\n"
        f"A: {item.get('answer', 'N/A')} | normalized: {item.get('normalized', 'N/A')}"
        f" | clinical_flags: {item.get('clinical_flags', [])}"
        for item in responses
    )


def analyse_responses(state: TriageState) -> dict[str, Any]:
    """Score concern level and surface red flags from the call transcript.

    The appointment-consent answer is operational, not clinical, so it is
    excluded from the risk analysis.
    """
    patient_response = state.get("patient_response", {})
    responses = [
        item
        for item in patient_response.get("responses", [])
        if item.get("question_id") != APPOINTMENT_CONSENT_QUESTION_ID
    ]
    diagnosis = patient_response.get("diagnosis", "Unknown")

    logger.info(
        "analyse_responses.start",
        patient_id=state.get("patient_id"),
        response_count=len(responses),
    )

    user_prompt = (
        f"Patient diagnosis: {diagnosis}\n\n"
        f"Responses:\n{_format_responses(responses)}"
    )

    try:
        reply = get_pipeline_model().invoke(
            [
                SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        analysis = load_json_object(message_text(reply.content))
        analysis.setdefault("analysis", [])
        analysis.setdefault("overall_concern", "low")
        analysis.setdefault("flags", [])
    except Exception:  # noqa: BLE001 - escalate rather than silently pass
        logger.exception("analyse_responses.llm_error")
        analysis = {
            "analysis": [],
            "overall_concern": "medium",
            "flags": ["automated_analysis_failed"],
        }

    return {"response_analysis": analysis}
