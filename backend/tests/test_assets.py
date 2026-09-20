import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from asgi_client import ASGIClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.api.schemas.assets import _safe_metadata
from ara.domain.models import (
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

ApiClient = tuple[
    ASGIClient, async_sessionmaker[AsyncSession], dict[str, EffectiveRoles]
]


@pytest.fixture
def asset_api_client(tmp_path: Path) -> Iterator[ApiClient]:
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
    with ASGIClient(app) as client:
        yield client, factory, roles
    asyncio.run(engine.dispose())


def test_asset_api_roles_filters_pagination_archival_and_credentials(
    asset_api_client: ApiClient,
) -> None:
    client, factory, roles = asset_api_client
    lab, other, archived_group = _groups(factory)
    laptop = _create(client, lab, "Laptop", "computer", "fast Linux machine")
    _create(client, lab, "Alpha", "computer", "portable")
    beta = _create(client, other, "Beta", "phone", "test phone")
    _reserve_now(factory, str(beta["id"]))

    assert (
        client.post(
            "/api/assets",
            json={
                "group_id": lab,
                "name": "Bad",
                "asset_type": "computer",
                "password": "x",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/assets",
            json={
                "group_id": lab,
                "name": "Nested bad",
                "asset_type": "computer",
                "operational_metadata": {"connection": {"api-token": "x"}},
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/assets",
            json={
                "group_id": archived_group,
                "name": "Blocked",
                "asset_type": "computer",
            },
        ).status_code
        == 409
    )

    page = client.get("/api/assets", params={"offset": 1, "limit": 1}).json()
    assert page["total"] == 3
    assert [item["name"] for item in page["items"]] == ["Beta"]
    assert client.get("/api/assets", params={"group_id": lab}).json()["total"] == 2
    assert (
        client.get("/api/assets", params={"asset_type": "phone"}).json()["total"] == 1
    )
    assert client.get("/api/assets", params={"text": "LINUX"}).json()["total"] == 1
    assert client.get("/api/assets", params={"availability": "reserved"}).json()[
        "items"
    ][0] == {
        **beta,
        "availability": "reserved",
        "reserved_by_display_name": "Unknown user",
    }
    available_items = client.get(
        "/api/assets", params={"availability": "available"}
    ).json()["items"]
    assert len(available_items) == 2
    assert {item["availability"] for item in available_items} == {"available"}

    updated = client.patch(
        f"/api/assets/{laptop['id']}",
        json={"remote_host": "lab.example", "access_instructions": "Use SSH"},
    )
    assert updated.status_code == 200
    assert updated.json()["remote_host"] == "lab.example"
    assert client.post(f"/api/assets/{laptop['id']}/archive").status_code == 200
    assert client.get("/api/assets").json()["total"] == 2
    assert client.get("/api/assets", params={"archived": "true"}).json()["total"] == 1
    assert client.post(f"/api/assets/{beta['id']}/archive").status_code == 200

    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.USER}
    )
    assert client.get(f"/api/assets/{laptop['id']}").status_code == 404
    assert client.get("/api/assets", params={"archived": "true"}).json()["total"] == 0
    assert client.get("/api/assets").json()["total"] == 1
    assert client.get("/api/assets", params={"group_id": other}).json()["total"] == 0
    assert client.post(f"/api/assets/{laptop['id']}/reactivate").status_code == 403

    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(lab): GroupRole.GROUP_ADMIN}
    )
    assert client.get(f"/api/assets/{laptop['id']}").status_code == 200
    # Administrative archival visibility is scoped to admin groups, not every
    # group in which the actor is merely a User.
    roles["value"] = EffectiveRoles(
        is_owner=False,
        group_roles={
            uuid.UUID(lab): GroupRole.GROUP_ADMIN,
            uuid.UUID(other): GroupRole.USER,
        },
    )
    assert client.get("/api/assets", params={"archived": "true"}).json()["total"] == 1
    assert client.post(f"/api/assets/{laptop['id']}/reactivate").status_code == 200
    rename = client.patch(f"/api/assets/{laptop['id']}", json={"name": "Renamed"})
    assert rename.status_code == 200
    assert (
        client.post(
            "/api/assets",
            json={"group_id": other, "name": "Denied", "asset_type": "computer"},
        ).status_code
        == 403
    )

    # An owner may archive a group but may not reactivate its asset until the
    # group is reactivated, preserving the archived-group creation constraint.
    roles["value"] = EffectiveRoles(is_owner=True, group_roles={})
    assert client.post(f"/api/assets/{laptop['id']}/archive").status_code == 200
    assert client.post(f"/api/groups/{lab}/archive").status_code == 200
    assert client.post(f"/api/assets/{laptop['id']}/reactivate").status_code == 409


def test_asset_response_metadata_removes_legacy_credential_like_keys() -> None:
    metadata = {
        "host": "lab",
        "password": "nope",
        "nested": {"api-token": "nope"},
    }
    assert _safe_metadata(metadata) == {
        "host": "lab",
        "nested": {},
    }


def test_asset_catalogue_current_reservation_holders_are_scoped_and_safe(
    asset_api_client: ApiClient,
) -> None:
    client, factory, roles = asset_api_client
    alpha, bravo, _archived = _groups(factory)
    named = _create(client, alpha, "Named", "device", "")
    fallback = _create(client, alpha, "Fallback", "device", "")
    _create(client, alpha, "Available", "device", "")
    future = _create(client, alpha, "Future", "device", "")
    ended = _create(client, alpha, "Ended", "device", "")
    terminal = _create(client, alpha, "Terminal", "device", "")
    open_ended = _create(client, bravo, "Open ended", "device", "")
    _seed_holder_reservations(
        factory,
        {
            "named": str(named["id"]),
            "fallback": str(fallback["id"]),
            "future": str(future["id"]),
            "ended": str(ended["id"]),
            "terminal": str(terminal["id"]),
            "open_ended": str(open_ended["id"]),
        },
    )

    items = {item["name"]: item for item in client.get("/api/assets").json()["items"]}
    assert items["Named"]["reserved_by_display_name"] == "Ada Lovelace"
    assert items["Fallback"]["reserved_by_display_name"] == "fallback@example.test"
    assert items["Open ended"]["reserved_by_display_name"] == "Unknown user"
    for name in ("Available", "Future", "Ended", "Terminal"):
        assert items[name]["availability"] == "available"
        assert items[name]["reserved_by_display_name"] is None

    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(alpha): GroupRole.GROUP_ADMIN}
    )
    admin_items = {
        item["name"]: item for item in client.get("/api/assets").json()["items"]
    }
    assert admin_items["Named"]["reserved_by_display_name"] == "Ada Lovelace"
    assert "Open ended" not in admin_items

    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={uuid.UUID(alpha): GroupRole.USER}
    )
    member_items = {
        item["name"]: item for item in client.get("/api/assets").json()["items"]
    }
    assert (
        member_items["Fallback"]["reserved_by_display_name"] == "fallback@example.test"
    )
    assert "Open ended" not in member_items
    assert client.get(f"/api/assets/{open_ended['id']}").status_code != 200


def _seed_holder_reservations(
    factory: async_sessionmaker[AsyncSession], asset_ids: dict[str, str]
) -> None:
    async def seed() -> None:
        async with factory() as session:
            now = utc_now()
            named = User(
                oidc_issuer="https://issuer.example",
                oidc_subject="named-holder",
                display_name="Ada Lovelace",
                email="not-disclosed@example.test",
            )
            fallback = User(
                oidc_issuer="https://issuer.example",
                oidc_subject="fallback-holder",
                display_name="  ",
                email="fallback@example.test",
            )
            unknown = User(
                oidc_issuer="https://issuer.example", oidc_subject="unknown-holder"
            )
            session.add_all([named, fallback, unknown])
            session.add_all(
                [
                    Reservation(
                        asset_id=uuid.UUID(asset_ids["named"]),
                        user=named,
                        starts_at=now - timedelta(minutes=1),
                        ends_at=now + timedelta(minutes=1),
                    ),
                    Reservation(
                        asset_id=uuid.UUID(asset_ids["fallback"]),
                        user=fallback,
                        starts_at=now - timedelta(minutes=1),
                        ends_at=now + timedelta(minutes=1),
                    ),
                    Reservation(
                        asset_id=uuid.UUID(asset_ids["future"]),
                        user=named,
                        starts_at=now + timedelta(minutes=1),
                        ends_at=now + timedelta(minutes=2),
                    ),
                    Reservation(
                        asset_id=uuid.UUID(asset_ids["ended"]),
                        user=named,
                        starts_at=now - timedelta(minutes=2),
                        ends_at=now,
                    ),
                    Reservation(
                        asset_id=uuid.UUID(asset_ids["terminal"]),
                        user=named,
                        starts_at=now - timedelta(minutes=1),
                        ends_at=now + timedelta(minutes=1),
                        status=ReservationStatus.RETURNED,
                    ),
                    Reservation(
                        asset_id=uuid.UUID(asset_ids["open_ended"]),
                        user=unknown,
                        starts_at=now - timedelta(minutes=1),
                    ),
                ]
            )
            await session.commit()

    asyncio.run(seed())


def _create(
    client: ASGIClient, group_id: str, name: str, asset_type: str, description: str
) -> dict[str, object]:
    response = client.post(
        "/api/assets",
        json={
            "group_id": group_id,
            "name": name,
            "asset_type": asset_type,
            "description": description,
        },
    )
    assert response.status_code == 201
    return response.json()


def _groups(factory: async_sessionmaker[AsyncSession]) -> tuple[str, str, str]:
    async def create_groups() -> tuple[str, str, str]:
        async with factory() as session:
            lab = Group(name="Lab")
            other = Group(name="Other")
            archived = Group(name="Archived")
            session.add_all([lab, other, archived])
            await session.commit()
            archived.archived_at = lab.created_at
            await session.commit()
            return str(lab.id), str(other.id), str(archived.id)

    return asyncio.run(create_groups())


def _reserve_now(factory: async_sessionmaker[AsyncSession], asset_id: str) -> None:
    async def create_reservation() -> None:
        async with factory() as session:
            user = User(
                oidc_issuer="https://issuer.example", oidc_subject="catalogue-test"
            )
            now = utc_now()
            session.add(user)
            session.add(
                Reservation(
                    asset_id=uuid.UUID(asset_id),
                    user=user,
                    starts_at=now - timedelta(minutes=1),
                    ends_at=now + timedelta(minutes=1),
                )
            )
            await session.commit()

    asyncio.run(create_reservation())
