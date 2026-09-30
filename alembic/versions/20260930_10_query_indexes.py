"""Indexes for frequent lists and text search.

Revision ID: 20260930_10
Revises: 20260929_09
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260930_10"
down_revision: str | None = "20260929_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index("ix_study_session_subject_started", "study_sessions", ["subject_uid", "started_at"])
    op.create_index("ix_exam_result_subject_date", "exam_results", ["subject_uid", "exam_date"])
    op.create_index("ix_ai_material_task", "ai_materials", ["task_uid"])
    op.create_index("ix_task_topic_done_deadline", "tasks", ["topic_uid", "is_done", "deadline"])
    op.create_index("ix_task_topic_priority", "tasks", ["topic_uid", "priority"])
    op.create_index("ix_subject_name_trgm", "subjects", ["nazwa"], postgresql_using="gin", postgresql_ops={"nazwa": "gin_trgm_ops"})
    op.create_index("ix_task_title_trgm", "tasks", ["title"], postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"})


def downgrade() -> None:
    for name, table in (
        ("ix_task_title_trgm", "tasks"), ("ix_subject_name_trgm", "subjects"),
        ("ix_task_topic_priority", "tasks"), ("ix_task_topic_done_deadline", "tasks"),
        ("ix_ai_material_task", "ai_materials"), ("ix_exam_result_subject_date", "exam_results"),
        ("ix_study_session_subject_started", "study_sessions"),
    ):
        op.drop_index(name, table_name=table)
