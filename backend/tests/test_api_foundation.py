import json
import logging
import uuid

from fastapi import Query
from fastapi.testclient import TestClient

from ara.errors import DomainError
from ara.main import create_app


def test_routes_are_mounted_and_responses_have_correlation_ids() -> None:
    client = TestClient(create_app())
    supplied_id = str(uuid.uuid4())

    response = client.get("/api/health/live", headers={"X-Correlation-ID": supplied_id})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"] == supplied_id

    missing_auth_route = client.get("/auth/missing")
    assert missing_auth_route.status_code == 404
    assert missing_auth_route.headers["X-Correlation-ID"]
    assert (
        missing_auth_route.json()["correlation_id"]
        == missing_auth_route.headers["X-Correlation-ID"]
    )


def test_liveness_does_not_require_a_database(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unavailable_engine() -> None:
        raise AssertionError("liveness must not access the database")

    monkeypatch.setattr("ara.health.get_engine", unavailable_engine)

    response = TestClient(create_app()).get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_service_unavailable_when_database_is_unavailable(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    def unavailable_engine() -> None:
        raise OSError("database unavailable")

    monkeypatch.setattr("ara.health.get_engine", unavailable_engine)

    response = TestClient(create_app()).get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "service_unavailable",
        "message": "Database is unavailable",
    }
    assert response.headers["X-Correlation-ID"]


def test_validation_and_domain_errors_use_safe_consistent_responses() -> None:
    app = create_app()

    @app.get("/api/test-validation")
    async def test_validation(value: int = Query(gt=0)) -> dict[str, int]:
        return {"value": value}

    @app.get("/api/test-domain")
    async def test_domain() -> None:
        raise DomainError(
            "reservation_conflict", "The asset is already reserved", status_code=409
        )

    client = TestClient(app)
    validation = client.get("/api/test-validation?value=invalid")
    domain = client.get("/api/test-domain")

    assert validation.status_code == 422
    assert validation.json()["error"]["code"] == "validation_error"
    assert validation.json()["correlation_id"] == validation.headers["X-Correlation-ID"]
    assert domain.status_code == 409
    assert domain.json() == {
        "error": {
            "code": "reservation_conflict",
            "message": "The asset is already reserved",
        },
        "correlation_id": domain.headers["X-Correlation-ID"],
    }


def test_request_logs_exclude_sensitive_headers_and_settings(caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO, logger="ara.request")
    secret = "very-secret-value"

    response = TestClient(create_app()).get(
        "/api/health/live",
        headers={"Authorization": f"Bearer {secret}", "Cookie": f"session={secret}"},
    )

    request_logs = [
        record.message for record in caplog.records if record.name == "ara.request"
    ]
    assert len(request_logs) == 1
    assert secret not in request_logs[0]
    assert json.loads(request_logs[0]) == {
        "event": "request_completed",
        "correlation_id": response.headers["X-Correlation-ID"],
        "method": "GET",
        "path": "/api/health/live",
        "status_code": 200,
        "duration_ms": json.loads(request_logs[0])["duration_ms"],
    }
