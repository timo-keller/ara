# 067 - Render My reservations as a paginated table

## Goal

Make a user's reservations compact and scannable in a table-style layout while
retaining all reservation lifecycle actions.

## Scope

- Replace the card list in
  `frontend/src/app/features/reservations/reservations.page.html` with an
  accessible, responsive table-style layout. Render columns for Asset Name,
  Type, Reservation timespan, and Actions/Details; Asset Name and Details must
  retain authorized links to `/assets/:id` when the asset is available.
- Extend the authorized own-reservations response only as needed to supply an
  asset type alongside the existing `asset_name`, without frontend N+1
  requests. Update the reservation schema, DAO/service projection, frontend
  `Reservation` type, and backend/frontend tests while preserving existing API
  fields and asset/group visibility rules. Use a clear non-identifying fallback
  for unavailable historical assets and do not disclose a type for an asset the
  user may not view.
- Format each start/end timespan in the browser's local time using an explicit
  24-hour clock. Retain the understandable open-ended fallback (`until
  returned`) and status/lifecycle eligibility behavior.
- Keep Extend, Return asset, and Details available as appropriate for each row;
  preserve the current conditional cancellation action, confirmation dialogs,
  mutation error guidance, and reload behavior rather than removing lifecycle
  capabilities during the layout change.
- Add pagination following the existing catalogue/audit convention. Pass
  `offset` and `limit` to `GET /api/reservations/mine`, use its existing total
  response, provide a sensible default and page-size options consistent with
  comparable pages, and keep page changes and page-size resets accessible and
  reproducible in route state where application conventions require it.
- Retain loading, error, empty, keyboard, and narrow-screen behavior; add
  focused backend/API, component, and browser coverage for type visibility,
  24-hour times, links/actions, paging, and fallback states.

## Acceptance Criteria

- My reservations displays a responsive accessible table with Asset Name, Type,
  a local 24-hour reservation timespan, and Extend, Return, and Details
  controls/links when applicable.
- Reservation type data is delivered without N+1 requests or unauthorized
  asset metadata disclosure, and unavailable assets have clear safe fallbacks.
- Existing lifecycle actions, confirmations, errors, authorization, and
  pagination behavior remain functional.
- Backend and frontend formatting, linting, type checks, unit/API tests,
  relevant browser tests, and the production build pass.

## Dependencies

- Ticket 014
- Ticket 025
- Ticket 054
- Ticket 062
