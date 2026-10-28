"""Tool definitions offered to the Care Act model.

Each tool returns a compact JSON *intent* (an `op` plus its arguments). Intents
are converted into event-bus actions by `tool_dispatch.py`, so the model itself
never talks to RabbitMQ. Read-only tools return data to the model only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from langchain_core.tools import tool

from app.shared.core.config import get_settings
from app.shared.core.logging import get_logger

logger = get_logger("triage_agent.clinical_tools")

# --- Clinical spacing between proactive check-ins -----------------------------
# Demo mode compresses hours into minutes (see DEMO_FOLLOWUP_MINUTES_* in .env).
PRODUCTION_FOLLOWUP_DELAYS: dict[str, timedelta] = {
    "low": timedelta(days=3),
    "medium": timedelta(days=1),
    "high": timedelta(hours=6),
    "critical": timedelta(hours=1),
}


def followup_delay_for(urgency: str) -> timedelta:
    """How far ahead a follow-up should be scheduled for a given urgency."""
    settings = get_settings()
    tier = urgency.lower()

    if not settings.demo_mode:
        return PRODUCTION_FOLLOWUP_DELAYS.get(tier, timedelta(days=1))

    demo_minutes = {
        "low": settings.demo_followup_minutes_low,
        "medium": settings.demo_followup_minutes_medium,
        "high": settings.demo_followup_minutes_high,
        "critical": settings.demo_followup_minutes_critical,
    }
    return timedelta(minutes=int(demo_minutes.get(tier, settings.demo_followup_minutes_medium)))


@tool
def save_patient_discharge() -> str:
    """Persist the parsed discharge chart: demographics, diagnosis, medications, risk, questions.

    Call exactly once during discharge intake, after parsing completes. Never call
    it after a voice follow-up: that would overwrite chart fields with empty
    intake state.
    """
    return json.dumps({"op": "save_patient_discharge"})


@tool
def create_clinical_alert(message: str, severity: str = "medium") -> str:
    """Raise a dashboard alert for the care team.

    Use for concerning symptoms or high/critical intake risk.
    severity: low | medium | high | critical
    message: concise clinical summary for the nurse or physician.
    """
    return json.dumps(
        {"op": "create_clinical_alert", "message": message, "severity": severity}
    )


@tool
def schedule_voice_followup(urgency: str = "medium", reason: str = "") -> str:
    """Schedule an outbound voice check-in for this patient.

    On discharge intake: normally schedule the first proactive check-in.
    After a call: schedule only when another check-in is clinically indicated;
    omit it when the patient is clearly stable.
    urgency: low | medium | high | critical (controls the delay until the call).
    """
    return json.dumps(
        {"op": "schedule_voice_followup", "urgency": urgency, "reason": reason}
    )


@tool
def request_appointment(urgency: str = "medium", reason: str = "") -> str:
    """Request a clinician appointment when voice follow-up alone is insufficient.

    Prefer schedule_voice_followup for routine monitoring. Use sparingly, when an
    in-person or clinician visit is clearly indicated beyond the call consent flow.
    """
    return json.dumps(
        {"op": "request_appointment", "urgency": urgency, "reason": reason}
    )


@tool
def get_patient_context(patient_id: str) -> str:
    """Load the current chart summary (diagnosis, risk, medications) from the DB service.

    Use during post-call reasoning when fresher chart context is needed before
    choosing an action. Read-only: it never queues an action.
    """
    settings = get_settings()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{settings.db_service_url}/patients/{patient_id}")
        if response.status_code != 200:
            return json.dumps(
                {"op": "get_patient_context", "error": f"HTTP {response.status_code}"}
            )

        patient = response.json()
        discharge = patient.get("discharge_summary") or {}
        medications = patient.get("medications") or []
        return json.dumps(
            {
                "op": "get_patient_context",
                "patient_id": patient_id,
                "name": patient.get("name"),
                "risk_level": patient.get("risk_level"),
                "status": patient.get("status"),
                "diagnosis": discharge.get("diagnosis"),
                "discharge_date": discharge.get("discharge_date"),
                "medication_count": len(medications),
                "medication_names": [
                    med["name"]
                    for med in medications[:8]
                    if isinstance(med, dict) and med.get("name")
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001 - reported back to the model
        logger.exception("get_patient_context.error", patient_id=patient_id)
        return json.dumps({"op": "get_patient_context", "error": str(exc)})


INTAKE_TOOLS = [
    save_patient_discharge,
    create_clinical_alert,
    schedule_voice_followup,
    request_appointment,
]

RESPONSE_TOOLS = [
    get_patient_context,
    create_clinical_alert,
    schedule_voice_followup,
    request_appointment,
]

TOOLS_BY_NAME = {tool_.name: tool_ for tool_ in [*INTAKE_TOOLS, get_patient_context]}

# Tools that only read data and therefore never produce an action.
READ_ONLY_OPS = frozenset({"get_patient_context"})

__all__ = [
    "INTAKE_TOOLS",
    "READ_ONLY_OPS",
    "RESPONSE_TOOLS",
    "TOOLS_BY_NAME",
    "followup_delay_for",
]
