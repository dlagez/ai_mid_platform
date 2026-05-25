"""add checkpoint generation jobs

Revision ID: f4c8e2a1b7d0
Revises: e7a9c2f4d6b1
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f4c8e2a1b7d0"
down_revision = "e7a9c2f4d6b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_checkpoint_generation_job",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="审查点生成任务主键"),
        sa.Column("standard_id", sa.BigInteger(), nullable=True, comment="来源规范ID"),
        sa.Column("clause_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="本次提交的规范条文ID列表"),
        sa.Column("use_llm", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="是否使用大模型生成"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued", comment="任务状态：queued/running/success/partial_success/failed"),
        sa.Column("total_clauses", sa.Integer(), nullable=False, server_default="0", comment="总条文数"),
        sa.Column("processed_clauses", sa.Integer(), nullable=False, server_default="0", comment="已处理条文数"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0", comment="已生成审查点数量"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0", comment="失败条文数量"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0", comment="跳过条文数量"),
        sa.Column("checkpoint_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="本任务生成的审查点ID列表"),
        sa.Column("failed", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="失败明细"),
        sa.Column("skipped", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="跳过明细"),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True, comment="Celery 异步任务ID"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="任务级错误信息"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="创建人用户ID"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="SET NULL"),
        comment="从规范条文异步生成审查点的任务表，用于展示队列进度和汇总结果",
    )
    for column in ("id", "standard_id", "status", "celery_task_id", "created_by", "created_at"):
        op.create_index(op.f(f"ix_review_checkpoint_generation_job_{column}"), "review_checkpoint_generation_job", [column])

    op.create_table(
        "review_checkpoint_generation_item",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="审查点生成任务条目主键"),
        sa.Column("job_id", sa.BigInteger(), nullable=False, comment="所属生成任务ID"),
        sa.Column("standard_id", sa.BigInteger(), nullable=True, comment="来源规范ID"),
        sa.Column("clause_id", sa.BigInteger(), nullable=True, comment="来源规范条文ID"),
        sa.Column("clause_no", sa.String(length=100), nullable=True, comment="条文编号快照"),
        sa.Column("clause_title", sa.String(length=255), nullable=True, comment="条文标题快照"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued", comment="条目状态：queued/running/success/skipped/failed"),
        sa.Column("checkpoint_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="该条文生成的审查点ID列表"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0", comment="该条文生成的审查点数量"),
        sa.Column("message", sa.Text(), nullable=True, comment="处理结果说明或失败原因"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["clause_id"], ["standard_clause.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["review_checkpoint_generation_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"], ondelete="SET NULL"),
        comment="从规范条文生成审查点的逐条处理明细，记录 clause 到 checkpoint 的映射",
    )
    for column in ("id", "job_id", "standard_id", "clause_id", "clause_no", "status", "created_at"):
        op.create_index(op.f(f"ix_review_checkpoint_generation_item_{column}"), "review_checkpoint_generation_item", [column])


def downgrade() -> None:
    for column in ("id", "job_id", "standard_id", "clause_id", "clause_no", "status", "created_at"):
        op.drop_index(op.f(f"ix_review_checkpoint_generation_item_{column}"), table_name="review_checkpoint_generation_item")
    op.drop_table("review_checkpoint_generation_item")

    for column in ("id", "standard_id", "status", "celery_task_id", "created_by", "created_at"):
        op.drop_index(op.f(f"ix_review_checkpoint_generation_job_{column}"), table_name="review_checkpoint_generation_job")
    op.drop_table("review_checkpoint_generation_job")
