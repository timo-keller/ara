import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from asgi_client import ASGIClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.api.routers import role_mappings as mapping_router
from ara.core.errors import DomainError
from ara.domain.models import ApplicationSession, Group, GroupRole, RoleMapping, utc_now
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.main import create_app
from ara.services.authorization import EffectiveRoles
from ara.services.role_mappings import RoleMappingService

ApiClient = tuple[
    ASGIClient, async_sessionmaker[AsyncSession], dict[str, EffectiveRoles]
]


@pytest.fixture
def role_mapping_api_client(tmp_path) -> Iterator[ApiClient]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)

    async def initialise() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(initialise())
    app = create_app()
    roles = {"value": EffectiveRoles(is_owner=True, group_roles={})}
    application_session = ApplicationSession(
        user_id=uuid.uuid4(),
        csrf_token_hash="unused",
        oidc_claims={"groups": ["ara-lab-users"], "private_claim": "never expose"},
        expires_at=utc_now(),
    )

    async def get_roles() -> EffectiveRoles:
        return roles["value"]

    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def get_application_session() -> ApplicationSession:
        return application_session

    async def csrf() -> None:
        return None

    app.dependency_overrides[group_router.get_effective_roles] = get_roles
    app.dependency_overrides[mapping_router.get_current_application_session] = (
        get_application_session
    )
    app.dependency_overrides[auth_router.require_csrf] = csrf
    app.dependency_overrides[auth_router.get_session] = get_test_session
    with ASGIClient(app) as client:
        yield client, factory, roles
    asyncio.run(engine.dispose())


def test_role_mapping_api_owner_lifecycle_and_safe_expression_testing(
    role_mapping_api_client: ApiClient,
) -> None:
    client, factory, roles = role_mapping_api_client
    first_id, second_id = _create_groups(factory)

    created = client.post(
        "/api/role-mappings",
        json={
            "group_id": first_id,
            "expression": "contains(groups, 'ara-lab-users')",
            "role": "user",
            "priority": 2,
        },
    )
    assert created.status_code == 201
    mapping = created.json()
    assert mapping["group_id"] == first_id
    assert mapping["enabled"] is True

    updated = client.patch(
        f"/api/role-mappings/{mapping['id']}",
        json={"group_id": second_id, "role": "group_admin", "priority": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["group_id"] == second_id
    assert updated.json()["role"] == "group_admin"

    listed = client.get("/api/role-mappings", params={"offset": 0, "limit": 1})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert [item["id"] for item in listed.json()["items"]] == [mapping["id"]]

    disabled = client.post(f"/api/role-mappings/{mapping['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    archived = client.post(f"/api/role-mappings/{mapping['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert (
        client.get("/api/role-mappings", params={"archived": "false"}).json()["total"]
        == 0
    )
    assert (
        client.get("/api/role-mappings", params={"archived": "true"}).json()["total"]
        == 1
    )

    tested = client.post(
        "/api/role-mappings/test",
        json={"expression": "contains(groups, 'ara-lab-users')"},
    )
    assert tested.status_code == 200
    assert tested.json() == {"matches": True}
    assert "private_claim" not in tested.text
    assert _mapping_count(factory) == 1

    invalid = client.post("/api/role-mappings/test", json={"expression": "contains("})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_role_mapping_expression"
    non_boolean = client.post("/api/role-mappings/test", json={"expression": "groups"})
    assert non_boolean.status_code == 400
    assert non_boolean.json()["error"]["code"] == "role_mapping_expression_not_boolean"

    roles["value"] = EffectiveRoles(is_owner=False, group_roles={})
    assert client.get("/api/role-mappings").status_code == 403
    assert (
        client.post(
            "/api/role-mappings/test", json={"expression": "`true`"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/role-mappings",
            json={"group_id": first_id, "expression": "`true`", "role": "user"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/role-mappings/{mapping['id']}", json={"priority": 0}
        ).status_code
        == 403
    )
    assert client.post(f"/api/role-mappings/{mapping['id']}/disable").status_code == 403
    assert client.post(f"/api/role-mappings/{mapping['id']}/archive").status_code == 403


async def test_role_mapping_service_rejects_missing_or_archived_groups_and_non_booleans(
    database_session: AsyncSession,
) -> None:
    owner = EffectiveRoles(is_owner=True, group_roles={})
    service = RoleMappingService(database_session)
    with pytest.raises(DomainError, match="Group not found"):
        await service.create(
            owner, group_id=uuid.uuid4(), expression="`true`", role=GroupRole.USER
        )

    group = Group(name="Archived")
    database_session.add(group)
    await database_session.commit()
    group.archived_at = group.created_at
    await database_session.commit()
    with pytest.raises(DomainError, match="Group is archived"):
        await service.create(
            owner, group_id=group.id, expression="`true`", role=GroupRole.USER
        )
    with pytest.raises(DomainError, match="must evaluate to a boolean"):
        await service.test_expression(owner, expression="groups", claims={"groups": []})


@pytest.fixture
async def database_session(tmp_path) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


def _create_groups(factory: async_sessionmaker[AsyncSession]) -> tuple[str, str]:
    async def create() -> tuple[str, str]:
        async with factory() as session:
            first, second = Group(name="First"), Group(name="Second")
            session.add_all([first, second])
            await session.commit()
            return str(first.id), str(second.id)

    return asyncio.run(create())


def _mapping_count(factory: async_sessionmaker[AsyncSession]) -> int:
    async def count() -> int:
        async with factory() as session:
            return (
                await session.scalar(select(func.count()).select_from(RoleMapping)) or 0
            )

    return asyncio.run(count())
