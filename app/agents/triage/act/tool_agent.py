"""Care Act: the ReAct (reason → call tool → observe) subagent.

Two prompts share the same loop:

* `run_intake_act`: after the deterministic intake pipeline, the agent decides
  which writes/alerts/schedules to perform for a fresh discharge.
* `run_response_act`: after a voice call, the agent decides how to react to the
  patient's answers.

The agent only produces *actions*; publishing to RabbitMQ is the caller's job.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.triage.act.clinical_tools import INTAKE_TOOLS, RESPONSE_TOOLS
from app.agents.triage.act.tool_dispatch import materialise_action, summarise_decision
from app.agents.triage.pipeline.model import get_pipeline_model
from app.agents.triage.pipeline.state import TriageState
from app.shared.core.logging import get_logger

logger = get_logger("triage_agent.tool_agent")

MAX_TOOL_TURNS = 6

_NO_TOOL_CALLS = "NO_TOOL_CALLS"

INTAKE_ACT_PROMPT = f"""\
You are Care Act, the action-taking half of an AI discharge-follow-up service.
The analytical pipeline has finished. Your job is to decide which side effects to
trigger so the patient receives the right follow-up care.

Available actions:
- save_patient_discharge: persist the parsed discharge chart (exactly once, always first).
- create_clinical_alert: raise a dashboard alert for the care team.
- schedule_voice_followup: queue an automated outbound voice check-in.
- request_appointment: request a clinician appointment.

Instructions:
1. Call save_patient_discharge exactly once.
2. Call schedule_voice_followup for the first proactive check-in (urgency mirrors risk)
   unless the risk evaluation says the patient is in stable condition and already
   scheduled.
3. Call create_clinical_alert when risk_level is high or critical.
4. Call request_appointment only if risk is critical or the summary suggests the
   patient cannot be safely monitored by phone alone.
5. When you are done, reply with the single token {_NO_TOOL_CALLS} and nothing else.
   Never invent tool names.
"""

RESPONSE_ACT_PROMPT = f"""\
You are Care Act, the action-taking half of an AI discharge-follow-up service.
A patient has just completed an automated voice call. Decide the next step.

Available actions:
- get_patient_context: read the current chart when more context is needed.
- create_clinical_alert: raise a dashboard alert for the care team.
- schedule_voice_followup: queue another automated outbound check-in.
- request_appointment: request a clinician appointment.

Instructions:
1. Combine the response analysis with the known risk level.
2. Use get_patient_context only when the analysis lacks information you need.
3. Alert on high concern: red-flag symptoms, missed critical medication, or call failure.
4. Schedule another voice follow-up when symptoms are worsening or answers were partial.
5. Request an appointment when a clinician must see the patient.
6. If the patient is stable with no concerns, take no action.
7. When you are done, reply with the single token {_NO_TOOL_CALLS} and nothing else.
"""


def _message_text(reply: AIMessage) -> str:
    content = reply.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _run_react_loop(
    *,
    messages: list[Any],
    tools: list[Any],
    state: TriageState,
) -> list[dict[str, Any]]:
    """Run the tool loop until the model stops calling tools (or hits the turn cap)."""
    model = get_pipeline_model().bind_tools(tools)
    tools_by_name = {item.name: item for item in tools}
    actions: list[dict[str, Any]] = []

    for turn in range(MAX_TOOL_TURNS):
        reply: AIMessage = model.invoke(messages)
        messages.append(reply)

        tool_calls = getattr(reply, "tool_calls", None) or []
        if not tool_calls:
            break

        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("args") or {}
            tool_impl = tools_by_name.get(name)

            if tool_impl is None:
                messages.append(
                    ToolMessage(
                        content=json.dumps({"error": f"unknown tool: {name}"}),
                        tool_call_id=call.get("id", ""),
                        name=name,
                    )
                )
                continue

            try:
                result = tool_impl.invoke(args)
            except Exception as exc:  # noqa: BLE001 - surfaced back to the model
                logger.exception("act.tool_error", tool=name)
                result = json.dumps({"error": str(exc)})

            messages.append(
                ToolMessage(
                    content=result if isinstance(result, str) else json.dumps(result),
                    tool_call_id=call.get("id", ""),
                    name=name,
                )
            )

            intent = _decode_intent(result)
            if intent is None:
                continue
            action = materialise_action(intent, state)
            if action is not None:
                actions.append(action)

        if turn == MAX_TOOL_TURNS - 1:
            logger.warning("act.turn_limit_reached", turns=MAX_TOOL_TURNS)

    return actions


def _decode_intent(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if not isinstance(result, str):
        return None
    try:
        decoded = json.loads(result)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) and decoded.get("op") else None


def _intake_context(state: TriageState) -> str:
    extracted = state.get("extracted_data", {})
    risk = state.get("risk_evaluation", {})
    questions = state.get("generated_questions", [])
    discharge = extracted.get("discharge", {})

    return json.dumps(
        {
            "patient_name": extracted.get("demographics", {}).get(
                "name", state.get("patient_name")
            ),
            "diagnosis": discharge.get("diagnosis"),
            "procedures": discharge.get("procedures"),
            "discharge_date": discharge.get("discharge_date"),
            "medication_count": len(extracted.get("medications", [])),
            "risk_level": risk.get("risk_level"),
            "risk_factors": risk.get("risk_factors", []),
            "questionnaire_items": len(questions),
        },
        indent=2,
    )


def _response_context(state: TriageState) -> str:
    patient_response = state.get("patient_response", {})
    analysis = state.get("response_analysis", {})
    risk = state.get("risk_evaluation", {})

    answers = []
    for item in patient_response.get("responses", []):
        if item.get("question_id") == "q_appt_consent":
            continue
        answers.append(
            {
                "question": item.get("question_text"),
                "answer": item.get("answer"),
                "normalized": item.get("normalized"),
                "clinical_flags": item.get("clinical_flags", []),
            }
        )

    return json.dumps(
        {
            "diagnosis": patient_response.get("diagnosis"),
            "chart_risk_level": risk.get("risk_level", "medium"),
            "call_metadata": patient_response.get("call_metadata", {}),
            "answers": answers,
            "concern_analysis": analysis,
        },
        indent=2,
    )


def _fallback_actions(*, state: TriageState, post_call: bool) -> list[dict[str, Any]]:
    """Deterministic safety net when the model produces nothing usable."""
    risk_level = str(state.get("risk_evaluation", {}).get("risk_level", "medium")).lower()
    actions: list[dict[str, Any]] = []

    if not post_call:
        actions.append(
            materialise_action({"op": "save_patient_discharge"}, state)  # type: ignore[arg-type]
        )
        actions.append(
            materialise_action(
                {
                    "op": "schedule_voice_followup",
                    "urgency": risk_level,
                    "reason": "default first check-in",
                },
                state,
            )  # type: ignore[arg-type]
        )
        if risk_level in {"high", "critical"}:
            actions.append(
                materialise_action(
                    {
                        "op": "create_clinical_alert",
                        "message": f"Intake risk level: {risk_level}",
                        "severity": risk_level,
                    },
                    state,
                )  # type: ignore[arg-type]
            )
    else:
        concern = str(
            state.get("response_analysis", {}).get("overall_concern", "medium")
        ).lower()
        if concern == "high" or risk_level in {"high", "critical"}:
            actions.append(
                materialise_action(
                    {
                        "op": "create_clinical_alert",
                        "message": "Post-call concern detected by response analysis",
                        "severity": "high",
                    },
                    state,
                )  # type: ignore[arg-type]
            )
        actions.append(
            materialise_action(
                {
                    "op": "schedule_voice_followup",
                    "urgency": "medium",
                    "reason": "default follow-up after call",
                },
                state,
            )  # type: ignore[arg-type]
        )
        actions.append(
            materialise_action(
                {
                    "op": "request_appointment",
                    "urgency": "medium",
                    "reason": "default clinician review after call",
                },
                state,
            )  # type: ignore[arg-type]
        )

    return [action for action in actions if action is not None]


def run_intake_act(state: TriageState) -> dict[str, Any]:
    """LangGraph node: decide and materialise intake actions."""
    messages = [
        SystemMessage(content=INTAKE_ACT_PROMPT),
        HumanMessage(content=_intake_context(state)),
    ]

    try:
        actions = _run_react_loop(messages=messages, tools=INTAKE_TOOLS, state=state)
    except Exception:  # noqa: BLE001 - never drop a discharge silently
        logger.exception("act.intake_llm_error")
        actions = []

    if not actions:
        actions = _fallback_actions(state=state, post_call=False)

    decision = summarise_decision(actions, post_call=False)
    logger.info(
        "act.intake_done",
        patient_id=state.get("patient_id"),
        action_count=len(actions),
        decision=decision["decision_type"],
    )
    return {"actions": actions, "decision": decision}


def run_response_act(state: TriageState) -> dict[str, Any]:
    """LangGraph node: decide and materialise post-call actions."""
    messages = [
        SystemMessage(content=RESPONSE_ACT_PROMPT),
        HumanMessage(content=_response_context(state)),
    ]

    try:
        actions = _run_react_loop(messages=messages, tools=RESPONSE_TOOLS, state=state)
    except Exception:  # noqa: BLE001
        logger.exception("act.response_llm_error")
        actions = []

    if not actions:
        actions = _fallback_actions(state=state, post_call=True)

    decision = summarise_decision(actions, post_call=True)
    logger.info(
        "act.response_done",
        patient_id=state.get("patient_id"),
        action_count=len(actions),
        decision=decision["decision_type"],
    )
    return {"actions": actions, "decision": decision}
