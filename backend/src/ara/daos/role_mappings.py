"""Persistence queries for OIDC claim role mappings."""

from sqlalchemy import select
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
