"""Persist temporary login lockouts.

Revision ID: 20260929_07
Revises: 20260929_06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_07"
down_revision: str | None = "20260929_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("failed_login_window_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_window_started_at")
    op.drop_column("users", "failed_login_attempts")
