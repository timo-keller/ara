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
`ARA_AUDIT_RETENTION_DAYS` (default: `365`), and
`ARA_NOTIFICATION_REMINDER_OFFSETS_MINUTES` (comma- or space-separated
non-negative minute offsets; default: `60 15 0`). Offsets must be unique.

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

## Production container

Build the backend from the `backend` directory. The image installs the locked
runtime dependency set only, runs as the `ara` user, and stores its default
SQLite database in the writable `/app/data` mount point.

```sh
docker build -t ara-backend .
```

The entrypoint validates required configuration, runs `alembic upgrade head`,
then `exec`s exactly one Uvicorn worker. Do not enable reload or additional
workers: the application's lifespan owns the single APScheduler instance.
Provide production secrets with the documented `/run/secrets` `_FILE` settings.
The image healthcheck calls `GET /api/health/live` using Python's standard
library. For a local, non-secret image smoke test, run:

```sh
./scripts/verify-container.sh
```

## Scheduled work

APScheduler runs in the FastAPI lifespan and uses one asyncio scheduler per
backend process. Jobs receive a fresh async database session through
`run_scheduled_job`, which emits structured completion or failure logs. The
deployment must continue to use exactly one backend process and one Uvicorn
worker: the in-process scheduler is not safe to run across multiple workers.
Job executions coalesce missed runs, allow one concurrent instance, and have a
60-second misfire grace period.

Reservation reminders run every minute. They create an in-application record
for every configured offset once its scheduled time is due, including overdue
records after downtime. Open-ended, returned, cancelled, and administratively
ended reservations are excluded. The database uniqueness key
`(reservation_id, kind, scheduled_for)` (where kind includes the offset) makes
repeated runs idempotent.

Audit retention runs daily. It deletes events strictly older than
`ARA_AUDIT_RETENTION_DAYS` in independently committed batches of 100; events
created exactly at the calculated UTC cutoff remain. Each run logs its deleted
event count, batch count, and cutoff as structured metrics.

`GET /api/notifications` returns only the authenticated user's notifications,
paginated with `offset` and `limit`, newest-first by `created_at` with `id` as
the tie-breaker. `POST /api/notifications/{id}/read` requires CSRF protection,
returns `404` for another user's record, and is idempotent: once set, the
original `read_at` is retained.

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

## Role mappings

Only Owners can manage `/api/role-mappings`. Mappings can be created, listed,
updated, disabled, and archived. `POST /api/role-mappings/test` evaluates an
expression against the Owner's server-side session claims and returns only a
boolean `matches` result; it never persists the expression or returns claims.

## Assets

`/api/assets` provides create, list, read, update, archive, and reactivate
operations. Lists support `group_id`, `asset_type`, `text`, `archived`,
`offset`, and `limit` filters and are ordered by name and identifier. Owners
manage all assets, Group Admins manage assets in their groups, and Users see
only active assets in their groups. Remote metadata may contain host names,
URLs, operating-system details, and access instructions, but credential-like
fields (including nested operational metadata) and unknown input fields are
rejected and are never stored or returned.

## Reservation intervals

Reservation timestamps must be timezone-aware UTC values. Active reservations
use exclusive intervals: adjacent intervals are allowed, while an omitted end
is positive infinity. Conflict checking and insertion run in one SQLite
`BEGIN IMMEDIATE` write transaction. This relies on the documented single
backend-process deployment model; SQLite does not provide a range exclusion
constraint for multi-process deployments.

## Reservations API

Authenticated group members create their own reservations with `POST
/api/reservations`; the CSRF token is required. `GET /api/reservations/mine`
lists the current user's reservations newest-first and includes `asset_name`
only when the referenced asset remains visible to that user; otherwise it is
`null`. `GET
/api/assets/{asset_id}/reservations` lists an accessible asset's active schedule
chronologically. Both lists use `offset` and `limit` pagination and a stable
identifier tie-breaker. Creation rejects archived groups or assets and requires
UTC timestamps (`Z` or `+00:00`). A self-service start in the past is clamped
to the server's current UTC time after its write lock is acquired; bounded
reservations retain their submitted end and must still have a positive effective
interval.

`POST /api/reservations/{id}/extend` extends the authenticated user's bounded
active reservation to a strictly later UTC `ends_at`; the full revised interval
is checked under the same `BEGIN IMMEDIATE` lock as creation.  Open-ended and
terminal reservations cannot be extended. `POST /api/reservations/{id}/return`
returns only the authenticated user's active reservation after it has started:
a current reservation, or a bounded elapsed reservation including exactly at
its scheduled end. Returning an elapsed reservation preserves its scheduled
end as historical data. Future and terminal reservations are not returnable.
`POST /api/reservations/{id}/cancel` cancels only a future reservation: its
owner may cancel it, as may an Owner or Group Admin for the asset's group.
`POST /api/reservations/{id}/end` ends a currently active reservation and is
restricted to those administrators. At the exact start time a reservation is
no longer future for cancellation and is returnable/endable; at its exact end
it is returnable but no longer endable. All lifecycle POST routes require CSRF
and reject terminal/repeated operations with `409`.

## Audit API

`GET /api/audit-events` returns reverse-chronological audit history with a
deterministic event-identifier tie-breaker. It accepts `group_id`, `actor_id`,
`action`, `target_type`, `target_id`, `created_at_from`, `created_at_to`,
`offset`, and `limit` filters; time values must be UTC. `action` and
`target_type` may each be repeated to match any supplied value; these two
filters, and all other filters, are intersected. Supported actions are
`asset.create`, `asset.update`, `asset.archive`, `asset.reactivate`,
`group.create`, `group.update`, `group.archive`, `group.reactivate`,
`reservation.create`, `reservation.extend`, `reservation.return`,
`reservation.cancel`, `reservation.end`, `role_mapping.create`,
`role_mapping.update`, `role_mapping.disable`, and `role_mapping.archive`.
Supported target types are `asset`, `group`, `reservation`, and `role_mapping`.
Owners can query all events, while Group Admins see only events associated with
their administered groups. Users are denied access.
## Webex delivery

The optional `ARA_WEBEX_BOT_TOKEN_FILE` Docker secret enables outbound Webex bot
delivery. `ARA_WEBEX_BOT_TOKEN` is also supported for explicit local/test settings;
do not set both forms. Tokens are redacted and never persisted in the outbox.
The local `run-dev.sh` launcher automatically mounts the optional token when
`secrets/webex_bot_token` exists, falling back to `.dev/secrets/webex_bot_token`
(or using the source path configured through `ARA_WEBEX_BOT_TOKEN_FILE`).
With no file, it starts without Webex; rerun `./run-dev.sh up` after adding or
removing the file.

`PATCH /api/groups/{id}/webex` accepts `webex_space_link` (or null to disable
room notifications). Add **ARA Notification Bot** to a group space, copy its
`webexteams://im?space=<UUID>` link, save it, and send a test. Resolution saves
the actual canonical room ID returned by Webex plus the normalized display link.
Legacy `webex_room_id` API updates and existing room configurations remain supported.
Lookups use only `https://webexapis.com/v1/rooms`, at most 20 pages of 100 rooms,
with a 15-second HTTP timeout and a 30-second total deadline. Pagination URLs
must target that same HTTPS endpoint. Network calls run outside the database
transaction; failed lookups preserve both previous settings and audit history.
Errors distinguish invalid links, unavailable Webex, missing/invalid credentials,
rate limits, and missing bot membership without exposing remote response bodies.

`GET /api/groups/{id}/webex` returns room-only counts and the latest 20 delivery
states; `POST /api/groups/{id}/webex/test` queues a test and returns HTTP 202.
All require Owner or responsible Group Admin access; mutations also require
CSRF protection. Room settings are audited. The asset API accepts
`room_notifications_enabled` (default true), replacing its removed room-ID field.

The durable dispatcher is registered in the FastAPI scheduler lifespan. It
queues due future starts and personal end reminders, while reservation creation
and explicit returns stage room events in their domain transaction. Webex
delivery is independent of browser notification read state. See
`deployment/README.md` for opt-in Compose setup, retry/catch-up defaults, retention,
and the ambiguous remote-delivery limitation.
