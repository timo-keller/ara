"""Asynchronous database engine and FastAPI session dependency."""

from collections.abc import AsyncIterator, Callable
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from ara.core.config import get_settings

SQLITE_BUSY_TIMEOUT_MS = 5_000


class Base(DeclarativeBase):
    """Base class whose metadata is shared by models and Alembic."""


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async engine with the SQLite settings required by ARA."""
    engine = create_async_engine(
        database_url,
        connect_args={"timeout": SQLITE_BUSY_TIMEOUT_MS / 1_000},
    )
    if engine.url.get_backend_name() == "sqlite":
        _configure_sqlite(engine.sync_engine)
    return engine


def _configure_sqlite(engine: Engine) -> None:
    """Configure every SQLite connection, including connections opened later."""

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create sessions that are scoped to one request or scheduler job."""
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the process-wide engine configured from validated settings."""
    return create_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide factory used by the request dependency."""
    return create_session_factory(get_engine())


def session_dependency(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    """Build a FastAPI dependency that always closes its request session."""

    async def get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    return get_session


async def get_session() -> AsyncIterator[AsyncSession]:
    """Provide one closed-after-response session to FastAPI request handlers."""
    async with get_session_factory()() as session:
        yield session
