# ARA backend

Install dependencies and run the development server with:

```sh
uv sync
uv run ara
```

## Configuration

The backend reads non-sensitive settings from environment variables:
`ARA_DATABASE_URL` (default: `sqlite+aiosqlite:////app/data/ara.db`),
`ARA_PUBLIC_URL`, `ARA_OIDC_ISSUER_URL`, `ARA_OIDC_CLIENT_ID`,
`ARA_OIDC_SCOPES` (default: `openid profile email`), and
`ARA_AUDIT_RETENTION_DAYS` (default: `365`).

`ARA_OIDC_CLIENT_SECRET`, `ARA_SESSION_SECRET`, and `ARA_OWNER_SUBJECTS` are
required secrets. In production provide each through its corresponding
`_FILE` setting (for example, `ARA_OIDC_CLIENT_SECRET_FILE`) pointing to a
file below `/run/secrets`. Direct and `_FILE` values cannot be set together.

## Database migrations

Schema changes are applied only through Alembic; the application never creates
tables at startup. Run pending migrations before starting the API:

```sh
uv run alembic upgrade head
```

## Health and API conventions

The API and authentication route foundations are mounted at `/api` and `/auth`.
`GET /api/health/live` checks only that the process can answer requests, while
`GET /api/health/ready` verifies database connectivity and returns `503` when
the database is unavailable. Every response includes an `X-Correlation-ID`
header. Expected validation and domain failures use an `error` object with a
safe code and message; request logs contain only request metadata and the
correlation ID, never headers, cookies, query strings, or settings.

## Backend layout

HTTP routers and API schemas live in `ara.api`; routers delegate business rules
and transaction boundaries to `ara.services`. Persistence queries without
commits live in `ara.daos`, SQLAlchemy models in `ara.domain`, and database/OIDC
adapters in `ara.infrastructure`. Configuration, errors, and request context
helpers are in `ara.core`.

## OIDC login

`GET /auth/login` discovers the configured provider and starts an Authorization
Code flow. `GET /auth/callback` validates state, nonce, issuer, audience,
signature, and token lifetime before creating a local user and issuing an
HttpOnly, Secure, SameSite=Lax session cookie. Sessions are persisted server
side, expire after eight hours of inactivity, renew during their final hour,
and are revoked on logout. The callback also issues an `ara_csrf` cookie; the
frontend must send its value in `X-CSRF-Token` for unsafe authenticated calls.
`GET /auth/session` returns the safe local profile and `POST /auth/logout`
revokes the session. REST handlers can use `require_authenticated_user` and
`require_csrf` from `ara.api.routers.auth` as reusable dependencies. OIDC access and ID
tokens are never returned to the browser or persisted by ARA. Validated OIDC
claims are retained only with the server-side application session so enabled
JMESPath role mappings can be evaluated; they are never returned by the API or
written to request logs. `ARA_OWNER_SUBJECTS` is a comma- or newline-separated
bootstrap Owner subject allowlist and should be supplied via
`ARA_OWNER_SUBJECTS_FILE` in production.
