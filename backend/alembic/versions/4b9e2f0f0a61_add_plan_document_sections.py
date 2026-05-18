"""add plan document sections

Revision ID: 4b9e2f0f0a61
Revises: aa5a11fddc4d
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b9e2f0f0a61"
down_revision: Union[str, None] = "aa5a11fddc4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_document",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_document_id"), "plan_document", ["id"], unique=False)
    op.create_index(
        op.f("ix_plan_document_parse_status"),
        "plan_document",
        ["parse_status"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO plan_document (file_name, file_path, file_size, parse_status, created_at)
        SELECT file_name, minio_path, 0, 'uploaded', uploaded_at
        FROM document_records dr
        WHERE NOT EXISTS (
            SELECT 1 FROM plan_document pd WHERE pd.file_path = dr.minio_path
        )
        """
    )

    op.create_table(
        "plan_section",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("section_no", sa.String(length=64), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["plan_document.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["plan_section.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_section_document_id"), "plan_section", ["document_id"], unique=False)
    op.create_index(op.f("ix_plan_section_id"), "plan_section", ["id"], unique=False)
    op.create_index(op.f("ix_plan_section_parent_id"), "plan_section", ["parent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_section_parent_id"), table_name="plan_section")
    op.drop_index(op.f("ix_plan_section_id"), table_name="plan_section")
    op.drop_index(op.f("ix_plan_section_document_id"), table_name="plan_section")
    op.drop_table("plan_section")
    op.drop_index(op.f("ix_plan_document_parse_status"), table_name="plan_document")
    op.drop_index(op.f("ix_plan_document_id"), table_name="plan_document")
    op.drop_table("plan_document")
