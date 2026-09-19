"""Group administration business operations."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.groups import GroupDAO
from ara.domain.models import Group, utc_now
from ara.services.audit import AuditContext, AuditService, group_snapshot
from ara.services.authorization import AuthorizationService, EffectiveRoles


class GroupService:
    """Own group authorization, rules, and one transaction per mutation.

    Audit recording can be added beside the staged mutation before the single
    commit in each method; DAOs deliberately never commit independently.
    """

    def __init__(
        self, session: AsyncSession, audit_context: AuditContext | None = None
    ) -> None:
        self.session = session
        self.groups = GroupDAO(session)
        self.audit = AuditService(session, audit_context)

    async def create(
        self, actor_roles: EffectiveRoles, *, name: str, description: str | None
    ) -> Group:
        AuthorizationService.require_owner(actor_roles)
        group = Group(name=name, description=description)
        self.groups.add(group)
        await self._commit(group, "group.create", None)
        return group

    async def list_groups(
        self,
        actor_roles: EffectiveRoles,
        *,
        archived: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Group], int]:
        # Mappings to archived groups are excluded during role resolution, so a
        # non-owner can never discover archived groups through this endpoint.
        if actor_roles.is_owner:
            group_ids, effective_archived = None, archived
        elif archived is True:
            # An archived-only request must not silently become an active-group
            # request. Effective roles never grant access to archived groups.
            group_ids, effective_archived = set(), True
        else:
            group_ids, effective_archived = set(actor_roles.group_roles), False
        return await self.groups.list_groups(
            group_ids=group_ids,
            archived=effective_archived,
            offset=offset,
            limit=limit,
        )

    async def get(self, actor_roles: EffectiveRoles, group_id: uuid.UUID) -> Group:
        group = await self._get_required(group_id)
        if actor_roles.is_owner:
            return group
        AuthorizationService.require_group_user(actor_roles, group.id)
        if group.archived_at is not None:
            # Role resolution normally makes this unreachable, but retaining
            # the check makes the effective-group rule explicit and robust.
            self._not_found()
        return group

    async def update(
        self,
        actor_roles: EffectiveRoles,
        group_id: uuid.UUID,
        *,
        name: str | None,
        description: str | None,
        update_name: bool,
        update_description: bool,
    ) -> Group:
        AuthorizationService.require_owner(actor_roles)
        group = await self._get_required(group_id)
        before = group_snapshot(group)
        if update_name:
            assert name is not None
            group.name = name
        if update_description:
            group.description = description
        await self._commit(group, "group.update", before)
        return group

    async def archive(self, actor_roles: EffectiveRoles, group_id: uuid.UUID) -> Group:
        AuthorizationService.require_owner(actor_roles)
        group = await self._get_required(group_id)
        if group.archived_at is None:
            if await self.groups.has_unresolved_reservations(group_id):
                raise DomainError(
                    "group_has_unresolved_reservations",
                    "Group has unresolved reservations",
                    status_code=409,
                )
            before = group_snapshot(group)
            group.archived_at = utc_now()
            await self._commit(group, "group.archive", before)
        return group

    async def reactivate(
        self, actor_roles: EffectiveRoles, group_id: uuid.UUID
    ) -> Group:
        AuthorizationService.require_owner(actor_roles)
        group = await self._get_required(group_id)
        if group.archived_at is not None:
            before = group_snapshot(group)
            group.archived_at = None
            await self._commit(group, "group.reactivate", before)
        return group

    async def _get_required(self, group_id: uuid.UUID) -> Group:
        group = await self.groups.get_by_id(group_id)
        if group is None:
            self._not_found()
            raise AssertionError("_not_found always raises")
        return group

    async def _commit(
        self, group: Group, action: str, before: dict[str, object] | None
    ) -> None:
        try:
            await self.session.flush()
            self.audit.record(
                action=action,
                group_id=group.id,
                target_type="group",
                target_id=group.id,
                before=before,
                after=group_snapshot(group),
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise DomainError(
                "group_name_conflict",
                "A group with this name already exists",
                status_code=409,
            ) from error
        await self.session.refresh(group)

    @staticmethod
    def _not_found() -> None:
        raise DomainError("group_not_found", "Group not found", status_code=404)
