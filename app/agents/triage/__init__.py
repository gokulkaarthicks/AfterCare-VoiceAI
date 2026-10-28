"""Triage Agent: the clinical reasoning service.

Only two LLM-backed agents exist in AfterCare: this Triage Agent (clinical
reasoning) and the Follow-up Agent (understanding and speaking). The FastAPI
surface lives in `app.api.triage`.

Layout:
  pipeline/     deterministic LangGraph nodes (parse → extract → risk → questions,
                and response analysis)
  act/          the triage tool-calling subagent plus its tool → action mapping
  graph.py      compiled pipelines
  publisher.py  action → RabbitMQ contract translation
"""

SERVICE_NAME = "triage_agent"
SERVICE_PORT = 8001
