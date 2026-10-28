"""Generate condition-specific voice check-in questions."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.triage.pipeline.model import get_pipeline_model
from app.agents.triage.pipeline.state import TriageState
from app.shared.clinical.questionnaire import APPOINTMENT_CONSENT_QUESTION
from app.shared.core.llm_json import load_json_value, message_text
from app.shared.core.logging import get_logger

logger = get_logger("triage_agent.build_questionnaire")

QUESTION_SYSTEM_PROMPT = """\
You are a clinical follow-up question generator. Based on the patient's diagnosis,
procedures, and medications, generate EXACTLY 2 highly specific follow-up questions
that a nurse should ask during a post-discharge check-in. Each question must be
tailored to THIS patient's condition. Prioritise the highest-risk symptoms first.

Respond ONLY with a JSON array of exactly 2 elements (no wrapping object). Each element:
{
  "id": "q1",
  "text": "<the question>",
  "question_type": "open|yes_no|scale",
  "relevance": "<why this question matters for this patient>"
}

Examples of the specificity expected:
- Cardiac: "Have you experienced any chest tightness or shortness of breath since discharge?"
- Post-surgical: "Is there any redness, swelling, or drainage at the incision site?"
- Diabetes: "Have you been able to check your blood sugar levels regularly?"
"""

_FALLBACK_QUESTIONS = [
    {
        "id": "q1",
        "text": "How are you feeling since your discharge?",
        "question_type": "open",
        "relevance": "General wellness check",
    }
]


def _normalise(question: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": question.get("id") or f"q{index + 1}",
        "text": question.get("text", ""),
        "question_type": question.get("question_type", "open"),
        "relevance": question.get("relevance", ""),
    }


def build_questionnaire(state: TriageState) -> dict[str, Any]:
    """Create the interview script, finishing with the appointment-consent item.

    The consent question is always the last item: the Follow-up Agent uses it
    to decide whether the call continues into slot selection.
    """
    extracted = state.get("extracted_data", {})
    discharge = extracted.get("discharge", {})
    medications = extracted.get("medications", [])
    risk = state.get("risk_evaluation", {})

    logger.info("build_questionnaire.start", patient_id=state.get("patient_id"))

    user_prompt = (
        f"Diagnosis: {discharge.get('diagnosis', 'N/A')}\n"
        f"Procedures: {discharge.get('procedures', 'N/A')}\n"
        f"Medications: {json.dumps(medications)}\n"
        f"Risk level: {risk.get('risk_level', 'N/A')}\n"
        f"Risk factors: {json.dumps(risk.get('risk_factors', []))}"
    )

    try:
        reply = get_pipeline_model().invoke(
            [
                SystemMessage(content=QUESTION_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        questions = [
            _normalise(item, index)
            for index, item in enumerate(load_json_value(message_text(reply.content)))
        ]
        if not questions:
            raise ValueError("model returned no questions")
    except Exception:  # noqa: BLE001 - fall back to a safe generic script
        logger.exception("build_questionnaire.llm_error")
        questions = [dict(item) for item in _FALLBACK_QUESTIONS]

    questions.append({**APPOINTMENT_CONSENT_QUESTION})
    return {"generated_questions": questions}
