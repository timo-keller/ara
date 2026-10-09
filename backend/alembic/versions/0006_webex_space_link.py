"""Retain the configured Webex space link alongside its canonical room ID."""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: Final = "0006_webex_space_link"
down_revision: Final = "0005_webex_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("webex_space_link", sa.String(255)))


def downgrade() -> None:
    op.drop_column("groups", "webex_space_link")
