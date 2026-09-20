# 039 - Group role mappings by group

## Goal

Make the role-mapping list easy to scan by presenting mappings under their
associated group rather than as one mixed list.

## Scope

- Replace the flat Role mappings list in Group administration with sections
  grouped by group name.
- Include active and disabled mappings in the relevant group section, using the
  existing status display and actions.
- Show groups with no mappings explicitly so an Owner can identify where a new
  mapping will apply.
- Preserve edit, disable, expression-test, and existing group archive behavior.
- Sort groups deterministically by displayed name and mappings by priority,
  then their existing stable identifier/order.
- Add focused component tests for grouping, empty groups, ordering, and action
  wiring.

## Acceptance Criteria

- No role mapping appears in more than one group section.
- Every mapping is displayed beneath the group selected by its `group_id`.
- Groups without mappings have an accessible empty state.
- Existing Owner-only access controls and mapping operations remain intact.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 026
- Ticket 038
