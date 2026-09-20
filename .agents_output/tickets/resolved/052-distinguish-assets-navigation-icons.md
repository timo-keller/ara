# 052 - Distinguish asset navigation icons

## Goal

Give `Assets` and `Manage assets` distinct sidebar icons so their different
user and administration tasks are recognisable at a glance.

## Scope

- Replace one of the currently duplicated sidebar icons with a semantically
  appropriate, distinct icon from the documented Synergy asset set.
- Keep labels, routes, access controls, active-route behavior, accessible
  names, keyboard navigation, and responsive side navigation unchanged.
- Do not introduce custom inline SVGs or icons outside the configured Synergy
  icon library.
- Add focused component coverage confirming the two navigation entries use
  distinct icon names.

## Acceptance Criteria

- `Assets` and `Manage assets` have visibly and semantically distinct icons.
- Navigation behavior and accessibility are unchanged.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 023
- Ticket 024
- Ticket 027
