# 078 - Return expired reservations from My reservations

## Goal

Allow a user to mark their own elapsed, still-active reservation as returned
from My reservations, so an overdue reservation is represented as returned
rather than permanently remaining in the `Expired` lifecycle.

## Scope

- Change `POST /api/reservations/{reservation_id}/return` and its reservation
  service rule so the authenticated reservation owner may return an active
  reservation whose scheduled interval has elapsed: a bounded reservation with
  `ends_at <=` the one server UTC `now` captured inside the existing
  `BEGIN IMMEDIATE` write transaction. This includes the exact scheduled-end
  boundary. Keep the existing authorization checks: the caller must be the
  reservation owner and still be authorized as a user of the asset's group;
  another user's reservation remains forbidden and missing records retain the
  existing not-found behavior.
- Retain return of a currently active own reservation (`starts_at <= now` and
  no end or `ends_at > now`) exactly as it works today. Do not allow return of
  a future reservation (`starts_at > now`), including a reservation whose end
  would otherwise be in the past due to malformed historical data. Continue to
  reject returned, cancelled, and administratively ended reservations, and all
  repeated return attempts, with the established terminal/conflict response.
  Do not loosen cancellation, administrative end, extension, schedule, or
  reservation-creation rules as part of this ticket.
- On a successful elapsed return, set `status` to `returned` and set
  `returned_at` to that captured server UTC operation time. Preserve the
  original scheduled `ends_at` verbatim: it is historical schedule data and
  must not be moved forward to the return time. In particular, do not reuse the
  early-end adjustment for an elapsed reservation. The status is what removes
  it from active conflict/schedule queries; its historical interval remains
  available for list and audit views. Preserve the existing current-reservation
  early-return timestamp/end semantics.
- Continue to create exactly one `reservation.return` audit event in the same
  transaction on success, with snapshots showing the active pre-state and the
  returned post-state (including `returned_at` and the preserved scheduled
  end). Rejected requests must not alter the reservation or create an audit
  event.
- In `frontend/src/app/features/reservations/`, treat the server-derived
  `expired` lifecycle as eligible for the existing `Return asset` confirmation
  action, alongside `current`. Do not infer elapsed status from the browser
  clock or enable the action solely from `status: active`; use the server
  `lifecycle` supplied by ticket 073. On success, retain the existing reload
  behavior so the row is refreshed as the server-derived `Returned` lifecycle
  and obeys the existing lifecycle filter/pagination state. Future rows still
  offer only cancellation, terminal rows offer no return, and current rows keep
  their existing return affordance.
- Handle a stale return action safely: if the authoritative API rejects it
  because its state or authorization changed, leave no optimistic terminal UI,
  show the existing safe mutation error, and refresh the My reservations data
  when needed so unavailable actions are removed. Keep the existing confirmation
  wording and accessible button/dialog behavior; update it only if necessary to
  accurately describe returning an elapsed reservation without claiming it
  makes already-elapsed time newly available.
- Update the reservation API documentation and architecture lifecycle wording
  to state that an owner can return an active current or elapsed bounded
  reservation, while future and terminal reservations remain non-returnable.

## Acceptance Criteria

- An owner can return an active bounded reservation after its scheduled end,
  including exactly at its end, from My reservations; the refreshed row is
  labelled `Returned`, not `Expired`.
- That operation stores a UTC `returned_at` equal to the server action time,
  retains the original scheduled `ends_at`, changes status to `returned`, and
  writes one accurate `reservation.return` audit event.
- Current own reservations remain returnable; future, terminal, unauthorized,
  and repeated return requests retain their established safe rejection and do
  not create mutations or audit events.
- My reservations exposes Return asset only for server-classified `current` or
  `expired` active rows. It does not rely on the client clock or expose the
  action for future/terminal rows, and it safely reconciles a stale rejection.
- Backend formatting/linting/type checks and relevant backend tests, plus
  frontend formatting/linting/unit tests, relevant Playwright coverage, and the
  production build pass.

## Tests

- Add service/API coverage with a fixed UTC clock for an expired bounded own
  reservation, including the exact-end boundary and a later return. Assert the
  response and persisted status/timestamps, unchanged `ends_at`, exclusion from
  active scheduling/conflict behavior, and the before/after audit snapshot.
- Cover the return guard matrix: existing current bounded and open-ended
  reservations still succeed; future, returned, cancelled, ended, another
  user's, and no-longer-group-authorized reservations fail with the existing
  appropriate status/code and leave persistence/audit unchanged.
- Add reservation-page unit tests for action eligibility and labels using
  server lifecycles: `expired` presents Return asset and becomes `Returned`
  after refresh; `current` remains returnable; `future` is cancel-only; terminal
  values are actionless. Test stale return failure reconciliation without an
  optimistic status change.
- Extend the relevant Playwright My reservations flow with an elapsed active
  reservation, confirm Return asset, and verify the refreshed returned label
  and no remaining return action; retain coverage that future and terminal rows
  cannot be returned.

## Dependencies

- Ticket 073
