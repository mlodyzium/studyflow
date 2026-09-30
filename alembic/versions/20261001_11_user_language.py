"""Persist the user's interface language.

Revision ID: 20261001_11
Revises: 20260930_10
"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_11"
down_revision = "20260930_10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("language", sa.String(2), nullable=False, server_default="en"))
    op.create_check_constraint("user_language_supported", "users", "language IN ('en', 'pl')")


def downgrade():
    op.drop_constraint("user_language_supported", "users", type_="check")
    op.drop_column("users", "language")
