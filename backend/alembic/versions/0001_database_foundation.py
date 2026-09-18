"""Establish the database migration baseline.

Revision ID: 0001_database_foundation
Revises:
Create Date: 2026-09-19 00:00:00.000000
"""

from typing import Final

revision: Final = "0001_database_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Record the initial Alembic baseline without creating application tables."""


def downgrade() -> None:
    """Remove the initial Alembic baseline without changing application tables."""
