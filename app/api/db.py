"""DB service HTTP API: database lifecycle, event consumers, and routers."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import SERVICE_NAME, SERVICE_PORT
from app.db.routers import alerts, patients, scheduling
from app.db.seed.doctors import seed_doctors_and_slots
from app.db.seed.patients import seed_demo_patients
from app.events.handlers import (
    handle_alert_event,
    handle_patient_response_event,
    handle_patient_state_upsert,
    handle_schedule_event,
)
from app.shared.cache.redis_json import cache
from app.shared.core.logging import CorrelationIdMiddleware, configure_logging, get_logger
from app.shared.database.engine import create_all_tables
from app.shared.messaging.bus import event_bus

configure_logging()
logger = get_logger(SERVICE_NAME)

_CONSUMED_EVENTS = {
    "patient_state_upsert": handle_patient_state_upsert,
    "alert_event": handle_alert_event,
    "schedule_event": handle_schedule_event,
    "patient_response_event": handle_patient_response_event,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("db_service.starting")
    await event_bus.connect()
    await cache.connect()
    await create_all_tables()
    await seed_demo_patients()
    await seed_doctors_and_slots()

    for event_name, handler in _CONSUMED_EVENTS.items():
        await event_bus.subscribe(
            event_name, handler, queue_name=f"db_service.{event_name}"
        )

    logger.info("db_service.ready", consumers=len(_CONSUMED_EVENTS))
    yield

    await event_bus.disconnect()
    await cache.disconnect()
    logger.info("db_service.stopped")


app = FastAPI(title="AfterCare · DB Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(alerts.router)
app.include_router(scheduling.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api.db:app", host="0.0.0.0", port=SERVICE_PORT, reload=True)
