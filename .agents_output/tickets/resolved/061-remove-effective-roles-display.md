# 061 - Remove the Effective roles display

## Goal

Remove the internal `Effective roles` diagnostic text from the authenticated
application shell so it is not shown on every page.

## Scope

- Remove the visible Effective roles display from the authenticated navbar or
  shell on every route.
- Preserve the underlying role-resolution state, route guards, Owner/Group
  Admin visibility, authorization enforcement, and account display.
- Remove shell-only role-label rendering code if it becomes unused; do not
  remove role data needed elsewhere.
- Add focused component coverage that the diagnostic text is absent while
  role-gated navigation remains correct.

## Acceptance Criteria

- Authenticated pages no longer display `Effective roles` or role identifiers
  as shell diagnostic text.
- Role-based navigation and server-side behavior remain unchanged.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 023
