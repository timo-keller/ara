import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.domain.models import AuditEvent, GroupRole, User
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.services.assets import AssetService
from ara.services.audit import AuditContext
from ara.services.authorization import EffectiveRoles
from ara.services.groups import GroupService
from ara.services.reservations import ReservationService
from ara.services.role_mappings import RoleMappingService


@pytest.fixture
async def database_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_mutations_stage_sanitized_audit_events_atomically(
    database_session: AsyncSession,
) -> None:
    user = User(oidc_issuer="https://issuer.example", oidc_subject="owner")
    database_session.add(user)
    await database_session.commit()
    actor_id = user.id
    context = AuditContext(actor_id=actor_id, correlation_id="request-123")
    owner = EffectiveRoles(is_owner=True, group_roles={}, actor_id=actor_id)

    groups = GroupService(database_session, context)
    group = await groups.create(owner, name="Lab", description="Devices")
    group_id = group.id
    await groups.update(
        owner,
        group.id,
        name="Lab assets",
        description=None,
        update_name=True,
        update_description=False,
    )
    mappings = RoleMappingService(database_session, context)
    mapping = await mappings.create(
        owner, group_id=group.id, expression="enabled", role=GroupRole.USER
    )
    await mappings.update(
        owner,
        mapping.id,
        group_id=None,
        expression="contains(groups, 'lab')",
        role=None,
        enabled=None,
        priority=None,
    )
    await mappings.disable(owner, mapping.id)
    await mappings.archive(owner, mapping.id)

    assets = AssetService(database_session, context)
    asset = await assets.create(
        owner,
        group_id=group.id,
        asset_type="laptop",
        name="L1",
        operational_metadata={
            "token": "SENTINEL_TOKEN",
            "secret": "SENTINEL_SECRET",
            "cookie": "SENTINEL_COOKIE",
            "claims": {"sub": "SENTINEL_CLAIMS"},
            "credential": "SENTINEL_CREDENTIAL",
        },
        access_instructions="SENTINEL_CREDENTIAL",
    )
    await assets.update(owner, asset.id, description="updated")
    await assets.archive(owner, asset.id)
    await assets.reactivate(owner, asset.id)

    reservations = ReservationService(database_session, context)
    now = datetime.now(UTC)
    reservation = await reservations.create_for_current_user(
        owner,
        asset_id=asset.id,
        user_id=user.id,
        starts_at=now,
        ends_at=now + timedelta(hours=1),
    )
    await reservations.extend_own(
        owner,
        actor_id=user.id,
        reservation_id=reservation.id,
        ends_at=now + timedelta(hours=2),
    )
    await reservations.return_own(
        owner, actor_id=user.id, reservation_id=reservation.id
    )

    future = await reservations.create_for_current_user(
        owner,
        asset_id=asset.id,
        user_id=user.id,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=1),
    )
    await reservations.cancel(owner, actor_id=user.id, reservation_id=future.id)
    administrative = await reservations.create_for_current_user(
        owner,
        asset_id=asset.id,
        user_id=user.id,
        starts_at=now,
        ends_at=now + timedelta(hours=1),
    )
    await reservations.end_administratively(
        owner, actor_id=user.id, reservation_id=administrative.id
    )

    await groups.archive(owner, group.id)
    await groups.reactivate(owner, group.id)

    events_before_failure = list(await database_session.scalars(select(AuditEvent)))

    with pytest.raises(DomainError, match="name already exists"):
        await assets.create(owner, group_id=group.id, asset_type="laptop", name="L1")

    events = list(
        await database_session.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at)
        )
    )
    assert [event.action for event in events] == [
        "group.create",
        "group.update",
        "role_mapping.create",
        "role_mapping.update",
        "role_mapping.disable",
        "role_mapping.archive",
        "asset.create",
        "asset.update",
        "asset.archive",
        "asset.reactivate",
        "reservation.create",
        "reservation.extend",
        "reservation.return",
        "reservation.create",
        "reservation.cancel",
        "reservation.create",
        "reservation.end",
        "group.archive",
        "group.reactivate",
    ]
    assert len(events) == len(events_before_failure)
    assert all(event.actor_id == actor_id for event in events)
    assert all(event.group_id == group_id for event in events)
    assert all(event.correlation_id == "request-123" for event in events)
    asset_event = next(event for event in events if event.action == "asset.create")
    assert asset_event.after_state is not None
    assert "operational_metadata" not in asset_event.after_state
    assert "access_instructions" not in asset_event.after_state
    serialized_snapshots = json.dumps(
        [(event.before_state, event.after_state) for event in events]
    )
    for sentinel in (
        "SENTINEL_TOKEN",
        "SENTINEL_SECRET",
        "SENTINEL_COOKIE",
        "SENTINEL_CLAIMS",
        "SENTINEL_CREDENTIAL",
    ):
        assert sentinel not in serialized_snapshots
    for event in events:
        if event.action.endswith(".create"):
            assert event.before_state is None
            assert event.after_state is not None
        else:
            assert event.before_state is not None
            assert event.after_state is not None
            assert event.before_state != event.after_state
