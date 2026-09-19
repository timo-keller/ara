import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.core.errors import DomainError
from ara.domain.models import Asset, Group, Reservation, ReservationStatus, User
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.services.reservations import ReservationService


@pytest.fixture
async def reservation_database(
    tmp_path,
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], uuid.UUID, uuid.UUID]]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        group = Group(name="Lab")
        user = User(oidc_issuer="https://issuer.example", oidc_subject="user")
        session.add_all([group, user])
        await session.flush()
        asset = Asset(group_id=group.id, name="Laptop", asset_type="computer")
        session.add(asset)
        await session.commit()
        asset_id, user_id = asset.id, user.id
    try:
        yield factory, asset_id, user_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bounded_intervals_cover_past_current_future_and_adjacency(
    reservation_database: tuple[async_sessionmaker[AsyncSession], uuid.UUID, uuid.UUID],
) -> None:
    factory, asset_id, user_id = reservation_database
    instant = datetime.now(UTC)

    async with factory() as session:
        service = ReservationService(session)
        await service.create(
            asset_id=asset_id,
            user_id=user_id,
            starts_at=instant - timedelta(hours=6),
            ends_at=instant - timedelta(hours=4),
        )
        await service.create(
            asset_id=asset_id,
            user_id=user_id,
            starts_at=instant - timedelta(hours=4),
            ends_at=instant + timedelta(hours=3),
        )
        await service.create(
            asset_id=asset_id,
            user_id=user_id,
            starts_at=instant + timedelta(hours=3),
            ends_at=instant + timedelta(hours=5),
        )

        with pytest.raises(DomainError, match="already reserved") as error:
            await service.create(
                asset_id=asset_id,
                user_id=user_id,
                starts_at=instant + timedelta(hours=2),
                ends_at=instant + timedelta(hours=4),
            )
    assert error.value.code == "reservation_conflict"
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_open_ended_intervals_and_lifecycle_self_exclusion(
    reservation_database: tuple[async_sessionmaker[AsyncSession], uuid.UUID, uuid.UUID],
) -> None:
    factory, asset_id, user_id = reservation_database
    instant = datetime(2030, 1, 1, tzinfo=UTC)

    async with factory() as session:
        service = ReservationService(session)
        reservation = await service.create(
            asset_id=asset_id,
            user_id=user_id,
            starts_at=instant,
            ends_at=None,
        )

        with pytest.raises(DomainError, match="already reserved"):
            await service.ensure_available(
                asset_id=asset_id,
                starts_at=instant + timedelta(days=1),
                ends_at=instant + timedelta(days=2),
            )
        # An interval before an open-ended reservation may be exactly adjacent.
        await service.ensure_available(
            asset_id=asset_id,
            starts_at=instant - timedelta(days=1),
            ends_at=instant,
        )
        # Future lifecycle updates can query their own unchanged interval.
        await service.ensure_available(
            asset_id=asset_id,
            starts_at=reservation.starts_at,
            ends_at=reservation.ends_at,
            exclude_reservation_id=reservation.id,
        )
        reservation.status = ReservationStatus.RETURNED
        await session.commit()
        await service.ensure_available(
            asset_id=asset_id,
            starts_at=instant + timedelta(days=1),
            ends_at=None,
        )


@pytest.mark.asyncio
async def test_interval_validation_requires_utc_and_a_positive_range(
    reservation_database: tuple[async_sessionmaker[AsyncSession], uuid.UUID, uuid.UUID],
) -> None:
    factory, asset_id, user_id = reservation_database
    instant = datetime(2030, 1, 1, tzinfo=UTC)
    invalid_cases = [
        (
            instant.replace(tzinfo=None),
            instant + timedelta(hours=1),
            "timestamp_not_utc",
        ),
        (
            instant.astimezone(timezone(timedelta(hours=2))),
            instant + timedelta(hours=1),
            "timestamp_not_utc",
        ),
        (instant, instant, "invalid_interval"),
    ]

    async with factory() as session:
        service = ReservationService(session)
        for starts_at, ends_at, code in invalid_cases:
            with pytest.raises(DomainError) as error:
                await service.create(
                    asset_id=asset_id,
                    user_id=user_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
            assert error.value.code.endswith(code)


@pytest.mark.asyncio
async def test_concurrent_sqlite_writers_create_only_one_overlapping_reservation(
    reservation_database: tuple[async_sessionmaker[AsyncSession], uuid.UUID, uuid.UUID],
) -> None:
    factory, asset_id, user_id = reservation_database
    instant = datetime(2030, 1, 1, tzinfo=UTC)

    async def create() -> str:
        async with factory() as session:
            try:
                await ReservationService(session).create(
                    asset_id=asset_id,
                    user_id=user_id,
                    starts_at=instant,
                    ends_at=instant + timedelta(hours=1),
                )
            except DomainError as error:
                assert error.code == "reservation_conflict"
                return "conflict"
            return "created"

    assert sorted(await asyncio.gather(create(), create())) == ["conflict", "created"]
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Reservation)) == 1
