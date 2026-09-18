# 032 - Create Compose deployment

## Goal

Run the complete application with Caddy, FastAPI, bind mounts, and secrets.

## Scope

- Add `web` and `backend` services on an internal network.
- Publish only the Caddy port.
- Mount data as `${ARA_DATA_DIR:-./data}:/app/data:rw`.
- Mount certificates as a read-only short-syntax bind mount.
- Define file-backed OIDC, session, and Owner Docker secrets.

## Acceptance Criteria

- Compose starts from documented host directories and secret files.
- Backend health gates the web service startup.
- SQLite data survives container replacement.
- Secret values are absent from the Compose model and frontend assets.
- Custom certificate replacement and Caddy reload are documented.

## Dependencies

- Ticket 030
- Ticket 031
