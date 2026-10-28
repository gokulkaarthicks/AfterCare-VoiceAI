"""Structured JSON logging with request-scoped correlation IDs.

Every service calls `configure_logging()` once at import time. HTTP requests and
event-bus messages then contribute their correlation ID automatically, so a
single discharge intake can be traced across all four services.
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def _attach_correlation_id(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor that copies the active correlation ID onto each event."""
    current = correlation_id_var.get()
    if current:
        event_dict["correlation_id"] = current
    return event_dict


def configure_logging() -> None:
    """Install the structlog pipeline used by every service process."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _attach_correlation_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound logger; pass a dotted module name for filtering."""
    return structlog.get_logger(name) if name else structlog.get_logger()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Reuse an inbound `X-Correlation-ID` (or mint one) for the whole request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
