import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.core.errors import DomainError
from ara.domain.models import Asset, Group, GroupRole, Reservation, User
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.main import create_app
from ara.services.authorization import EffectiveRoles
from ara.services.reservations import ReservationService

ApiClient = tuple[
    TestClient,
    async_sessionmaker[AsyncSession],
    User,
    dict[str, EffectiveRoles],
]


@pytest.fixture
def reservation_api_client(tmp_path) -> Iterator[ApiClient]:  # type: ignore[no-untyped-def]
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
    with TestClient(app) as client:
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
    past = client.post(
        "/api/reservations",
        json={"asset_id": laptop, "starts_at": "2020-01-01T00:00:00Z"},
    )
    assert past.status_code == 400
    assert past.json()["error"]["code"] == "reservation_start_in_past"
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
    schedule = client.get(
        f"/api/assets/{laptop}/reservations", params={"limit": 1}
    ).json()
    assert schedule["total"] == 1
    assert schedule["items"][0]["id"] == created.json()["id"]


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
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
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

        # Simulate request authentication/role-resolution reads before service
        # entry. The service must end this implicit transaction before BEGIN
        # IMMEDIATE, then validate and insert under that write lock.
        await session.get(Asset, asset.id)
        service = ReservationService(session)
        roles = EffectiveRoles(is_owner=False, group_roles={group.id: GroupRole.USER})
        with pytest.raises(DomainError, match="now or in the future") as error:
            await service.create_for_current_user(
                roles,
                asset_id=asset.id,
                user_id=user.id,
                starts_at=datetime(2020, 1, 1, tzinfo=UTC),
                ends_at=None,
            )
        assert error.value.code == "reservation_start_in_past"

        immediate = datetime.now(UTC)
        reservation = await service.create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=immediate,
            ends_at=immediate + timedelta(hours=1),
        )
        assert reservation.user_id == user.id
        assert await session.get(Reservation, reservation.id) is not None
        future = await service.create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=immediate + timedelta(hours=1),
            ends_at=immediate + timedelta(hours=2),
        )
        assert future.starts_at == immediate + timedelta(hours=1)
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
