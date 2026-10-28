"""SQLAlchemy 2.0 ORM models for the AfterCare clinical chart store.

The DB service is the only writer; every other service talks to it over HTTP or
the event bus. Relationships cascade from `Patient` so a chart can be dropped as
a single unit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base shared with Alembic autogenerate."""


class Patient(Base):
    """A discharged patient under automated follow-up."""

    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(255))
    dob: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active")
    risk_level: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    discharge_summaries: Mapped[list[DischargeSummary]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    medications: Mapped[list[Medication]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    questionnaires: Mapped[list[Questionnaire]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    interactions: Mapped[list[PatientInteraction]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    followup_jobs: Mapped[list[FollowupJob]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class DischargeSummary(Base):
    """Parsed (and raw) discharge note for one admission."""

    __tablename__ = "discharge_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    diagnosis: Mapped[str] = mapped_column(Text)
    procedures: Mapped[str | None] = mapped_column(Text)
    discharge_date: Mapped[str | None] = mapped_column(String(20))
    instructions: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="discharge_summaries")


class Medication(Base):
    """A discharge medication with its dosing schedule."""

    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    name: Mapped[str] = mapped_column(String(255))
    dosage: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="medications")


class Questionnaire(Base):
    """Generated voice check-in questions, stored as JSON."""

    __tablename__ = "questionnaires"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    questions_json: Mapped[str] = mapped_column(Text, default="[]")
    diagnosis_context: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="questionnaires")


class PatientInteraction(Base):
    """A completed follow-up attempt with its question/answer transcript."""

    __tablename__ = "patient_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    interaction_type: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str] = mapped_column(String(20), default="voice")
    questionnaire_id: Mapped[str | None] = mapped_column(String(36))
    questions_json: Mapped[str | None] = mapped_column(Text)
    responses_json: Mapped[str | None] = mapped_column(Text)
    raw_transcript: Mapped[str | None] = mapped_column(Text)
    twilio_sid: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="interactions")


class Alert(Base):
    """Clinical alert awaiting care-team acknowledgement."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    alert_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="alerts")


class Appointment(Base):
    """A clinician visit created by the voice booking flow or a doctor."""

    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    appointment_type: Mapped[str] = mapped_column(String(50))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text)
    doctor_id: Mapped[str | None] = mapped_column(String(36))
    doctor_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="appointments")


class FollowupJob(Base):
    """Dashboard-visible record of a scheduled follow-up call."""

    __tablename__ = "followup_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    job_type: Mapped[str] = mapped_column(String(50))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="followup_jobs")


class AuditLog(Base):
    """Append-only trail of chart mutations, correlated to the originating event."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(50))
    changes_json: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Doctor(Base):
    """Clinician available for follow-up appointments."""

    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    specialty: Mapped[str] = mapped_column(String(255), default="General Practice")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class DoctorSchedule(Base):
    """A bookable one-hour slot in a clinician's calendar."""

    __tablename__ = "doctor_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    doctor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slot_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available")
    patient_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class EventStore(Base):
    """Raw inbound events, deduplicated by (event_type, correlation_id)."""

    __tablename__ = "event_store"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    event_type: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[str] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(36))
    source_service: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
