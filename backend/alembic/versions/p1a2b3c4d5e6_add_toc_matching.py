"""add toc matching

Revision ID: p1a2b3c4d5e6
Revises: o9c1d2e3f4a5
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p1a2b3c4d5e6"
down_revision = "o9c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "toc_match_job",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("plan_document_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_parse_result_id", sa.BigInteger(), nullable=True),
        sa.Column("standard_id", sa.BigInteger(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("raw_llm_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["plan_document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_parse_result_id"], ["plan_parse_result.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "plan_document_id", "plan_parse_result_id", "standard_id", "status", "created_by", "created_at"):
        op.create_index(op.f(f"ix_toc_match_job_{column}"), "toc_match_job", [column])

    op.create_table(
        "toc_match_item",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("standard_id", sa.BigInteger(), nullable=False),
        sa.Column("standard_clause_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_document_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_section_id", sa.BigInteger(), nullable=False),
        sa.Column("match_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["toc_match_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["standard_clause_id"], ["standard_clause.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_section_id"], ["plan_section.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "job_id", "standard_id", "standard_clause_id", "plan_document_id", "plan_section_id", "created_at"):
        op.create_index(op.f(f"ix_toc_match_item_{column}"), "toc_match_item", [column])


def downgrade() -> None:
    for column in ("created_at", "plan_section_id", "plan_document_id", "standard_clause_id", "standard_id", "job_id", "id"):
        op.drop_index(op.f(f"ix_toc_match_item_{column}"), table_name="toc_match_item")
    op.drop_table("toc_match_item")
    for column in ("created_at", "created_by", "status", "standard_id", "plan_parse_result_id", "plan_document_id", "id"):
        op.drop_index(op.f(f"ix_toc_match_job_{column}"), table_name="toc_match_job")
    op.drop_table("toc_match_job")
