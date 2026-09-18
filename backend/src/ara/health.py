"""Operational health endpoints."""

from fastapi import Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ara.api import api_router
from ara.database import get_engine


@api_router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report that the API process is able to serve requests.

    This intentionally does not access configuration or the database.
    """
    return {"status": "ok"}


@api_router.get("/health/ready")
async def readiness() -> Response:
    """Report whether the database is reachable for application requests."""
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:  # Readiness must also fail safely for invalid DB configuration.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "service_unavailable",
                    "message": "Database is unavailable",
                }
            },
        )
    return JSONResponse(content={"status": "ok"})
