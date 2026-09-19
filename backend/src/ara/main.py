"""FastAPI application entry point."""

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ara.api.routers import api_router, auth_router
from ara.core.errors import DomainError
from ara.core.request_context import add_request_context, get_correlation_id
from ara.infrastructure.scheduler import scheduler_lifespan


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    """Create the common, safe error representation."""
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "correlation_id": get_correlation_id()},
    )


def create_app() -> FastAPI:
    """Create the ARA API application."""
    app = FastAPI(title="ARA", lifespan=scheduler_lifespan)
    app.middleware("http")(add_request_context)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request, error: DomainError) -> JSONResponse:
        return _error_response(
            error.status_code, error.code, error.message, error.details
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request, error: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "location": list(item["loc"]),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        return _error_response(
            422, "validation_error", "Request validation failed", details
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request, error: StarletteHTTPException
    ) -> JSONResponse:
        message = error.detail if isinstance(error.detail, str) else "Request failed"
        return _error_response(error.status_code, "http_error", message)

    @app.get("/")
    async def index() -> dict[str, str]:
        return {"message": "ARA API"}

    # Importing routers registers their routes on the shared router instances.
    import ara.api.routers.assets  # noqa: F401
    import ara.api.routers.audit  # noqa: F401
    import ara.api.routers.auth  # noqa: F401
    import ara.api.routers.groups  # noqa: F401
    import ara.api.routers.health  # noqa: F401
    import ara.api.routers.reservations  # noqa: F401
    import ara.api.routers.role_mappings  # noqa: F401

    app.include_router(api_router)
    app.include_router(auth_router)

    return app


app = create_app()


def run() -> None:
    """Run the development server."""
    uvicorn.run("ara.main:app", host="127.0.0.1", port=8000)
