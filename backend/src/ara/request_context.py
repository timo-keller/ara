"""Correlation IDs and safe structured request logging."""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

CORRELATION_ID_HEADER = "X-Correlation-ID"
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
request_logger = logging.getLogger("ara.request")


def get_correlation_id() -> str | None:
    """Return the correlation ID for the current request, when one exists."""
    return _correlation_id.get()


def _request_correlation_id(request: Request) -> str:
    """Use a client UUID when supplied, otherwise generate a new UUID."""
    value = request.headers.get(CORRELATION_ID_HEADER)
    if value:
        try:
            return str(uuid.UUID(value))
        except ValueError:
            pass
    return str(uuid.uuid4())


async def add_request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a correlation ID and log only non-sensitive request metadata."""
    correlation_id = _request_correlation_id(request)
    request.state.correlation_id = correlation_id
    context_token = _correlation_id.set(correlation_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
    finally:
        request_logger.info(
            json.dumps(
                {
                    "event": "request_completed",
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": (
                        response.status_code if "response" in locals() else 500
                    ),
                    "duration_ms": round((time.perf_counter() - started_at) * 1_000, 2),
                },
                separators=(",", ":"),
            )
        )
        _correlation_id.reset(context_token)
