# 075 - Scope role mappings to the selected group

## Goal

Make Group administration's role-mapping editor and mapping list explicitly
belong to the group selected in the left-hand Groups master list, rather than
showing a page-wide mapping workspace beneath the group editor.

## Scope

- Update only the Group administration frontend feature and its frontend tests
  (including the relevant Playwright workflow). Keep the existing group and
  role-mapping API contracts, Owner authorization, audit events, and
  role-resolution behavior unchanged.
- Treat the selected master-list group as the role-mapping context. When an
  Owner selects a group, render that group's role-mapping area in the right
  detail pane with a clear accessible heading that includes the group name.
  Render only non-archived mappings whose `group_id` is the selected group's
  ID, ordered by priority and then the existing stable ID order. Do not render
  mappings from another group in that context.
- In selected active-group context, make the mapping create form group-scoped:
  initialize a new mapping draft with the selected group ID, show the selected
  group as read-only context rather than a group picker, and create/update only
  that group's mapping. Editing an existing mapping must keep it in its current
  group; this UI no longer offers reassignment to another group. Retain the
  existing expression, role, non-negative whole-number priority validation,
  enabled/disabled state, expression-test result, no-save/no-claims disclosure,
  Save, Edit, and Disable behavior.
- A mapping draft is owned by its group context. Switching to another group or
  to Create group mode must not silently discard an unsaved mapping draft or
  expression-test result: retain it per selected group and restore it when that
  group is selected again. A fresh group has a fresh mapping-create draft.
  Saving a mapping resets only the saved group's mapping-create draft, then
  refreshes while retaining the selected group. Selecting a mapping must select
  (or remain in) its owning group before opening its edit draft so the form and
  list cannot disagree about scope.
- `Create group` remains explicit create mode: clear the selected group and the
  group draft as ticket 074 specifies, show no group-scoped mapping form or
  cross-group list, and provide an accessible explanation that a saved, selected
  group is required before managing role mappings. Do not use the unsaved group
  name as a mapping target. On successful group creation, retain the API-returned
  group as the selected detail context as today.
- Show an explicit selected-group empty state when it has no mappings. Archived
  groups remain selectable and show their existing mappings (including disabled
  status) for administration/history, but must not offer creation or
  reassignment of a mapping because role mappings can target only active groups.
  Preserve any archived group's staged mapping draft without allowing it to be
  submitted until the group is reactivated; after reactivation, restore that
  group context and draft. Keep group archive conflict guidance and
  archive/reactivate selection behavior from ticket 074.
- Keep role-mapping mutations Owner-only in the UI and leave the route guard,
  CSRF use, and server-side Owner checks as the security boundary. Do not expose
  a group selector that lets a Group Admin imply it can administer mappings, and
  do not weaken backend rejection of non-Owners, missing groups, or archived
  mapping targets.
- Keep the ticket-074 responsive master/detail model. On desktop, the selected
  group's group form and its role-mapping content belong to the independently
  scrolling detail pane, while the Groups list scrolls independently. At 48rem
  and below, stack master and detail in normal document flow. Preserve semantic
  headings, keyboard selection and `aria-current`, focus-visible/selected
  affordances, fixed desktop rail behavior, and wrapping for long group names
  and JMESPath expressions without horizontal overflow.
- Extend Angular tests for selected-group filtering and ordering, selected
  active/archived/no-mapping states, create mode's absent mapping controls,
  read-only group context, no cross-group reassignment, per-group draft/test
  result retention, save/reset/refresh behavior, archived-target blocking and
  reactivation, and existing mapping edit/disable/error behavior. Update
  Playwright coverage to select groups by keyboard, verify that the right pane
  shows only the selected group's mappings and an empty state, exercise scoped
  create/edit/test/disable behavior, verify draft retention across selection and
  Create group mode, and retain desktop scrolling, narrow stacking, and fixed
  rail assertions.

## Acceptance Criteria

- A selected group is the unambiguous context for both the role-mapping form and
  the role-mapping list; no mappings from other groups are displayed or editable
  in that context.
- Create mode has no mapping target or global mapping list, and creating a group
  selects it before mapping administration becomes available.
- Mapping drafts and test feedback are not lost merely because an Owner changes
  group selection or enters group create mode.
- Groups with no mappings and archived selected groups have clear, correct
  states; mapping creation/reassignment is available only for active groups.
- Existing Owner-only mapping operations, server enforcement, audit semantics,
  validation, and responsive/accessibility behavior remain intact.
- Frontend formatting, linting, unit tests, relevant Playwright tests, and the
  production build pass.

## Dependencies

- Ticket 074
