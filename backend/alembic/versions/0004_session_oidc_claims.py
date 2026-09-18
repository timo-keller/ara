"""Retain OIDC claims in server-side application sessions.

Revision ID: 0004_session_oidc_claims
Revises: 0003_application_sessions
Create Date: 2026-09-19 00:00:00.000000
"""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: Final = "0004_session_oidc_claims"
down_revision: Final = "0003_application_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add server-only claims required for role mapping evaluation."""
    with op.batch_alter_table("application_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("oidc_claims", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    """Remove retained session claims."""
    with op.batch_alter_table("application_sessions") as batch_op:
        batch_op.drop_column("oidc_claims")
