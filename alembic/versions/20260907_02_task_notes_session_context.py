"""Add task notes and study session context.

Revision ID: 20260907_02
Revises: 20260907_01
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_02"
down_revision: str | None = "20260907_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("study_sessions", sa.Column("topic_uid", sa.Uuid(), nullable=True))
    op.add_column("study_sessions", sa.Column("task_uid", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_study_sessions_topic_uid", "study_sessions", "topics", ["topic_uid"], ["topic_uid"], ondelete="SET NULL")
    op.create_foreign_key("fk_study_sessions_task_uid", "study_sessions", "tasks", ["task_uid"], ["task_uid"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_study_sessions_task_uid", "study_sessions", type_="foreignkey")
    op.drop_constraint("fk_study_sessions_topic_uid", "study_sessions", type_="foreignkey")
    op.drop_column("study_sessions", "task_uid")
    op.drop_column("study_sessions", "topic_uid")
    op.drop_column("tasks", "notes")
