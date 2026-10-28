"""Insert the fictional demo patients the dashboard and scripts rely on."""

from __future__ import annotations

import json
import os

from sqlalchemy import select

from app.db.repositories.common import utcnow
from app.shared.core.logging import get_logger
from app.shared.database.engine import get_session_factory
from app.shared.database.models import (
    Appointment,
    DischargeSummary,
    Medication,
    Patient,
    Questionnaire,
)
from app.shared.fixtures.patients import DEMO_PATIENTS

logger = get_logger("db_service.seed.patients")


def _disabled() -> bool:
    return os.getenv("SKIP_DEMO_SEED", "").strip().lower() in ("1", "true", "yes")


async def seed_demo_patients() -> None:
    if _disabled():
        logger.info("demo_patients.skipped", reason="SKIP_DEMO_SEED")
        return

    async with get_session_factory()() as session:
        async with session.begin():
            first_id = DEMO_PATIENTS[0]["id"]
            existing = await session.execute(select(Patient.id).where(Patient.id == first_id))
            if existing.scalar_one_or_none() is not None:
                logger.info("demo_patients.skipped", reason="already_present")
                return

            for spec in DEMO_PATIENTS:
                patient_id = spec["id"]
                session.add(
                    Patient(
                        id=patient_id,
                        name=spec["name"],
                        dob=spec.get("dob"),
                        phone=spec["phone"],
                        email=spec.get("email"),
                        status=spec["status"],
                        risk_level=spec.get("risk_level"),
                    )
                )

                discharge = spec["discharge_summary"]
                session.add(
                    DischargeSummary(
                        id=f"{patient_id}-ds",
                        patient_id=patient_id,
                        diagnosis=discharge["diagnosis"],
                        procedures=discharge.get("procedures"),
                        discharge_date=discharge.get("discharge_date"),
                        instructions=discharge.get("instructions"),
                        raw_text=discharge.get("raw_text", ""),
                    )
                )

                for index, med in enumerate(spec.get("medications", [])):
                    session.add(
                        Medication(
                            id=f"{patient_id}-med-{index}",
                            patient_id=patient_id,
                            name=med["name"],
                            dosage=med["dosage"],
                            frequency=med["frequency"],
                        )
                    )

                questionnaire = spec.get("questionnaire")
                if questionnaire:
                    session.add(
                        Questionnaire(
                            id=f"{patient_id}-q",
                            patient_id=patient_id,
                            questions_json=json.dumps(questionnaire["questions"]),
                            diagnosis_context=questionnaire.get("diagnosis_context", ""),
                        )
                    )

                for index, appointment in enumerate(spec.get("appointments", [])):
                    session.add(
                        Appointment(
                            id=f"{patient_id}-appt-{index}",
                            patient_id=patient_id,
                            appointment_type=appointment["appointment_type"],
                            scheduled_at=appointment.get("scheduled_at"),
                            status=appointment.get("status", "scheduled"),
                            notes=appointment.get("notes"),
                            doctor_id=appointment.get("doctor_id"),
                            doctor_name=appointment.get("doctor_name"),
                            created_at=utcnow(),
                        )
                    )

            logger.info("demo_patients.seeded", patients=len(DEMO_PATIENTS))
