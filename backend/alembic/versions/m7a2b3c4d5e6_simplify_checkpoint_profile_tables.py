"""simplify checkpoint and chapter profile tables

Revision ID: m7a2b3c4d5e6
Revises: l6e8f9a0b1c2
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "m7a2b3c4d5e6"
down_revision = "l6e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_checkpoint", sa.Column("rule_code", sa.String(length=100), nullable=True, comment="审查规则编码"))
    op.add_column("review_checkpoint", sa.Column("rule_text", sa.Text(), nullable=True, comment="最小规范审查点"))
    op.add_column(
        "review_checkpoint",
        sa.Column("object_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="对象词列表"),
    )
    op.add_column("review_checkpoint", sa.Column("context_text", sa.Text(), nullable=True, comment="父级条件/适用场景"))
    op.add_column("review_checkpoint", sa.Column("confidence", sa.Numeric(5, 2), nullable=True, comment="抽取置信度"))
    op.execute(
        """
        UPDATE review_checkpoint
        SET
            rule_code = COALESCE(rule_code, checkpoint_code),
            rule_text = COALESCE(NULLIF(rule_text, ''), NULLIF(checkpoint_name, ''), NULLIF(check_goal, ''), NULLIF(clause_text, ''), ''),
            object_terms = CASE
                WHEN object_terms IS NOT NULL AND object_terms <> '[]'::jsonb THEN object_terms
                WHEN target_objects IS NOT NULL THEN target_objects
                ELSE '[]'::jsonb
            END,
            context_text = COALESCE(NULLIF(context_text, ''), NULLIF(check_goal, ''), NULLIF(clause_text, ''))
        """
    )
    op.alter_column("review_checkpoint", "rule_text", nullable=False)
    op.create_index(op.f("ix_review_checkpoint_rule_code"), "review_checkpoint", ["rule_code"])

    op.add_column("chapter_review_profile", sa.Column("evidence_code", sa.String(length=100), nullable=True, comment="方案证据编码"))
    op.add_column("chapter_review_profile", sa.Column("evidence_text", sa.Text(), nullable=True, comment="最小方案证据点"))
    op.add_column(
        "chapter_review_profile",
        sa.Column("object_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]", comment="对象词列表"),
    )
    op.add_column("chapter_review_profile", sa.Column("context_text", sa.Text(), nullable=True, comment="上下文/适用场景"))
    op.add_column("chapter_review_profile", sa.Column("source_text", sa.Text(), nullable=True, comment="原始句子或段落"))
    op.add_column("chapter_review_profile", sa.Column("status", sa.String(length=50), nullable=False, server_default="active", comment="状态"))
    op.execute(
        """
        UPDATE chapter_review_profile
        SET
            evidence_code = COALESCE(evidence_code, 'E-' || section_id::text || '-001'),
            evidence_text = COALESCE(NULLIF(evidence_text, ''), NULLIF(summary, ''), NULLIF(chapter_title, ''), ''),
            object_terms = CASE
                WHEN object_terms IS NOT NULL AND object_terms <> '[]'::jsonb THEN object_terms
                WHEN construction_objects IS NOT NULL THEN (
                    SELECT COALESCE(jsonb_agg(DISTINCT COALESCE(item->>'object_name', item->>'name', item#>>'{}')), '[]'::jsonb)
                    FROM jsonb_array_elements(construction_objects) AS item
                    WHERE COALESCE(item->>'object_name', item->>'name', item#>>'{}') IS NOT NULL
                )
                ELSE '[]'::jsonb
            END,
            context_text = COALESCE(NULLIF(context_text, ''), NULLIF(summary, ''), NULLIF(chapter_path, '')),
            source_text = COALESCE(NULLIF(source_text, ''), NULLIF(summary, ''))
        """
    )
    op.alter_column("chapter_review_profile", "evidence_text", nullable=False)
    op.create_index(op.f("ix_chapter_review_profile_evidence_code"), "chapter_review_profile", ["evidence_code"])
    op.create_index(op.f("ix_chapter_review_profile_status"), "chapter_review_profile", ["status"])

    for index_name in (
        "ix_review_checkpoint_checkpoint_code",
        "ix_review_checkpoint_checkpoint_name",
        "ix_review_checkpoint_checkpoint_type",
        "ix_review_checkpoint_domain",
        "ix_review_checkpoint_subdomain",
        "ix_review_checkpoint_work_type",
        "ix_review_checkpoint_risk_level",
        "ix_review_checkpoint_is_mandatory",
        "ix_review_checkpoint_priority",
        "ix_chapter_review_profile_chapter_type",
        "ix_chapter_review_profile_main_domain",
    ):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    for column_name in (
        "checkpoint_code",
        "checkpoint_name",
        "checkpoint_type",
        "domain",
        "subdomain",
        "work_type",
        "chapter_types",
        "target_objects",
        "target_parameters",
        "keywords",
        "check_goal",
        "check_method",
        "expected_items",
        "forbidden_items",
        "parameters",
        "applicable_condition",
        "risk_level",
        "is_mandatory",
        "priority",
    ):
        op.drop_column("review_checkpoint", column_name)

    for column_name in (
        "chapter_type",
        "main_domain",
        "subdomains",
        "construction_objects",
        "materials",
        "mentioned_parameters",
        "mentioned_methods",
        "mentioned_risks",
        "mentioned_standards",
        "expected_missing_objects",
        "summary",
    ):
        op.drop_column("chapter_review_profile", column_name)


def downgrade() -> None:
    op.add_column("review_checkpoint", sa.Column("checkpoint_code", sa.String(length=100), nullable=True))
    op.add_column("review_checkpoint", sa.Column("checkpoint_name", sa.String(length=255), nullable=True))
    op.add_column("review_checkpoint", sa.Column("checkpoint_type", sa.String(length=100), nullable=False, server_default="semantic_check"))
    op.add_column("review_checkpoint", sa.Column("domain", sa.String(length=100), nullable=True))
    op.add_column("review_checkpoint", sa.Column("subdomain", sa.String(length=100), nullable=True))
    op.add_column("review_checkpoint", sa.Column("work_type", sa.String(length=100), nullable=True))
    for column_name in ("chapter_types", "target_objects", "target_parameters", "keywords", "expected_items", "forbidden_items"):
        op.add_column("review_checkpoint", sa.Column(column_name, postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))
    op.add_column("review_checkpoint", sa.Column("check_goal", sa.Text(), nullable=True))
    op.add_column("review_checkpoint", sa.Column("check_method", sa.String(length=100), nullable=True))
    op.add_column("review_checkpoint", sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    op.add_column("review_checkpoint", sa.Column("applicable_condition", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    op.add_column("review_checkpoint", sa.Column("risk_level", sa.String(length=50), nullable=False, server_default="major"))
    op.add_column("review_checkpoint", sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("review_checkpoint", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        """
        UPDATE review_checkpoint
        SET checkpoint_code = rule_code,
            checkpoint_name = LEFT(rule_text, 255),
            target_objects = object_terms,
            keywords = object_terms,
            check_goal = rule_text
        """
    )
    op.alter_column("review_checkpoint", "checkpoint_name", nullable=False)

    op.add_column("chapter_review_profile", sa.Column("chapter_type", sa.String(length=100), nullable=True))
    op.add_column("chapter_review_profile", sa.Column("main_domain", sa.String(length=100), nullable=True))
    for column_name in (
        "subdomains",
        "construction_objects",
        "materials",
        "mentioned_parameters",
        "mentioned_methods",
        "mentioned_risks",
        "mentioned_standards",
        "expected_missing_objects",
    ):
        op.add_column("chapter_review_profile", sa.Column(column_name, postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))
    op.add_column("chapter_review_profile", sa.Column("summary", sa.Text(), nullable=True))
    op.execute("UPDATE chapter_review_profile SET summary = evidence_text")

    op.drop_index(op.f("ix_review_checkpoint_rule_code"), table_name="review_checkpoint")
    op.drop_index(op.f("ix_chapter_review_profile_evidence_code"), table_name="chapter_review_profile")
    op.drop_index(op.f("ix_chapter_review_profile_status"), table_name="chapter_review_profile")
    for column_name in ("rule_code", "rule_text", "object_terms", "context_text", "confidence"):
        op.drop_column("review_checkpoint", column_name)
    for column_name in ("evidence_code", "evidence_text", "object_terms", "context_text", "source_text", "status"):
        op.drop_column("chapter_review_profile", column_name)
