# 063 - Show and search audit entity names

## Goal

Make Audit history readable by displaying actor and target names alongside their
UUIDs, and allow actor/target search to match either representation.

## Scope

- Extend authorized audit-event API responses with safe actor and target display
  names, resolved without frontend N+1 requests. Render populated values as
  `<Name> (<uuid>)` for both Actor and Target.
- Resolve target names for every recorded target type (asset, group,
  reservation, and role mapping) using a meaningful authorized display label.
  For a reservation, use its associated authorized asset name or another clear
  stable reservation label rather than a raw UUID alone.
- Preserve the raw actor/target identifiers in API responses and use an
  explicit accessible fallback for unavailable historical entities; do not
  silently claim an unknown name.
- Extend audit actor and target search so one entered query matches a UUID or a
  relevant display name, with existing scopes and all other filters still
  enforced. Define case/partial matching consistently and test it.
- Replace or relabel free-form search controls as needed so their visible
  guidance states that names and UUIDs are searchable. Preserve URL/deep-link,
  pagination-reset, multiselect action/type, and authorization behavior.
- Add backend DAO/service/API tests and frontend tests for enriched display,
  name/UUID search, scope isolation, fallback, and query restoration.

## Acceptance Criteria

- Audit history renders known actors and targets as `<Name> (<uuid>)`.
- Actor and target search each match both the relevant name and UUID without
  leaking names outside the caller's audit scope.
- Missing historical entities use a clear accessible fallback while retaining
  the identifier.
- Existing audit filters, deep links, scopes, and pagination behavior remain
  functional.
- Backend and frontend formatting, linting, type checks, unit/API tests,
  relevant browser tests, and production build pass.

## Dependencies

- Ticket 017
- Ticket 028
- Ticket 041
