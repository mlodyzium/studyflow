"""Store T3ACH conversation history.

Revision ID: 20260913_05
Revises: 20260911_04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_05"
down_revision: str | None = "20260911_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("conversation_uid", sa.Uuid(), nullable=False),
        sa.Column("user_uid", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("user_message", sa.String(length=3000), nullable=False),
        sa.Column("assistant_message", sa.String(length=4000), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_uid"], ["users.user_uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("conversation_uid"),
    )
    op.create_index("ix_ai_conversations_user_uid", "ai_conversations", ["user_uid"])


def downgrade() -> None:
    op.drop_index("ix_ai_conversations_user_uid", table_name="ai_conversations")
    op.drop_table("ai_conversations")
