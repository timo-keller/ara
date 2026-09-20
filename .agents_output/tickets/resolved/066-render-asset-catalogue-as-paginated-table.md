# 066 - Render asset catalogue as a paginated table

## Goal

Make the Assets catalogue easier to scan by rendering its authorized active
assets in a responsive table-style layout rather than a grid of cards.

## Scope

- Replace the result-card grid in
  `frontend/src/app/features/assets/asset-catalogue.page.html` with an
  accessible table-style result layout using the project/Synergy conventions.
  It must expose these columns in this order: Asset name, Asset type,
  Description, Availability, and Details.
- Render the asset name as the existing authorized asset-detail link, retain
  the existing availability wording (`Available now`/`Reserved now`), use the
  existing no-description fallback, and provide a clearly named Details link
  to the same `/assets/:id` route. Do not expose archived or unauthorized
  assets.
- Preserve all current search, group, type, availability, URL query-state,
  loading, error, empty-state, page-size, and API pagination behavior in
  `asset-catalogue.page.ts` and `asset-catalogue.service.ts`. Keep the existing
  `syn-pagination` controls and their 10/25/50 options associated with the
  table results.
- Make the table usable at narrow widths without truncating required columns
  or creating an inaccessible horizontal-scroll trap; retain keyboard-accessible
  detail links and meaningful header-to-cell associations.
- Remove card-only imports/styles only if no longer used, and add focused
  component and browser coverage for column order/content, detail navigation,
  pagination, result states, and narrow-screen behavior.

## Acceptance Criteria

- Assets renders an accessible table-style layout with Asset name, Asset type,
  Description, Availability, and Details columns.
- Each visible row preserves the existing authorized detail navigation and
  understandable description/availability fallbacks.
- Existing filters, deep links, pagination, authorization, and responsive
  access continue to work.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 024
- Ticket 048
- Ticket 064
