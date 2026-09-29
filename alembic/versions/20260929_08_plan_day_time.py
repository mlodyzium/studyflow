"""Allow optional study time for each plan day.

Revision ID: 20260929_08
Revises: 20260929_07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_08"
down_revision: str | None = "20260929_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("study_plan_days", sa.Column("scheduled_time", sa.String(5), nullable=True))
    op.alter_column("users", "task_shortcut", server_default="")


def downgrade() -> None:
    op.alter_column("users", "task_shortcut", server_default="Alt+N")
    op.drop_column("study_plan_days", "scheduled_time")
