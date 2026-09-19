# 044 - Redesign asset administration as a two-column editor

## Goal

Make asset administration an efficient master-detail workflow: choose an asset
from a list on the left and edit its values in a stable editor on the right.

## Scope

- Redesign the Asset administration route into a desktop two-column layout:
  an accessible managed-asset list on the left and the create/edit form on the
  right.
- Provide a clear Create asset action that selects a blank draft; selecting a
  list item loads it into the right-hand editor. The selected asset must be
  visually and programmatically identified.
- Keep archive/reactivate available from the selected asset workflow and define
  the post-action selection deterministically (for example, select the next
  visible item or return to a blank create draft).
- Preserve Owner/Group Admin scoping, active/archived visibility, validation,
  error handling, asset-type suggestions, and Webex room suggestions.
- On narrow viewports, stack or otherwise adapt the layout without hiding the
  list, selected state, or editor controls.
- Do not change asset API contracts, migrations, or authorization rules.
- Add component and relevant browser coverage for selection, create, edit,
  save refresh, archive/reactivate, keyboard access, and responsive layout.

## Acceptance Criteria

- At desktop widths, the managed-asset list is left of the editable detail
  pane, and clicking an asset shows that asset's current values for editing.
- Creating a new asset and saving an existing one refreshes the list and keeps
  selection state predictable.
- Group Admins never see or mutate assets outside their groups; Owners retain
  access to all groups.
- The UI remains usable and accessible at narrow viewport sizes.
- Frontend formatting, linting, unit tests, relevant browser tests, and
  production build pass.

## Dependencies

- Ticket 027
- Ticket 042
- Ticket 043
