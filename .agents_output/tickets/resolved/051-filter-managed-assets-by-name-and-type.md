# 051 - Filter managed assets by name and type

## Goal

Let administrators quickly find an asset in the master-detail managed-assets
list using its name and a known asset type.

## Scope

- Add a name filter and a documented clearable restricted Synergy dropdown for
  asset type above the managed-assets list in Asset administration.
- Derive unique type options only from assets within the current user's
  management scope, including archived assets when they are visible in the
  list. Do not leak group-external types to Group Admins.
- Apply both filters together to the list, retain active/archived visibility,
  and make clearing either filter restore the applicable assets.
- Define predictable selection behavior when the selected asset is filtered
  out: retain its editor draft without falsely presenting it as selected, or
  return to a blank draft; document and test the chosen behavior.
- Preserve create/edit/archive/reactivate workflows, existing asset-type and
  Webex suggestions, responsive layout, and authorization.
- Add focused component tests for filtering, type options, Group Admin scope,
  combined filters, selection, and action wiring.

## Acceptance Criteria

- Administrators can filter managed assets by name and select an asset type
  from a dropdown.
- Type options and results are limited to assets the current user may manage.
- Filters compose correctly, clear correctly, and do not break editor or
  archive/reactivate workflows.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 042
- Ticket 044
