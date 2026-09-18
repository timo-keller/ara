# 004 - Configure async database access

## Goal

Establish asynchronous SQLAlchemy access and Alembic migrations.

## Scope

- Create the async engine and request-scoped session factory.
- Enable SQLite foreign keys, WAL mode, and busy timeout.
- Configure Alembic against shared model metadata.
- Add an initial connectivity test and migration smoke test.

## Acceptance Criteria

- FastAPI dependencies provide and close an AsyncSession correctly.
- SQLite connection settings are verified by tests.
- Alembic can upgrade a new database to the latest revision.
- Application code does not create tables directly.

## Dependencies

- Ticket 003
