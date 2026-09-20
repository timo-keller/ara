"""HTTP transport endpoints for reservations."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.auth import require_authenticated_user, require_csrf
from ara.api.routers.groups import get_audit_context, get_effective_roles
from ara.api.schemas.reservations import (
    ReservationCreateSchema,
    ReservationExtensionSchema,
    ReservationListSchema,
    ReservationSchema,
)
from ara.core.errors import DomainError
from ara.domain.models import User
from ara.infrastructure.database import get_session
from ara.services.audit import AuditContext
from ara.services.authorization import EffectiveRoles
from ara.services.reservations import ReservationService


def _reservation_schema(reservation: object) -> ReservationSchema:
    return ReservationSchema.model_validate(reservation, from_attributes=True)


@api_router.post(
    "/reservations",
    response_model=ReservationSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    payload: ReservationCreateSchema,
    user: Annotated[User, Depends(require_authenticated_user)],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationSchema:
    reservation = await ReservationService(session, audit).create_for_current_user(
        roles, user_id=user.id, **payload.model_dump()
    )
    return _reservation_schema(reservation)


@api_router.post(
    "/reservations/{reservation_id}/extend", response_model=ReservationSchema
)
async def extend_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationExtensionSchema,
    user: Annotated[User, Depends(require_authenticated_user)],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationSchema:
    reservation = await ReservationService(session, audit).extend_own(
        roles, actor_id=user.id, reservation_id=reservation_id, ends_at=payload.ends_at
    )
    return _reservation_schema(reservation)


@api_router.post(
    "/reservations/{reservation_id}/return", response_model=ReservationSchema
)
async def return_reservation(
    reservation_id: uuid.UUID,
    user: Annotated[User, Depends(require_authenticated_user)],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationSchema:
    reservation = await ReservationService(session, audit).return_own(
        roles, actor_id=user.id, reservation_id=reservation_id
    )
    return _reservation_schema(reservation)


@api_router.post(
    "/reservations/{reservation_id}/cancel", response_model=ReservationSchema
)
async def cancel_reservation(
    reservation_id: uuid.UUID,
    user: Annotated[User, Depends(require_authenticated_user)],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationSchema:
    reservation = await ReservationService(session, audit).cancel(
        roles, actor_id=user.id, reservation_id=reservation_id
    )
    return _reservation_schema(reservation)


@api_router.post("/reservations/{reservation_id}/end", response_model=ReservationSchema)
async def end_reservation(
    reservation_id: uuid.UUID,
    user: Annotated[User, Depends(require_authenticated_user)],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    _csrf: Annotated[None, Depends(require_csrf)],
    audit: Annotated[AuditContext, Depends(get_audit_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationSchema:
    reservation = await ReservationService(session, audit).end_administratively(
        roles, actor_id=user.id, reservation_id=reservation_id
    )
    return _reservation_schema(reservation)


@api_router.get("/reservations/mine", response_model=ReservationListSchema)
async def list_own_reservations(
    user: Annotated[User, Depends(require_authenticated_user)],
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    asset_name: str | None = None,
    asset_type: str | None = None,
    timespan_from: datetime | None = None,
    timespan_to: datetime | None = None,
    lifecycle: Annotated[
        list[Literal["current", "future", "expired", "returned", "cancelled", "ended"]]
        | None,
        Query(),
    ] = None,
) -> ReservationListSchema:
    for name, value in (("timespan_from", timespan_from), ("timespan_to", timespan_to)):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise DomainError(
                "reservation_timestamp_not_utc", f"{name} must be timezone-aware UTC"
            )
    if (
        timespan_from is not None
        and timespan_to is not None
        and timespan_from > timespan_to
    ):
        raise DomainError(
            "reservation_invalid_timespan",
            "timespan_from must not be after timespan_to",
        )
    reservations, total = await ReservationService(session).list_own(
        roles,
        user_id=user.id,
        offset=offset,
        limit=limit,
        asset_name=asset_name,
        asset_type=asset_type,
        timespan_from=timespan_from,
        timespan_to=timespan_to,
        lifecycle=tuple(lifecycle or ()),
    )
    return ReservationListSchema(
        items=[_reservation_schema(reservation) for reservation in reservations],
        total=total,
        offset=offset,
        limit=limit,
    )


@api_router.get("/assets/{asset_id}/reservations", response_model=ReservationListSchema)
async def list_asset_schedule(
    asset_id: uuid.UUID,
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReservationListSchema:
    reservations, total = await ReservationService(session).list_asset_schedule(
        roles, asset_id=asset_id, offset=offset, limit=limit
    )
    return ReservationListSchema(
        items=[_reservation_schema(reservation) for reservation in reservations],
        total=total,
        offset=offset,
        limit=limit,
    )
