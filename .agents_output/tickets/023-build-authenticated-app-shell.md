# 023 - Build authenticated app shell

## Goal

Provide login, logout, current-user state, and role-aware navigation.

## Scope

- Integrate session and CSRF APIs.
- Add login and authentication callback states.
- Build the responsive Synergy-based application shell.
- Hide unavailable navigation while retaining backend enforcement.

## Acceptance Criteria

- Anonymous users can initiate OIDC login.
- Authenticated users can log out and view their effective roles.
- State-changing requests include the CSRF token.
- Session expiry returns the UI to a safe login state.

## Dependencies

- Ticket 008
- Ticket 009
- Ticket 022
