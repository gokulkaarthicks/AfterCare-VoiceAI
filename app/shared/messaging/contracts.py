"""Pydantic event contracts for the AfterCare event bus.

Routing keys are identical to event names. The full flow is documented in the
project README; the short version is:

    patient_state_upsert / alert_event / schedule_event   -> DB service
    schedule_event                                        -> Scheduler
    patient_response_event                                -> Triage Agent, DB service
    appointment_booking_request                           -> Follow-up Agent
    patient_record_updated / appointment_confirmed        -> dashboard refreshers
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class BaseEvent(BaseModel):
    """Envelope shared by every published event."""

    correlation_id: str = Field(default_factory=_new_id)
    event_type: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)
    source_service: str = "unknown"


class RiskLevel(str, Enum):
    """Post-discharge clinical risk tiers (lowest to highest)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    """Alert severity shown on the care-team dashboard."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    FEVER = "fever"
    CHEST_PAIN = "chest_pain"
    MISSED_MEDS = "missed_meds"
    DIZZINESS = "dizziness"
    GENERAL = "general"


class JobType(str, Enum):
    """What the Scheduler should do when a schedule event fires."""

    FOLLOWUP = "followup"
    APPOINTMENT = "appointment"


class DecisionType(str, Enum):
    """Summary of what the Care Act agent chose to do."""

    STABLE = "stable"
    FOLLOWUP_NEEDED = "followup_needed"
    ALERT = "alert"
    ESCALATION = "escalation"
    APPOINTMENT_REQUIRED = "appointment_required"


class QuestionItem(BaseModel):
    """One voice follow-up question generated for a patient."""

    id: str
    text: str
    question_type: str = "open"  # open | yes_no | scale | appointment_consent
    relevance: str = ""


class ResponseItem(BaseModel):
    """One answered question, already interpreted by the Follow-up Agent."""

    question_id: str
    question_text: str
    answer: str
    normalized: str | None = None
    clinical_flags: list[str] = []


class DemographicsData(BaseModel):
    name: str
    dob: str | None = None
    phone: str
    email: str | None = None


class DischargeData(BaseModel):
    diagnosis: str
    procedures: str | None = None
    discharge_date: str | None = None
    instructions: str | None = None
    raw_text: str = ""


class MedicationData(BaseModel):
    name: str
    dosage: str
    frequency: str


class PatientStateUpsert(BaseEvent):
    """Persist a parsed discharge: demographics, chart data, risk, questionnaire."""

    event_type: str = "patient_state_upsert"
    patient_id: str
    demographics: DemographicsData
    discharge_data: DischargeData
    medications: list[MedicationData] = []
    risk_level: RiskLevel = RiskLevel.LOW
    generated_questions: list[QuestionItem] = []


class PatientResponseEvent(BaseEvent):
    """A completed voice check-in, published after both calls finish."""

    event_type: str = "patient_response_event"
    patient_id: str
    interaction_id: str = Field(default_factory=_new_id)
    questionnaire_id: str | None = None
    responses: list[ResponseItem] = []
    channel: str = "voice"
    twilio_sid: str | None = None


class AlertEvent(BaseEvent):
    """Raise a dashboard alert for the care team."""

    event_type: str = "alert_event"
    patient_id: str
    alert_type: AlertType = AlertType.GENERAL
    severity: Severity = Severity.MEDIUM
    message: str = ""


class ScheduleEvent(BaseEvent):
    """Ask the Scheduler to arm a follow-up call or an appointment record."""

    event_type: str = "schedule_event"
    patient_id: str
    job_type: JobType = JobType.FOLLOWUP
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = {}


class PatientRecordUpdated(BaseEvent):
    """Dashboard invalidation hint emitted by the DB service."""

    event_type: str = "patient_record_updated"
    patient_id: str
    updated_fields: list[str] = []


class AppointmentBookingRequest(BaseEvent):
    """Ask the Follow-up Agent to run an automated booking call."""

    event_type: str = "appointment_booking_request"
    patient_id: str
    urgency: str = "medium"
    reason: str = ""


class AppointmentConfirmed(BaseEvent):
    """An appointment slot was locked in for a patient."""

    event_type: str = "appointment_confirmed"
    patient_id: str
    appointment_id: str
    scheduled_at: datetime
    doctor_name: str
