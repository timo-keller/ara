# 055 - Upgrade pytest-asyncio to 1.x

## Goal

Upgrade the backend test dependency to a supported pytest-asyncio 1.x release
and remove deprecation warnings caused by the older event-loop policy APIs.

## Scope

- Update the locked backend dependency from the current pytest-asyncio release
  to a compatible 1.x version using the repository's uv workflow.
- Regenerate and commit the uv lock file; do not manually edit resolved package
  versions.
- Adapt async test fixtures, markers, and pytest configuration only as required
  by pytest-asyncio 1.x.
- Confirm test collection and execution no longer emit pytest-asyncio
  event-loop-policy deprecation warnings.
- Do not combine unrelated warning cleanups from ticket 036 into this upgrade.

## Acceptance Criteria

- The backend resolves pytest-asyncio 1.x from the lock file.
- Backend test collection and execution are free of pytest-asyncio
  event-loop-policy deprecation warnings.
- Ruff formatting/linting, ty type checks, and the backend test suite pass.
- The dependency and lock-file changes are minimal and reproducible through uv.

## Dependencies

- Ticket 010
