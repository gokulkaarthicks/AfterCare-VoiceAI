"""Base URLs for CLI scripts and demos.

Resolves each service from its environment variable so the same script works on
the host (localhost defaults), inside Docker Compose (container DNS names), or
behind a tunnel.
"""

from __future__ import annotations

import os


def _service_url(env_var: str, default: str) -> str:
    return (os.environ.get(env_var) or default).strip().rstrip("/")


def triage_agent_url() -> str:
    return _service_url("TRIAGE_AGENT_URL", "http://localhost:8001")


def followup_agent_url() -> str:
    return _service_url("FOLLOWUP_AGENT_URL", "http://localhost:8002")


def db_service_url() -> str:
    return _service_url("DB_SERVICE_URL", "http://localhost:8003")


def scheduler_url() -> str:
    return _service_url("SCHEDULER_URL", "http://localhost:8004")


def frontend_url() -> str:
    return _service_url("FRONTEND_URL", "http://localhost:3000")
