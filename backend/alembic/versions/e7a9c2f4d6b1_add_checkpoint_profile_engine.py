"""add checkpoint profile review engine

Revision ID: e7a9c2f4d6b1
Revises: d8e5f6a7b8c9
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e7a9c2f4d6b1"
down_revision = "d8e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "construction_object",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="施工对象主键"),
        sa.Column("object_code", sa.String(length=100), nullable=True, comment="施工对象编码"),
        sa.Column("object_name", sa.String(length=255), nullable=False, comment="施工对象名称"),
        sa.Column("object_type", sa.String(length=100), nullable=True, comment="对象类型，例如构件、工艺、设备、部位"),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="父级施工对象ID"),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="别名列表"),
        sa.Column("related_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="相关参数名列表"),
        sa.Column("related_scenarios", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="相关施工场景列表"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["parent_id"], ["construction_object.id"], ondelete="SET NULL"),
        comment="施工对象本体词典，用于从章节中识别盘扣架、剪刀撑、基础等对象",
    )
    op.create_index(op.f("ix_construction_object_id"), "construction_object", ["id"])
    op.create_index(op.f("ix_construction_object_object_code"), "construction_object", ["object_code"])
    op.create_index(op.f("ix_construction_object_object_name"), "construction_object", ["object_name"])
    op.create_index(op.f("ix_construction_object_object_type"), "construction_object", ["object_type"])
    op.create_index(op.f("ix_construction_object_parent_id"), "construction_object", ["parent_id"])

    op.create_table(
        "chapter_review_profile",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="章节画像主键"),
        sa.Column("task_id", sa.BigInteger(), nullable=False, comment="审核任务ID"),
        sa.Column("document_id", sa.BigInteger(), nullable=False, comment="施工方案文档ID"),
        sa.Column("section_id", sa.BigInteger(), nullable=False, comment="施工方案章节ID"),
        sa.Column("chapter_title", sa.String(length=512), nullable=True, comment="章节标题"),
        sa.Column("chapter_path", sa.String(length=1024), nullable=True, comment="章节路径"),
        sa.Column("chapter_type", sa.String(length=100), nullable=True, comment="章节类型，例如施工工艺技术、工程概况"),
        sa.Column("main_domain", sa.String(length=100), nullable=True, comment="主专业领域"),
        sa.Column("subdomains", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="子领域列表"),
        sa.Column("construction_objects", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="识别到的施工对象列表"),
        sa.Column("materials", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="识别到的材料列表"),
        sa.Column("mentioned_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="识别到的参数列表"),
        sa.Column("mentioned_methods", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="识别到的施工方法列表"),
        sa.Column("mentioned_risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="识别到的风险点列表"),
        sa.Column("mentioned_standards", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="章节提到的规范标准列表"),
        sa.Column("expected_missing_objects", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="按章节类型推断应出现但未出现的对象"),
        sa.Column("summary", sa.Text(), nullable=True, comment="章节审查画像摘要"),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True, comment="画像置信度"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["plan_section.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["review_task.id"], ondelete="CASCADE"),
        comment="章节审查画像，中间语义层，承接 plan_section 与 review_checkpoint 匹配",
    )
    op.create_index(op.f("ix_chapter_review_profile_id"), "chapter_review_profile", ["id"])
    op.create_index(op.f("ix_chapter_review_profile_task_id"), "chapter_review_profile", ["task_id"])
    op.create_index(op.f("ix_chapter_review_profile_document_id"), "chapter_review_profile", ["document_id"])
    op.create_index(op.f("ix_chapter_review_profile_section_id"), "chapter_review_profile", ["section_id"])
    op.create_index(op.f("ix_chapter_review_profile_chapter_type"), "chapter_review_profile", ["chapter_type"])
    op.create_index(op.f("ix_chapter_review_profile_main_domain"), "chapter_review_profile", ["main_domain"])
    op.create_index("uq_chapter_review_profile_task_section", "chapter_review_profile", ["task_id", "section_id"], unique=True)

    op.create_table(
        "review_checkpoint",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="审查点主键"),
        sa.Column("checkpoint_code", sa.String(length=100), nullable=True, comment="审查点编码"),
        sa.Column("checkpoint_name", sa.String(length=255), nullable=False, comment="审查点名称"),
        sa.Column("checkpoint_type", sa.String(length=100), nullable=False, comment="审查点类型"),
        sa.Column("domain", sa.String(length=100), nullable=True, comment="专业领域"),
        sa.Column("subdomain", sa.String(length=100), nullable=True, comment="子领域"),
        sa.Column("work_type", sa.String(length=100), nullable=True, comment="适用工程类型"),
        sa.Column("standard_id", sa.BigInteger(), nullable=True, comment="来源规范ID"),
        sa.Column("clause_id", sa.BigInteger(), nullable=True, comment="来源规范条文ID"),
        sa.Column("clause_no", sa.String(length=100), nullable=True, comment="来源条文编号"),
        sa.Column("clause_text", sa.Text(), nullable=True, comment="来源条文原文"),
        sa.Column("chapter_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="适用章节类型列表"),
        sa.Column("target_objects", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="目标施工对象列表"),
        sa.Column("target_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="目标参数列表"),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="匹配关键词列表"),
        sa.Column("check_goal", sa.Text(), nullable=True, comment="审查目标"),
        sa.Column("check_method", sa.String(length=100), nullable=True, comment="审查方法"),
        sa.Column("expected_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="应包含内容项"),
        sa.Column("forbidden_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="禁止内容项"),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}", comment="阈值参数配置"),
        sa.Column("applicable_condition", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}", comment="适用条件"),
        sa.Column("risk_level", sa.String(length=50), nullable=False, server_default="major", comment="风险等级"),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="是否强制性条文"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0", comment="优先级"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active", comment="状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["clause_id"], ["standard_clause.id"]),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"]),
        comment="规范审查点库，由规范条文转成可匹配、可执行的中间规则",
    )
    for column in (
        "id",
        "checkpoint_code",
        "checkpoint_name",
        "checkpoint_type",
        "domain",
        "subdomain",
        "work_type",
        "standard_id",
        "clause_id",
        "clause_no",
        "risk_level",
        "is_mandatory",
        "priority",
        "status",
        "created_at",
    ):
        op.create_index(op.f(f"ix_review_checkpoint_{column}"), "review_checkpoint", [column])

    op.create_table(
        "checkpoint_match_result",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="审查点匹配结果主键"),
        sa.Column("task_id", sa.BigInteger(), nullable=False, comment="审核任务ID"),
        sa.Column("section_id", sa.BigInteger(), nullable=False, comment="章节ID"),
        sa.Column("checkpoint_id", sa.BigInteger(), nullable=False, comment="审查点ID"),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=False, server_default="0", comment="匹配分数"),
        sa.Column("match_reason", sa.Text(), nullable=True, comment="匹配原因"),
        sa.Column("match_dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}", comment="各维度命中详情"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="candidate", comment="匹配状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["review_checkpoint.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["plan_section.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["review_task.id"], ondelete="CASCADE"),
        comment="章节画像与审查点的匹配结果",
    )
    op.create_index(op.f("ix_checkpoint_match_result_id"), "checkpoint_match_result", ["id"])
    op.create_index(op.f("ix_checkpoint_match_result_task_id"), "checkpoint_match_result", ["task_id"])
    op.create_index(op.f("ix_checkpoint_match_result_section_id"), "checkpoint_match_result", ["section_id"])
    op.create_index(op.f("ix_checkpoint_match_result_checkpoint_id"), "checkpoint_match_result", ["checkpoint_id"])
    op.create_index(op.f("ix_checkpoint_match_result_status"), "checkpoint_match_result", ["status"])
    op.create_index("uq_checkpoint_match_task_section_checkpoint", "checkpoint_match_result", ["task_id", "section_id", "checkpoint_id"], unique=True)

    op.add_column("review_issue", sa.Column("checkpoint_id", sa.BigInteger(), nullable=True, comment="关联审查点ID"))
    op.add_column("review_issue", sa.Column("match_result_id", sa.BigInteger(), nullable=True, comment="关联审查点匹配结果ID"))
    op.add_column("review_issue", sa.Column("confidence", sa.Numeric(5, 2), nullable=True, comment="问题置信度"))
    op.add_column("review_issue", sa.Column("confidence_reason", sa.Text(), nullable=True, comment="问题置信度说明"))
    op.create_foreign_key("fk_review_issue_checkpoint_id", "review_issue", "review_checkpoint", ["checkpoint_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_review_issue_match_result_id",
        "review_issue",
        "checkpoint_match_result",
        ["match_result_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_review_issue_checkpoint_id"), "review_issue", ["checkpoint_id"])
    op.create_index(op.f("ix_review_issue_match_result_id"), "review_issue", ["match_result_id"])

    op.create_table(
        "review_issue_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="问题证据主键"),
        sa.Column("issue_id", sa.BigInteger(), nullable=False, comment="审核问题ID"),
        sa.Column("evidence_type", sa.String(length=100), nullable=True, comment="证据类型"),
        sa.Column("standard_id", sa.BigInteger(), nullable=True, comment="规范ID"),
        sa.Column("clause_id", sa.BigInteger(), nullable=True, comment="条文ID"),
        sa.Column("clause_no", sa.String(length=100), nullable=True, comment="条文编号"),
        sa.Column("clause_text", sa.Text(), nullable=True, comment="条文原文"),
        sa.Column("plan_section_id", sa.BigInteger(), nullable=True, comment="方案章节ID"),
        sa.Column("plan_text", sa.Text(), nullable=True, comment="方案原文片段"),
        sa.Column("checkpoint_id", sa.BigInteger(), nullable=True, comment="审查点ID"),
        sa.Column("match_reason", sa.Text(), nullable=True, comment="匹配原因"),
        sa.Column("score", sa.Numeric(5, 2), nullable=True, comment="证据或匹配分数"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["review_checkpoint.id"]),
        sa.ForeignKeyConstraint(["clause_id"], ["standard_clause.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["review_issue.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_section_id"], ["plan_section.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["standard_id"], ["standard_document.id"]),
        comment="审核问题证据表，记录规范条文、方案文本、匹配原因和分数",
    )
    op.create_index(op.f("ix_review_issue_evidence_id"), "review_issue_evidence", ["id"])
    op.create_index(op.f("ix_review_issue_evidence_issue_id"), "review_issue_evidence", ["issue_id"])
    op.create_index(op.f("ix_review_issue_evidence_evidence_type"), "review_issue_evidence", ["evidence_type"])
    op.create_index(op.f("ix_review_issue_evidence_standard_id"), "review_issue_evidence", ["standard_id"])
    op.create_index(op.f("ix_review_issue_evidence_clause_id"), "review_issue_evidence", ["clause_id"])
    op.create_index(op.f("ix_review_issue_evidence_plan_section_id"), "review_issue_evidence", ["plan_section_id"])
    op.create_index(op.f("ix_review_issue_evidence_checkpoint_id"), "review_issue_evidence", ["checkpoint_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_review_issue_evidence_checkpoint_id"), table_name="review_issue_evidence")
    op.drop_index(op.f("ix_review_issue_evidence_plan_section_id"), table_name="review_issue_evidence")
    op.drop_index(op.f("ix_review_issue_evidence_clause_id"), table_name="review_issue_evidence")
    op.drop_index(op.f("ix_review_issue_evidence_standard_id"), table_name="review_issue_evidence")
    op.drop_index(op.f("ix_review_issue_evidence_evidence_type"), table_name="review_issue_evidence")
    op.drop_index(op.f("ix_review_issue_evidence_issue_id"), table_name="review_issue_evidence")
    op.drop_index(op.f("ix_review_issue_evidence_id"), table_name="review_issue_evidence")
    op.drop_table("review_issue_evidence")

    op.drop_index(op.f("ix_review_issue_match_result_id"), table_name="review_issue")
    op.drop_index(op.f("ix_review_issue_checkpoint_id"), table_name="review_issue")
    op.drop_constraint("fk_review_issue_match_result_id", "review_issue", type_="foreignkey")
    op.drop_constraint("fk_review_issue_checkpoint_id", "review_issue", type_="foreignkey")
    op.drop_column("review_issue", "confidence_reason")
    op.drop_column("review_issue", "confidence")
    op.drop_column("review_issue", "match_result_id")
    op.drop_column("review_issue", "checkpoint_id")

    op.drop_index("uq_checkpoint_match_task_section_checkpoint", table_name="checkpoint_match_result")
    op.drop_index(op.f("ix_checkpoint_match_result_status"), table_name="checkpoint_match_result")
    op.drop_index(op.f("ix_checkpoint_match_result_checkpoint_id"), table_name="checkpoint_match_result")
    op.drop_index(op.f("ix_checkpoint_match_result_section_id"), table_name="checkpoint_match_result")
    op.drop_index(op.f("ix_checkpoint_match_result_task_id"), table_name="checkpoint_match_result")
    op.drop_index(op.f("ix_checkpoint_match_result_id"), table_name="checkpoint_match_result")
    op.drop_table("checkpoint_match_result")

    for column in reversed(
        (
            "id",
            "checkpoint_code",
            "checkpoint_name",
            "checkpoint_type",
            "domain",
            "subdomain",
            "work_type",
            "standard_id",
            "clause_id",
            "clause_no",
            "risk_level",
            "is_mandatory",
            "priority",
            "status",
            "created_at",
        )
    ):
        op.drop_index(op.f(f"ix_review_checkpoint_{column}"), table_name="review_checkpoint")
    op.drop_table("review_checkpoint")

    op.drop_index("uq_chapter_review_profile_task_section", table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_main_domain"), table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_chapter_type"), table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_section_id"), table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_document_id"), table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_task_id"), table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_id"), table_name="chapter_review_profile")
    op.drop_table("chapter_review_profile")

    op.drop_index(op.f("ix_construction_object_parent_id"), table_name="construction_object")
    op.drop_index(op.f("ix_construction_object_object_type"), table_name="construction_object")
    op.drop_index(op.f("ix_construction_object_object_name"), table_name="construction_object")
    op.drop_index(op.f("ix_construction_object_object_code"), table_name="construction_object")
    op.drop_index(op.f("ix_construction_object_id"), table_name="construction_object")
    op.drop_table("construction_object")
