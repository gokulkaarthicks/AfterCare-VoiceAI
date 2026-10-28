"""Patient chart rows: discharge summaries, medications, questionnaires, call transcripts."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.common import new_id
from app.shared.core.logging import get_logger
from app.shared.database.models import (
    DischargeSummary,
    Medication,
    PatientInteraction,
    Questionnaire,
)

logger = get_logger("db_service.charts")


async def add_discharge_summary(
    session: AsyncSession, patient_id: str, discharge: dict[str, Any]
) -> DischargeSummary:
    summary = DischargeSummary(
        id=new_id(),
        patient_id=patient_id,
        diagnosis=discharge.get("diagnosis", ""),
        procedures=discharge.get("procedures"),
        discharge_date=discharge.get("discharge_date"),
        instructions=discharge.get("instructions"),
        raw_text=discharge.get("raw_text", ""),
    )
    session.add(summary)
    await session.flush()
    logger.info("discharge_summary.created", patient_id=patient_id, summary_id=summary.id)
    return summary


async def add_medications(
    session: AsyncSession, patient_id: str, medications: list[dict[str, Any]]
) -> list[Medication]:
    rows = [
        Medication(
            id=new_id(),
            patient_id=patient_id,
            name=med.get("name", ""),
            dosage=med.get("dosage", ""),
            frequency=med.get("frequency", ""),
        )
        for med in medications
    ]
    session.add_all(rows)
    await session.flush()
    logger.info("medications.created", patient_id=patient_id, count=len(rows))
    return rows


async def add_questionnaire(
    session: AsyncSession, patient_id: str, questions: list[dict[str, Any]], diagnosis: str
) -> Questionnaire:
    questionnaire = Questionnaire(
        id=new_id(),
        patient_id=patient_id,
        questions_json=json.dumps(questions),
        diagnosis_context=diagnosis,
    )
    session.add(questionnaire)
    await session.flush()
    logger.info("questionnaire.created", patient_id=patient_id, questionnaire_id=questionnaire.id)
    return questionnaire


async def add_interaction(session: AsyncSession, data: dict[str, Any]) -> PatientInteraction:
    """Store the Q&A from one finished call."""
    interaction = PatientInteraction(
        id=data.get("id") or new_id(),
        patient_id=data["patient_id"],
        interaction_type=data.get("interaction_type", "followup"),
        channel=data.get("channel", "voice"),
        questionnaire_id=data.get("questionnaire_id"),
        questions_json=data.get("questions_json"),
        responses_json=data.get("responses_json"),
        raw_transcript=data.get("raw_transcript"),
        twilio_sid=data.get("twilio_sid"),
    )
    session.add(interaction)
    await session.flush()
    logger.info("interaction.created", interaction_id=interaction.id)
    return interaction
