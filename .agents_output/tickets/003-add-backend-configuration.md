# 003 - Add backend configuration

## Goal

Provide typed runtime configuration with Docker-secret file support.

## Scope

- Add typed settings for database, public URL, OIDC, sessions, and retention.
- Resolve supported `_FILE` settings from `/run/secrets` paths.
- Validate required settings and reject conflicting direct and file values.
- Prevent secret values from appearing in representations or logs.

## Acceptance Criteria

- Non-sensitive values load from environment variables.
- OIDC, session, and Owner secrets load from files.
- Missing and unreadable secret files produce clear startup errors.
- Unit tests cover precedence and secret redaction.

## Dependencies

- Ticket 002
