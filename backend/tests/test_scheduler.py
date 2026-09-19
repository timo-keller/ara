import json

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from ara.infrastructure.database import create_engine, create_session_factory
from ara.infrastructure.scheduler import (
    MISFIRE_GRACE_TIME_SECONDS,
    SCHEDULER_JOB_DEFAULTS,
    create_scheduler,
    run_scheduled_job,
    scheduler_lifespan,
)


def test_scheduler_has_safe_job_defaults() -> None:
    scheduler = create_scheduler()

    assert scheduler._job_defaults == SCHEDULER_JOB_DEFAULTS
    assert scheduler._job_defaults["misfire_grace_time"] == MISFIRE_GRACE_TIME_SECONDS


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
