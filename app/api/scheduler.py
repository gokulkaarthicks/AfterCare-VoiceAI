"""Scheduler HTTP API: APScheduler driven by `schedule_event` messages."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.scheduler import SERVICE_NAME, SERVICE_PORT
from app.scheduler.calls import initiate_followup_call
from app.shared.core.config import get_settings
from app.shared.core.logging import CorrelationIdMiddleware, configure_logging, get_logger
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import JobType, ScheduleEvent

configure_logging()
logger = get_logger(SERVICE_NAME)

# A generous misfire grace keeps brief event-loop stalls (GC, Docker scheduling)
# from discarding a due follow-up.
scheduler = AsyncIOScheduler(job_defaults={"misfire_grace_time": 600, "coalesce": True})

FALLBACK_DELAY = timedelta(hours=24)


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _demo_run_date(event: ScheduleEvent) -> datetime:
    """Demo mode: honour the Triage Agent's time, but never schedule in the past."""
    now = datetime.now(timezone.utc)
    if event.scheduled_at is None:
        delay = max(60, int(get_settings().demo_followup_delay_seconds))
        return now + timedelta(seconds=delay)

    run_date = _as_utc(event.scheduled_at)
    return now + timedelta(seconds=60) if run_date <= now else run_date


async def handle_schedule_event(envelope: dict[str, Any]) -> None:
    """Add (or ignore) an outbound call job for a schedule event."""
    try:
        event = ScheduleEvent(**envelope.get("payload", {}))
    except ValidationError:
        logger.exception("schedule_event.invalid")
        return

    correlation_id = str(envelope.get("correlation_id") or "").strip()
    logger.info(
        "schedule_event.received",
        patient_id=event.patient_id,
        job_type=event.job_type,
        scheduled_at=str(event.scheduled_at),
        correlation_id=correlation_id or None,
    )

    if event.job_type == JobType.APPOINTMENT:
        # Appointment calls are placed by the Follow-up Agent itself; the
        # scheduler only handles voice follow-ups.
        logger.info("schedule_event.appointment_ignored", patient_id=event.patient_id)
        return

    settings = get_settings()
    if settings.demo_mode and not event.metadata.get("from_response_chain", False):
        run_date = _demo_run_date(event)
    else:
        run_date = _as_utc(event.scheduled_at) if event.scheduled_at else (
            datetime.now(timezone.utc) + FALLBACK_DELAY
        )

    scheduler.add_job(
        initiate_followup_call,
        trigger=DateTrigger(run_date=run_date),
        kwargs={
            "patient_id": event.patient_id,
            "schedule_correlation_id": correlation_id or None,
        },
        id=f"followup_{event.patient_id}_{correlation_id or run_date.isoformat()}",
        replace_existing=False,
        name=f"Follow-up call for {event.patient_id}",
    )
    logger.info(
        "followup_call.scheduled",
        patient_id=event.patient_id,
        run_date=run_date.isoformat(),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("scheduler.starting", port=SERVICE_PORT)
    await event_bus.connect()
    await event_bus.subscribe(
        "schedule_event", handle_schedule_event, queue_name="scheduler.schedule_event"
    )
    scheduler.start()
    logger.info("scheduler.ready")
    yield
    scheduler.shutdown(wait=False)
    await event_bus.disconnect()
    logger.info("scheduler.stopped")


app = FastAPI(title="AfterCare · Scheduler", version="0.1.0", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)


@app.get("/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]


@app.post("/trigger/{patient_id}")
async def trigger_now(patient_id: str) -> dict[str, Any]:
    """Call a patient immediately, cancelling any pending scheduled job for them."""
    for job in scheduler.get_jobs():
        if patient_id in job.id:
            scheduler.remove_job(job.id)
            logger.info("followup_call.pending_cancelled", job_id=job.id, patient_id=patient_id)

    try:
        call = await initiate_followup_call(patient_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("followup_call.manual_trigger_failed", patient_id=patient_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "triggered", "patient_id": patient_id, "call": call}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": SERVICE_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
