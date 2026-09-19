"""HTTP transport endpoints for reservations."""

import uuid
from typing import Annotated

from fastapi import Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.auth import require_authenticated_user, require_csrf
from ara.api.routers.groups import get_effective_roles
from ara.api.schemas.reservations import (
    ReservationCreateSchema,
    ReservationListSchema,
    ReservationSchema,
)
from ara.domain.models import User
from ara.infrastructure.database import get_session
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
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationSchema:
    reservation = await ReservationService(session).create_for_current_user(
        roles, user_id=user.id, **payload.model_dump()
    )
    return _reservation_schema(reservation)


@api_router.get("/reservations/mine", response_model=ReservationListSchema)
async def list_own_reservations(
    user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReservationListSchema:
    reservations, total = await ReservationService(session).list_own(
        user_id=user.id, offset=offset, limit=limit
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
