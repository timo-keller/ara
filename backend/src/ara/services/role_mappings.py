"""Business operations shared by role-mapping administration endpoints."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ara.daos.role_mappings import RoleMappingDAO
from ara.domain.models import GroupRole, RoleMapping
from ara.services.authorization import (
    AuthorizationService,
    EffectiveRoles,
    validate_role_expression,
)


class RoleMappingService:
    """Validate role mappings before their service-owned persistence transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.mappings = RoleMappingDAO(session)

    async def create(
        self,
        actor_roles: EffectiveRoles,
        *,
        group_id: uuid.UUID,
        expression: str,
        role: GroupRole,
        enabled: bool = True,
        priority: int = 0,
    ) -> RoleMapping:
        """Create a syntax-checked mapping; only Owners may administer mappings."""
        AuthorizationService.require_owner(actor_roles)
        validate_role_expression(expression)
        mapping = RoleMapping(
            group_id=group_id,
            expression=expression,
            role=role,
            enabled=enabled,
            priority=priority,
        )
        self.mappings.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping
