"""Publish Care Act actions to RabbitMQ.

`app.agents.triage.act.tool_dispatch` produces plain dicts so they can be
logged and returned in API responses. This module is the only place that turns
them into typed contract events and hands them to the event bus.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.shared.core.logging import get_logger
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import (
    AlertEvent,
    AlertType,
    JobType,
    MedicationData,
    PatientStateUpsert,
    RiskLevel,
    ScheduleEvent,
    Severity,
)

logger = get_logger("triage_agent.publisher")

SOURCE_SERVICE = "triage_agent"


async def _publish(action_type: str, event: Any, correlation_id: str) -> None:
    await event_bus.publish(
        action_type,
        event,
        correlation_id=correlation_id,
        source_service=SOURCE_SERVICE,
    )


async def _publish_patient_state(action: dict[str, Any]) -> None:
    demographics = action.get("demographics", {})
    discharge = action.get("discharge_data", {})
    event = PatientStateUpsert(
        patient_id=action["patient_id"],
        correlation_id=action.get("correlation_id", ""),
        source_service=SOURCE_SERVICE,
        demographics={
            "name": demographics.get("name") or "Unknown",
            "phone": demographics.get("phone", ""),
            "dob": demographics.get("dob"),
            "email": demographics.get("email"),
        },
        discharge_data={
            "diagnosis": discharge.get("diagnosis", ""),
            "procedures": discharge.get("procedures"),
            "discharge_date": discharge.get("discharge_date"),
            "instructions": discharge.get("instructions"),
            "raw_text": discharge.get("raw_text", ""),
        },
        medications=[MedicationData(**med) for med in action.get("medications", [])],
        risk_level=RiskLevel(action.get("risk_level", "low")),
        generated_questions=action.get("generated_questions", []),
    )
    await _publish("patient_state_upsert", event, event.correlation_id)


async def _publish_alert(action: dict[str, Any]) -> None:
    event = AlertEvent(
        patient_id=action["patient_id"],
        correlation_id=action.get("correlation_id", ""),
        source_service=SOURCE_SERVICE,
        alert_type=AlertType(action.get("alert_type", "general")),
        severity=Severity(action.get("severity", "medium")),
        message=action.get("message", ""),
    )
    await _publish("alert_event", event, event.correlation_id)


async def _publish_schedule(action: dict[str, Any]) -> None:
    raw_scheduled_at = action.get("scheduled_at")
    event = ScheduleEvent(
        patient_id=action["patient_id"],
        correlation_id=action.get("correlation_id", ""),
        source_service=SOURCE_SERVICE,
        job_type=JobType(action.get("job_type", "followup")),
        scheduled_at=datetime.fromisoformat(raw_scheduled_at) if raw_scheduled_at else None,
        metadata=action.get("metadata", {}),
    )
    await _publish("schedule_event", event, event.correlation_id)


_HANDLERS = {
    "patient_state_upsert": _publish_patient_state,
    "alert_event": _publish_alert,
    "schedule_event": _publish_schedule,
}


async def publish_actions(actions: list[dict[str, Any]]) -> None:
    """Publish every Care Act action in order; unknown actions are logged and skipped."""
    for action in actions:
        action_type = action.get("type", "")
        handler = _HANDLERS.get(action_type)
        if handler is None:
            logger.warning("publisher.unknown_action", action_type=action_type)
            continue
        try:
            await handler(action)
        except Exception:  # noqa: BLE001 - one bad action must not abort the rest
            logger.exception("publisher.publish_failed", action_type=action_type)
