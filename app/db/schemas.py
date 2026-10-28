"""Request/response bodies for the DB service API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DoctorScheduleFollowupRequest(BaseModel):
    """A clinician scheduling a follow-up from the dashboard (Eastern time)."""

    eastern_date: str = Field(description="YYYY-MM-DD")
    eastern_time: str = Field(description="HH:MM (24h)")


class DoctorScheduleFollowupResponse(BaseModel):
    correlation_id: str
    scheduled_at: datetime


class FollowupJobStatusPatch(BaseModel):
    status: str
    executed_at: datetime | None = None
    completed_at: datetime | None = None


class CreateAppointmentRequest(BaseModel):
    patient_id: str
    appointment_type: str = "followup"
    status: str = "pending_confirmation"
    notes: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None


class ConfirmAppointmentRequest(BaseModel):
    slot_id: str
    appointment_id: str
    patient_id: str


class UpdateAppointmentRequest(BaseModel):
    status: str | None = None
    notes: str | None = None
    scheduled_at: str | None = None
    doctor_id: str | None = None
    doctor_name: str | None = None
