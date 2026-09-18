import sqlite3
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
from ara.database import (
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

    with sqlite3.connect(database_path) as connection:
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert version == ("0001_database_foundation",)
