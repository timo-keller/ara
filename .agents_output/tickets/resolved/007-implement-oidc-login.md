# 007 - Implement OIDC login

## Goal

Authenticate users through a generic OpenID Connect provider.

## Scope

- Discover provider endpoints from the configured issuer.
- Implement login, callback, logout, and current-session endpoints.
- Use Authorization Code flow and validate state, nonce, and tokens.
- Resolve users by issuer and subject and update safe profile fields.

## Acceptance Criteria

- The client secret remains backend-only.
- Login creates an HttpOnly, Secure, SameSite session cookie.
- Logout invalidates the application session.
- Provider and token failures return safe errors without leaking tokens.
- OIDC behavior is tested with a mocked provider.

## Dependencies

- Ticket 003
- Ticket 005
- Ticket 006
