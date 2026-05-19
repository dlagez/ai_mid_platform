"""add utility parse record

Revision ID: b7d2c8a9f031
Revises: 4b9e2f0f0a61
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d2c8a9f031"
down_revision: Union[str, None] = "4b9e2f0f0a61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "utility_parse_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_file_name", sa.String(length=256), nullable=False),
        sa.Column("source_file_path", sa.String(length=512), nullable=False),
        sa.Column("source_file_size", sa.BigInteger(), nullable=False),
        sa.Column("source_content_type", sa.String(length=128), nullable=True),
        sa.Column("parsed_file_name", sa.String(length=256), nullable=True),
        sa.Column("parsed_file_path", sa.String(length=512), nullable=True),
        sa.Column("parsed_file_size", sa.BigInteger(), nullable=True),
        sa.Column("parser_provider", sa.String(length=64), nullable=False),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parsed", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_utility_parse_record_created_at"), "utility_parse_record", ["created_at"], unique=False)
    op.create_index(op.f("ix_utility_parse_record_id"), "utility_parse_record", ["id"], unique=False)
    op.create_index(op.f("ix_utility_parse_record_parse_status"), "utility_parse_record", ["parse_status"], unique=False)
    op.create_index(op.f("ix_utility_parse_record_parsed"), "utility_parse_record", ["parsed"], unique=False)
    op.create_index(
        op.f("ix_utility_parse_record_parser_provider"),
        "utility_parse_record",
        ["parser_provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_utility_parse_record_parser_provider"), table_name="utility_parse_record")
    op.drop_index(op.f("ix_utility_parse_record_parsed"), table_name="utility_parse_record")
    op.drop_index(op.f("ix_utility_parse_record_parse_status"), table_name="utility_parse_record")
    op.drop_index(op.f("ix_utility_parse_record_id"), table_name="utility_parse_record")
    op.drop_index(op.f("ix_utility_parse_record_created_at"), table_name="utility_parse_record")
    op.drop_table("utility_parse_record")
