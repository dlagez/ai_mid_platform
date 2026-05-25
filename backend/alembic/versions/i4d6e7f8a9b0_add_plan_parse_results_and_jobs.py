"""add plan parse results and jobs

Revision ID: i4d6e7f8a9b0
Revises: h3c5d6e7f8a9
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i4d6e7f8a9b0"
down_revision: Union[str, None] = "h3c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plan_document",
        sa.Column("parse_progress", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_table(
        "plan_parse_result",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("section_parse_mode", sa.String(length=64), nullable=False),
        sa.Column("parse_status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("parse_progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("section_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("toc_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "section_parse_mode", name="uq_plan_parse_result_document_mode"),
    )
    op.create_index(op.f("ix_plan_parse_result_id"), "plan_parse_result", ["id"], unique=False)
    op.create_index(op.f("ix_plan_parse_result_document_id"), "plan_parse_result", ["document_id"], unique=False)
    op.create_index(
        op.f("ix_plan_parse_result_section_parse_mode"),
        "plan_parse_result",
        ["section_parse_mode"],
        unique=False,
    )
    op.create_index(op.f("ix_plan_parse_result_parse_status"), "plan_parse_result", ["parse_status"], unique=False)

    op.create_table(
        "plan_parse_job",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("parse_result_id", sa.BigInteger(), nullable=True),
        sa.Column("parser_provider", sa.String(length=64), nullable=True),
        sa.Column("section_parse_mode", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False, server_default="parse"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parse_result_id"], ["plan_parse_result.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_plan_parse_job_id"), "plan_parse_job", ["id"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_document_id"), "plan_parse_job", ["document_id"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_parse_result_id"), "plan_parse_job", ["parse_result_id"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_parser_provider"), "plan_parse_job", ["parser_provider"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_section_parse_mode"), "plan_parse_job", ["section_parse_mode"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_job_type"), "plan_parse_job", ["job_type"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_status"), "plan_parse_job", ["status"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_celery_task_id"), "plan_parse_job", ["celery_task_id"], unique=False)
    op.create_index(op.f("ix_plan_parse_job_created_at"), "plan_parse_job", ["created_at"], unique=False)

    op.execute("DELETE FROM plan_section")
    op.execute(
        """
        UPDATE plan_document
        SET parse_status = 'uploaded',
            parse_progress = 0
        """
    )
    op.add_column("plan_section", sa.Column("parse_result_id", sa.BigInteger(), nullable=False))
    op.create_foreign_key(
        "fk_plan_section_parse_result_id_plan_parse_result",
        "plan_section",
        "plan_parse_result",
        ["parse_result_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_plan_section_parse_result_id"), "plan_section", ["parse_result_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_section_parse_result_id"), table_name="plan_section")
    op.drop_constraint("fk_plan_section_parse_result_id_plan_parse_result", "plan_section", type_="foreignkey")
    op.drop_column("plan_section", "parse_result_id")

    op.drop_index(op.f("ix_plan_parse_job_created_at"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_celery_task_id"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_status"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_job_type"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_section_parse_mode"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_parser_provider"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_parse_result_id"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_document_id"), table_name="plan_parse_job")
    op.drop_index(op.f("ix_plan_parse_job_id"), table_name="plan_parse_job")
    op.drop_table("plan_parse_job")

    op.drop_index(op.f("ix_plan_parse_result_parse_status"), table_name="plan_parse_result")
    op.drop_index(op.f("ix_plan_parse_result_section_parse_mode"), table_name="plan_parse_result")
    op.drop_index(op.f("ix_plan_parse_result_document_id"), table_name="plan_parse_result")
    op.drop_index(op.f("ix_plan_parse_result_id"), table_name="plan_parse_result")
    op.drop_table("plan_parse_result")
    op.drop_column("plan_document", "parse_progress")
