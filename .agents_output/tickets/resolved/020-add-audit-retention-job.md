# 020 - Add audit retention job

## Goal

Delete audit events older than the configured one-year retention period.

## Scope

- Add a daily APScheduler job for retention cleanup.
- Delete expired events in bounded batches.
- Make the retention period configurable with a 365-day default.
- Add structured cleanup metrics to logs.

## Acceptance Criteria

- Events newer than the cutoff remain untouched.
- Events older than the cutoff are removed in bounded transactions.
- Running cleanup repeatedly is safe.
- Retention deletion does not generate new audit events.

## Dependencies

- Ticket 016
- Ticket 018
