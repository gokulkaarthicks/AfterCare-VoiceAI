"""State schema shared by the Triage Agent's intake and post-call graphs."""

from __future__ import annotations

from typing import Any, TypedDict


class TriageState(TypedDict, total=False):
    """Accumulated state for one discharge intake or one post-call analysis.

    Each graph node returns a partial update that LangGraph merges into this
    dict, so every key is optional.
    """

    # --- Request inputs ---
    raw_text: str
    patient_name: str
    patient_phone: str
    patient_dob: str | None
    patient_email: str | None
    patient_id: str
    correlation_id: str

    # --- Intake pipeline outputs ---
    parsed_summary: dict[str, Any]
    extracted_data: dict[str, Any]
    risk_evaluation: dict[str, Any]
    generated_questions: list[dict[str, Any]]

    # --- Post-call pipeline inputs and outputs ---
    patient_response: dict[str, Any]
    response_analysis: dict[str, Any]

    # --- Care Act outputs ---
    actions: list[dict[str, Any]]
    decision: dict[str, Any]
