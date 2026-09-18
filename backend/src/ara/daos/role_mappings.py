"""Persistence queries for OIDC claim role mappings."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import Group, RoleMapping


class RoleMappingDAO:
    """Role-mapping queries; callers own authorization and transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_enabled(self) -> list[RoleMapping]:
        """Return active mappings in stable evaluation order.

        Archived mappings and mappings to archived groups cannot grant access.
        UUID is the deterministic tiebreaker for equal priorities.
        """
        result = await self.session.scalars(
            select(RoleMapping)
            .join(Group)
            .where(
                RoleMapping.enabled.is_(True),
                RoleMapping.archived_at.is_(None),
                Group.archived_at.is_(None),
            )
            .order_by(RoleMapping.priority, RoleMapping.id)
        )
        return list(result)

    def add(self, mapping: RoleMapping) -> None:
        """Stage a role mapping for the caller's service transaction."""
        self.session.add(mapping)

    async def get_by_id(self, mapping_id: uuid.UUID) -> RoleMapping | None:
        """Return a mapping regardless of its archival state."""
        return await self.session.get(RoleMapping, mapping_id)

    async def list_mappings(
        self, *, archived: bool | None, offset: int, limit: int
    ) -> tuple[list[RoleMapping], int]:
        """Return a stable administrative page without authorization checks."""
        filters = []
        if archived is True:
            filters.append(RoleMapping.archived_at.is_not(None))
        elif archived is False:
            filters.append(RoleMapping.archived_at.is_(None))
        statement = select(RoleMapping).where(*filters)
        total = await self.session.scalar(
            select(func.count()).select_from(statement.subquery())
        )
        result = await self.session.scalars(
            statement.order_by(RoleMapping.priority, RoleMapping.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result), total or 0
