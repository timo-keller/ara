# 043 - Suggest existing group Webex room identifiers

## Goal

Help administrators reuse Webex room identifiers already associated with
assets in the selected group.

## Scope

- Replace the Webex room identifier text input on Asset administration with a
  documented editable `syn-combobox`.
- Derive unique, non-empty suggestions only from assets in the currently
  selected group, including archived assets.
- Refresh suggestions when the create-form group changes and use the edited
  asset's group in edit mode.
- Keep the field optional and editable: an administrator can select a known
  room, enter a new identifier, or clear it to send `null`.
- Preserve the existing API's no-credentials boundary; do not add any Webex
  credentials, discovery requests, or room validation calls.
- Add focused tests for scope filtering, de-duplication, clearing, custom
  values, and persistence payloads.

## Acceptance Criteria

- Only identifiers used by assets in the selected manageable group are
  suggested.
- Empty or null identifiers are never offered as choices.
- Selecting, entering, or clearing an identifier retains current create/update
  behavior and authorization.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 027
- Ticket 042
