# 023 - Build authenticated app shell

## Goal

Provide login, logout, current-user state, and role-aware navigation.

## Scope

- Integrate session and CSRF APIs.
- Add login and authentication callback states.
- Build the responsive application shell from Synergy's Appshell
  "Rail Navigation" template, using `syn-header`,
  `syn-side-nav variant="rail"`, and `syn-nav-item` with the documented
  desktop and tablet behavior.
- Hide unavailable navigation while retaining backend enforcement.

## Acceptance Criteria

- Anonymous users can initiate OIDC login.
- Authenticated users can log out and view their effective roles.
- State-changing requests include the CSRF token.
- Session expiry returns the UI to a safe login state.
- The authenticated layout uses Synergy's Appshell "Rail Navigation" pattern,
  and its rail items drive Angular routes while preserving responsive and
  accessible navigation behavior.

## Dependencies

- Ticket 008
- Ticket 009
- Ticket 022
