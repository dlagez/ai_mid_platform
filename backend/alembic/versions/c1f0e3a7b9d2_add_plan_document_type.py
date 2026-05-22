"""add plan document type

Revision ID: c1f0e3a7b9d2
Revises: b2e7c9d4a5f1
Create Date: 2026-05-22 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1f0e3a7b9d2"
down_revision: Union[str, None] = "b2e7c9d4a5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plan_document",
        sa.Column("document_type", sa.String(length=32), server_default="template", nullable=False),
    )
    op.create_index(op.f("ix_plan_document_document_type"), "plan_document", ["document_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_document_document_type"), table_name="plan_document")
    op.drop_column("plan_document", "document_type")
