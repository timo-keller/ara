"""SQLAlchemy models for ARA's persisted domain state.

All application-generated timestamps are timezone-aware UTC values.  Database
defaults use ``CURRENT_TIMESTAMP``, which SQLite defines in UTC, so data loaded
outside the ORM follows the same convention.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ara.database import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time for persisted timestamps."""
    return datetime.now(UTC)


UUID = Uuid(as_uuid=True)


class UTCDateTimeType(TypeDecorator[datetime]):
    """Store only UTC datetimes and restore SQLite values as UTC-aware values."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        """Reject ambiguous values and normalize offsets before storage."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware UTC values")
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        """Restore SQLite's timezone-less datetime representation as UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


UTCDateTime = UTCDateTimeType()


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Persist string enum values rather than their Python member names."""
    return [member.value for member in enum_class]


class GroupRole(StrEnum):
    """Roles which may be granted through an OIDC claim mapping."""

    USER = "user"
    GROUP_ADMIN = "group_admin"


class ReservationStatus(StrEnum):
    """The lifecycle state of a reservation."""

    ACTIVE = "active"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    ENDED = "ended"


class User(Base):
    """A local record for a stable OIDC identity."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_users_oidc_identity"),
        Index("ix_users_oidc_identity", "oidc_issuer", "oidc_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    oidc_issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    oidc_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    reservations: Mapped[list[Reservation]] = relationship(back_populates="user")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")


class Group(Base):
    """An ARA-owned organizational unit, retained after archival."""

    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.current_timestamp(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)

    assets: Mapped[list[Asset]] = relationship(back_populates="group")
    role_mappings: Mapped[list[RoleMapping]] = relationship(back_populates="group")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="group")


class RoleMapping(Base):
    """An OIDC claim expression that grants a role in one ARA group."""

    __tablename__ = "role_mappings"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_role_mappings_priority_nonnegative"),
        Index("ix_role_mappings_enabled_priority", "enabled", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[GroupRole] = mapped_column(
        SqlEnum(
            GroupRole,
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
    )
    enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="1"
    )
    priority: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.current_timestamp(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)

    group: Mapped[Group] = relationship(back_populates="role_mappings")


class Asset(Base):
    """A reservable asset and its non-secret operational metadata."""

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_assets_group_name"),
        Index("ix_assets_group_type_archived", "group_id", "asset_type", "archived_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    operational_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    remote_host: Mapped[str | None] = mapped_column(String(255))
    remote_url: Mapped[str | None] = mapped_column(String(2048))
    operating_system: Mapped[str | None] = mapped_column(String(255))
    access_instructions: Mapped[str | None] = mapped_column(Text)
    webex_room_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.current_timestamp(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)

    group: Mapped[Group] = relationship(back_populates="assets")
    reservations: Mapped[list[Reservation]] = relationship(back_populates="asset")


class Reservation(Base):
    """An exclusive time interval requested by a user for one asset."""

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_reservations_end_after_start",
        ),
        Index("ix_reservations_asset_status_start", "asset_id", "status", "starts_at"),
        Index("ix_reservations_user_start", "user_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[ReservationStatus] = mapped_column(
        SqlEnum(
            ReservationStatus,
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ReservationStatus.ACTIVE,
        server_default=ReservationStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.current_timestamp(),
    )
    returned_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    asset: Mapped[Asset] = relationship(back_populates="reservations")
    user: Mapped[User] = relationship(back_populates="reservations")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="reservation"
    )


class Notification(Base):
    """A persistent in-application notification for one user."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "reservation_id", "kind", "scheduled_for", name="uq_notifications_reminder"
        ),
        Index("ix_notifications_user_read_created", "user_id", "read_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("reservations.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="notifications")
    reservation: Mapped[Reservation | None] = relationship(
        back_populates="notifications"
    )


class AuditEvent(Base):
    """An append-only record of a security-relevant domain mutation."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_group_created", "group_id", "created_at"),
        Index("ix_audit_events_actor_created", "actor_id", "created_at"),
        Index("ix_audit_events_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("groups.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    actor: Mapped[User | None] = relationship(back_populates="audit_events")
    group: Mapped[Group | None] = relationship(back_populates="audit_events")
