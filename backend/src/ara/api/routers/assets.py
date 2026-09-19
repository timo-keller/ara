"""HTTP transport endpoints for the group-scoped asset catalogue."""

import uuid
from typing import Annotated

from fastapi import Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.auth import require_csrf
from ara.api.routers.groups import get_audit_context, get_effective_roles
from ara.api.schemas.assets import (
    AssetCreateSchema,
    AssetListSchema,
    AssetSchema,
    AssetUpdateSchema,
)
from ara.infrastructure.database import get_session
from ara.services.assets import AssetService
from ara.services.audit import AuditContext
from ara.services.authorization import EffectiveRoles


def _asset_schema(asset: object) -> AssetSchema:
    return AssetSchema.model_validate(asset, from_attributes=True)


@api_router.post(
    "/assets", response_model=AssetSchema, status_code=status.HTTP_201_CREATED
)
async def create_asset(
    payload: AssetCreateSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetSchema:
    asset = await AssetService(session, audit).create(roles, **payload.model_dump())
    return _asset_schema(asset)


@api_router.get("/assets", response_model=AssetListSchema)
async def list_assets(
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    group_id: uuid.UUID | None = None,
    asset_type: str | None = None,
    text: str | None = None,
    archived: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AssetListSchema:
    assets, total = await AssetService(session).list_assets(
        roles,
        group_id=group_id,
        asset_type=asset_type,
        text=text,
        archived=archived,
        offset=offset,
        limit=limit,
    )
    return AssetListSchema(
        items=[_asset_schema(asset) for asset in assets],
        total=total,
        offset=offset,
        limit=limit,
    )


@api_router.get("/assets/{asset_id}", response_model=AssetSchema)
async def get_asset(
    asset_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetSchema:
    return _asset_schema(await AssetService(session).get(roles, asset_id))


@api_router.patch("/assets/{asset_id}", response_model=AssetSchema)
async def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdateSchema,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetSchema:
    return _asset_schema(
        await AssetService(session, audit).update(
            roles, asset_id, **payload.model_dump(exclude_unset=True)
        )
    )


@api_router.post("/assets/{asset_id}/archive", response_model=AssetSchema)
async def archive_asset(
    asset_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetSchema:
    return _asset_schema(await AssetService(session, audit).archive(roles, asset_id))


@api_router.post("/assets/{asset_id}/reactivate", response_model=AssetSchema)
async def reactivate_asset(
    asset_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssetSchema:
    return _asset_schema(await AssetService(session, audit).reactivate(roles, asset_id))
