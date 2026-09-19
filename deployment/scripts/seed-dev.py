"""Idempotently install local development group mappings (never in an image)."""

import asyncio

from sqlalchemy import select

from ara.domain.models import Group, GroupRole, RoleMapping
from ara.infrastructure.database import create_engine, create_session_factory


async def main() -> None:
    engine = create_engine("sqlite+aiosqlite:////app/data/ara.db")
    factory = create_session_factory(engine)
    async with factory() as session:
        group = await session.scalar(
            select(Group).where(Group.name == "ARA Development")
        )
        if group is None:
            group = Group(name="ARA Development")
            session.add(group)
            await session.flush()
        expected = {
            "contains(realm_access.roles, 'ara-group-admin')": GroupRole.GROUP_ADMIN,
            "contains(realm_access.roles, 'ara-user')": GroupRole.USER,
        }
        mappings = (
            await session.scalars(
                select(RoleMapping).where(RoleMapping.group_id == group.id)
            )
        ).all()
        existing = {mapping.expression: mapping for mapping in mappings}
        for expression, role in expected.items():
            mapping = existing.get(expression)
            if mapping is None:
                session.add(
                    RoleMapping(group_id=group.id, expression=expression, role=role)
                )
            else:
                mapping.role, mapping.enabled = role, True
        await session.commit()
    await engine.dispose()


asyncio.run(main())
