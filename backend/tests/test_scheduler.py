import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from ara.domain.models import AuditEvent
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.infrastructure.scheduler import (
    AUDIT_RETENTION_JOB_ID,
    MISFIRE_GRACE_TIME_SECONDS,
    RESERVATION_REMINDER_JOB_ID,
    SCHEDULER_JOB_DEFAULTS,
    cleanup_expired_audit_events,
    create_scheduler,
    register_audit_retention_job,
    register_reservation_reminder_job,
    run_scheduled_job,
    scheduler_lifespan,
)


def test_scheduler_has_safe_job_defaults() -> None:
    scheduler = create_scheduler()

    assert scheduler._job_defaults == SCHEDULER_JOB_DEFAULTS
    assert scheduler._job_defaults["misfire_grace_time"] == MISFIRE_GRACE_TIME_SECONDS


def test_reminder_job_registration_does_not_duplicate_the_job() -> None:
    scheduler = create_scheduler()
    register_reservation_reminder_job(scheduler)
    register_reservation_reminder_job(scheduler)

    assert [job.id for job in scheduler.get_jobs()] == [RESERVATION_REMINDER_JOB_ID]


def test_audit_retention_job_registration_does_not_duplicate_the_job() -> None:
    scheduler = create_scheduler()
    register_audit_retention_job(scheduler)
    register_audit_retention_job(scheduler)

    assert [job.id for job in scheduler.get_jobs()] == [AUDIT_RETENTION_JOB_ID]


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_one_scheduler() -> None:
    app = FastAPI()

    async with scheduler_lifespan(app):
        assert app.state.scheduler.running

    assert not app.state.scheduler.running


@pytest.mark.asyncio
async def test_jobs_can_run_directly_with_an_independent_session_and_log_results(
    tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)
    messages: list[str] = []

    async def successful_job(session):  # type: ignore[no-untyped-def]
        return await session.scalar(text("SELECT 1"))

    monkeypatch.setattr(
        "ara.infrastructure.scheduler.scheduler_logger.info", messages.append
    )
    try:
        assert await run_scheduled_job("test-job", successful_job, factory) == 1
    finally:
        await engine.dispose()

    assert json.loads(messages[-1]) == {
        "event": "scheduled_job_completed",
        "job_id": "test-job",
    }


@pytest.mark.asyncio
async def test_audit_retention_logs_structured_cleanup_metrics(
    tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)
    messages: list[str] = []
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(
        "ara.core.config.get_settings",
        lambda: SimpleNamespace(audit_retention_days=1),
    )
    monkeypatch.setattr(
        "ara.infrastructure.scheduler.scheduler_logger.info", messages.append
    )
    try:
        async with factory() as session:
            session.add(
                AuditEvent(
                    action="test.event",
                    target_type="test",
                    target_id="test",
                    created_at=datetime.now(UTC) - timedelta(days=2),
                )
            )
            await session.commit()

            assert await cleanup_expired_audit_events(session) == 1
    finally:
        await engine.dispose()

    metrics = json.loads(messages[-1])
    assert metrics["event"] == "audit_retention_cleanup_completed"
    assert metrics["deleted_count"] == 1
    assert metrics["batches"] == 1
    assert datetime.fromisoformat(metrics["cutoff"]).tzinfo is UTC


@pytest.mark.asyncio
async def test_failed_job_is_logged_and_does_not_prevent_a_later_run(
    tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)
    messages: list[str] = []

    async def failing_job(session):  # type: ignore[no-untyped-def]
        await session.execute(text("SELECT 1"))
        raise RuntimeError("expected failure")

    async def successful_job(session):  # type: ignore[no-untyped-def]
        return await session.scalar(text("SELECT 2"))

    monkeypatch.setattr(
        "ara.infrastructure.scheduler.scheduler_logger.info", messages.append
    )
    monkeypatch.setattr(
        "ara.infrastructure.scheduler.scheduler_logger.exception", messages.append
    )
    try:
        with pytest.raises(RuntimeError, match="expected failure"):
            await run_scheduled_job("test-job", failing_job, factory)
        assert await run_scheduled_job("test-job", successful_job, factory) == 2
    finally:
        await engine.dispose()

    events = [json.loads(message) for message in messages]
    assert {"event": "scheduled_job_failed", "job_id": "test-job"} in events
    assert {"event": "scheduled_job_completed", "job_id": "test-job"} in events
