"""Request bodies for the Follow-up Agent HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InitiateCallRequest(BaseModel):
    """Ask the service to dial a patient for their post-discharge follow-up."""

    patient_id: str
    schedule_correlation_id: str | None = Field(
        default=None,
        description="Follow-up job id to mark in_progress/completed as the call runs.",
    )


class ActiveSession(BaseModel):
    """One in-progress voice call, as shown by GET /active-sessions."""

    session_key: str
    patient_id: str | None = None
    patient_name: str | None = None
    diagnosis: str | None = None
    channel: str = "voice"
    current_index: int | None = None
    total_questions: int = 0
    call_sid: str | None = None
