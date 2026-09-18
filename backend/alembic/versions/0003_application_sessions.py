"""Add revocable application browser sessions.

Revision ID: 0003_application_sessions
Revises: 0002_core_domain_schema
Create Date: 2026-09-19 00:00:00.000000
"""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: Final = "0003_application_sessions"
down_revision: Final = "0002_core_domain_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create server-side state for revocable browser sessions."""
    op.create_table(
        "application_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("renewed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_sessions_user_id", "application_sessions", ["user_id"]
    )
    op.create_index(
        "ix_application_sessions_user_expires",
        "application_sessions",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_application_sessions_expires", "application_sessions", ["expires_at"]
    )


def downgrade() -> None:
    """Remove server-side browser sessions."""
    op.drop_table("application_sessions")
