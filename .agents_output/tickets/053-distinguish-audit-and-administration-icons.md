# 053 - Distinguish audit and administration navigation icons

## Goal

Give `Audit history` and `Administration` distinct sidebar icons that reflect
their different tasks.

## Scope

- Replace one of the currently duplicated sidebar icons with a semantically
  appropriate, distinct icon from the documented Synergy asset set.
- Keep labels, routes, Owner and Group Admin access controls, active-route
  behavior, accessible names, keyboard navigation, and responsive side
  navigation unchanged.
- Do not introduce custom inline SVGs or icons outside the configured Synergy
  icon library.
- Add focused component coverage confirming the two navigation entries use
  distinct icon names.

## Acceptance Criteria

- `Audit history` and `Administration` have visibly and semantically distinct
  icons.
- Navigation behavior, role visibility, and accessibility are unchanged.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 023
- Ticket 026
- Ticket 028
