"""Create the initial StudyFlow schema.

Revision ID: 20260907_01
Revises:
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

priority_enum = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", name="session_priority", create_type=False
)


def upgrade() -> None:
    priority_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("user_uid", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_uid"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "subjects",
        sa.Column("subject_uid", sa.Uuid(), nullable=False),
        sa.Column("nazwa", sa.String(length=100), nullable=False),
        sa.Column("user_uid", sa.Uuid(), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["user_uid"], ["users.user_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("subject_uid"),
    )

    op.create_table(
        "topics",
        sa.Column("topic_uid", sa.Uuid(), nullable=False),
        sa.Column("nazwa", sa.String(length=100), nullable=False),
        sa.Column("subject_uid", sa.Uuid(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["subject_uid"], ["subjects.subject_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("topic_uid"),
    )

    op.create_table(
        "tasks",
        sa.Column("task_uid", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False),
        sa.Column("topic_uid", sa.Uuid(), nullable=False),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("priority", priority_enum, nullable=False),
        sa.ForeignKeyConstraint(["topic_uid"], ["topics.topic_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_uid"),
    )

    op.create_table(
        "study_sessions",
        sa.Column("study_uid", sa.Uuid(), nullable=False),
        sa.Column("subject_uid", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["subject_uid"], ["subjects.subject_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("study_uid"),
    )

    op.create_table(
        "exam_results",
        sa.Column("exam_uid", sa.Uuid(), nullable=False),
        sa.Column("subject_uid", sa.Uuid(), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("score_percent", sa.Numeric(5, 2), nullable=True),
        sa.ForeignKeyConstraint(["subject_uid"], ["subjects.subject_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exam_uid"),
    )


def downgrade() -> None:
    op.drop_table("exam_results")
    op.drop_table("study_sessions")
    op.drop_table("tasks")
    op.drop_table("topics")
    op.drop_table("subjects")
    op.drop_table("users")
    priority_enum.drop(op.get_bind(), checkfirst=True)
