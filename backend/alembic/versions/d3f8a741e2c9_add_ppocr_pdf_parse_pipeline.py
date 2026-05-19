"""add ppocr pdf parse pipeline

Revision ID: d3f8a741e2c9
Revises: b7d2c8a9f031
Create Date: 2026-05-19 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3f8a741e2c9"
down_revision: Union[str, None] = "b7d2c8a9f031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parse_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("source_file_path", sa.String(length=512), nullable=False),
        sa.Column("parser_provider", sa.String(length=64), nullable=False),
        sa.Column("parse_mode", sa.String(length=64), nullable=False),
        sa.Column("ocr_endpoint", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dpi", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("page_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("min_confidence", sa.Float(), nullable=False),
        sa.Column("low_confidence_flag", sa.Boolean(), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("succeeded_pages", sa.Integer(), nullable=False),
        sa.Column("failed_pages", sa.Integer(), nullable=False),
        sa.Column("low_confidence_pages", sa.Integer(), nullable=False),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_markdown_path", sa.String(length=512), nullable=True),
        sa.Column("result_json_path", sa.String(length=512), nullable=True),
        sa.Column("raw_result_path", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parse_job_created_at"), "parse_job", ["created_at"], unique=False)
    op.create_index(op.f("ix_parse_job_file_hash"), "parse_job", ["file_hash"], unique=False)
    op.create_index(op.f("ix_parse_job_file_id"), "parse_job", ["file_id"], unique=False)
    op.create_index(op.f("ix_parse_job_id"), "parse_job", ["id"], unique=False)
    op.create_index(op.f("ix_parse_job_low_confidence_flag"), "parse_job", ["low_confidence_flag"], unique=False)
    op.create_index(op.f("ix_parse_job_parser_provider"), "parse_job", ["parser_provider"], unique=False)
    op.create_index(op.f("ix_parse_job_status"), "parse_job", ["status"], unique=False)

    op.create_table(
        "parse_page_result",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("image_path", sa.String(length=512), nullable=True),
        sa.Column("raw_json_path", sa.String(length=512), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column("rec_texts", sa.JSON(), nullable=False),
        sa.Column("rec_scores", sa.JSON(), nullable=False),
        sa.Column("rec_polys", sa.JSON(), nullable=False),
        sa.Column("average_confidence", sa.Float(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("low_confidence_flag", sa.Boolean(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["parse_job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parse_page_result_id"), "parse_page_result", ["id"], unique=False)
    op.create_index(op.f("ix_parse_page_result_job_id"), "parse_page_result", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_parse_page_result_low_confidence_flag"),
        "parse_page_result",
        ["low_confidence_flag"],
        unique=False,
    )
    op.create_index(op.f("ix_parse_page_result_page_no"), "parse_page_result", ["page_no"], unique=False)
    op.create_index(op.f("ix_parse_page_result_status"), "parse_page_result", ["status"], unique=False)
    op.create_unique_constraint("uq_parse_page_result_job_page", "parse_page_result", ["job_id", "page_no"])

    op.create_table(
        "parse_result",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("markdown_file_path", sa.String(length=512), nullable=True),
        sa.Column("json_file_path", sa.String(length=512), nullable=True),
        sa.Column("raw_result_file_path", sa.String(length=512), nullable=True),
        sa.Column("markdown_file_size", sa.BigInteger(), nullable=True),
        sa.Column("json_file_size", sa.BigInteger(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("succeeded_pages", sa.Integer(), nullable=False),
        sa.Column("failed_pages", sa.Integer(), nullable=False),
        sa.Column("low_confidence_pages", sa.Integer(), nullable=False),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["parse_job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(op.f("ix_parse_result_id"), "parse_result", ["id"], unique=False)
    op.create_index(op.f("ix_parse_result_status"), "parse_result", ["status"], unique=False)

    op.create_table(
        "document_markdown_map",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("page_result_id", sa.BigInteger(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("markdown_start", sa.Integer(), nullable=False),
        sa.Column("markdown_end", sa.Integer(), nullable=False),
        sa.Column("anchor", sa.String(length=64), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["parse_job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_result_id"], ["parse_page_result.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_markdown_map_id"), "document_markdown_map", ["id"], unique=False)
    op.create_index(op.f("ix_document_markdown_map_job_id"), "document_markdown_map", ["job_id"], unique=False)
    op.create_index(op.f("ix_document_markdown_map_page_no"), "document_markdown_map", ["page_no"], unique=False)
    op.create_index(
        op.f("ix_document_markdown_map_page_result_id"),
        "document_markdown_map",
        ["page_result_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_markdown_map_page_result_id"), table_name="document_markdown_map")
    op.drop_index(op.f("ix_document_markdown_map_page_no"), table_name="document_markdown_map")
    op.drop_index(op.f("ix_document_markdown_map_job_id"), table_name="document_markdown_map")
    op.drop_index(op.f("ix_document_markdown_map_id"), table_name="document_markdown_map")
    op.drop_table("document_markdown_map")
    op.drop_index(op.f("ix_parse_result_status"), table_name="parse_result")
    op.drop_index(op.f("ix_parse_result_id"), table_name="parse_result")
    op.drop_table("parse_result")
    op.drop_constraint("uq_parse_page_result_job_page", "parse_page_result", type_="unique")
    op.drop_index(op.f("ix_parse_page_result_status"), table_name="parse_page_result")
    op.drop_index(op.f("ix_parse_page_result_page_no"), table_name="parse_page_result")
    op.drop_index(op.f("ix_parse_page_result_low_confidence_flag"), table_name="parse_page_result")
    op.drop_index(op.f("ix_parse_page_result_job_id"), table_name="parse_page_result")
    op.drop_index(op.f("ix_parse_page_result_id"), table_name="parse_page_result")
    op.drop_table("parse_page_result")
    op.drop_index(op.f("ix_parse_job_status"), table_name="parse_job")
    op.drop_index(op.f("ix_parse_job_parser_provider"), table_name="parse_job")
    op.drop_index(op.f("ix_parse_job_low_confidence_flag"), table_name="parse_job")
    op.drop_index(op.f("ix_parse_job_id"), table_name="parse_job")
    op.drop_index(op.f("ix_parse_job_file_id"), table_name="parse_job")
    op.drop_index(op.f("ix_parse_job_file_hash"), table_name="parse_job")
    op.drop_index(op.f("ix_parse_job_created_at"), table_name="parse_job")
    op.drop_table("parse_job")
