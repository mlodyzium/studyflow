"""Add configurable shortcut for AI assistant.

Revision ID: 20260929_09
Revises: 20260929_08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_09"
down_revision: str | None = "20260929_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ai_shortcut", sa.String(30), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "ai_shortcut")
