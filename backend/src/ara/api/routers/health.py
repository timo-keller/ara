"""Operational health HTTP endpoints."""

from fastapi import Depends, Response, status
from fastapi.responses import JSONResponse

from ara.api.routers import api_router
from ara.services.health import HealthService, get_health_service


@api_router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report process liveness without accessing dependencies."""
    return {"status": "ok"}


@api_router.get("/health/ready")
async def readiness(
    health: HealthService = Depends(get_health_service),
) -> Response:
    """Report database readiness as an HTTP response."""
    if not await health.is_ready():
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
