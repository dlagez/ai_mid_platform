"""add checkpoint generation concurrency

Revision ID: k5d7e8f9a0b1
Revises: i4d6e7f8a9b0, j4c9d1e2f3a4
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "k5d7e8f9a0b1"
down_revision = ("i4d6e7f8a9b0", "j4c9d1e2f3a4")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE review_checkpoint_generation_job
        ADD COLUMN IF NOT EXISTS concurrency integer NOT NULL DEFAULT 5
        """
    )
    op.execute(
        "COMMENT ON COLUMN review_checkpoint_generation_job.concurrency IS '审查点生成任务并发处理条文数量'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE review_checkpoint_generation_job DROP COLUMN IF EXISTS concurrency")
