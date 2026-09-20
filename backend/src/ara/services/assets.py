"""Asset catalogue business operations."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.assets import AssetDAO
from ara.daos.groups import GroupDAO
from ara.domain.models import Asset, Group, GroupRole, utc_now
from ara.services.audit import (
    AuditAction,
    AuditContext,
    AuditService,
    AuditTargetType,
    asset_snapshot,
)
from ara.services.authorization import AuthorizationService, EffectiveRoles


class AssetService:
    """Own asset authorization, business rules, and mutation transactions."""

    def __init__(
        self, session: AsyncSession, audit_context: AuditContext | None = None
    ) -> None:
        self.session = session
        self.assets = AssetDAO(session)
        self.groups = GroupDAO(session)
        self.audit = AuditService(session, audit_context)

    async def create(
        self, actor_roles: EffectiveRoles, *, group_id: uuid.UUID, **values: object
    ) -> Asset:
        group = await self._get_group_required(group_id)
        AuthorizationService.require_group_admin(actor_roles, group.id)
        self._require_active_group(group)
        asset = Asset(group_id=group.id, **values)
        self.assets.add(asset)
        await self._commit(asset, AuditAction.ASSET_CREATE, None)
        return asset

    async def list_assets(
        self,
        actor_roles: EffectiveRoles,
        *,
        group_id: uuid.UUID | None,
        asset_type: str | None,
        text: str | None,
        availability: str | None,
        archived: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Asset], int]:
        if actor_roles.is_owner:
            group_ids = None
            effective_archived = False if archived is None else archived
        elif actor_roles.group_roles:
            # Users only receive active assets.  An actor who is an admin in
            # one group remains a User in their other groups.
            if archived is True:
                group_ids = {
                    group_id
                    for group_id, role in actor_roles.group_roles.items()
                    if role is GroupRole.GROUP_ADMIN
                }
                effective_archived = True
            else:
                group_ids = set(actor_roles.group_roles)
                effective_archived = False
        else:
            group_ids, effective_archived = set(), False
        rows, total = await self.assets.list_assets(
            group_ids=group_ids,
            group_id=group_id,
            asset_type=asset_type,
            text=text,
            availability=availability,
            archived=effective_archived,
            offset=offset,
            limit=limit,
        )
        assets = []
        for asset, reserved_by_display_name in rows:
            setattr(
                asset,
                "availability",
                "reserved" if reserved_by_display_name is not None else "available",
            )
            setattr(asset, "reserved_by_display_name", reserved_by_display_name)
            assets.append(asset)
        return assets, total

    async def get(self, actor_roles: EffectiveRoles, asset_id: uuid.UUID) -> Asset:
        asset = await self._get_required(asset_id)
        group = await self._get_group_required(asset.group_id)
        AuthorizationService.require_group_user(actor_roles, group.id)
        if not actor_roles.is_owner and (
            group.archived_at is not None
            or (
                asset.archived_at is not None
                and not actor_roles.is_group_admin(group.id)
            )
        ):
            self._not_found()
        return asset

    async def update(
        self, actor_roles: EffectiveRoles, asset_id: uuid.UUID, **values: object
    ) -> Asset:
        asset = await self._get_required(asset_id)
        AuthorizationService.require_group_admin(actor_roles, asset.group_id)
        before = asset_snapshot(asset)
        for field, value in values.items():
            setattr(asset, field, value)
        await self._commit(asset, AuditAction.ASSET_UPDATE, before)
        return asset

    async def archive(self, actor_roles: EffectiveRoles, asset_id: uuid.UUID) -> Asset:
        asset = await self._get_required(asset_id)
        AuthorizationService.require_group_admin(actor_roles, asset.group_id)
        if asset.archived_at is None:
            before = asset_snapshot(asset)
            asset.archived_at = utc_now()
            await self._commit(asset, AuditAction.ASSET_ARCHIVE, before)
        return asset

    async def reactivate(
        self, actor_roles: EffectiveRoles, asset_id: uuid.UUID
    ) -> Asset:
        asset = await self._get_required(asset_id)
        AuthorizationService.require_group_admin(actor_roles, asset.group_id)
        self._require_active_group(await self._get_group_required(asset.group_id))
        if asset.archived_at is not None:
            before = asset_snapshot(asset)
            asset.archived_at = None
            await self._commit(asset, AuditAction.ASSET_REACTIVATE, before)
        return asset

    async def _get_required(self, asset_id: uuid.UUID) -> Asset:
        asset = await self.assets.get_by_id(asset_id)
        if asset is None:
            self._not_found()
            raise AssertionError("_not_found always raises")
        return asset

    async def _get_group_required(self, group_id: uuid.UUID) -> Group:
        group = await self.groups.get_by_id(group_id)
        if group is None:
            raise DomainError("group_not_found", "Group not found", status_code=404)
        return group

    async def _commit(
        self, asset: Asset, action: AuditAction, before: dict[str, object] | None
    ) -> None:
        try:
            await self.session.flush()
            self.audit.record(
                action=action,
                group_id=asset.group_id,
                target_type=AuditTargetType.ASSET,
                target_id=asset.id,
                before=before,
                after=asset_snapshot(asset),
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise DomainError(
                "asset_name_conflict",
                "An asset with this name already exists in the group",
                status_code=409,
            ) from error
        await self.session.refresh(asset)

    @staticmethod
    def _require_active_group(group: Group) -> None:
        if group.archived_at is not None:
            raise DomainError("group_archived", "Group is archived", status_code=409)

    @staticmethod
    def _not_found() -> None:
        raise DomainError("asset_not_found", "Asset not found", status_code=404)
