"""add plan document section parse mode

Revision ID: h3c5d6e7f8a9
Revises: g2b1c4d5e6f7
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h3c5d6e7f8a9"
down_revision: Union[str, None] = "g2b1c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plan_document",
        sa.Column("section_parse_mode", sa.String(length=64), server_default="docling_auto", nullable=False),
    )
    op.create_index(
        op.f("ix_plan_document_section_parse_mode"),
        "plan_document",
        ["section_parse_mode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_document_section_parse_mode"), table_name="plan_document")
    op.drop_column("plan_document", "section_parse_mode")
