"""add section parse mode to profile jobs

Revision ID: j4c9d1e2f3a4
Revises: g2b1c4d5e6f7
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "j4c9d1e2f3a4"
down_revision = "g2b1c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapter_profile_generation_job",
        sa.Column(
            "section_parse_mode",
            sa.String(length=64),
            nullable=False,
            server_default="docling_auto",
            comment="生成画像所使用的分章解析方法",
        ),
    )
    op.create_index(
        op.f("ix_chapter_profile_generation_job_section_parse_mode"),
        "chapter_profile_generation_job",
        ["section_parse_mode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_chapter_profile_generation_job_section_parse_mode"),
        table_name="chapter_profile_generation_job",
    )
    op.drop_column("chapter_profile_generation_job", "section_parse_mode")
