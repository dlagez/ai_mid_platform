"""migrate toc match items to parse result sections

Revision ID: r3c4d5e6f7a8
Revises: q2b3c4d5e6f7
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "r3c4d5e6f7a8"
down_revision = "q2b3c4d5e6f7"
branch_labels = None
depends_on = None


TABLE_NAME = "toc_match_item"
OLD_COLUMN = "standard_clause_id"
NEW_COLUMN = "standard_section_id"
NEW_INDEX = "ix_toc_match_item_standard_section_id"
NEW_FK = "fk_toc_match_item_standard_section_id_parse_result_section"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}

    if OLD_COLUMN in columns:
        _drop_foreign_keys(inspector, TABLE_NAME, OLD_COLUMN)
        _drop_indexes(inspector, TABLE_NAME, OLD_COLUMN)
        op.alter_column(
            TABLE_NAME,
            OLD_COLUMN,
            existing_type=sa.BigInteger(),
            new_column_name=NEW_COLUMN,
            existing_nullable=False,
        )
        columns.remove(OLD_COLUMN)
        columns.add(NEW_COLUMN)

    if NEW_COLUMN not in columns:
        return

    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if NEW_INDEX not in indexes:
        op.create_index(op.f(NEW_INDEX), TABLE_NAME, [NEW_COLUMN])

    inspector = inspect(bind)
    has_new_fk = any(
        NEW_COLUMN in foreign_key.get("constrained_columns", [])
        and foreign_key.get("referred_table") == "parse_result_section"
        for foreign_key in inspector.get_foreign_keys(TABLE_NAME)
    )
    if not has_new_fk:
        op.create_foreign_key(
            op.f(NEW_FK),
            TABLE_NAME,
            "parse_result_section",
            [NEW_COLUMN],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # Intentionally left as a no-op: the current schema must remain based on
    # parse_result_section, and this migration only repairs older databases.
    pass


def _drop_foreign_keys(inspector: sa.Inspector, table_name: str, column_name: str) -> None:
    for foreign_key in inspector.get_foreign_keys(table_name):
        if column_name in foreign_key.get("constrained_columns", []) and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def _drop_indexes(inspector: sa.Inspector, table_name: str, column_name: str) -> None:
    for index in inspector.get_indexes(table_name):
        if column_name in index.get("column_names", []) and index.get("name"):
            op.drop_index(index["name"], table_name=table_name)
