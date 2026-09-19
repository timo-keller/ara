"""Business operations shared by role-mapping administration endpoints."""

import uuid
from collections.abc import Mapping
from typing import Any

from jmespath.exceptions import JMESPathError
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.groups import GroupDAO
from ara.daos.role_mappings import RoleMappingDAO
from ara.domain.models import GroupRole, RoleMapping, utc_now
from ara.services.audit import AuditContext, AuditService, role_mapping_snapshot
from ara.services.authorization import (
    AuthorizationService,
    EffectiveRoles,
    validate_role_expression,
)


class RoleMappingService:
    """Validate role mappings before their service-owned persistence transaction."""

    def __init__(
        self, session: AsyncSession, audit_context: AuditContext | None = None
    ) -> None:
        self.session = session
        self.groups = GroupDAO(session)
        self.mappings = RoleMappingDAO(session)
        self.audit = AuditService(session, audit_context)

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
        await self._require_active_group(group_id)
        mapping = RoleMapping(
            group_id=group_id,
            expression=expression,
            role=role,
            enabled=enabled,
            priority=priority,
        )
        self.mappings.add(mapping)
        await self._commit(mapping, "role_mapping.create", None)
        return mapping

    async def list_mappings(
        self,
        actor_roles: EffectiveRoles,
        *,
        archived: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[RoleMapping], int]:
        """List mappings for Owners in deterministic evaluation order."""
        AuthorizationService.require_owner(actor_roles)
        return await self.mappings.list_mappings(
            archived=archived, offset=offset, limit=limit
        )

    async def update(
        self,
        actor_roles: EffectiveRoles,
        mapping_id: uuid.UUID,
        *,
        group_id: uuid.UUID | None,
        expression: str | None,
        role: GroupRole | None,
        enabled: bool | None,
        priority: int | None,
    ) -> RoleMapping:
        """Update an Owner-managed mapping after validating changed fields."""
        AuthorizationService.require_owner(actor_roles)
        mapping = await self._get_required(mapping_id)
        before = role_mapping_snapshot(mapping)
        if group_id is not None:
            await self._require_active_group(group_id)
            mapping.group_id = group_id
        if expression is not None:
            validate_role_expression(expression)
            mapping.expression = expression
        if role is not None:
            mapping.role = role
        if enabled is not None:
            mapping.enabled = enabled
        if priority is not None:
            mapping.priority = priority
        await self._commit(mapping, "role_mapping.update", before)
        return mapping

    async def disable(
        self, actor_roles: EffectiveRoles, mapping_id: uuid.UUID
    ) -> RoleMapping:
        """Disable a mapping without removing its administrative history."""
        AuthorizationService.require_owner(actor_roles)
        mapping = await self._get_required(mapping_id)
        before = role_mapping_snapshot(mapping)
        mapping.enabled = False
        await self._commit(mapping, "role_mapping.disable", before)
        return mapping

    async def archive(
        self, actor_roles: EffectiveRoles, mapping_id: uuid.UUID
    ) -> RoleMapping:
        """Archive a mapping so it can no longer grant roles."""
        AuthorizationService.require_owner(actor_roles)
        mapping = await self._get_required(mapping_id)
        if mapping.archived_at is None:
            before = role_mapping_snapshot(mapping)
            mapping.archived_at = utc_now()
            await self._commit(mapping, "role_mapping.archive", before)
        return mapping

    async def test_expression(
        self,
        actor_roles: EffectiveRoles,
        *,
        expression: str,
        claims: Mapping[str, Any],
    ) -> bool:
        """Evaluate an Owner's expression without persisting or exposing claims."""
        AuthorizationService.require_owner(actor_roles)
        compiled = validate_role_expression(expression)
        try:
            result = compiled.search(claims)
        except JMESPathError as error:
            raise DomainError(
                "invalid_role_mapping_expression",
                "Role mapping expression is invalid",
            ) from error
        if not isinstance(result, bool):
            raise DomainError(
                "role_mapping_expression_not_boolean",
                "Role mapping expression must evaluate to a boolean",
            )
        return result

    async def _require_active_group(self, group_id: uuid.UUID) -> None:
        group = await self.groups.get_by_id(group_id)
        if group is None:
            raise DomainError("group_not_found", "Group not found", status_code=404)
        if group.archived_at is not None:
            raise DomainError("group_archived", "Group is archived", status_code=409)

    async def _get_required(self, mapping_id: uuid.UUID) -> RoleMapping:
        mapping = await self.mappings.get_by_id(mapping_id)
        if mapping is None:
            raise DomainError(
                "role_mapping_not_found", "Role mapping not found", status_code=404
            )
        return mapping

    async def _commit(
        self, mapping: RoleMapping, action: str, before: dict[str, object] | None
    ) -> None:
        try:
            await self.session.flush()
            self.audit.record(
                action=action,
                group_id=mapping.group_id,
                target_type="role_mapping",
                target_id=mapping.id,
                before=before,
                after=role_mapping_snapshot(mapping),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(mapping)
