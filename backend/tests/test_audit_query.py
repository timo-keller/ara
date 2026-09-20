import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from asgi_client import ASGIClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.core.errors import DomainError
from ara.domain.models import (
    Asset,
    AuditEvent,
    Group,
    GroupRole,
    Reservation,
    RoleMapping,
    User,
)
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.main import create_app
from ara.services.audit import AUDIT_ACTIONS, AUDIT_TARGET_TYPES, AuditService
from ara.services.authorization import EffectiveRoles

ApiClient = tuple[
    ASGIClient,
    async_sessionmaker[AsyncSession],
    dict[str, EffectiveRoles],
    dict[str, object],
]


@pytest.fixture
def audit_api_client(tmp_path: Path) -> Iterator[ApiClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    factory = create_session_factory(engine)

    async def initialise() -> dict[str, object]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            group_a, group_b = Group(name="A"), Group(name="B")
            actor_a = User(oidc_issuer="https://issuer.example", oidc_subject="a")
            actor_b = User(oidc_issuer="https://issuer.example", oidc_subject="b")
            session.add_all([group_a, group_b, actor_a, actor_b])
            await session.flush()
            base = datetime(2030, 1, 1, tzinfo=UTC)
            events = [
                AuditEvent(
                    group_id=group_a.id,
                    actor_id=actor_a.id,
                    action="asset.create",
                    target_type="asset",
                    target_id="asset-a1",
                    created_at=base,
                ),
                AuditEvent(
                    group_id=group_a.id,
                    actor_id=actor_b.id,
                    action="asset.update",
                    target_type="asset",
                    target_id="asset-a2",
                    created_at=base + timedelta(hours=1),
                ),
                AuditEvent(
                    group_id=group_a.id,
                    actor_id=actor_a.id,
                    action="reservation.create",
                    target_type="reservation",
                    target_id="reservation-a",
                    created_at=base + timedelta(hours=2),
                ),
                # Deliberately share a timestamp to verify the identifier tie-breaker.
                AuditEvent(
                    group_id=group_b.id,
                    actor_id=actor_b.id,
                    action="asset.create",
                    target_type="asset",
                    target_id="asset-b1",
                    created_at=base + timedelta(hours=2),
                ),
                AuditEvent(
                    group_id=group_b.id,
                    actor_id=actor_a.id,
                    action="asset.archive",
                    target_type="asset",
                    target_id="asset-b2",
                    created_at=base + timedelta(hours=3),
                ),
            ]
            session.add_all(events)
            await session.commit()
            return {
                "group_a": group_a.id,
                "group_b": group_b.id,
                "actor_a": actor_a.id,
                "actor_b": actor_b.id,
                "events": events,
            }

    seeded = asyncio.run(initialise())
    app = create_app()
    roles = {"value": EffectiveRoles(is_owner=True, group_roles={})}

    async def get_roles() -> EffectiveRoles:
        return roles["value"]

    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[group_router.get_effective_roles] = get_roles
    app.dependency_overrides[auth_router.get_session] = get_test_session
    with ASGIClient(app) as client:
        yield client, factory, roles, seeded
    asyncio.run(engine.dispose())


def test_audit_query_api_filters_pagination_and_ordering(
    audit_api_client: ApiClient,
) -> None:
    client, _factory, _roles, seeded = audit_api_client
    events = seeded["events"]
    assert isinstance(events, list)
    expected = sorted(
        events, key=lambda event: (event.created_at, event.id), reverse=True
    )

    response = client.get("/api/audit-events")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert [item["id"] for item in body["items"]] == [
        str(event.id) for event in expected
    ]

    first_page = client.get("/api/audit-events", params={"limit": 2}).json()
    second_page = client.get(
        "/api/audit-events", params={"offset": 2, "limit": 2}
    ).json()
    assert first_page["total"] == second_page["total"] == 5
    assert [item["id"] for item in first_page["items"]] == [
        str(event.id) for event in expected[:2]
    ]
    assert [item["id"] for item in second_page["items"]] == [
        str(event.id) for event in expected[2:4]
    ]

    filters = [
        ({"group_id": seeded["group_a"]}, 3),
        ({"actor_id": seeded["actor_b"]}, 2),
        ({"action": "asset.create"}, 2),
        ({"target_type": "reservation"}, 1),
        ({"target_id": "asset-a2"}, 1),
        (
            {
                "created_at_from": "2030-01-01T01:00:00Z",
                "created_at_to": "2030-01-01T02:00:00Z",
            },
            3,
        ),
    ]
    for params, total in filters:
        assert client.get("/api/audit-events", params=params).json()["total"] == total

    repeated = client.get(
        "/api/audit-events",
        params=[
            ("action", "asset.create"),
            ("action", "reservation.create"),
            ("target_type", "asset"),
        ],
    )
    assert repeated.status_code == 200
    assert repeated.json()["total"] == 2
    assert {item["action"] for item in repeated.json()["items"]} == {"asset.create"}

    assert (
        client.get("/api/audit-events", params={"action": "unknown"}).status_code == 422
    )
    assert (
        client.get("/api/audit-events", params={"target_type": "unknown"}).status_code
        == 422
    )

    assert (
        client.get(
            "/api/audit-events", params={"created_at_from": "2030-01-01T01:00:00+01:00"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/audit-events",
            params={
                "created_at_from": "2030-01-02T00:00:00Z",
                "created_at_to": "2030-01-01T00:00:00Z",
            },
        ).status_code
        == 422
    )


def test_audit_filter_vocabulary_matches_recorded_domain_actions() -> None:
    assert AUDIT_ACTIONS == (
        "asset.create",
        "asset.update",
        "asset.archive",
        "asset.reactivate",
        "group.create",
        "group.update",
        "group.archive",
        "group.reactivate",
        "reservation.create",
        "reservation.extend",
        "reservation.return",
        "reservation.cancel",
        "reservation.end",
        "role_mapping.create",
        "role_mapping.update",
        "role_mapping.disable",
        "role_mapping.archive",
    )
    assert AUDIT_TARGET_TYPES == ("asset", "group", "reservation", "role_mapping")


def test_audit_query_api_role_scope_and_cross_group_filter_isolation(
    audit_api_client: ApiClient,
) -> None:
    client, _factory, roles, seeded = audit_api_client
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    assert isinstance(group_a, uuid.UUID)
    assert isinstance(group_b, uuid.UUID)
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={group_a: GroupRole.GROUP_ADMIN}
    )

    assert client.get("/api/audit-events").json()["total"] == 3
    # Every client filter is intersected with the service's allowed-group set.
    assert (
        client.get("/api/audit-events", params={"group_id": group_b}).json()["total"]
        == 0
    )
    assert (
        client.get("/api/audit-events", params={"target_id": "asset-b1"}).json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get(
            "/api/audit-events",
            params={"group_id": group_a, "target_id": "asset-b1"},
        ).json()["total"]
        == 0
    )

    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={group_a: GroupRole.USER}
    )
    denied = client.get("/api/audit-events")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "authorization_denied"


async def test_audit_service_denies_users_and_scopes_target_filters(
    audit_api_client: ApiClient,
) -> None:
    _client, factory, _roles, seeded = audit_api_client
    group_a = seeded["group_a"]
    assert isinstance(group_a, uuid.UUID)
    async with factory() as session:
        service = AuditService(session)
        admin = EffectiveRoles(
            is_owner=False, group_roles={group_a: GroupRole.GROUP_ADMIN}
        )
        events, total = await service.list_events(
            admin,
            group_id=None,
            actor_id=None,
            action=None,
            target_type=None,
            target_id="asset-b1",
            created_at_from=None,
            created_at_to=None,
            offset=0,
            limit=50,
        )
        assert events == []
        assert total == 0
        with pytest.raises(DomainError, match="Authorization denied"):
            await service.list_events(
                EffectiveRoles(is_owner=False, group_roles={}),
                group_id=None,
                actor_id=None,
                action=None,
                target_type=None,
                target_id=None,
                created_at_from=None,
                created_at_to=None,
                offset=0,
                limit=50,
            )


async def test_audit_query_enriches_names_searches_names_or_ids_and_preserves_scope(
    audit_api_client: ApiClient,
) -> None:
    client, factory, roles, seeded = audit_api_client
    group_a = seeded["group_a"]
    group_b = seeded["group_b"]
    actor_a = seeded["actor_a"]
    assert isinstance(group_a, uuid.UUID)
    assert isinstance(group_b, uuid.UUID)
    assert isinstance(actor_a, uuid.UUID)
    async with factory() as session:
        alice = await session.get(User, actor_a)
        assert alice is not None
        alice.display_name = "Alice Auditor"
        secret_actor = User(
            oidc_issuer="https://issuer.example",
            oidc_subject="secret",
            display_name="Secret Actor",
        )
        asset = Asset(group_id=group_a, asset_type="laptop", name="Named asset")
        private_asset = Asset(
            group_id=group_b, asset_type="laptop", name="Private target"
        )
        session.add_all([secret_actor, asset, private_asset])
        await session.flush()
        reservation = Reservation(
            asset_id=asset.id, user_id=actor_a, starts_at=datetime.now(UTC)
        )
        mapping = RoleMapping(
            group_id=group_a, expression="department == 'lab'", role=GroupRole.USER
        )
        session.add_all([reservation, mapping])
        await session.flush()
        session.add_all(
            [
                AuditEvent(
                    group_id=group_a,
                    actor_id=actor_a,
                    action="asset.create",
                    target_type="asset",
                    target_id=str(asset.id),
                ),
                AuditEvent(
                    group_id=group_a,
                    actor_id=actor_a,
                    action="group.update",
                    target_type="group",
                    target_id=str(group_a),
                ),
                AuditEvent(
                    group_id=group_a,
                    actor_id=actor_a,
                    action="reservation.create",
                    target_type="reservation",
                    target_id=str(reservation.id),
                ),
                AuditEvent(
                    group_id=group_a,
                    actor_id=actor_a,
                    action="role_mapping.create",
                    target_type="role_mapping",
                    target_id=str(mapping.id),
                ),
                AuditEvent(
                    group_id=group_b,
                    actor_id=secret_actor.id,
                    action="asset.create",
                    target_type="asset",
                    target_id=str(private_asset.id),
                ),
                AuditEvent(
                    group_id=group_a,
                    action="asset.create",
                    target_type="asset",
                    target_id=str(uuid.uuid4()),
                ),
            ]
        )
        await session.commit()

    named = await client._client.get(
        "/api/audit-events", params={"target_id": "NAMED ass"}
    )
    assert named.status_code == 200
    assert named.json()["total"] == 2
    assert {item["target_name"] for item in named.json()["items"]} == {
        "Named asset",
        "Reservation for Named asset",
    }
    assert (
        await client._client.get(
            "/api/audit-events", params={"target_id": "reservation for named"}
        )
    ).json()["total"] == 1
    assert (
        await client._client.get(
            "/api/audit-events", params={"target_id": "department =="}
        )
    ).json()["total"] == 1
    assert (
        await client._client.get(
            "/api/audit-events", params={"actor_id": "alice audit"}
        )
    ).json()["total"] == 7
    assert (
        await client._client.get(
            "/api/audit-events", params={"actor_id": str(actor_a)[:8]}
        )
    ).json()["total"] == 7
    assert (
        await client._client.get(
            "/api/audit-events", params={"target_id": str(asset.id)[:8]}
        )
    ).json()["total"] == 1

    items = (await client._client.get("/api/audit-events")).json()["items"]
    target_names = {item["target_name"] for item in items}
    assert {
        "Named asset",
        "A",
        "Reservation for Named asset",
        "Role mapping: department == 'lab'",
    } <= target_names
    missing = next(item for item in items if item["actor_id"] is None)
    assert missing["actor_name"] is None
    assert missing["target_name"] is None

    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={group_a: GroupRole.GROUP_ADMIN}
    )
    assert (
        await client._client.get(
            "/api/audit-events", params={"target_id": "private target"}
        )
    ).json()["total"] == 0
    assert (
        await client._client.get(
            "/api/audit-events", params={"actor_id": "secret actor"}
        )
    ).json()["total"] == 0
