# 073 - Filter My reservations

## Goal

Let a user narrow My reservations by visible asset name, visible asset type,
scheduled timespan, and a clearly labelled lifecycle category, while retaining
server-side pagination, URL state, and the existing asset-visibility privacy
rules.

## Scope

- Extend `GET /api/reservations/mine`, its router query validation, service,
  DAO, and frontend service model with these optional filters:
  - `asset_name`: case-insensitive substring match on the asset name;
  - `asset_type`: exact asset type match;
  - `timespan_from` and `timespan_to`: timezone-aware UTC instants defining an
    inclusive search window; a reservation matches when its scheduled
    half-open interval overlaps that window (`starts_at <= timespan_to` and
    `ends_at IS NULL OR ends_at >= timespan_from`);
  - repeatable `lifecycle` values: `current`, `future`, `expired`, `returned`,
    `cancelled`, and `ended`. Multiple values are an OR within this filter and
    intersect with every other filter.
- Validate both timespan values as UTC using the existing reservation timestamp
  convention and reject `timespan_from > timespan_to` with the normal safe
  validation response. Capture one server UTC `now` for a list operation.
  `current` means active with `starts_at <= now` and no end or `ends_at > now`;
  `future` means active with `starts_at > now`; `expired` means active with a
  bounded `ends_at <= now`; the other three map to their terminal stored
  statuses. These categories must be mutually exclusive. Preserve the existing
  newest-first `starts_at DESC, id DESC` order and count/page query identity.
- Do not turn this endpoint into an asset-information side channel. Continue to
  return every reservation owned by the caller, but apply `asset_name` and
  `asset_type` predicates only where the asset would be visible under the exact
  existing `list_own` policy (same group membership plus archived Owner/Group
  Admin exceptions). A hidden/missing/unauthorized asset must neither expose
  its name/type nor match either asset-metadata filter. Timespan and lifecycle
  filters may still match the caller's own reservation without revealing asset
  metadata. Totals must be computed from the same privacy-aware predicate as
  the page.
- Return a server-derived `lifecycle` field on each My reservations item (and
  keep the existing stored `status` unchanged). Use it to label active future
  rows visibly as `Future`, rather than relying on a potentially skewed browser
  clock. Render a readable current/expired/terminal label as appropriate; do
  not claim that a terminal reservation is current merely because its original
  scheduled interval includes now. Keep return, cancel, and extend affordances
  governed by the existing lifecycle routes and their authoritative API checks.
- Add a compact filter area above the responsive table in
  `frontend/src/app/features/reservations/`: asset-name text input, asset-type
  input or select based only on types present in authorized response data,
  local date/time `from` and `to` controls converted to UTC, and a multi-select
  or equivalent accessible lifecycle control. Filter changes reset `offset` to
  zero; page and page-size changes retain all selected filters. Preserve all
  filters in the query string with the exact REST names above, omit defaults,
  restore valid links/back-forward state, and safely discard malformed offsets,
  limits, lifecycle values, and local date inputs. Do not expose an asset-type
  vocabulary for hidden historical assets.
- Keep the existing asset-unavailable fallback and no-detail-link behavior for
  hidden assets. An empty filtered result should say that no reservations match
  the filters and provide a clear way to remove filters, rather than claiming
  the user has never made a reservation.
- Add API/service/DAO tests spanning every category and its `now` boundaries,
  repeated lifecycle OR/intersection behavior, UTC/invalid-range validation,
  open-ended overlap, deterministic pagination/totals, and hidden archived or
  unauthorized asset metadata. Add frontend unit tests for query parse/serialize
  round trips, UTC conversion, reset/pagination preservation, labels including
  `Future`, filter controls, and unavailable rows; update the My reservations
  Playwright coverage for filtering, URL restoration, pagination, and the
  narrow responsive table.

## Acceptance Criteria

- My reservations can be filtered by asset name, asset type, timespan, and one
  or more lifecycle categories, with server-side filtered totals and stable
  pagination.
- Future active reservations visibly say `Future`; current, expired, returned,
  cancelled, and ended classifications follow one server-side UTC reference and
  boundary rules.
- Query-state links/back-forward navigation preserve valid filters and page
  size; filtering resets only the page offset and date input is converted from
  local time to UTC.
- Hidden or unauthorized asset names/types remain null and cannot be inferred
  through name/type filtering, result counts, type choices, or links.
- Existing lifecycle actions, visibility behavior, responsive table semantics,
  and API authorization are unchanged.
- Backend formatting/linting/type checks and relevant backend tests, plus
  frontend formatting/linting/unit tests, relevant Playwright tests, and the
  production build pass.

## Dependencies

- Ticket 067
- Ticket 071
