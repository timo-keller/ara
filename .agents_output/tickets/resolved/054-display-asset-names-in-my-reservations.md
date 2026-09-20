# 054 - Display asset names in My reservations

## Goal

Show a human-readable asset name instead of an asset UUID for every reservation
on the My reservations page.

## Scope

- Identify the reservation page field that currently renders an asset UUID and
  replace it with the corresponding authorized asset name.
- Extend the reservation API response only as needed to provide a stable asset
  display name without client-side N+1 requests. Preserve existing reservation
  identifiers and API fields for compatibility.
- Enforce existing reservation and asset visibility rules: a user must never
  learn an asset name they are not authorized to view through this response.
- Define and render a clear accessible fallback for a historically deleted,
  unavailable, or otherwise non-resolvable asset reference without reverting to
  an opaque UUID as the primary user-facing value.
- Update backend API/service/DAO tests and frontend component tests for normal,
  scoped, and fallback display behavior.

## Acceptance Criteria

- My reservations shows the asset's authorized name rather than its UUID.
- Existing reservation workflows and API consumers remain compatible.
- No unauthorized asset names are disclosed, and missing historical references
  have a clear non-UUID fallback.
- Backend and frontend formatting, linting, type checks, unit/API tests, and
  production build pass.

## Dependencies

- Ticket 014
- Ticket 025
