"""Translate Care Act tool intents into event-bus action dicts.

A tool intent looks like `{"op": "schedule_voice_followup", "urgency": "high"}`.
`materialise_action` turns it into the action shape published by
`app.agents.triage.main` (patient state upsert, alert, or schedule request).
Read-only intents return `None`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.agents.triage.act.clinical_tools import READ_ONLY_OPS, followup_delay_for
from app.shared.core.logging import get_logger
from app.shared.messaging.contracts import AlertType, JobType, Severity

logger = get_logger("triage_agent.tool_dispatch")

_SEVERITY_BY_NAME: dict[str, Severity] = {
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}

_APPOINTMENT_LEAD_TIME = timedelta(days=1)


def _schedule_event(
    *,
    state: dict[str, Any],
    job_type: JobType,
    scheduled_at: datetime,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "schedule_event",
        "patient_id": state.get("patient_id", ""),
        "correlation_id": state.get("correlation_id", ""),
        "job_type": job_type.value,
        "scheduled_at": scheduled_at.isoformat(),
        "metadata": {"via": "care_act", **metadata},
    }


def materialise_action(
    intent: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any] | None:
    """Convert one tool intent into a publishable action (or None when read-only)."""
    op = intent.get("op")
    if op in READ_ONLY_OPS:
        return None

    patient_id = state.get("patient_id", "")
    correlation_id = state.get("correlation_id", "")

    if op == "save_patient_discharge":
        extracted = state.get("extracted_data") or {}
        risk = state.get("risk_evaluation") or {}
        return {
            "type": "patient_state_upsert",
            "patient_id": patient_id,
            "correlation_id": correlation_id,
            "demographics": extracted.get("demographics", {}),
            "discharge_data": extracted.get("discharge", {}),
            "medications": extracted.get("medications", []),
            "risk_level": risk.get("risk_level", "low"),
            "generated_questions": state.get("generated_questions", []),
        }

    if op == "create_clinical_alert":
        requested = str(intent.get("severity", "medium")).lower()
        severity = _SEVERITY_BY_NAME.get(requested, Severity.MEDIUM)
        return {
            "type": "alert_event",
            "patient_id": patient_id,
            "correlation_id": correlation_id,
            "alert_type": AlertType.GENERAL.value,
            "severity": severity.value,
            "message": intent.get("message") or "Clinical concern detected",
        }

    if op == "schedule_voice_followup":
        urgency = str(intent.get("urgency", "medium")).lower()
        return _schedule_event(
            state=state,
            job_type=JobType.FOLLOWUP,
            scheduled_at=datetime.now(timezone.utc) + followup_delay_for(urgency),
            metadata={
                "urgency": urgency,
                "reason": intent.get("reason", ""),
                "from_response_chain": state.get("patient_response") is not None,
            },
        )

    if op == "request_appointment":
        return _schedule_event(
            state=state,
            job_type=JobType.APPOINTMENT,
            scheduled_at=datetime.now(timezone.utc) + _APPOINTMENT_LEAD_TIME,
            metadata={
                "urgency": intent.get("urgency", "medium"),
                "reason": intent.get("reason", ""),
            },
        )

    logger.warning("materialise_action.unknown_op", op=op)
    return None


def summarise_decision(
    actions: list[dict[str, Any]], *, post_call: bool
) -> dict[str, Any]:
    """Condense the queued actions into the decision returned by the API."""
    severity_order = ["low", "medium", "high", "critical"]
    has_alert = any(action.get("type") == "alert_event" for action in actions)
    has_followup = any(
        action.get("type") == "schedule_event"
        and action.get("job_type") == JobType.FOLLOWUP.value
        for action in actions
    )
    has_appointment = any(
        action.get("type") == "schedule_event"
        and action.get("job_type") == JobType.APPOINTMENT.value
        for action in actions
    )

    highest_severity = "low"
    for action in actions:
        if action.get("type") != "alert_event":
            continue
        severity = action.get("severity", "medium")
        severity = severity if severity in severity_order else "medium"
        if severity_order.index(severity) > severity_order.index(highest_severity):
            highest_severity = severity

    if has_alert and highest_severity == "critical":
        decision_type = "escalation"
    elif has_alert:
        decision_type = "alert"
    elif has_appointment:
        decision_type = "appointment_required"
    elif has_followup:
        decision_type = "followup_needed"
    else:
        decision_type = "stable"

    # An intake that only persisted the chart still implies an initial check-in.
    persisted_only = all(
        action.get("type") == "patient_state_upsert" for action in actions
    )
    if not post_call and decision_type == "stable" and actions and persisted_only:
        decision_type = "followup_needed"

    urgency = (
        highest_severity
        if has_alert
        else "medium"
        if has_followup or has_appointment
        else "low"
    )

    tool_names: list[str] = []
    for action in actions:
        action_type = action.get("type")
        if action_type == "patient_state_upsert":
            tool_names.append("save_patient_discharge")
        elif action_type == "alert_event":
            tool_names.append("create_clinical_alert")
        elif action.get("job_type") == JobType.FOLLOWUP.value:
            tool_names.append("schedule_voice_followup")
        elif action.get("job_type") == JobType.APPOINTMENT.value:
            tool_names.append("request_appointment")

    return {
        "decision_type": decision_type,
        "urgency": urgency,
        "reasoning": f"Care Act selected: {', '.join(tool_names) or 'no actions'}",
        "via": "care_act",
    }
