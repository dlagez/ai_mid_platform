"""add toc match review results

Revision ID: q2b3c4d5e6f7
Revises: p1a2b3c4d5e6
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "q2b3c4d5e6f7"
down_revision = "p1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("toc_match_job", sa.Column("reviewed_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("toc_match_job", sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("toc_match_item", sa.Column("review_status", sa.String(length=50), nullable=False, server_default="pending"))
    op.add_column(
        "toc_match_item",
        sa.Column("review_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column("toc_match_item", sa.Column("raw_review_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("toc_match_item", sa.Column("review_error", sa.Text(), nullable=True))
    op.add_column("toc_match_item", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_toc_match_item_review_status"), "toc_match_item", ["review_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_toc_match_item_review_status"), table_name="toc_match_item")
    op.drop_column("toc_match_item", "reviewed_at")
    op.drop_column("toc_match_item", "review_error")
    op.drop_column("toc_match_item", "raw_review_response")
    op.drop_column("toc_match_item", "review_issues")
    op.drop_column("toc_match_item", "review_status")
    op.drop_column("toc_match_job", "issue_count")
    op.drop_column("toc_match_job", "reviewed_count")
