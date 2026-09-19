# 038 - Explain role-mapping priority

## Goal

Make the role-mapping priority field understandable before an Owner creates or
edits a mapping.

## Scope

- Add concise, visible help text adjacent to the `Priority` field in Group
  administration.
- Explain that a lower number is evaluated first, that equal priorities use a
  stable deterministic ordering, and that priority does not override an Owner
  grant.
- Retain the existing non-negative whole-number validation and default of zero.
- Use the Synergy form-control help-text mechanism or documented slot API; do
  not replace the field with a custom control.
- Add focused frontend tests for the explanation and retained validation.

## Acceptance Criteria

- An Owner can determine how to choose a priority without consulting external
  documentation.
- The explanation accurately reflects `RoleResolutionService` evaluation
  semantics.
- Creating and editing mappings still sends the selected integer priority.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 026
