"""shorten random reference codes to ten hexadecimal characters

Revision ID: d42f9b5e0a13
Revises: c31e8a4d9f02
Create Date: 2026-08-30
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "d42f9b5e0a13"
down_revision = "c31e8a4d9f02"
branch_labels = None
depends_on = None


def _codes(count: int) -> list[str]:
    values: set[str] = set()
    while len(values) < count:
        values.add(uuid4().hex[:10].upper())
    return list(values)


def _replace_codes(table: str) -> None:
    connection = op.get_bind()
    ids = list(connection.execute(sa.text(f"SELECT id FROM {table}")).scalars())
    for row_id, code in zip(ids, _codes(len(ids)), strict=True):
        connection.execute(sa.text(f"UPDATE {table} SET reference_code = :code WHERE id = :id"), {"id": row_id, "code": code})


def upgrade():
    _replace_codes("users")
    _replace_codes("crime_reports")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=36), type_=sa.String(length=10), nullable=False)
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=35), type_=sa.String(length=10), nullable=False)


def downgrade():
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=10), type_=sa.String(length=35), nullable=False)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=10), type_=sa.String(length=36), nullable=False)
