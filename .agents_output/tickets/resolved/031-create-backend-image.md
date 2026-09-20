# 031 - Create backend image

## Goal

Create a minimal production image for migrations and one API worker.

## Scope

- Add a multi-stage uv-based Dockerfile.
- Run Alembic migrations before application startup.
- Run one Uvicorn worker as a non-root user.
- Add container-safe shutdown and health behavior.

## Acceptance Criteria

- The image builds reproducibly from the uv lock file.
- Startup fails if migrations or required configuration fail.
- `/app/data` is writable by the runtime user.
- The image starts exactly one API process and one scheduler.

## Dependencies

- Ticket 006
- Ticket 018
