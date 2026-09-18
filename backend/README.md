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
