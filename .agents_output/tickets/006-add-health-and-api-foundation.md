# 006 - Add health and API foundation

## Goal

Establish shared REST conventions and operational health endpoints.

## Scope

- Mount API routes below `/api` and auth routes below `/auth`.
- Add correlation IDs and structured request logging.
- Add liveness and database-backed readiness endpoints.
- Add consistent validation and domain-error responses.

## Acceptance Criteria

- Liveness does not depend on the database.
- Readiness fails when the database is unavailable.
- Responses include a correlation identifier.
- Logs exclude authorization headers, cookies, and sensitive settings.

## Dependencies

- Ticket 004
