"""drop context text from checkpoint and chapter profile

Revision ID: n8b4c5d6e7f8
Revises: m7a2b3c4d5e6
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "n8b4c5d6e7f8"
down_revision = "m7a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("review_checkpoint", "context_text")
    op.drop_column("chapter_review_profile", "context_text")


def downgrade() -> None:
    op.add_column("chapter_review_profile", sa.Column("context_text", sa.Text(), nullable=True, comment="上下文/适用场景"))
    op.add_column("review_checkpoint", sa.Column("context_text", sa.Text(), nullable=True, comment="父级条件/适用场景"))
