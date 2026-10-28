"""Questionnaire fragments reused by intake, storage, and the voice flow.

The appointment-consent item is appended to every questionnaire: when the patient
says "yes" the outbound call continues straight into slot selection.
"""

from __future__ import annotations

from typing import Any

APPOINTMENT_CONSENT_QUESTION_ID = "q_appt_consent"

APPOINTMENT_CONSENT_QUESTION: dict[str, Any] = {
    "id": APPOINTMENT_CONSENT_QUESTION_ID,
    "text": (
        "Based on how you're feeling, would you like to schedule an "
        "in-person appointment with your doctor?"
    ),
    "question_type": "appointment_consent",
    "relevance": "Patient consent for appointment scheduling",
}


def ensure_appointment_consent(questions: Any) -> tuple[list[Any], bool]:
    """Append the consent question when a stored questionnaire is missing it.

    Returns:
        (normalised_questions, inserted): `inserted` is True when a row was added.
        Non-list input yields `([], False)`.
    """
    if not isinstance(questions, list):
        return [], False
    if any(
        isinstance(item, dict) and item.get("id") == APPOINTMENT_CONSENT_QUESTION_ID
        for item in questions
    ):
        return questions, False
    return [*questions, {**APPOINTMENT_CONSENT_QUESTION}], True
