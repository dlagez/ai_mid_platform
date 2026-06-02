"""add model prompt test records

Revision ID: o9c1d2e3f4a5
Revises: n8b4c5d6e7f8
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "o9c1d2e3f4a5"
down_revision = "n8b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_prompt_test_record",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("prompt_type", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_prompt_test_record_id"), "model_prompt_test_record", ["id"])
    op.create_index(op.f("ix_model_prompt_test_record_prompt_type"), "model_prompt_test_record", ["prompt_type"])
    op.create_index(op.f("ix_model_prompt_test_record_model"), "model_prompt_test_record", ["model"])
    op.create_index(op.f("ix_model_prompt_test_record_provider"), "model_prompt_test_record", ["provider"])
    op.create_index(op.f("ix_model_prompt_test_record_status"), "model_prompt_test_record", ["status"])
    op.create_index(op.f("ix_model_prompt_test_record_created_by"), "model_prompt_test_record", ["created_by"])
    op.create_index(op.f("ix_model_prompt_test_record_created_at"), "model_prompt_test_record", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_model_prompt_test_record_created_at"), table_name="model_prompt_test_record")
    op.drop_index(op.f("ix_model_prompt_test_record_created_by"), table_name="model_prompt_test_record")
    op.drop_index(op.f("ix_model_prompt_test_record_status"), table_name="model_prompt_test_record")
    op.drop_index(op.f("ix_model_prompt_test_record_provider"), table_name="model_prompt_test_record")
    op.drop_index(op.f("ix_model_prompt_test_record_model"), table_name="model_prompt_test_record")
    op.drop_index(op.f("ix_model_prompt_test_record_prompt_type"), table_name="model_prompt_test_record")
    op.drop_index(op.f("ix_model_prompt_test_record_id"), table_name="model_prompt_test_record")
    op.drop_table("model_prompt_test_record")
