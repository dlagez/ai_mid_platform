"""add review template standard rule tables

Revision ID: c9b2a1d4e6f7
Revises: f6c3d2a9b8e1
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c9b2a1d4e6f7"
down_revision: Union[str, None] = "f6c3d2a9b8e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_template",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("work_type", sa.String(length=100), nullable=True),
        sa.Column("source_document_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=50), server_default="v1.0", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["plan_document.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_template_id"), "review_template", ["id"], unique=False)
    op.create_index(op.f("ix_review_template_code"), "review_template", ["code"], unique=False)
    op.create_index(op.f("ix_review_template_work_type"), "review_template", ["work_type"], unique=False)
    op.create_index(op.f("ix_review_template_status"), "review_template", ["status"], unique=False)
    op.create_index(op.f("ix_review_template_source_document_id"), "review_template", ["source_document_id"], unique=False)
    op.create_index(op.f("ix_review_template_created_at"), "review_template", ["created_at"], unique=False)

    op.create_table(
        "template_section_rule",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("section_code", sa.String(length=100), nullable=True),
        sa.Column("standard_title", sa.String(length=255), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "required_points",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("min_word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("risk_level", sa.String(length=50), server_default="major", nullable=False),
        sa.Column("match_strategy", sa.String(length=50), server_default="title_semantic", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["review_template.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["template_section_rule.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_section_rule_id"), "template_section_rule", ["id"], unique=False)
    op.create_index(op.f("ix_template_section_rule_template_id"), "template_section_rule", ["template_id"], unique=False)
    op.create_index(op.f("ix_template_section_rule_parent_id"), "template_section_rule", ["parent_id"], unique=False)
    op.create_index(op.f("ix_template_section_rule_enabled"), "template_section_rule", ["enabled"], unique=False)

    op.create_table(
        "standard_document",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("standard_code", sa.String(length=100), nullable=True),
        sa.Column("standard_name", sa.String(length=255), nullable=False),
        sa.Column("standard_type", sa.String(length=50), nullable=True),
        sa.Column("version", sa.String(length=50), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_file_id", sa.BigInteger(), nullable=True),
        sa.Column("source_document_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["parse_result.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_standard_document_id"), "standard_document", ["id"], unique=False)
    op.create_index(op.f("ix_standard_document_standard_code"), "standard_document", ["standard_code"], unique=False)
    op.create_index(op.f("ix_standard_document_standard_type"), "standard_document", ["standard_type"], unique=False)
    op.create_index(op.f("ix_standard_document_source_file_id"), "standard_document", ["source_file_id"], unique=False)
    op.create_index(op.f("ix_standard_document_source_document_id"), "standard_document", ["source_document_id"], unique=False)
    op.create_index(op.f("ix_standard_document_status"), "standard_document", ["status"], unique=False)
    op.create_index(op.f("ix_standard_document_created_at"), "standard_document", ["created_at"], unique=False)

    op.create_table(
        "standard_clause",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("standard_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("chapter_no", sa.String(length=50), nullable=True),
        sa.Column("clause_no", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("level", sa.Integer(), server_default="1", nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "applicable_work_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_section_id", sa.BigInteger(), nullable=True),
        sa.Column("order_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["standard_clause.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_section_id"], ["parse_result_section.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_standard_clause_id"), "standard_clause", ["id"], unique=False)
    op.create_index(op.f("ix_standard_clause_standard_id"), "standard_clause", ["standard_id"], unique=False)
    op.create_index(op.f("ix_standard_clause_parent_id"), "standard_clause", ["parent_id"], unique=False)
    op.create_index(op.f("ix_standard_clause_clause_no"), "standard_clause", ["clause_no"], unique=False)
    op.create_index(op.f("ix_standard_clause_is_mandatory"), "standard_clause", ["is_mandatory"], unique=False)
    op.create_index(op.f("ix_standard_clause_source_section_id"), "standard_clause", ["source_section_id"], unique=False)

    op.create_table(
        "review_rule_candidate",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("standard_id", sa.BigInteger(), nullable=True),
        sa.Column("clause_id", sa.BigInteger(), nullable=True),
        sa.Column("rule_name", sa.String(length=255), nullable=True),
        sa.Column("rule_type", sa.String(length=100), nullable=True),
        sa.Column("work_type", sa.String(length=100), nullable=True),
        sa.Column("check_object", sa.String(length=255), nullable=True),
        sa.Column("operator", sa.String(length=20), nullable=True),
        sa.Column("threshold_value", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column(
            "required_items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "forbidden_items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "applicable_condition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("risk_level_suggestion", sa.String(length=50), nullable=True),
        sa.Column("source_clause_text", sa.Text(), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pending_review", nullable=False),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["clause_id"], ["standard_clause.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_rule_candidate_id"), "review_rule_candidate", ["id"], unique=False)
    op.create_index(op.f("ix_review_rule_candidate_standard_id"), "review_rule_candidate", ["standard_id"], unique=False)
    op.create_index(op.f("ix_review_rule_candidate_clause_id"), "review_rule_candidate", ["clause_id"], unique=False)
    op.create_index(op.f("ix_review_rule_candidate_rule_type"), "review_rule_candidate", ["rule_type"], unique=False)
    op.create_index(op.f("ix_review_rule_candidate_work_type"), "review_rule_candidate", ["work_type"], unique=False)
    op.create_index(op.f("ix_review_rule_candidate_status"), "review_rule_candidate", ["status"], unique=False)
    op.create_index(op.f("ix_review_rule_candidate_created_at"), "review_rule_candidate", ["created_at"], unique=False)

    op.create_table(
        "review_rule",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("standard_id", sa.BigInteger(), nullable=True),
        sa.Column("clause_id", sa.BigInteger(), nullable=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=100), nullable=False),
        sa.Column("work_type", sa.String(length=100), nullable=True),
        sa.Column("check_object", sa.String(length=255), nullable=True),
        sa.Column("operator", sa.String(length=20), nullable=True),
        sa.Column("threshold_value", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column(
            "required_items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "forbidden_items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "applicable_condition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("risk_level", sa.String(length=50), server_default="major", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="active", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["review_rule_candidate.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["clause_id"], ["standard_clause.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_rule_id"), "review_rule", ["id"], unique=False)
    op.create_index(op.f("ix_review_rule_source_candidate_id"), "review_rule", ["source_candidate_id"], unique=False)
    op.create_index(op.f("ix_review_rule_source_type"), "review_rule", ["source_type"], unique=False)
    op.create_index(op.f("ix_review_rule_standard_id"), "review_rule", ["standard_id"], unique=False)
    op.create_index(op.f("ix_review_rule_clause_id"), "review_rule", ["clause_id"], unique=False)
    op.create_index(op.f("ix_review_rule_rule_type"), "review_rule", ["rule_type"], unique=False)
    op.create_index(op.f("ix_review_rule_work_type"), "review_rule", ["work_type"], unique=False)
    op.create_index(op.f("ix_review_rule_risk_level"), "review_rule", ["risk_level"], unique=False)
    op.create_index(op.f("ix_review_rule_status"), "review_rule", ["status"], unique=False)
    op.create_index(op.f("ix_review_rule_created_at"), "review_rule", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("review_rule")
    op.drop_table("review_rule_candidate")
    op.drop_table("standard_clause")
    op.drop_table("standard_document")
    op.drop_table("template_section_rule")
    op.drop_table("review_template")
