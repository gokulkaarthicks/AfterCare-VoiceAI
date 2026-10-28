"""Request/response bodies for the Triage Agent HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.shared.messaging.contracts import DecisionType, ResponseItem, RiskLevel


class DischargeIntakeRequest(BaseModel):
    """A discharge summary to parse, plus the patient details known upfront."""

    patient_name: str
    patient_phone: str
    discharge_summary_text: str
    patient_dob: str | None = None
    patient_email: str | None = None
    existing_patient_id: str | None = Field(
        default=None,
        description="Re-run intake for an existing patient instead of creating a new one.",
    )


class DischargeIntakeResponse(BaseModel):
    """Outcome of one discharge intake run."""

    patient_id: str
    risk_level: RiskLevel
    decision: DecisionType
    generated_questions: list[dict] = []
    correlation_id: str


class EvaluateResponseRequest(BaseModel):
    """Post-call answers to evaluate outside of the RabbitMQ flow."""

    patient_id: str
    responses: list[ResponseItem]


class EvaluateResponseResult(BaseModel):
    """Decision and alerts produced for a batch of follow-up answers."""

    patient_id: str
    risk_level: RiskLevel
    decision: DecisionType
    alerts: list[dict] = []
    correlation_id: str
