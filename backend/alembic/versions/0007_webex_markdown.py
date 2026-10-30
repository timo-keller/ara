"""Persist formatted Webex messages alongside their plain-text fallback."""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: Final = "0007_webex_markdown"
down_revision: Final = "0006_webex_space_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webex_deliveries", sa.Column("markdown", sa.Text()))


def downgrade() -> None:
    op.drop_column("webex_deliveries", "markdown")
