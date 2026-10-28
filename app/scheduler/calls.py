"""Ask the Follow-up Agent to dial a patient."""

from __future__ import annotations

from typing import Any

import httpx

from app.shared.core.config import get_settings
from app.shared.core.logging import get_logger

logger = get_logger("scheduler.calls")


async def initiate_followup_call(
    patient_id: str,
    schedule_correlation_id: str | None = None,
) -> dict[str, Any]:
    """POST /initiate-call on the Follow-up Agent and return its response body."""
    logger.info(
        "followup_call.requested",
        patient_id=patient_id,
        schedule_correlation_id=schedule_correlation_id,
    )

    body: dict[str, Any] = {"patient_id": patient_id}
    if schedule_correlation_id:
        body["schedule_correlation_id"] = schedule_correlation_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{get_settings().followup_agent_url}/initiate-call", json=body
        )

    if response.status_code != 200:
        logger.error(
            "followup_call.request_failed",
            patient_id=patient_id,
            status_code=response.status_code,
            detail=response.text,
        )
        raise RuntimeError(
            f"Follow-up Agent returned {response.status_code}: {response.text}"
        )

    result = response.json()
    logger.info("followup_call.initiated", patient_id=patient_id, result=result)
    return result
