"""Service-layer audit staging with deliberately small state snapshots."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ara.daos.audit import AuditDAO
from ara.domain.models import Asset, AuditEvent, Group, Reservation, RoleMapping


@dataclass(frozen=True)
class AuditContext:
    """Invocation metadata supplied by an adapter or scheduler."""

    actor_id: uuid.UUID | None = None
    correlation_id: str | None = None


def _time(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


# These allowlists intentionally do not serialize models, request payloads, or
# operational metadata. The latter may contain deployment-specific credentials.
def group_snapshot(group: Group) -> dict[str, Any]:
    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
        "archived_at": _time(group.archived_at),
    }


def role_mapping_snapshot(mapping: RoleMapping) -> dict[str, Any]:
    return {
        "id": str(mapping.id),
        "group_id": str(mapping.group_id),
        "expression": mapping.expression,
        "role": mapping.role.value,
        "enabled": mapping.enabled,
        "priority": mapping.priority,
        "archived_at": _time(mapping.archived_at),
    }


def asset_snapshot(asset: Asset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "group_id": str(asset.group_id),
        "asset_type": asset.asset_type,
        "name": asset.name,
        "description": asset.description,
        "remote_host": asset.remote_host,
        "remote_url": asset.remote_url,
        "operating_system": asset.operating_system,
        "webex_room_id": asset.webex_room_id,
        "archived_at": _time(asset.archived_at),
    }


def reservation_snapshot(reservation: Reservation) -> dict[str, Any]:
    return {
        "id": str(reservation.id),
        "asset_id": str(reservation.asset_id),
        "user_id": str(reservation.user_id),
        "starts_at": _time(reservation.starts_at),
        "ends_at": _time(reservation.ends_at),
        "status": reservation.status.value,
        "returned_at": _time(reservation.returned_at),
        "cancelled_at": _time(reservation.cancelled_at),
        "ended_at": _time(reservation.ended_at),
    }


class AuditService:
    """Stage audit records beside the domain mutation, never committing itself."""

    def __init__(
        self, session: AsyncSession, context: AuditContext | None = None
    ) -> None:
        self.events = AuditDAO(session)
        self.context = context or AuditContext()

    def record(
        self,
        *,
        action: str,
        group_id: uuid.UUID | None,
        target_type: str,
        target_id: uuid.UUID,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        self.events.add(
            AuditEvent(
                actor_id=self.context.actor_id,
                group_id=group_id,
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                before_state=before,
                after_state=after,
                correlation_id=self.context.correlation_id,
            )
        )
