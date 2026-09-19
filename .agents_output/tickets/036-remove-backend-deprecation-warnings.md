# 036 - Remove backend deprecation warnings

## Goal

Keep the Python 3.14 backend test suite free of deprecation and resource
warnings instead of allowing compatibility issues to accumulate.

## Scope

- Replace uses of Starlette's deprecated synchronous `TestClient` path with
  supported asynchronous HTTPX ASGI test clients, preserving cookie and
  dependency-override behavior.
- Stop passing per-request cookies in authentication tests; manage persistent
  cookies through the test client cookie jar.
- Upgrade pytest-asyncio to a release that supports Python 3.14 without the
  deprecated event-loop policy APIs and update async fixtures when required.
- Replace the deprecated `authlib.jose` API with direct `joserfc` JWT and JWK
  APIs while preserving issuer, audience, authorized-party, nonce, algorithm,
  signature, and lifetime validation.
- Add signed ID-token tests that exercise successful and rejected JWT/JWK
  validation before removing the Authlib implementation.
- Explicitly close every synchronous SQLite connection opened by migration and
  schema tests.
- Remove dependencies that become unused and regenerate the uv lock file.

## Acceptance Criteria

- The complete backend test suite passes on Python 3.14 with deprecation and
  resource warnings treated as errors.
- Test collection and execution no longer emit warnings from Starlette's
  deprecated HTTPX integration, AnyIO's `BlockingPortal` alias,
  pytest-asyncio event-loop policy APIs, or `authlib.jose`.
- Authentication tests do not use per-request `cookies=` arguments.
- OIDC tests validate real signed tokens and cover invalid signature, issuer,
  audience or authorized party, nonce, algorithm, and expiration failures.
- Database and migration tests leave no unclosed SQLite connections or
  unraisable resource warnings.
- Ruff formatting and linting, ty type checking, and the full pytest suite
  pass.

## Dependencies

- Ticket 010
