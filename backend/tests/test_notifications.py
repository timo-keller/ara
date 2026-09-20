import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from asgi_client import ASGIClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.domain.models import (
    Asset,
    Group,
    Notification,
    Reservation,
    ReservationStatus,
    User,
)
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.main import create_app
from ara.services.notifications import NotificationService


@pytest.fixture
def notification_client(
    tmp_path,
) -> Iterator[tuple[ASGIClient, async_sessionmaker[AsyncSession], User, User]]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)

    async def initialise() -> tuple[User, User]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            users = [
                User(oidc_issuer="https://issuer.example", oidc_subject="first"),
                User(oidc_issuer="https://issuer.example", oidc_subject="second"),
            ]
            session.add_all(users)
            await session.commit()
            return users[0], users[1]

    first, second = asyncio.run(initialise())
    current = {"user": first}
    app = create_app()

    async def get_user() -> User:
        return current["user"]

    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def csrf() -> None:
        return None

    app.dependency_overrides[auth_router.require_authenticated_user] = get_user
    app.dependency_overrides[auth_router.require_csrf] = csrf
    app.dependency_overrides[auth_router.get_session] = get_test_session
    with ASGIClient(app) as client:
        yield client, factory, first, second
    asyncio.run(engine.dispose())


@pytest.mark.asyncio
async def test_reminders_are_idempotent_catch_up_and_exclude_terminal_reservations(
    tmp_path,
) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)
    now = datetime.now(UTC)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        user = User(oidc_issuer="https://issuer.example", oidc_subject="user")
        group = Group(name="Group")
        session.add_all((user, group))
        await session.flush()
        asset = Asset(group_id=group.id, asset_type="laptop", name="Laptop")
        session.add(asset)
        await session.flush()
        reservations = [
            Reservation(
                user_id=user.id,
                asset_id=asset.id,
                starts_at=now - timedelta(hours=2),
                ends_at=now - timedelta(minutes=30),
            ),
            Reservation(
                user_id=user.id,
                asset_id=asset.id,
                starts_at=now - timedelta(hours=2),
                ends_at=None,
            ),
            Reservation(
                user_id=user.id,
                asset_id=asset.id,
                starts_at=now - timedelta(hours=2),
                ends_at=now - timedelta(minutes=30),
                status=ReservationStatus.RETURNED,
            ),
            Reservation(
                user_id=user.id,
                asset_id=asset.id,
                starts_at=now - timedelta(hours=2),
                ends_at=now + timedelta(minutes=70),
            ),
        ]
        session.add_all(reservations)
        await session.commit()

        service = NotificationService(session)
        assert await service.generate_due_reminders((60, 15, 0)) == 3
        assert await service.generate_due_reminders((60, 15, 0)) == 0
        notifications = list(await session.scalars(select(Notification)))
        assert len(notifications) == 3
        assert all(
            notification.reservation_id != reservations[1].id
            for notification in notifications
        )
    await engine.dispose()


def test_notifications_are_private_paginated_and_read_idempotently(
    notification_client,
) -> None:  # type: ignore[no-untyped-def]
    client, factory, first, second = notification_client

    async def add_notifications() -> tuple[Notification, Notification]:
        async with factory() as session:
            notifications = [
                Notification(user_id=first.id, kind="first", title="First"),
                Notification(user_id=first.id, kind="second", title="Second"),
                Notification(user_id=second.id, kind="other", title="Other"),
            ]
            session.add_all(notifications)
            await session.commit()
            return notifications[0], notifications[2]

    own, other = asyncio.run(add_notifications())
    listed = client.get("/api/notifications?limit=1")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert len(listed.json()["items"]) == 1

    assert client.post(f"/api/notifications/{other.id}/read").status_code == 404
    first_read = client.post(f"/api/notifications/{own.id}/read")
    assert first_read.status_code == 200
    read_at = first_read.json()["read_at"]
    assert client.post(f"/api/notifications/{own.id}/read").json()["read_at"] == read_at

    mark_all = client.post("/api/notifications/read")
    assert mark_all.status_code == 204
    assert client.post("/api/notifications/read").status_code == 204
    all_read = client.get("/api/notifications").json()["items"]
    assert all(notification["read_at"] is not None for notification in all_read)
