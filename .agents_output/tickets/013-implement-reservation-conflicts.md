# 013 - Implement reservation conflict rules

## Goal

Implement and thoroughly test exclusive reservation interval logic.

## Scope

- Add DAO queries for bounded and open-ended interval conflicts.
- Treat a missing end as positive infinity.
- Permit exactly adjacent reservation intervals.
- Run conflict checks within the reservation write transaction.

## Acceptance Criteria

- Past, current, future, adjacent, and overlapping cases are tested.
- Open-ended reservations conflict with every later interval.
- A conflicting request produces a domain conflict, not a server error.
- Concurrent write behavior is tested within SQLite's supported model.

## Dependencies

- Ticket 005
- Ticket 012
