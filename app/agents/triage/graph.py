"""Compiled LangGraph workflows for the Triage Agent.

Intake chain (deterministic analysis, then Care Act actions):
    parse_summary → extract_data → risk_evaluation → questionnaire_review → act_intake

Response chain (post-call analysis, then Care Act actions):
    analyse_response → act_response

Both chains return the same `TriageState` keys (`actions`, `decision`), so
`app.agents.triage.main` publishes them through one code path.
"""

from __future__ import annotations

from langgraph.graph import StateGraph

from app.agents.triage.act.tool_agent import run_intake_act, run_response_act
from app.agents.triage.pipeline.analyse_responses import analyse_responses
from app.agents.triage.pipeline.build_questionnaire import build_questionnaire
from app.agents.triage.pipeline.extract_chart import extract_chart_data
from app.agents.triage.pipeline.parse_discharge import parse_discharge_summary
from app.agents.triage.pipeline.score_risk import score_clinical_risk
from app.agents.triage.pipeline.state import TriageState


def _build_intake_graph():
    graph = StateGraph(TriageState)
    graph.add_node("parse_summary", parse_discharge_summary)
    graph.add_node("extract_data", extract_chart_data)
    graph.add_node("risk_evaluation", score_clinical_risk)
    graph.add_node("questionnaire_review", build_questionnaire)
    graph.add_node("act_intake", run_intake_act)

    graph.set_entry_point("parse_summary")
    graph.add_edge("parse_summary", "extract_data")
    graph.add_edge("extract_data", "risk_evaluation")
    graph.add_edge("risk_evaluation", "questionnaire_review")
    graph.add_edge("questionnaire_review", "act_intake")
    graph.set_finish_point("act_intake")
    return graph.compile()


def _build_response_graph():
    graph = StateGraph(TriageState)
    graph.add_node("analyse_response", analyse_responses)
    graph.add_node("act_response", run_response_act)

    graph.set_entry_point("analyse_response")
    graph.add_edge("analyse_response", "act_response")
    graph.set_finish_point("act_response")
    return graph.compile()


intake_chain = _build_intake_graph()
response_chain = _build_response_graph()

__all__ = ["intake_chain", "response_chain"]
