# 002 - Bootstrap backend tooling

## Goal

Create the uv-managed FastAPI project and its quality configuration.

## Scope

- Add the Python package below `backend/src/ara`.
- Configure uv dependencies and lock them.
- Configure Ruff, ty, pytest, and pytest-asyncio.
- Add a minimal application factory and test.

## Acceptance Criteria

- The application imports and starts through uv.
- Ruff formatting and linting pass.
- ty passes.
- The minimal pytest suite passes.

## Dependencies

- Ticket 001
