# 018 - Integrate APScheduler

## Goal

Run periodic application maintenance safely in the FastAPI process.

## Scope

- Start and stop AsyncIOScheduler through the FastAPI lifespan.
- Configure coalescing, one instance per job, and misfire grace time.
- Provide request-independent async database sessions to jobs.
- Add observable job success and failure logging.

## Acceptance Criteria

- Exactly one scheduler starts in the supported one-worker deployment.
- Shutdown waits for or safely stops scheduler work.
- One failing run does not stop subsequent scheduled runs.
- Tests can run job functions directly without waiting for timers.

## Dependencies

- Ticket 006
