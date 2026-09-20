# 071 - Clamp past reservation starts to now

## Goal

Allow a current user to create a reservation when the submitted UTC start time
has passed, persisting the reservation from the server's current UTC time rather
than rejecting it. Remove the existing one-minute client-clock/request-transit
grace period.

## Scope

- Update the self-service creation path in
  `backend/src/ara/services/reservations.py` (`create_for_current_user`), which
  is used by `POST /api/reservations` in
  `backend/src/ara/api/routers/reservations.py`. Do not change the lower-level
  `ReservationService.create` helper: conflict tests use it to create
  historical fixtures and it is not exposed by an API route.
- Preserve the API schema's requirements that submitted timestamps are
  timezone-aware UTC and that a submitted bounded interval has `ends_at >
  starts_at`. Keep the `Reservation` SQLite check constraint requiring the
  persisted bounded interval to have `ends_at > starts_at`.
- Acquire the existing `BEGIN IMMEDIATE` write transaction before choosing the
  reference instant. Capture `now` once with `utc_now()` inside that
  transaction, after the lock is held, and derive one effective start:
  `max(submitted_starts_at, now)`. Use that same effective start for the
  post-clamp interval validation, availability/conflict query, constructed
  `Reservation`, API response, and creation audit snapshot. This keeps the
  persisted value and the serialized SQLite conflict decision consistent while
  avoiding a stale pre-lock clock reading.
- Do not retain a tolerance window or return
  `reservation_start_in_past` for self-service creation. A start even slightly
  before the captured reference instant is clamped; a future start is persisted
  unchanged.
- Preserve `ends_at` rather than shifting it: clamping a bounded reservation
  shortens its duration. If its unchanged end is at or before the captured
  `now`, reject it as `reservation_invalid_interval` (HTTP 400) before any
  insert/audit commit, because a positive interval cannot be persisted. An
  open-ended reservation remains open-ended from `now`.
- Run availability using the effective interval. Thus, a current/future active
  reservation conflicts with a clamped request exactly as it would with a
  request beginning at `now`; existing half-open interval and adjacency
  semantics in `ReservationDAO` remain unchanged.
- Replace the obsolete past-start rejection assertions in
  `backend/tests/test_reservations_api.py` with focused service/API coverage.
  Freeze or monkeypatch `ara.services.reservations.utc_now` rather than using
  timing-sensitive assertions. Cover a historical start with a future end
  (201 response and SQLite-loaded `starts_at` exactly equal to the fixed UTC
  `now`, unchanged end, and audit `after` snapshot), a start just before `now`
  (proving no one-minute grace behavior remains), an unchanged future start,
  an open-ended past start, and a bounded interval whose end is no longer after
  the clamped start (400/no reservation or audit event). Add a conflict case
  demonstrating that the clamped start, not the submitted historical start,
  is used for the conflict check.

## Acceptance Criteria

- `POST /api/reservations` accepts valid UTC requests whose `starts_at` is in
  the past and persists/returns a UTC `starts_at` equal to the single
  transaction-local server `now` reference; no one-minute grace rejection
  remains.
- Future starts are unchanged. For a bounded past-start request, `ends_at` is
  unchanged and the effective interval remains strictly positive; otherwise
  the request fails with `reservation_invalid_interval` and writes neither a
  reservation nor its create audit event.
- Conflict detection, the persisted row, API response, and create audit record
  all use the same clamped start. Open-ended and adjacent interval behavior is
  retained.
- UTC validation, authorization, asset/group reservability checks, SQLite
  `BEGIN IMMEDIATE` transaction behavior, and all non-self-service creation
  helper semantics remain intact.
- Backend formatting/linting and the relevant reservation and audit tests pass.

## Dependencies

- Ticket 017
