"""Add titles to study sessions.

Revision ID: 20260911_04
Revises: 20260908_03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260911_04"
down_revision: str | None = "20260908_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("study_sessions", sa.Column("title", sa.String(length=160), nullable=True))
    op.execute("UPDATE study_sessions SET title = 'Sesja nauki' WHERE title IS NULL")
    op.alter_column("study_sessions", "title", nullable=False)


def downgrade() -> None:
    op.drop_column("study_sessions", "title")
