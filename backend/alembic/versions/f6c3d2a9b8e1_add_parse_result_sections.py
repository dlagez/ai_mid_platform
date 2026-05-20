"""add parse result sections

Revision ID: f6c3d2a9b8e1
Revises: e4a1d7b9c6f2
Create Date: 2026-05-20 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6c3d2a9b8e1"
down_revision: Union[str, None] = "e4a1d7b9c6f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parse_result_section",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("title_level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("section_no", sa.String(length=64), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["parse_result.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["parse_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["parse_result_section.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parse_result_section_document_id"), "parse_result_section", ["document_id"], unique=False)
    op.create_index(op.f("ix_parse_result_section_id"), "parse_result_section", ["id"], unique=False)
    op.create_index(op.f("ix_parse_result_section_job_id"), "parse_result_section", ["job_id"], unique=False)
    op.create_index(op.f("ix_parse_result_section_parent_id"), "parse_result_section", ["parent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parse_result_section_parent_id"), table_name="parse_result_section")
    op.drop_index(op.f("ix_parse_result_section_job_id"), table_name="parse_result_section")
    op.drop_index(op.f("ix_parse_result_section_id"), table_name="parse_result_section")
    op.drop_index(op.f("ix_parse_result_section_document_id"), table_name="parse_result_section")
    op.drop_table("parse_result_section")
