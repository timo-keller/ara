# 046 - End the identity-provider session on logout

## Goal

Make Logout sign the user out of both ARA and the configured identity provider
so the next Sign in can select or authenticate as a different user.

## Scope

- Extend OIDC discovery to consume an optional `end_session_endpoint` when the
  provider advertises one. Validate it as a public issuer-relative browser
  endpoint; never rewrite it to the backend-only OIDC backchannel.
- Change the logout flow so ARA revokes its application session and clears all
  ARA cookies before sending the browser to the provider's end-session endpoint.
  Use only the configured public URL as the post-logout return location; do not
  accept a client-supplied redirect URL.
- Preserve safe application-only logout for generic providers that do not
  advertise an end-session endpoint, and make the UI state/error behavior
  explicit rather than leaving a stale local session.
- Configure the local Keycloak confidential client idempotently with the exact
  post-logout redirect URI required by the flow. Keep its existing
  authorization-code redirect/origin configuration and secret stability.
- Update Angular logout handling to consume the logout result and navigate the
  browser to the provider only after the ARA session has been cleared. Do not
  expose ID tokens, session cookies, client secrets, or provider error details.
- Add backend mocked-provider tests for endpoint validation, session/cookie
  invalidation, fixed post-logout redirect construction, and no-endpoint
  fallback; add frontend tests for navigation and fallback.
- Extend the local real OIDC verification to log in as one development user,
  log out, then log in as a different development user and assert the second
  email and roles. It must not rely on clearing browser cookies or manually
  visiting Keycloak's admin console.

## Acceptance Criteria

- After Logout in the local Keycloak environment, selecting Sign in permits a
  different configured development user to authenticate; the previous Keycloak
  SSO session does not silently select the old user.
- ARA's server-side session is revoked and its session, state, and CSRF cookies
  are cleared even if the provider logout flow is unavailable or fails.
- Browser logout uses the public provider endpoint only; the internal OIDC
  backchannel remains limited to server-side discovery, token, and JWKS calls.
- Post-logout navigation cannot be redirected to an attacker-controlled URL.
- Existing login, callback, CSRF protection, session expiry, Owner claim
  resolution, and production behavior for providers without logout support
  remain functional.
- Backend and frontend formatting, linting, type checks, unit/API tests, the
  real local OIDC test, Compose verification, and production build pass.

## Dependencies

- Ticket 007
- Ticket 008
- Ticket 023
- Ticket 037
