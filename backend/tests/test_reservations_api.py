import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from asgi_client import ASGIClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.core.errors import DomainError
from ara.domain.models import Asset, AuditEvent, Group, GroupRole, Reservation, User
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.main import create_app
from ara.services.authorization import EffectiveRoles
from ara.services.reservations import ReservationService

ApiClient = tuple[
    ASGIClient,
    async_sessionmaker[AsyncSession],
    User,
    dict[str, EffectiveRoles],
]


@pytest.fixture
def reservation_api_client(tmp_path: Path) -> Iterator[ApiClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)

    async def initialise() -> User:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            user = User(oidc_issuer="https://issuer.example", oidc_subject="user")
            session.add(user)
            await session.commit()
            return user

    user = asyncio.run(initialise())
    app = create_app()
    roles = {"value": EffectiveRoles(is_owner=False, group_roles={})}

    async def get_user() -> User:
        return user

    async def get_roles() -> EffectiveRoles:
        return roles["value"]

    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def csrf() -> None:
        return None

    app.dependency_overrides[auth_router.require_authenticated_user] = get_user
    app.dependency_overrides[group_router.get_effective_roles] = get_roles
    app.dependency_overrides[auth_router.require_csrf] = csrf
    app.dependency_overrides[auth_router.get_session] = get_test_session
    with ASGIClient(app) as client:
        yield client, factory, user, roles
    asyncio.run(engine.dispose())


def test_reservation_api_creation_access_schedule_and_pagination(
    reservation_api_client: ApiClient,
) -> None:
    client, factory, user, roles = reservation_api_client
    lab, other_laptop, archived_group, laptop, archived_laptop = _fixtures(factory)
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.USER}
    )
    starts_at = datetime(2030, 1, 2, 10, tzinfo=UTC)

    assert (
        client.post("/api/reservations", json={"asset_id": laptop}).status_code == 422
    )
    assert (
        client.post(
            "/api/reservations",
            json={
                "asset_id": laptop,
                "starts_at": "2030-01-02T10:00:00+02:00",
                "ends_at": "2030-01-02T11:00:00+02:00",
            },
        ).status_code
        == 422
    )
    created = client.post(
        "/api/reservations",
        json={
            "asset_id": laptop,
            "starts_at": starts_at.isoformat().replace("+00:00", "Z"),
            "ends_at": (starts_at + timedelta(hours=1))
            .isoformat()
            .replace("+00:00", "Z"),
        },
    )
    assert created.status_code == 201
    assert created.json()["user_id"] == str(user.id)
    assert created.json()["starts_at"].endswith("Z") or created.json()[
        "starts_at"
    ].endswith("+00:00")
    assert (
        client.post(
            "/api/reservations",
            json={
                "asset_id": laptop,
                "starts_at": starts_at.isoformat(),
                "ends_at": (starts_at + timedelta(hours=2)).isoformat(),
            },
        ).status_code
        == 409
    )

    assert client.get(f"/api/assets/{other_laptop}/reservations").status_code == 403
    assert (
        client.post(
            "/api/reservations",
            json={"asset_id": archived_laptop, "starts_at": starts_at.isoformat()},
        ).status_code
        == 409
    )
    roles["value"] = EffectiveRoles(is_owner=True, group_roles={})
    assert (
        client.post(
            "/api/reservations",
            json={"asset_id": archived_group, "starts_at": starts_at.isoformat()},
        ).status_code
        == 409
    )

    mine = client.get("/api/reservations/mine", params={"limit": 1}).json()
    assert mine["total"] == 1
    assert len(mine["items"]) == 1
    assert mine["items"][0]["asset_id"] == laptop
    assert mine["items"][0]["asset_name"] == "Laptop"
    assert mine["items"][0]["asset_type"] == "computer"
    schedule = client.get(
        f"/api/assets/{laptop}/reservations", params={"limit": 1}
    ).json()
    assert schedule["total"] == 1
    assert schedule["items"][0]["id"] == created.json()["id"]


def test_reservation_api_clamps_a_past_start_and_audits_effective_interval(
    reservation_api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _, roles = reservation_api_client
    lab, _, _, laptop, _ = _fixtures(factory)
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.USER}
    )
    now = datetime(2030, 1, 2, 10, tzinfo=UTC)
    monkeypatch.setattr("ara.services.reservations.utc_now", lambda: now)
    ends_at = now + timedelta(hours=1)

    created = client.post(
        "/api/reservations",
        json={
            "asset_id": laptop,
            "starts_at": "2020-01-01T00:00:00Z",
            "ends_at": ends_at.isoformat().replace("+00:00", "Z"),
        },
    )

    assert created.status_code == 201
    assert datetime.fromisoformat(created.json()["starts_at"]) == now
    assert datetime.fromisoformat(created.json()["ends_at"]) == ends_at

    async def assert_persisted() -> None:
        async with factory() as session:
            reservation = await session.get(
                Reservation, uuid.UUID(created.json()["id"])
            )
            assert reservation is not None
            assert reservation.starts_at == now
            assert reservation.ends_at == ends_at
            event = await session.scalar(select(AuditEvent))
            assert event is not None
            assert event.after_state is not None
            assert event.after_state["starts_at"] == now.isoformat()
            assert event.after_state["ends_at"] == ends_at.isoformat()

    asyncio.run(assert_persisted())


def test_own_reservation_asset_names_follow_asset_visibility(
    reservation_api_client: ApiClient,
) -> None:
    client, factory, user, roles = reservation_api_client
    lab, _, _, laptop, _ = _fixtures(factory)
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.USER}
    )
    starts_at = datetime(2030, 1, 2, 10, tzinfo=UTC)
    created = client.post(
        "/api/reservations",
        json={"asset_id": laptop, "starts_at": starts_at.isoformat()},
    )
    assert created.status_code == 201

    visible = client.get("/api/reservations/mine").json()["items"][0]
    assert visible["asset_id"] == laptop
    assert visible["asset_name"] == "Laptop"
    assert visible["asset_type"] == "computer"

    roles["value"] = EffectiveRoles(is_owner=False, group_roles={})
    scoped = client.get("/api/reservations/mine").json()["items"][0]
    assert scoped["asset_id"] == laptop
    assert scoped["asset_name"] is None
    assert scoped["asset_type"] is None

    async def archive_asset() -> None:
        async with factory() as session:
            asset = await session.get(Asset, uuid.UUID(laptop))
            assert asset is not None
            asset.archived_at = datetime(2030, 1, 1, tzinfo=UTC)
            await session.commit()

    asyncio.run(archive_asset())
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.USER}
    )
    unavailable = client.get("/api/reservations/mine").json()["items"][0]
    assert unavailable["asset_id"] == laptop
    assert unavailable["asset_name"] is None
    assert unavailable["asset_type"] is None


def test_reservation_lifecycle_api_routes(
    reservation_api_client: ApiClient,
) -> None:
    client, factory, user, roles = reservation_api_client
    lab, _, _, laptop, _ = _fixtures(factory)
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.USER}
    )
    now = datetime.now(UTC)
    current = client.post(
        "/api/reservations",
        json={
            "asset_id": laptop,
            "starts_at": (now - timedelta(seconds=30)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert current.status_code == 201
    reservation_id = current.json()["id"]
    extended = client.post(
        f"/api/reservations/{reservation_id}/extend",
        json={"ends_at": (now + timedelta(hours=2)).isoformat()},
    )
    assert extended.status_code == 200
    assert extended.json()["status"] == "active"
    returned = client.post(f"/api/reservations/{reservation_id}/return")
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    assert client.post(f"/api/reservations/{reservation_id}/return").status_code == 409

    future = client.post(
        "/api/reservations",
        json={
            "asset_id": laptop,
            "starts_at": (now + timedelta(hours=3)).isoformat(),
            "ends_at": (now + timedelta(hours=4)).isoformat(),
        },
    )
    assert future.status_code == 201
    cancelled = client.post(f"/api/reservations/{future.json()['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert (
        client.post(
            f"/api/reservations/{future.json()['id']}/extend",
            json={"ends_at": (now + timedelta(hours=5)).isoformat()},
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/reservations/{future.json()['id']}/end").status_code == 403
    )


@pytest.mark.asyncio
async def test_current_user_creation_checks_group_and_asset_inside_write_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        just_before_asset = Asset(group_id=group.id, name="Phone", asset_type="phone")
        open_ended_asset = Asset(group_id=group.id, name="Tablet", asset_type="tablet")
        conflict_asset = Asset(group_id=group.id, name="Monitor", asset_type="monitor")
        session.add_all([asset, just_before_asset, open_ended_asset, conflict_asset])
        await session.commit()
        conflict_asset_id = conflict_asset.id
        user_id = user.id

        # Simulate request authentication/role-resolution reads before service
        # entry. The service must end this implicit transaction before BEGIN
        # IMMEDIATE, then validate and insert under that write lock.
        await session.get(Asset, asset.id)
        service = ReservationService(session)
        roles = EffectiveRoles(is_owner=False, group_roles={group.id: GroupRole.USER})
        now = datetime(2030, 1, 2, 10, tzinfo=UTC)
        monkeypatch.setattr("ara.services.reservations.utc_now", lambda: now)

        reservation = await service.create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(hours=1),
        )
        assert reservation.starts_at == now
        assert reservation.ends_at == now + timedelta(hours=1)
        assert reservation.user_id == user.id
        assert await session.get(Reservation, reservation.id) is not None

        just_before = await service.create_for_current_user(
            roles,
            asset_id=just_before_asset.id,
            user_id=user.id,
            starts_at=now - timedelta(microseconds=1),
            ends_at=now + timedelta(hours=1),
        )
        assert just_before.starts_at == now

        future = await service.create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
        )
        assert future.starts_at == now + timedelta(hours=1)

        open_ended = await service.create_for_current_user(
            roles,
            asset_id=open_ended_asset.id,
            user_id=user.id,
            starts_at=now - timedelta(days=1),
            ends_at=None,
        )
        assert open_ended.starts_at == now
        assert open_ended.ends_at is None

        audit_count = await session.scalar(select(func.count()).select_from(AuditEvent))
        with pytest.raises(DomainError) as error:
            await service.create_for_current_user(
                roles,
                asset_id=conflict_asset_id,
                user_id=user_id,
                starts_at=now - timedelta(hours=1),
                ends_at=now,
            )
        assert error.value.code == "reservation_invalid_interval"
        assert await session.scalar(select(func.count()).select_from(Reservation)) == 4
        assert (
            await session.scalar(select(func.count()).select_from(AuditEvent))
            == audit_count
        )

        await service.create(
            asset_id=conflict_asset_id,
            user_id=user_id,
            starts_at=now,
            ends_at=now + timedelta(hours=1),
        )
        with pytest.raises(DomainError) as error:
            await service.create_for_current_user(
                roles,
                asset_id=conflict_asset_id,
                user_id=user_id,
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(hours=2),
            )
        assert error.value.code == "reservation_conflict"
    await engine.dispose()


def _fixtures(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[str, str, str, str, str]:
    async def create() -> tuple[str, str, str, str, str]:
        async with factory() as session:
            lab = Group(name="Lab")
            other = Group(name="Other")
            archived = Group(name="Archived")
            session.add_all([lab, other, archived])
            await session.flush()
            laptop = Asset(group_id=lab.id, name="Laptop", asset_type="computer")
            other_laptop = Asset(
                group_id=other.id, name="Other laptop", asset_type="computer"
            )
            archived_laptop = Asset(
                group_id=lab.id,
                name="Archived laptop",
                asset_type="computer",
                archived_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
            archived_asset = Asset(
                group_id=archived.id, name="Old", asset_type="computer"
            )
            session.add_all([laptop, other_laptop, archived_laptop, archived_asset])
            archived.archived_at = datetime(2030, 1, 1, tzinfo=UTC)
            await session.commit()
            return (
                str(lab.id),
                str(other_laptop.id),
                str(archived_asset.id),
                str(laptop.id),
                str(archived_laptop.id),
            )

    return asyncio.run(create())
