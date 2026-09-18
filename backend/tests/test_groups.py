import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.core.errors import DomainError
from ara.domain.models import (
    Asset,
    Group,
    GroupRole,
    Reservation,
    ReservationStatus,
    User,
    utc_now,
)
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.main import create_app
from ara.services.authorization import EffectiveRoles
from ara.services.groups import GroupService


@pytest.fixture
async def database_session(tmp_path) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_group_service_enforces_access_and_preserves_blocked_archive(
    database_session: AsyncSession,
) -> None:
    group = Group(name="Lab")
    other = Group(name="Other")
    user = User(oidc_issuer="https://issuer.example", oidc_subject="member")
    database_session.add_all([group, other, user])
    await database_session.flush()
    asset = Asset(group_id=group.id, asset_type="device", name="Laptop")
    database_session.add(asset)
    await database_session.flush()
    reservation = Reservation(
        asset_id=asset.id,
        user_id=user.id,
        starts_at=utc_now() + timedelta(days=1),
    )
    database_session.add(reservation)
    await database_session.commit()

    service = GroupService(database_session)
    member = EffectiveRoles(is_owner=False, group_roles={group.id: GroupRole.USER})
    owner = EffectiveRoles(is_owner=True, group_roles={})

    assert (await service.get(member, group.id)).id == group.id
    with pytest.raises(DomainError, match="Authorization denied"):
        await service.get(member, other.id)
    with pytest.raises(DomainError, match="Authorization denied"):
        await service.update(
            member,
            group.id,
            name="Renamed",
            description=None,
            update_name=True,
            update_description=False,
        )
    with pytest.raises(DomainError, match="Group has unresolved reservations") as error:
        await service.archive(owner, group.id)
    assert error.value.status_code == 409
    await database_session.refresh(group)
    assert group.archived_at is None
    assert await database_session.get(Asset, asset.id) is not None
    assert await database_session.get(Reservation, reservation.id) is not None

    reservation.status = ReservationStatus.RETURNED
    await database_session.commit()
    archived = await service.archive(owner, group.id)
    assert archived.archived_at is not None
    assert (await service.reactivate(owner, group.id)).archived_at is None


ApiClient = tuple[
    TestClient, async_sessionmaker[AsyncSession], dict[str, EffectiveRoles]
]


@pytest.fixture
def group_api_client(tmp_path) -> Iterator[ApiClient]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)

    async def initialise() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(initialise())
    app = create_app()
    roles = {"value": EffectiveRoles(is_owner=True, group_roles={})}

    async def get_roles() -> EffectiveRoles:
        return roles["value"]

    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def csrf() -> None:
        return None

    app.dependency_overrides[group_router.get_effective_roles] = get_roles
    app.dependency_overrides[auth_router.require_csrf] = csrf
    app.dependency_overrides[auth_router.get_session] = get_test_session
    with TestClient(app) as client:
        yield client, factory, roles
    asyncio.run(engine.dispose())


def test_group_api_mutations_pagination_archiving_and_effective_reads(
    group_api_client: ApiClient,
) -> None:
    client, factory, roles = group_api_client
    created = client.post("/api/groups", json={"name": "Beta", "description": "B"})
    assert created.status_code == 201
    beta = created.json()
    assert beta["archived_at"] is None
    assert client.post("/api/groups", json={"name": "Alpha"}).status_code == 201
    assert client.post("/api/groups", json={"name": "Gamma"}).status_code == 201
    assert client.post("/api/groups", json={"name": "Alpha"}).status_code == 409

    page = client.get("/api/groups", params={"offset": 1, "limit": 1}).json()
    assert page["total"] == 3
    assert [item["name"] for item in page["items"]] == ["Beta"]
    updated = client.patch(f"/api/groups/{beta['id']}", json={"description": None})
    assert updated.status_code == 200
    assert updated.json()["description"] is None
    assert client.post(f"/api/groups/{beta['id']}/archive").status_code == 200
    assert client.get("/api/groups", params={"archived": "false"}).json()["total"] == 2
    assert client.get("/api/groups", params={"archived": "true"}).json()["total"] == 1
    assert client.get(f"/api/groups/{beta['id']}").status_code == 200
    reactivated = client.post(f"/api/groups/{beta['id']}/reactivate")
    assert reactivated.status_code == 200
    assert reactivated.json()["archived_at"] is None

    alpha_id = _group_id(factory, "Alpha")
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(alpha_id): GroupRole.GROUP_ADMIN}
    )
    assert client.post("/api/groups", json={"name": "Denied"}).status_code == 403
    visible = client.get("/api/groups", params={"archived": "true"}).json()
    assert visible["total"] == 0
    assert visible["items"] == []
    visible = client.get("/api/groups").json()
    assert visible["total"] == 1
    assert visible["items"][0]["name"] == "Alpha"
    assert client.get(f"/api/groups/{beta['id']}").status_code == 403


def _group_id(factory: async_sessionmaker[AsyncSession], name: str) -> str:
    async def get_id() -> str:
        async with factory() as session:
            group = await session.scalar(select(Group).where(Group.name == name))
            assert group is not None
            return str(group.id)

    return asyncio.run(get_id())
