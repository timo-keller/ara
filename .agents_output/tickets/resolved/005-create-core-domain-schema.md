# 005 - Create core domain schema

## Goal

Create the initial persistence schema for ARA domain records.

## Scope

- Add models for users, groups, role mappings, assets, reservations,
  notifications, and audit events.
- Add identifiers, UTC timestamps, relationships, and required indexes.
- Represent archived records without deleting them.
- Create and test the Alembic migration.

## Acceptance Criteria

- A clean database upgrades to the complete initial schema.
- Foreign keys and uniqueness constraints enforce basic integrity.
- Asset and group archive state is represented explicitly.
- Downgrade and subsequent upgrade work on an empty test database.

## Dependencies

- Ticket 004
