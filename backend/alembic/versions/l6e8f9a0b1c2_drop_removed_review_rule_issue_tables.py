"""drop removed review rule issue tables

Revision ID: l6e8f9a0b1c2
Revises: k5d7e8f9a0b1
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "l6e8f9a0b1c2"
down_revision = "k5d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in (
        "review_issue_evidence",
        "review_issue",
        "review_rule",
        "review_rule_candidate",
    ):
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))


def downgrade() -> None:
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
    op.create_index(op.f("ix_review_rule_candidate_id"), "review_rule_candidate", ["id"])
    op.create_index(op.f("ix_review_rule_candidate_standard_id"), "review_rule_candidate", ["standard_id"])
    op.create_index(op.f("ix_review_rule_candidate_clause_id"), "review_rule_candidate", ["clause_id"])
    op.create_index(op.f("ix_review_rule_candidate_rule_type"), "review_rule_candidate", ["rule_type"])
    op.create_index(op.f("ix_review_rule_candidate_work_type"), "review_rule_candidate", ["work_type"])
    op.create_index(op.f("ix_review_rule_candidate_status"), "review_rule_candidate", ["status"])
    op.create_index(op.f("ix_review_rule_candidate_created_at"), "review_rule_candidate", ["created_at"])

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
    op.create_index(op.f("ix_review_rule_id"), "review_rule", ["id"])
    op.create_index(op.f("ix_review_rule_source_candidate_id"), "review_rule", ["source_candidate_id"])
    op.create_index(op.f("ix_review_rule_source_type"), "review_rule", ["source_type"])
    op.create_index(op.f("ix_review_rule_standard_id"), "review_rule", ["standard_id"])
    op.create_index(op.f("ix_review_rule_clause_id"), "review_rule", ["clause_id"])
    op.create_index(op.f("ix_review_rule_rule_type"), "review_rule", ["rule_type"])
    op.create_index(op.f("ix_review_rule_work_type"), "review_rule", ["work_type"])
    op.create_index(op.f("ix_review_rule_risk_level"), "review_rule", ["risk_level"])
    op.create_index(op.f("ix_review_rule_status"), "review_rule", ["status"])
    op.create_index(op.f("ix_review_rule_created_at"), "review_rule", ["created_at"])

    op.create_table(
        "review_issue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("issue_type", sa.String(length=100), nullable=True),
        sa.Column("risk_level", sa.String(length=50), nullable=True),
        sa.Column("issue_title", sa.String(length=255), nullable=True),
        sa.Column("issue_description", sa.Text(), nullable=True),
        sa.Column("plan_section_id", sa.BigInteger(), nullable=True),
        sa.Column("plan_section_title", sa.String(length=255), nullable=True),
        sa.Column("plan_original_text", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_rule_id", sa.BigInteger(), nullable=True),
        sa.Column("source_template_rule_id", sa.BigInteger(), nullable=True),
        sa.Column("standard_clause_id", sa.BigInteger(), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("checkpoint_id", sa.BigInteger(), nullable=True),
        sa.Column("match_result_id", sa.BigInteger(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("confidence_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pending_confirm", nullable=False),
        sa.Column("expert_comment", sa.Text(), nullable=True),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["review_task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_section_id"], ["plan_section.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_rule_id"], ["review_rule.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_template_rule_id"], ["template_section_rule.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["standard_clause_id"], ["standard_clause.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["review_checkpoint.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["match_result_id"], ["checkpoint_match_result.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_issue_id"), "review_issue", ["id"])
    op.create_index(op.f("ix_review_issue_task_id"), "review_issue", ["task_id"])
    op.create_index(op.f("ix_review_issue_version"), "review_issue", ["version"])
    op.create_index("ix_review_issue_task_id_version", "review_issue", ["task_id", "version"])
    op.create_index(op.f("ix_review_issue_issue_type"), "review_issue", ["issue_type"])
    op.create_index(op.f("ix_review_issue_risk_level"), "review_issue", ["risk_level"])
    op.create_index(op.f("ix_review_issue_plan_section_id"), "review_issue", ["plan_section_id"])
    op.create_index(op.f("ix_review_issue_source_type"), "review_issue", ["source_type"])
    op.create_index(op.f("ix_review_issue_source_rule_id"), "review_issue", ["source_rule_id"])
    op.create_index(op.f("ix_review_issue_source_template_rule_id"), "review_issue", ["source_template_rule_id"])
    op.create_index(op.f("ix_review_issue_standard_clause_id"), "review_issue", ["standard_clause_id"])
    op.create_index(op.f("ix_review_issue_checkpoint_id"), "review_issue", ["checkpoint_id"])
    op.create_index(op.f("ix_review_issue_match_result_id"), "review_issue", ["match_result_id"])
    op.create_index(op.f("ix_review_issue_status"), "review_issue", ["status"])
    op.create_index(op.f("ix_review_issue_created_at"), "review_issue", ["created_at"])

    op.create_table(
        "review_issue_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=True),
        sa.Column("standard_id", sa.BigInteger(), nullable=True),
        sa.Column("clause_id", sa.BigInteger(), nullable=True),
        sa.Column("clause_no", sa.String(length=100), nullable=True),
        sa.Column("clause_text", sa.Text(), nullable=True),
        sa.Column("plan_section_id", sa.BigInteger(), nullable=True),
        sa.Column("plan_text", sa.Text(), nullable=True),
        sa.Column("checkpoint_id", sa.BigInteger(), nullable=True),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["review_checkpoint.id"]),
        sa.ForeignKeyConstraint(["clause_id"], ["standard_clause.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["review_issue.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_section_id"], ["plan_section.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"]),
    )
    op.create_index(op.f("ix_review_issue_evidence_id"), "review_issue_evidence", ["id"])
    op.create_index(op.f("ix_review_issue_evidence_issue_id"), "review_issue_evidence", ["issue_id"])
    op.create_index(op.f("ix_review_issue_evidence_evidence_type"), "review_issue_evidence", ["evidence_type"])
    op.create_index(op.f("ix_review_issue_evidence_standard_id"), "review_issue_evidence", ["standard_id"])
    op.create_index(op.f("ix_review_issue_evidence_clause_id"), "review_issue_evidence", ["clause_id"])
    op.create_index(op.f("ix_review_issue_evidence_plan_section_id"), "review_issue_evidence", ["plan_section_id"])
    op.create_index(op.f("ix_review_issue_evidence_checkpoint_id"), "review_issue_evidence", ["checkpoint_id"])
