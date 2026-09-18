# 034 - Document deployment and operations

## Goal

Provide reproducible deployment, backup, restore, and upgrade procedures.

## Scope

- Document host directory ownership and secret creation.
- Document certificate installation and Caddy reload.
- Document SQLite online backup and tested restore.
- Document migration, rollback limitations, health checks, and logs.

## Acceptance Criteria

- An operator can deploy ARA without reading source code.
- Backup instructions do not copy an uncoordinated live database file.
- Secret rotation and certificate replacement are covered.
- The one-container and one-worker backend constraint is explicit.

## Dependencies

- Ticket 032
- Ticket 033
