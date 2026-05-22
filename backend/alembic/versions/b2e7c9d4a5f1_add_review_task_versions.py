"""add review task versions

Revision ID: b2e7c9d4a5f1
Revises: a8f4d2c1b9e0
Create Date: 2026-05-22 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2e7c9d4a5f1"
down_revision: Union[str, None] = "a8f4d2c1b9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "review_task",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "review_issue",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "rule_execution_log",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index(op.f("ix_review_task_version"), "review_task", ["version"], unique=False)
    op.create_index(op.f("ix_review_issue_version"), "review_issue", ["version"], unique=False)
    op.create_index(op.f("ix_rule_execution_log_version"), "rule_execution_log", ["version"], unique=False)
    op.create_index("ix_review_issue_task_id_version", "review_issue", ["task_id", "version"], unique=False)
    op.create_index("ix_rule_execution_log_task_id_version", "rule_execution_log", ["task_id", "version"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rule_execution_log_task_id_version", table_name="rule_execution_log")
    op.drop_index("ix_review_issue_task_id_version", table_name="review_issue")
    op.drop_index(op.f("ix_rule_execution_log_version"), table_name="rule_execution_log")
    op.drop_index(op.f("ix_review_issue_version"), table_name="review_issue")
    op.drop_index(op.f("ix_review_task_version"), table_name="review_task")
    op.drop_column("rule_execution_log", "version")
    op.drop_column("review_issue", "version")
    op.drop_column("review_task", "version")
