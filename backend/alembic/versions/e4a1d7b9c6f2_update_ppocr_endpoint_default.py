"""update ppocr endpoint default

Revision ID: e4a1d7b9c6f2
Revises: d3f8a741e2c9
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e4a1d7b9c6f2"
down_revision: Union[str, None] = "d3f8a741e2c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE parse_job ALTER COLUMN ocr_endpoint SET DEFAULT '/layout-parsing'")


def downgrade() -> None:
    op.execute("ALTER TABLE parse_job ALTER COLUMN ocr_endpoint SET DEFAULT '/ocr'")
