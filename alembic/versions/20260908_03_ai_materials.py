"""Store generated AI materials.

Revision ID: 20260908_03
Revises: 20260907_02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_03"
down_revision: str | None = "20260907_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_materials",
        sa.Column("material_uid", sa.Uuid(), nullable=False),
        sa.Column("user_uid", sa.Uuid(), nullable=False),
        sa.Column("topic_uid", sa.Uuid(), nullable=False),
        sa.Column("task_uid", sa.Uuid(), nullable=True),
        sa.Column("material_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_uid"], ["tasks.task_uid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_uid"], ["topics.topic_uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_uid"], ["users.user_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("material_uid"),
    )
    op.create_index("ix_ai_materials_user_uid", "ai_materials", ["user_uid"])
    op.create_index("ix_ai_materials_topic_uid", "ai_materials", ["topic_uid"])


def downgrade() -> None:
    op.drop_index("ix_ai_materials_topic_uid", table_name="ai_materials")
    op.drop_index("ix_ai_materials_user_uid", table_name="ai_materials")
    op.drop_table("ai_materials")
