import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Annotated

import pytest
from alembic.config import Config
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from ara.infrastructure.database import (
    SQLITE_BUSY_TIMEOUT_MS,
    create_engine,
    create_session_factory,
    session_dependency,
)


@pytest.mark.asyncio
async def test_sqlite_connections_enable_required_pragmas(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert await connection.scalar(text("PRAGMA journal_mode")) == "wal"
            assert (
                await connection.scalar(text("PRAGMA busy_timeout"))
                == SQLITE_BUSY_TIMEOUT_MS
            )

            await connection.execute(
                text("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            )
            await connection.execute(
                text("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
            )
            with pytest.raises(IntegrityError):
                await connection.execute(text("INSERT INTO child VALUES (1)"))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_fastapi_session_dependency_closes_request_session(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    checked_in = 0

    @event.listens_for(engine.sync_engine, "checkin")
    def count_checkins(*_args: object) -> None:
        nonlocal checked_in
        checked_in += 1

    get_request_session = session_dependency(create_session_factory(engine))
    app = FastAPI()

    @app.get("/")
    async def endpoint(
        session: Annotated[AsyncSession, Depends(get_request_session)],
    ) -> dict[str, int]:
        return {"value": (await session.scalar(text("SELECT 1"))) or 0}

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/")

        assert response.json() == {"value": 1}
        assert checked_in == 1
    finally:
        await engine.dispose()


def test_alembic_upgrades_a_fresh_database(tmp_path: Path) -> None:
    database_path = tmp_path / "ara.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert version == ("0004_session_oidc_claims",)
    assert {
        "users",
        "groups",
        "role_mappings",
        "assets",
        "reservations",
        "notifications",
        "audit_events",
        "application_sessions",
    } <= tables


def test_alembic_downgrade_and_subsequent_upgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "ara.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    with closing(sqlite3.connect(database_path)) as connection:
        tables_after_downgrade = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert (
        not {
            "users",
            "groups",
            "role_mappings",
            "assets",
            "reservations",
            "notifications",
            "audit_events",
            "application_sessions",
        }
        & tables_after_downgrade
    )

    command.upgrade(config, "head")
    with closing(sqlite3.connect(database_path)) as connection:
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert version == ("0004_session_oidc_claims",)


def test_core_schema_enforces_integrity_constraints(tmp_path: Path) -> None:
    database_path = tmp_path / "ara.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO users (id, oidc_issuer, oidc_subject) VALUES (?, ?, ?)",
            ("user-1", "https://issuer.example", "subject-1"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO users (id, oidc_issuer, oidc_subject) VALUES (?, ?, ?)",
                ("user-2", "https://issuer.example", "subject-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO assets (id, group_id, asset_type, name) "
                "VALUES (?, ?, ?, ?)",
                ("asset-1", "missing-group", "laptop", "Laptop 1"),
            )

        connection.execute(
            "INSERT INTO groups (id, name) VALUES (?, ?)", ("group-1", "Lab")
        )
        connection.execute(
            "INSERT INTO assets (id, group_id, asset_type, name) VALUES (?, ?, ?, ?)",
            ("asset-1", "group-1", "laptop", "Laptop 1"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO assets (id, group_id, asset_type, name) "
                "VALUES (?, ?, ?, ?)",
                ("asset-2", "group-1", "laptop", "Laptop 1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO reservations
                (id, asset_id, user_id, starts_at, ends_at, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "reservation-1",
                    "asset-1",
                    "user-1",
                    "2026-01-02 00:00:00",
                    "2026-01-01 00:00:00",
                    "active",
                ),
            )
