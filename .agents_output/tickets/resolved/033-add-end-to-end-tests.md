# 033 - Add critical end-to-end tests

## Goal

Verify the highest-risk workflows across browser, API, and database boundaries.

## Scope

- Test authenticated asset discovery and reservation.
- Test future and open-ended reservation conflicts.
- Test extension, cancellation, and return.
- Test Group Admin scope and audit visibility.

## Acceptance Criteria

- Tests run against an isolated migrated database.
- OIDC behavior uses a deterministic test provider or fixture.
- Authorization failures and successful workflows are both covered.
- The suite can run in CI without production credentials.

## Dependencies

- Ticket 025
- Ticket 026
- Ticket 027
- Ticket 028
- Ticket 029
