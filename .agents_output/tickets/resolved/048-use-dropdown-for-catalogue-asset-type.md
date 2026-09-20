# 048 - Use a dropdown for catalogue asset type

## Goal

Let users choose an asset type from known values instead of guessing or typing
an exact free-form value in the asset catalogue filter.

## Scope

- Replace the Asset catalogue `Type` text filter with a documented Synergy
  restricted, clearable dropdown/combobox.
- Populate its options from the complete currently visible catalogue result
  vocabulary or an explicit server-provided vocabulary, rather than a
  hand-maintained partial list. Do not expose types from unauthorized groups.
- Preserve the existing exact asset-type filtering contract and all other
  filters, URL state, paging reset, clearing behavior, and authorization.
- Restore the selected type from deep links and browser back/forward
  navigation. Legacy `asset_type` query values must remain supported.
- Add focused tests for options, selection, clearing, scope, and URL/API
  serialization.

## Acceptance Criteria

- Asset type is selectable from a clearable restricted dropdown; arbitrary
  values cannot be submitted through this control.
- Options contain only authorized, known asset types and selecting one retains
  exact filtering behavior.
- Existing catalogue filters, deep links, and pagination behavior remain
  functional.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 024
