"""Move room configuration to groups and add durable Webex delivery."""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: Final = "0005_webex_delivery"
down_revision: Final = "0004_session_oidc_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("webex_room_id", sa.String(255)))
    # SQLite supports DROP COLUMN; avoid rebuilding a referenced assets table.
    op.drop_column("assets", "webex_room_id")
    op.add_column(
        "assets",
        sa.Column(
            "room_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "personal_start_eligible", sa.Boolean(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "reservations",
        sa.Column(
            "start_notification_processed",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
    )
    # Existing future bookings should still announce their eventual start;
    # historical/current bookings must not generate rollout announcements.
    op.execute(
        sa.text(
            "UPDATE reservations SET personal_start_eligible = 1, "
            "start_notification_processed = 0 "
            "WHERE status = 'active' AND starts_at > CURRENT_TIMESTAMP"
        )
    )
    op.create_table(
        "webex_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("groups.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "asset_id", sa.Uuid(), sa.ForeignKey("assets.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            sa.ForeignKey("reservations.id", ondelete="RESTRICT"),
        ),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("destination_type", sa.String(20), nullable=False),
        sa.Column("destination", sa.String(320)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("expected_end", sa.DateTime()),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime()),
        sa.Column("delivered_at", sa.DateTime()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("message_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "event_key", "destination_type", name="uq_webex_event_destination"
        ),
    )
    op.create_index(
        "ix_webex_dispatch", "webex_deliveries", ["state", "next_attempt_at"]
    )
    op.create_index(
        "ix_webex_group_created", "webex_deliveries", ["group_id", "created_at"]
    )
    op.create_index(
        "ix_webex_reservation_event",
        "webex_deliveries",
        ["reservation_id", "kind", "expected_end"],
    )


def downgrade() -> None:
    op.drop_table("webex_deliveries")
    op.drop_column("reservations", "start_notification_processed")
    op.drop_column("reservations", "personal_start_eligible")
    op.drop_column("assets", "room_notifications_enabled")
    op.add_column("assets", sa.Column("webex_room_id", sa.String(255)))
    op.drop_column("groups", "webex_room_id")
