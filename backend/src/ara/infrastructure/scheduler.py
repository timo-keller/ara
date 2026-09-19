"""Async scheduler lifecycle and request-independent job execution."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.infrastructure.database import get_session_factory

MISFIRE_GRACE_TIME_SECONDS = 60
SCHEDULER_JOB_DEFAULTS = {
    "coalesce": True,
    "max_instances": 1,
    "misfire_grace_time": MISFIRE_GRACE_TIME_SECONDS,
}

scheduler_logger = logging.getLogger("ara.scheduler")


def create_scheduler() -> AsyncIOScheduler:
    """Create the one in-process asyncio scheduler for an application process."""
    return AsyncIOScheduler(job_defaults=SCHEDULER_JOB_DEFAULTS)


async def run_scheduled_job[JobResult](
    job_id: str,
    job: Callable[[AsyncSession], Awaitable[JobResult]],
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> JobResult:
    """Run a job with its own session and log its result without request context.

    Exceptions are logged and propagated so APScheduler can account for failed
    executions; its scheduler remains available for the job's next run.
    """
    factory = session_factory or get_session_factory()
    try:
        async with factory() as session:
            result = await job(session)
    except Exception:
        scheduler_logger.exception(
            json.dumps({"event": "scheduled_job_failed", "job_id": job_id})
        )
        raise

    scheduler_logger.info(
        json.dumps({"event": "scheduled_job_completed", "job_id": job_id})
    )
    return result


@asynccontextmanager
async def scheduler_lifespan(app: FastAPI):
    """Start one scheduler for this app process and stop it gracefully."""
    scheduler = create_scheduler()
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=True)
        # AsyncIOScheduler schedules its shutdown callback on the event loop.
        await asyncio.sleep(0)
