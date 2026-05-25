"""add chapter profile generation jobs

Revision ID: g2b1c4d5e6f7
Revises: f4c8e2a1b7d0
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "g2b1c4d5e6f7"
down_revision = "f4c8e2a1b7d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("chapter_review_profile", "task_id", existing_type=sa.BigInteger(), nullable=True)

    op.create_table(
        "chapter_profile_generation_job",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False, comment="施工方案文档ID，关联 plan_document"),
        sa.Column("task_id", sa.BigInteger(), nullable=True, comment="可选审核任务ID；上传页生成时为空"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued", comment="任务状态：queued/running/success/partial_success/failed"),
        sa.Column("total_sections", sa.Integer(), nullable=False, server_default="0", comment="待生成画像的章节总数"),
        sa.Column("processed_sections", sa.Integer(), nullable=False, server_default="0", comment="已处理章节数"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0", comment="成功生成画像数"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0", comment="更新画像数"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0", comment="失败章节数"),
        sa.Column("rule_only_count", sa.Integer(), nullable=False, server_default="0", comment="LLM失败后仅使用规则生成的章节数"),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True, comment="Celery 异步任务ID"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="任务级错误信息"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="创建人ID，当前认证没有数字ID时为空"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["review_task.id"], ondelete="SET NULL"),
        comment="章节画像生成队列任务表",
    )
    op.create_index(op.f("ix_chapter_profile_generation_job_id"), "chapter_profile_generation_job", ["id"])
    op.create_index(op.f("ix_chapter_profile_generation_job_document_id"), "chapter_profile_generation_job", ["document_id"])
    op.create_index(op.f("ix_chapter_profile_generation_job_task_id"), "chapter_profile_generation_job", ["task_id"])
    op.create_index(op.f("ix_chapter_profile_generation_job_status"), "chapter_profile_generation_job", ["status"])
    op.create_index(op.f("ix_chapter_profile_generation_job_celery_task_id"), "chapter_profile_generation_job", ["celery_task_id"])
    op.create_index(op.f("ix_chapter_profile_generation_job_created_by"), "chapter_profile_generation_job", ["created_by"])
    op.create_index(op.f("ix_chapter_profile_generation_job_created_at"), "chapter_profile_generation_job", ["created_at"])

    op.create_table(
        "chapter_profile_generation_item",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False, comment="画像生成任务ID"),
        sa.Column("document_id", sa.BigInteger(), nullable=False, comment="施工方案文档ID"),
        sa.Column("section_id", sa.BigInteger(), nullable=True, comment="章节ID，关联 plan_section"),
        sa.Column("section_title", sa.String(length=512), nullable=True, comment="章节标题快照"),
        sa.Column("section_path", sa.String(length=1024), nullable=True, comment="章节路径快照"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued", comment="章节处理状态：queued/running/success/rule_only/failed"),
        sa.Column("profile_id", sa.BigInteger(), nullable=True, comment="生成的 chapter_review_profile ID"),
        sa.Column("used_llm", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="是否成功使用大模型抽取"),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True, comment="画像置信度"),
        sa.Column("message", sa.Text(), nullable=True, comment="章节处理信息或错误原因"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("finished_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["chapter_profile_generation_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["chapter_review_profile.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["section_id"], ["plan_section.id"], ondelete="SET NULL"),
        comment="章节画像生成队列明细表",
    )
    op.create_index(op.f("ix_chapter_profile_generation_item_id"), "chapter_profile_generation_item", ["id"])
    op.create_index(op.f("ix_chapter_profile_generation_item_job_id"), "chapter_profile_generation_item", ["job_id"])
    op.create_index(op.f("ix_chapter_profile_generation_item_document_id"), "chapter_profile_generation_item", ["document_id"])
    op.create_index(op.f("ix_chapter_profile_generation_item_section_id"), "chapter_profile_generation_item", ["section_id"])
    op.create_index(op.f("ix_chapter_profile_generation_item_status"), "chapter_profile_generation_item", ["status"])
    op.create_index(op.f("ix_chapter_profile_generation_item_profile_id"), "chapter_profile_generation_item", ["profile_id"])
    op.create_index(op.f("ix_chapter_profile_generation_item_created_at"), "chapter_profile_generation_item", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_chapter_profile_generation_item_created_at"), table_name="chapter_profile_generation_item")
    op.drop_index(op.f("ix_chapter_profile_generation_item_profile_id"), table_name="chapter_profile_generation_item")
    op.drop_index(op.f("ix_chapter_profile_generation_item_status"), table_name="chapter_profile_generation_item")
    op.drop_index(op.f("ix_chapter_profile_generation_item_section_id"), table_name="chapter_profile_generation_item")
    op.drop_index(op.f("ix_chapter_profile_generation_item_document_id"), table_name="chapter_profile_generation_item")
    op.drop_index(op.f("ix_chapter_profile_generation_item_job_id"), table_name="chapter_profile_generation_item")
    op.drop_index(op.f("ix_chapter_profile_generation_item_id"), table_name="chapter_profile_generation_item")
    op.drop_table("chapter_profile_generation_item")

    op.drop_index(op.f("ix_chapter_profile_generation_job_created_at"), table_name="chapter_profile_generation_job")
    op.drop_index(op.f("ix_chapter_profile_generation_job_created_by"), table_name="chapter_profile_generation_job")
    op.drop_index(op.f("ix_chapter_profile_generation_job_celery_task_id"), table_name="chapter_profile_generation_job")
    op.drop_index(op.f("ix_chapter_profile_generation_job_status"), table_name="chapter_profile_generation_job")
    op.drop_index(op.f("ix_chapter_profile_generation_job_task_id"), table_name="chapter_profile_generation_job")
    op.drop_index(op.f("ix_chapter_profile_generation_job_document_id"), table_name="chapter_profile_generation_job")
    op.drop_index(op.f("ix_chapter_profile_generation_job_id"), table_name="chapter_profile_generation_job")
    op.drop_table("chapter_profile_generation_job")

    op.alter_column("chapter_review_profile", "task_id", existing_type=sa.BigInteger(), nullable=False)
