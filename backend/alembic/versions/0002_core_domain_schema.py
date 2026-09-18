"""Create the initial ARA domain schema.

Revision ID: 0002_core_domain_schema
Revises: 0001_database_foundation
Create Date: 2026-09-19 00:00:00.000000
"""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: Final = "0002_core_domain_schema"
down_revision: Final = "0001_database_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tables, constraints, and indexes for persisted domain records."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("oidc_issuer", sa.String(length=2048), nullable=False),
        sa.Column("oidc_subject", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255)),
        sa.Column("email", sa.String(length=320)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "oidc_issuer", "oidc_subject", name="uq_users_oidc_identity"
        ),
    )
    op.create_index("ix_users_oidc_identity", "users", ["oidc_issuer", "oidc_subject"])

    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_groups_archived_at", "groups", ["archived_at"])

    op.create_table(
        "role_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "user",
                "group_admin",
                name="grouprole",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "priority >= 0", name="ck_role_mappings_priority_nonnegative"
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_role_mappings_group_id", "role_mappings", ["group_id"])
    op.create_index("ix_role_mappings_archived_at", "role_mappings", ["archived_at"])
    op.create_index(
        "ix_role_mappings_enabled_priority", "role_mappings", ["enabled", "priority"]
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("operational_metadata", sa.JSON()),
        sa.Column("remote_host", sa.String(length=255)),
        sa.Column("remote_url", sa.String(length=2048)),
        sa.Column("operating_system", sa.String(length=255)),
        sa.Column("access_instructions", sa.Text()),
        sa.Column("webex_room_id", sa.String(length=255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "name", name="uq_assets_group_name"),
    )
    op.create_index("ix_assets_group_id", "assets", ["group_id"])
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])
    op.create_index("ix_assets_archived_at", "assets", ["archived_at"])
    op.create_index(
        "ix_assets_group_type_archived",
        "assets",
        ["group_id", "asset_type", "archived_at"],
    )

    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "returned",
                "cancelled",
                "ended",
                name="reservationstatus",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_reservations_end_after_start",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservations_asset_id", "reservations", ["asset_id"])
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"])
    op.create_index(
        "ix_reservations_asset_status_start",
        "reservations",
        ["asset_id", "status", "starts_at"],
    )
    op.create_index(
        "ix_reservations_user_start", "reservations", ["user_id", "starts_at"]
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid()),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reservation_id", "kind", "scheduled_for", name="uq_notifications_reminder"
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index(
        "ix_notifications_reservation_id", "notifications", ["reservation_id"]
    )
    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "read_at", "created_at"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("group_id", sa.Uuid()),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("before_state", sa.JSON()),
        sa.Column("after_state", sa.JSON()),
        sa.Column("correlation_id", sa.String(length=255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_group_id", "audit_events", ["group_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index(
        "ix_audit_events_correlation_id", "audit_events", ["correlation_id"]
    )
    op.create_index(
        "ix_audit_events_group_created", "audit_events", ["group_id", "created_at"]
    )
    op.create_index(
        "ix_audit_events_actor_created", "audit_events", ["actor_id", "created_at"]
    )
    op.create_index(
        "ix_audit_events_target", "audit_events", ["target_type", "target_id"]
    )


def downgrade() -> None:
    """Remove the complete ARA domain schema in dependency order."""
    op.drop_table("audit_events")
    op.drop_table("notifications")
    op.drop_table("reservations")
    op.drop_table("assets")
    op.drop_table("role_mappings")
    op.drop_table("groups")
    op.drop_table("users")
