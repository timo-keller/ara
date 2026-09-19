"""Seed the migrated E2E database with deterministic groups, roles, and assets."""

import asyncio
import sys
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ara.domain.models import (
    Asset,
    AuditEvent,
    Group,
    GroupRole,
    Reservation,
    ReservationStatus,
    RoleMapping,
    User,
    utc_now,
)


async def seed(database_url: str, issuer: str) -> None:
    """Insert only fixture data; schema creation remains Alembic's responsibility."""
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        alpha = Group(
            id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
            name="Alpha Lab",
            description="E2E Alpha scope",
        )
        bravo = Group(
            id=uuid.UUID("20000000-0000-0000-0000-000000000002"),
            name="Bravo Lab",
            description="E2E Bravo scope",
        )
        session.add_all(
            [
                alpha,
                bravo,
                RoleMapping(
                    group=alpha,
                    expression="contains(groups, 'alpha-user')",
                    role=GroupRole.USER,
                ),
                RoleMapping(
                    group=alpha,
                    expression="contains(groups, 'alpha-admin')",
                    role=GroupRole.GROUP_ADMIN,
                ),
                RoleMapping(
                    group=bravo,
                    expression="contains(groups, 'bravo-user')",
                    role=GroupRole.USER,
                ),
                Asset(group=alpha, name="Alpha Laptop", asset_type="laptop"),
                Asset(
                    id=uuid.UUID("30000000-0000-0000-0000-000000000003"),
                    group=alpha,
                    name="Alpha Return Laptop",
                    asset_type="laptop",
                ),
                Asset(group=bravo, name="Bravo Laptop", asset_type="laptop"),
                User(
                    oidc_issuer=issuer,
                    oidc_subject="alpha-user",
                    display_name="alpha-user",
                ),
            ]
        )
        await session.flush()
        return_asset = await session.get(
            Asset, uuid.UUID("30000000-0000-0000-0000-000000000003")
        )
        alpha_user = await session.scalar(
            select(User).where(User.oidc_subject == "alpha-user")
        )
        assert return_asset is not None and alpha_user is not None
        session.add_all(
            [
                Reservation(
                    asset_id=return_asset.id,
                    user_id=alpha_user.id,
                    starts_at=utc_now() - timedelta(hours=1),
                    status=ReservationStatus.ACTIVE,
                ),
                AuditEvent(
                    group_id=alpha.id,
                    action="e2e_alpha_event",
                    target_type="asset",
                    target_id="00000000-0000-0000-0000-000000000001",
                ),
                AuditEvent(
                    group_id=bravo.id,
                    action="e2e_bravo_event",
                    target_type="asset",
                    target_id="00000000-0000-0000-0000-000000000002",
                ),
            ]
        )
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(sys.argv[1], sys.argv[2]))
