# ARA Architecture Decisions

## 1. Purpose

ARA (Asset Reservation & Allocation) manages reservable assets such as
computers, laptops, and remote systems. Authorized users can reserve assets
immediately or for a future period, return them, and receive browser
notifications when a reservation approaches or reaches its end.

This document records the architectural decisions agreed for the initial
implementation. Future changes should update this document or add a separate
architecture decision record.

## 2. System Context

ARA is an internal web application consisting of an Angular single-page
application and a FastAPI REST API. A generic OpenID Connect provider supplies
the authenticated identity and claims. ARA stores its application data in
SQLite and is deployed with Docker Compose.

The initial deployment is deliberately a single-node deployment. SQLite and
the in-process scheduler make running more than one backend process unsafe.

## 3. Repository Layout

The intended top-level layout is:

```text
ara/
|-- backend/
|-- frontend/
|-- deployment/
|-- .agents_output/
|   |-- architecture.md
|   `-- tickets/
`-- compose.yaml
```

The backend and frontend are independently buildable and testable. Deployment
configuration remains separate from application source where practical.

## 4. Backend Technology

The backend uses:

- Python
- FastAPI
- SQLAlchemy 2.x asynchronous APIs
- `aiosqlite`
- Alembic database migrations
- `uv` for project and dependency management
- Ruff for formatting and linting
- `ty` for static type checking
- pytest, pytest-asyncio, and HTTPX for testing
- APScheduler for periodic processes

All Python source resides below `backend/src/ara`.

## 5. Backend Layers

Backend dependencies flow inward as follows:

```text
REST routers -> services -> DAOs -> SQLAlchemy/database
```

The responsibilities are:

- REST routers validate transport input, call services, and produce HTTP
  responses.
- Services implement business rules, authorization, transaction boundaries,
  and audit recording.
- DAOs contain persistence queries and do not implement authorization or
  business policy.
- SQLAlchemy models represent persisted state.
- API schemas are separate from SQLAlchemy models.

An asynchronous SQLAlchemy session is scoped to a request or scheduler job.
Services own commits and rollbacks. DAOs must not commit independently, so a
domain operation and its audit event remain atomic.

## 6. Database

SQLite is accessed asynchronously through SQLAlchemy and `aiosqlite`. The
database file is stored at `/app/data/ara.db` in the backend container.

The connection is configured with:

- foreign key enforcement enabled
- WAL journal mode
- a bounded busy timeout
- UTC timestamps

Alembic is the only supported mechanism for schema changes. Migrations run
before the API process starts.

The deployment runs exactly one backend container and one Uvicorn worker.
Horizontal scaling requires moving to a database such as PostgreSQL and moving
scheduled work to a singleton worker or distributed job system.

## 7. Core Domain

### 7.1 Users

A user is identified by the pair of OIDC issuer and subject. A local user row
stores the stable identity, display information required by ARA, and login
timestamps. The OIDC provider remains the source of authentication.

### 7.2 Groups

Groups are ARA-owned organizational units. Assets and group-scoped roles belong
to a group. Groups are archived rather than deleted.

An archived group remains available for history and audit purposes but cannot
receive new assets or reservations. Existing active and future reservations
must be resolved explicitly before a group can be archived.

### 7.3 Assets

Every asset belongs to exactly one group. An asset has a type, name,
description, operational metadata, and optional remote-access metadata.

ARA stores only remote-access metadata, such as host name, URL, operating
system, and access instructions. It does not store passwords, private keys, or
other remote-system credentials.

Assets are archived rather than deleted. Archived assets remain visible in
history and audit views, cannot be newly reserved, and are hidden from normal
asset lists by default. An authorized administrator can reactivate them.

A future Webex integration may store a Webex room identifier per asset. The bot
credential will be a deployment secret and will not be stored on an asset.

### 7.4 Reservations

A reservation belongs to one asset and one user. It has a required start time
and an optional end time. All persisted timestamps use UTC. The frontend
converts values to and from the user's local time zone.

Reservations may start immediately or in the future. An omitted end means that
the reservation continues until returned. Such a reservation conflicts with
every reservation after its start.

Reservation intervals are exclusive and may not overlap. Two bounded
intervals overlap when:

```text
existing.start < requested.end
and requested.start < existing.end
```

A missing end is treated as positive infinity. Adjacent reservations are
allowed, so one reservation may start exactly when another ends.

Creating a reservation is immediate and requires no approval. Extending a
reservation is permitted only if the extended interval does not overlap
another reservation. Shortening a reservation is permitted as long as the end
does not precede its start.

A user may return an active reservation early. A future reservation may be
cancelled by its user. Owners and the responsible Group Admins may end or cancel
reservations administratively. These actions are audited.

SQLite has no exclusion constraint for time ranges. Conflict detection and
reservation creation therefore execute in one write transaction. The
single-process deployment is part of this correctness model.

## 8. Authentication

Login uses generic OpenID Connect with the Authorization Code flow. Provider
settings are supplied through environment variables:

- issuer URL
- client ID
- scopes
- public application URL and callback URL

The client secret is supplied as a Docker secret. It is never exposed to the
Angular application.

FastAPI acts as a backend for frontend for authentication. It exchanges the
authorization code, validates provider metadata and tokens, resolves the user,
and creates an application session. The browser receives an HttpOnly, Secure,
SameSite session cookie. State-changing REST calls require CSRF protection.

The application does not store access or ID tokens in browser local storage.

## 9. Authorization

ARA has three roles:

- Owner is global.
- Group Admin is scoped to an ARA group.
- User is scoped to an ARA group.

Permissions are:

| Capability | Owner | Group Admin | User |
| --- | --- | --- | --- |
| Manage all groups | Yes | No | No |
| Manage OIDC claim mappings | Yes | No | No |
| View assets | All | Own groups | Own groups |
| Manage assets | All | Own groups | No |
| Reserve available assets | Yes | Yes | Yes |
| Return own reservations | Yes | Yes | Yes |
| End another user's reservation | Yes | Own groups | No |
| View audit events | All | Own groups | No |

Authorization is always enforced in backend services. Frontend visibility is
only a usability feature and is not a security boundary.

## 10. OIDC Claim Mapping

The Owner maps OIDC claims to ARA groups and roles. Claim matching uses
JMESPath, which can inspect nested JSON claims without executing arbitrary
code.

Each mapping contains:

- a JMESPath expression that evaluates to a match
- a target ARA group
- either the User or Group Admin role
- enabled state and deterministic evaluation priority

Example mappings are:

```text
contains(groups, 'ara-lab-users') -> Lab -> User
contains(groups, 'ara-lab-admins') -> Lab -> Group Admin
```

The Owner UI provides a way to test an expression against the current user's
claims before saving it. Invalid expressions are rejected by the API.

The initial Owner cannot depend on database mappings. A deployment secret named
`owner_subjects` contains an allowlist of OIDC subject identifiers used to
bootstrap global Owner access.

## 11. REST API

The API is served below `/api`. Authentication endpoints are served below
`/auth`. JSON is the standard request and response format.

The initial resource areas are:

- session and current user
- groups
- OIDC role mappings
- assets
- reservations
- browser notifications
- audit events
- health information

Collection endpoints use explicit pagination, filtering, and stable ordering.
API schemas do not expose database models directly. Expected domain conflicts,
including overlapping reservations, return a conflict response rather than an
internal server error.

## 12. Audit

Audit events are append-only application records. A domain mutation and its
audit event are committed in the same transaction.

An audit event records at least:

- UTC timestamp
- acting user
- action
- affected group
- target object type and identifier
- relevant before and after state
- request or correlation identifier when available

Audit coverage includes group changes, role-mapping changes, asset changes,
reservation creation, extension, cancellation, return, and administrative end.

Owners can query all audit events. Group Admins can query only events associated
with their groups. Users cannot access the audit API.

Audit events are retained for one year. A daily scheduled job removes older
events in bounded batches. Retention deletion is operational maintenance and
does not create another audit event.

## 13. Scheduling

APScheduler runs inside the one FastAPI process and is started and stopped by
the FastAPI lifespan. It uses the asyncio scheduler integration.

Periodic jobs include:

- identifying due reservation notifications
- updating or deriving expired reservation state where necessary
- deleting audit events beyond the one-year retention period
- later, dispatching queued Webex messages

Jobs use coalescing, `max_instances=1`, and a bounded misfire grace period.
Business state and delivery state are persisted in SQLite; APScheduler memory
is not the source of truth. Jobs are idempotent, so restart recovery and
repeated execution cannot create duplicate notifications.

## 14. Notifications

The first implementation provides in-application notifications and uses the
browser Notification API when permission is granted and the application is
running. Notification records and read state are persisted in ARA.

Reservations without an end time cannot produce end-of-reservation reminders.
Reminder offsets must be configurable rather than embedded in frontend code.

Web Push for notifications while ARA is closed is not part of the initial
decision. A later Webex bot integration will send messages to the room
configured for an asset. Delivery attempts must use a persisted outbox and be
retryable without duplicate messages.

## 15. Frontend

The frontend uses Angular and TypeScript. It is organized by feature rather
than by low-level Angular artifact type. Initial features are authentication,
asset catalogue, reservations, group administration, role mappings, audit, and
notifications.

UI components come from the Synergy Design System. The Angular adapters are
preferred where available. Custom components should compose Synergy primitives
instead of recreating controls already provided by Synergy.

The Synergy MCP server is used during development over stdio:

```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["@synergy-design-system/mcp"]
}
```

The MCP server is a development tool and is not included in production
containers.

## 16. Container Build

The backend uses a multi-stage image built from the uv-managed lock file. The
runtime image contains only runtime dependencies, application code, and the
migration tooling needed at startup.

The web image uses a Node build stage to compile Angular. Its runtime stage is
Caddy and contains only the compiled frontend, the Caddy configuration, and
required runtime files.

Both containers run as non-root users where supported by their base images.
Images are pinned to explicit major or immutable versions rather than `latest`.

## 17. Docker Compose Deployment

Docker Compose runs two services:

- `web` serves Angular through Caddy and proxies API and authentication paths.
- `backend` runs one Uvicorn worker, APScheduler, and SQLite access.

Only Caddy publishes a host port. The backend is reachable only on the internal
Compose network. Caddy provides the common browser origin for Angular, REST,
and OIDC callbacks.

The SQLite data directory is a host bind mount using short volume syntax:

```yaml
volumes:
  - "${ARA_DATA_DIR:-./data}:/app/data:rw"
```

The custom certificate directory is mounted read-only:

```yaml
volumes:
  - "${ARA_CERTIFICATE_DIR:-./certificates}:/certificates:ro"
```

The production Caddy configuration loads the certificate and key from that
directory. Certificate replacement requires a Caddy reload or container
restart. Local development may use a separate Caddy configuration or Compose
override rather than making production TLS behavior ambiguous.

Caddy serves the Angular application with SPA fallback and proxies `/api/*`
and `/auth/*` to the backend. Compression is enabled.

## 18. Docker Secrets

Sensitive values are exposed to the backend as files under `/run/secrets`, not
as literal Compose values or browser-visible configuration. Initial secrets
are:

- OIDC client secret
- application session secret
- bootstrap Owner subject allowlist

The backend configuration supports `_FILE` settings such as
`ARA_OIDC_CLIENT_SECRET_FILE`. Non-sensitive values remain environment
variables.

Compose secrets outside Swarm are mounted files and are not automatically
encrypted by Docker. Host file permissions, backup controls, and deployment
access remain part of the security model.

## 19. Operations

The backend exposes liveness and readiness information. Caddy depends on the
backend health check for orderly startup, while all services use an appropriate
restart policy.

The data directory and secret directory must exist before deployment. The data
directory must be writable by the backend container's runtime UID.

Consistent online backups use SQLite's backup facility rather than copying a
live database file directly. Restore procedures must be tested.

Structured logs go to standard output and include correlation identifiers but
must not contain tokens, session cookies, secrets, or complete OIDC claims.

## 20. Quality Gates

Backend changes must pass Ruff formatting and linting, ty type checking, and
the automated test suite. Frontend changes must pass formatting, linting, unit
tests, and a production build.

Tests must cover authorization boundaries, claim mapping, archive behavior,
reservation interval boundaries, open-ended reservations, extension
conflicts, audit visibility, scheduler idempotency, and retention cleanup.

End-to-end tests cover the critical authenticated reservation and return flow.

## 21. Explicitly Deferred Work

The following capabilities are intentionally deferred:

- PostgreSQL and horizontally scaled API instances
- a separate scheduler or task-queue service
- Web Push while the application is closed
- Webex bot delivery
- storage or disclosure of remote-system credentials
- approval workflows for reservations
