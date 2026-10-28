"""Thin HTTP client for the DB service's patient, slot, and appointment endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from app.shared.core.config import get_settings
from app.shared.core.logging import get_logger

logger = get_logger("followup_agent.db_client")

SLOTS_OFFERED = 3


class DbServiceUnavailable(RuntimeError):
    """Raised when the DB service cannot serve a request the call depends on."""


def _base_url() -> str:
    return get_settings().db_service_url.rstrip("/")


async def fetch_patient(patient_id: str, *, client: httpx.AsyncClient) -> dict[str, Any] | None:
    response = await client.get(f"{_base_url()}/patients/{patient_id}")
    if response.status_code != 200:
        logger.warning("db.patient_fetch_failed", patient_id=patient_id, status=response.status_code)
        return None
    return response.json()


async def fetch_available_slots(
    *,
    urgency: str = "medium",
    limit: int = SLOTS_OFFERED,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    try:
        response = await client.get(
            f"{_base_url()}/doctors/availability",
            params={"urgency": urgency, "limit": limit},
        )
        if response.status_code != 200:
            logger.warning("db.slots_fetch_failed", status=response.status_code)
            return []
        return response.json()
    finally:
        if owns_client:
            await client.aclose()


async def create_pending_appointment(
    *,
    patient_id: str,
    notes: str,
    client: httpx.AsyncClient,
) -> str:
    """Create an appointment awaiting slot selection; returns its id (or "")."""
    response = await client.post(
        f"{_base_url()}/appointments",
        json={
            "patient_id": patient_id,
            "appointment_type": "followup",
            "status": "pending_confirmation",
            "notes": notes,
        },
    )
    if response.status_code not in (200, 201):
        logger.warning("db.create_appointment_failed", status=response.status_code)
        return ""
    return response.json().get("id", "")


async def confirm_appointment(
    *,
    slot_id: str,
    appointment_id: str,
    patient_id: str,
    client: httpx.AsyncClient,
) -> httpx.Response:
    """Book a slot; 200 = confirmed, 409 = slot already taken."""
    return await client.post(
        f"{_base_url()}/appointments/confirm",
        json={"slot_id": slot_id, "appointment_id": appointment_id, "patient_id": patient_id},
    )


async def mark_appointment_for_manual_scheduling(
    appointment_id: str,
    note: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Hand the appointment back to staff when automation cannot finish it."""
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=5.0)
    try:
        await client.patch(
            f"{_base_url()}/appointments/{appointment_id}",
            json={"status": "pending_manual", "notes": note},
        )
    except Exception:  # noqa: BLE001 - best effort during a live call
        logger.exception("db.mark_pending_manual_failed", appointment_id=appointment_id)
    finally:
        if owns_client:
            await client.aclose()


async def update_followup_job(
    correlation_id: str | None,
    status: str,
    *,
    executed_at: str | None = None,
    completed_at: str | None = None,
    attempts: int = 4,
) -> bool:
    """PATCH the follow-up job row, retrying briefly until the Scheduler's row appears."""
    if not (correlation_id or "").strip():
        return False

    import asyncio

    job_id = correlation_id.strip()
    url = f"{_base_url()}/followup-jobs/by-correlation/{job_id}"
    payload: dict[str, Any] = {"status": status}
    if executed_at:
        payload["executed_at"] = executed_at
    if completed_at:
        payload["completed_at"] = completed_at

    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.patch(url, json=payload)
            if response.status_code == 404:
                logger.warning("followup_job.not_found_yet", job_id=job_id, attempt=attempt + 1)
                await asyncio.sleep(0.4)
                continue
            response.raise_for_status()
            logger.info("followup_job.updated", job_id=job_id, status=status)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "followup_job.update_retry",
                job_id=job_id,
                attempt=attempt + 1,
                error=str(exc),
            )
            await asyncio.sleep(0.4)

    logger.error("followup_job.update_failed", job_id=job_id, status=status)
    return False
