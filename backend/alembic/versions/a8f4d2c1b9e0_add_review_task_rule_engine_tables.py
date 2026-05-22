"""add review task rule engine tables

Revision ID: a8f4d2c1b9e0
Revises: c9b2a1d4e6f7
Create Date: 2026-05-22 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8f4d2c1b9e0"
down_revision: Union[str, None] = "c9b2a1d4e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_task",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=True),
        sa.Column("plan_document_id", sa.BigInteger(), nullable=False),
        sa.Column("template_id", sa.BigInteger(), nullable=True),
        sa.Column("work_type", sa.String(length=100), nullable=True),
        sa.Column("review_mode", sa.String(length=50), server_default="standard", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="created", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("critical_issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("major_issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minor_issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["plan_document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["review_template.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_task_id"), "review_task", ["id"], unique=False)
    op.create_index(op.f("ix_review_task_plan_document_id"), "review_task", ["plan_document_id"], unique=False)
    op.create_index(op.f("ix_review_task_template_id"), "review_task", ["template_id"], unique=False)
    op.create_index(op.f("ix_review_task_work_type"), "review_task", ["work_type"], unique=False)
    op.create_index(op.f("ix_review_task_status"), "review_task", ["status"], unique=False)
    op.create_index(op.f("ix_review_task_created_at"), "review_task", ["created_at"], unique=False)

    op.create_table(
        "review_issue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_issue_id"), "review_issue", ["id"], unique=False)
    op.create_index(op.f("ix_review_issue_task_id"), "review_issue", ["task_id"], unique=False)
    op.create_index(op.f("ix_review_issue_issue_type"), "review_issue", ["issue_type"], unique=False)
    op.create_index(op.f("ix_review_issue_risk_level"), "review_issue", ["risk_level"], unique=False)
    op.create_index(op.f("ix_review_issue_plan_section_id"), "review_issue", ["plan_section_id"], unique=False)
    op.create_index(op.f("ix_review_issue_source_type"), "review_issue", ["source_type"], unique=False)
    op.create_index(op.f("ix_review_issue_source_rule_id"), "review_issue", ["source_rule_id"], unique=False)
    op.create_index(op.f("ix_review_issue_source_template_rule_id"), "review_issue", ["source_template_rule_id"], unique=False)
    op.create_index(op.f("ix_review_issue_standard_clause_id"), "review_issue", ["standard_clause_id"], unique=False)
    op.create_index(op.f("ix_review_issue_status"), "review_issue", ["status"], unique=False)
    op.create_index(op.f("ix_review_issue_created_at"), "review_issue", ["created_at"], unique=False)

    op.create_table(
        "rule_execution_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_type", sa.String(length=100), nullable=True),
        sa.Column("rule_id", sa.BigInteger(), nullable=True),
        sa.Column("template_rule_id", sa.BigInteger(), nullable=True),
        sa.Column("plan_section_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("actual_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["review_task.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_section_id"], ["plan_section.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rule_execution_log_id"), "rule_execution_log", ["id"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_task_id"), "rule_execution_log", ["task_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_rule_type"), "rule_execution_log", ["rule_type"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_rule_id"), "rule_execution_log", ["rule_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_template_rule_id"), "rule_execution_log", ["template_rule_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_plan_section_id"), "rule_execution_log", ["plan_section_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_status"), "rule_execution_log", ["status"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_created_at"), "rule_execution_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rule_execution_log_created_at"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_status"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_plan_section_id"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_template_rule_id"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_rule_id"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_rule_type"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_task_id"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_rule_execution_log_id"), table_name="rule_execution_log")
    op.drop_table("rule_execution_log")

    op.drop_index(op.f("ix_review_issue_created_at"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_status"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_standard_clause_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_source_template_rule_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_source_rule_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_source_type"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_plan_section_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_risk_level"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_issue_type"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_task_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_id"), table_name="review_issue")
    op.drop_table("review_issue")

    op.drop_index(op.f("ix_review_task_created_at"), table_name="review_task")
    op.drop_index(op.f("ix_review_task_status"), table_name="review_task")
    op.drop_index(op.f("ix_review_task_work_type"), table_name="review_task")
    op.drop_index(op.f("ix_review_task_template_id"), table_name="review_task")
    op.drop_index(op.f("ix_review_task_plan_document_id"), table_name="review_task")
    op.drop_index(op.f("ix_review_task_id"), table_name="review_task")
    op.drop_table("review_task")
