# 074 - Align Group administration with asset administration

## Goal

Refactor the Owner-only Group administration screen into the same responsive
master/detail interaction model used by Asset administration: a create action
and selectable group list on the left, with the selected group's create/edit
form on the right, without losing group or role-mapping workflows.

## Scope

- Rework only `frontend/src/app/features/administration/` markup, component
  state, styles, and tests. Do not change group or role-mapping API contracts,
  server authorization, audit behavior, or role-resolution semantics.
- Replace the current top-level create/edit group card and separate groups list
  with an `asset-workspace`-equivalent responsive two-column workspace. The
  left master pane has a `Groups` heading, `Create group` button, and an
  ordered, keyboard-operable list of all Owner-visible groups (including
  archived groups). Each item displays name, description/fallback, and an
  explicit Active/Archived badge; selecting it loads that group's draft into
  the right detail editor and exposes selection with `aria-current` and an
  accessible selected label. `Create group` clears selection/draft and changes
  the editor to create mode.
- The right detail card presents the group name and description form and keeps
  Save, Archive, and Reactivate actions in the selected group's editor. Keep
  current validation, duplicate-name/API errors, refresh-after-save behavior,
  archive conflict alert/details, and retained selected group behavior after a
  successful save/archive/reactivation. If a selected group is no longer in a
  refreshed list, safely return to create mode.
- Preserve the full Owner role-mapping experience: create/edit mapping,
  group choice limited to active groups, expression test (with its no-save/no-
  claims disclosure wording), enabled/disabled display, priority ordering,
  disable operation, and mapping grouping by group. Place this content below
  the group workspace (or in an equivalent clearly separate Owner section), so
  it is not mistaken for controls scoped to the selected group. Do not silently
  discard an in-progress mapping draft when a group is selected or created.
- Mirror Asset administration's responsive behavior: at widths above 48rem use
  a left/right grid with independent vertical scrolling for the master list and
  editor inside the fixed desktop application surface; at 48rem and below stack
  in a single column and use normal document scrolling. Keep minimum widths,
  focus-visible treatment, hover/selected affordances, semantic headings, and
  long names/descriptions/mapping expressions readable without horizontal
  overflow. Preserve the established compact route heading-to-content rhythm.
- Keep the route Owner-only as it is today. The UI must not imply that Group
  Admins can create or alter groups/mappings; backend denial remains the
  security boundary.
- Update Angular unit tests for draft selection/create/reset, rendered active
  and archived list states, selected ARIA state, group mutation/error/archive
  conflict flows, and role-mapping draft/workflow preservation. Replace or
  extend Playwright administration coverage to assert the desktop two-column
  layout, independently scrolling group list/editor, keyboard selection,
  create mode, narrow stacked layout, fixed rail behavior, and continuing role
  mapping operations.

## Acceptance Criteria

- Group administration has a responsive, accessible master/detail group
  workspace visually and behaviorally consistent with Asset administration.
- Owners can create, select, edit, archive, and reactivate groups without
  losing validation, conflict guidance, selection correctness, or archive
  visibility.
- All role-mapping create/edit/test/disable/list workflows and their active
  group constraints remain available and correct.
- Desktop panes scroll independently within the fixed application surface;
  narrow layouts stack and remain keyboard-accessible without horizontal
  overflow.
- Owner-only navigation/API authorization and all existing group/role-mapping
  data and audit semantics remain unchanged.
- Frontend formatting, linting, unit tests, relevant Playwright tests, and the
  production build pass.

## Dependencies

- Ticket 069
