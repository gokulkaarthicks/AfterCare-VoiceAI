"""Triage Agent HTTP API.

Exposes:
  POST /intake                    run discharge intake (pipeline + triage tool loop)
  POST /evaluate-response         evaluate follow-up answers without waiting for a call
  GET  /patients/{id}/questions   proxy the stored questionnaire
  GET  /health

And consumes `patient_response_event` from the Follow-up Agent, running the
response chain and publishing the resulting actions.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agents.triage import SERVICE_NAME, SERVICE_PORT
from app.agents.triage.graph import intake_chain, response_chain
from app.agents.triage.pipeline.state import TriageState
from app.agents.triage.publisher import publish_actions
from app.agents.triage.schemas import (
    DischargeIntakeRequest,
    DischargeIntakeResponse,
    EvaluateResponseRequest,
    EvaluateResponseResult,
)
from app.shared.core.config import get_settings
from app.shared.core.logging import CorrelationIdMiddleware, configure_logging, get_logger
from app.shared.messaging.bus import event_bus
from app.shared.messaging.contracts import DecisionType, RiskLevel

configure_logging()
logger = get_logger(SERVICE_NAME)


# --- Shared helpers -----------------------------------------------------------


async def _fetch_chart_context(patient_id: str) -> tuple[str, str]:
    """Return (diagnosis, chart risk level) from the DB service, with safe defaults."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{settings.db_service_url}/patients/{patient_id}")
        if response.status_code != 200:
            return "Unknown", "medium"
        payload = response.json()
        diagnosis = (payload.get("discharge_summary") or {}).get("diagnosis") or "Unknown"
        return diagnosis, payload.get("risk_level") or "medium"
    except Exception:  # noqa: BLE001 - intake must not fail on a chart lookup
        logger.exception("chart_context.fetch_failed", patient_id=patient_id)
        return "Unknown", "medium"


def _response_state(
    *,
    patient_id: str,
    correlation_id: str,
    responses: list[dict[str, Any]],
    diagnosis: str,
    chart_risk: str,
) -> TriageState:
    return TriageState(
        patient_id=patient_id,
        correlation_id=correlation_id,
        patient_response={"responses": responses, "diagnosis": diagnosis},
        risk_evaluation={"risk_level": chart_risk, "reasoning": "", "risk_factors": []},
    )


async def _run_response_chain(state: TriageState) -> dict[str, Any]:
    result = await response_chain.ainvoke(state)
    await publish_actions(result.get("actions", []))
    return result


# --- RabbitMQ consumer --------------------------------------------------------


async def handle_patient_response(envelope: dict[str, Any]) -> None:
    """React to a finished voice call: analyse answers, then act."""
    payload = envelope.get("payload", {})
    patient_id = payload.get("patient_id", "")
    correlation_id = envelope.get("correlation_id") or str(uuid.uuid4())

    logger.info("patient_response.received", patient_id=patient_id, correlation_id=correlation_id)

    diagnosis, chart_risk = await _fetch_chart_context(patient_id)
    state = _response_state(
        patient_id=patient_id,
        correlation_id=correlation_id,
        responses=payload.get("responses", []),
        diagnosis=diagnosis,
        chart_risk=chart_risk,
    )

    result = await _run_response_chain(state)
    logger.info(
        "patient_response.processed",
        patient_id=patient_id,
        decision=(result.get("decision") or {}).get("decision_type"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("triage_agent.startup")
    await event_bus.connect()
    await event_bus.subscribe(
        "patient_response_event",
        handle_patient_response,
        queue_name="triage_agent_patient_response_queue",
    )
    logger.info("triage_agent.ready")
    yield
    logger.info("triage_agent.shutdown")
    await event_bus.disconnect()


# --- HTTP API -----------------------------------------------------------------


app = FastAPI(title="AfterCare · Triage Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/intake", response_model=DischargeIntakeResponse)
async def run_intake(request: DischargeIntakeRequest) -> DischargeIntakeResponse:
    """Parse a discharge summary, score risk, build questions, and act."""
    existing = (request.existing_patient_id or "").strip()
    patient_id = existing or str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    logger.info("intake.start", patient_id=patient_id, patient_name=request.patient_name)

    state = TriageState(
        raw_text=request.discharge_summary_text,
        patient_name=request.patient_name,
        patient_phone=request.patient_phone,
        patient_dob=request.patient_dob,
        patient_email=request.patient_email,
        patient_id=patient_id,
        correlation_id=correlation_id,
    )

    result = await intake_chain.ainvoke(state)
    await publish_actions(result.get("actions", []))

    risk = result.get("risk_evaluation", {})
    decision = result.get("decision", {})
    logger.info("intake.done", patient_id=patient_id, decision=decision.get("decision_type"))

    return DischargeIntakeResponse(
        patient_id=patient_id,
        risk_level=RiskLevel(risk.get("risk_level", "medium")),
        decision=DecisionType(decision.get("decision_type", "stable")),
        generated_questions=result.get("generated_questions", []),
        correlation_id=correlation_id,
    )


@app.post("/evaluate-response", response_model=EvaluateResponseResult)
async def evaluate_response(request: EvaluateResponseRequest) -> EvaluateResponseResult:
    """Evaluate follow-up answers on demand (same logic as the event consumer)."""
    correlation_id = str(uuid.uuid4())
    logger.info("evaluate_response.start", patient_id=request.patient_id)

    diagnosis, chart_risk = await _fetch_chart_context(request.patient_id)
    state = _response_state(
        patient_id=request.patient_id,
        correlation_id=correlation_id,
        responses=[item.model_dump() for item in request.responses],
        diagnosis=diagnosis,
        chart_risk=chart_risk,
    )

    result = await _run_response_chain(state)
    actions = result.get("actions", [])
    risk = result.get("risk_evaluation", {})
    decision = result.get("decision", {})

    return EvaluateResponseResult(
        patient_id=request.patient_id,
        risk_level=RiskLevel(risk.get("risk_level", "medium")),
        decision=DecisionType(decision.get("decision_type", "stable")),
        alerts=[action for action in actions if action.get("type") == "alert_event"],
        correlation_id=correlation_id,
    )


@app.get("/patients/{patient_id}/questions")
async def get_patient_questions(patient_id: str) -> Any:
    """Proxy the stored questionnaire from the DB service."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.db_service_url}/patients/{patient_id}/questionnaire"
            )
    except httpx.HTTPError as exc:
        logger.exception("questions.fetch_failed", patient_id=patient_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if response.status_code == 200:
        return response.json()
    raise HTTPException(
        status_code=response.status_code,
        detail=f"DB service returned {response.status_code}",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
