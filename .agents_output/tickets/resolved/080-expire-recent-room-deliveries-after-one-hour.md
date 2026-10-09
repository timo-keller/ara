# 080 - Expire recent room deliveries after one hour

## Status

Resolved. Implemented and verified.

## Goal

Keep the recent Webex room-delivery history short by deleting completed room
delivery records after one hour instead of retaining them for 30 days.

## Scope

- Apply one-hour retention, measured from `created_at`, to room deliveries in
  terminal states (`delivered`, `failed`, and `skipped`), including test messages.
- Keep pending/sending deliveries for dispatch, retries, and restart recovery.
  Preserve records carrying an active Webex rate-limit or token cooldown until
  that cooldown expires, so cleanup cannot prematurely resume requests.
- Keep the existing 30-day retention for completed personal-message deliveries.
- Use the existing periodic cleanup and bounded batches of 100; no additional
  scheduler job or schema migration is required.
- Expired records are removed from SQLite and therefore from recent deliveries
  and status counts. No Webex messages are deleted from their destination space.
- Document the retention periods and cleanup timing.

## Acceptance Criteria

- Completed room deliveries older than one hour are deleted on cleanup.
- Room deliveries within the last hour remain visible, with the existing limit
  of 20 recent records.
- Pending/sending room deliveries and active cooldowns survive cleanup.
- Personal-message records retain their existing 30-day lifetime.
- Cleanup remains bounded and is covered by tests for state, destination,
  cutoff boundaries, cooldowns, and batching.

## Dependencies

- Ticket 035 - Add Webex delivery
- Ticket 079 - Resolve Webex space links in group administration

## Implementation and verification

- Added separate one-hour room and 30-day personal retention cutoffs to the
  existing outbox cleanup. Completed rows are deleted in oldest-first batches
  of at most 100 on the existing 15-second scheduler pass.
- Preserved pending/sending rows and active rate-limit/token cooldowns, including
  when cleanup runs with Webex disabled.
- Updated backend, deployment, and architecture documentation.
- Tests cover terminal/nonterminal states, room/personal destinations, exact
  cutoff boundaries, active cooldown expiry, status counts, disabled Webex, and
  multi-pass batching.
- Verification: all 154 backend tests passed (including 60 Webex tests), along
  with Ruff formatting/lint and ty checks.
