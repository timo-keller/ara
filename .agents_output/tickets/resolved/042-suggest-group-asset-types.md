# 042 - Suggest existing group asset types

## Goal

Help administrators reuse the asset types already established in the selected
group while still allowing a new type when needed.

## Scope

- Replace the Asset type text input on Asset administration with a documented
  editable `syn-combobox`.
- Derive unique, normalized suggestions only from assets in the currently
  selected group, including archived assets so a historical type remains
  reusable.
- Refresh suggestions immediately when the create-form group changes and show
  the edited asset's own group when editing.
- Keep the field required and editable: selecting a suggestion or entering a
  new non-empty value must preserve the current create/update payload contract.
- Do not expose assets from groups outside the current user's existing
  management scope.
- Add focused component tests for group filtering, de-duplication, edit state,
  new values, and save behavior.

## Acceptance Criteria

- Asset-type suggestions contain only unique types already used in the selected
  group.
- Changing the selected group changes the suggestion set without leaking types
  from another group.
- An administrator can select an existing type or enter a valid new type.
- Existing server-side authorization and asset validation remain unchanged.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 027
