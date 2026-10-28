"""Alert and activity-timeline queries."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.common import new_id, utcnow
from app.shared.core.logging import get_logger
from app.shared.database.models import Alert, Appointment, AuditLog, PatientInteraction

logger = get_logger("db_service.alerts")


async def add_alert(session: AsyncSession, data: dict[str, Any]) -> Alert:
    alert = Alert(
        id=data.get("id") or new_id(),
        patient_id=data["patient_id"],
        alert_type=data.get("alert_type", "general"),
        severity=data.get("severity", "medium"),
        message=data.get("message", ""),
        acknowledged=data.get("acknowledged", False),
    )
    session.add(alert)
    await session.flush()
    logger.info("alert.created", alert_id=alert.id, patient_id=alert.patient_id)
    return alert


async def list_alerts(
    session: AsyncSession,
    severity: str | None = None,
    acknowledged: bool | None = None,
) -> list[dict[str, Any]]:
    statement = select(Alert).options(selectinload(Alert.patient))
    if severity is not None:
        statement = statement.where(Alert.severity == severity)
    if acknowledged is not None:
        statement = statement.where(Alert.acknowledged == acknowledged)
    statement = statement.order_by(Alert.created_at.desc())

    result = await session.execute(statement)
    return [
        {
            "id": alert.id,
            "patient_id": alert.patient_id,
            "patient_name": alert.patient.name if alert.patient else None,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "acknowledged": alert.acknowledged,
            "created_at": alert.created_at,
        }
        for alert in result.scalars().all()
    ]


async def acknowledge_alert(session: AsyncSession, alert_id: str) -> Alert | None:
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        return None
    alert.acknowledged = True
    await session.flush()
    logger.info("alert.acknowledged", alert_id=alert_id)
    return alert


async def patient_timeline(session: AsyncSession, patient_id: str) -> list[dict[str, Any]]:
    """Everything that happened to a patient, newest first."""
    entries: list[dict[str, Any]] = []

    interactions = await session.execute(
        select(PatientInteraction).where(PatientInteraction.patient_id == patient_id)
    )
    for item in interactions.scalars().all():
        entries.append(
            {
                "id": item.id,
                "event_type": "interaction",
                "patient_id": item.patient_id,
                "summary": f"{item.interaction_type} via {item.channel}",
                "created_at": item.created_at,
                "details": {
                    "channel": item.channel,
                    "interaction_type": item.interaction_type,
                    "questionnaire_id": item.questionnaire_id,
                },
            }
        )

    alerts = await session.execute(select(Alert).where(Alert.patient_id == patient_id))
    for alert in alerts.scalars().all():
        entries.append(
            {
                "id": alert.id,
                "event_type": "alert",
                "patient_id": alert.patient_id,
                "summary": f"[{alert.severity}] {alert.alert_type}: {alert.message}",
                "created_at": alert.created_at,
                "details": {
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "acknowledged": alert.acknowledged,
                },
            }
        )

    appointments = await session.execute(
        select(Appointment).where(Appointment.patient_id == patient_id)
    )
    for appointment in appointments.scalars().all():
        entries.append(
            {
                "id": appointment.id,
                "event_type": "appointment",
                "patient_id": appointment.patient_id,
                "summary": f"{appointment.appointment_type}: {appointment.status}",
                "created_at": appointment.created_at,
                "details": {
                    "appointment_type": appointment.appointment_type,
                    "scheduled_at": (
                        appointment.scheduled_at.isoformat() if appointment.scheduled_at else None
                    ),
                    "status": appointment.status,
                    "notes": appointment.notes,
                },
            }
        )

    audits = await session.execute(select(AuditLog).where(AuditLog.entity_id == patient_id))
    for entry in audits.scalars().all():
        entries.append(
            {
                "id": entry.id,
                "event_type": "audit",
                "patient_id": patient_id,
                "summary": f"{entry.action} on {entry.entity_type}",
                "created_at": entry.created_at,
                "details": {
                    "entity_type": entry.entity_type,
                    "action": entry.action,
                    "changes": json.loads(entry.changes_json) if entry.changes_json else None,
                },
            }
        )

    entries.sort(key=lambda e: e["created_at"] or utcnow(), reverse=True)
    return entries
