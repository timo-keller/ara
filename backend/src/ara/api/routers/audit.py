"""HTTP transport endpoint for authorized audit-history queries."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import api_router
from ara.api.routers.groups import get_effective_roles
from ara.api.schemas.audit import (
    AuditEventListSchema,
    AuditEventSchema,
    AuditQuerySchema,
)
from ara.daos.audit import AuditEventResult
from ara.infrastructure.database import get_session
from ara.services.audit import AuditAction, AuditService, AuditTargetType
from ara.services.authorization import EffectiveRoles


def _event_schema(result: AuditEventResult) -> AuditEventSchema:
    return AuditEventSchema.model_validate(
        result.event, from_attributes=True
    ).model_copy(
        update={"actor_name": result.actor_name, "target_name": result.target_name}
    )


@api_router.get("/audit-events", response_model=AuditEventListSchema)
async def list_audit_events(
    roles: Annotated[EffectiveRoles, Depends(get_effective_roles)],
    session: Annotated[AsyncSession, Depends(get_session)],
    group_id: Annotated[uuid.UUID | None, Query()] = None,
    actor_id: Annotated[str | None, Query()] = None,
    action: Annotated[list[AuditAction] | None, Query()] = None,
    target_type: Annotated[list[AuditTargetType] | None, Query()] = None,
    target_id: Annotated[str | None, Query()] = None,
    created_at_from: Annotated[datetime | None, Query()] = None,
    created_at_to: Annotated[datetime | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditEventListSchema:
    """Return audit events after applying service-owned authorization scope."""
    try:
        query = AuditQuerySchema(
            group_id=group_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
            offset=offset,
            limit=limit,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error
    events, total = await AuditService(session).list_events(roles, **query.model_dump())
    return AuditEventListSchema(
        items=[_event_schema(event) for event in events],
        total=total,
        offset=query.offset,
        limit=query.limit,
    )
