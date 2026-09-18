# 008 - Add session and CSRF protection

## Goal

Protect authenticated API requests made with the session cookie.

## Scope

- Persist or cryptographically protect application sessions.
- Add expiration, renewal, and revocation behavior.
- Issue and validate CSRF tokens for state-changing requests.
- Add authentication dependencies for REST routers.

## Acceptance Criteria

- Anonymous access to protected routes is rejected.
- Unsafe methods without a valid CSRF token are rejected.
- Session cookies and CSRF tokens are not logged.
- Expired and revoked sessions cannot access protected routes.

## Dependencies

- Ticket 007
