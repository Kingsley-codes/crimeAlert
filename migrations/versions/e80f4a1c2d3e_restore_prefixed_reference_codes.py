"""restore prefixed user and crime reference codes

Revision ID: e80f4a1c2d3e
Revises: d42f9b5e0a13
Create Date: 2026-08-31
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "e80f4a1c2d3e"
down_revision = "d42f9b5e0a13"
branch_labels = None
depends_on = None


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def _replace_codes(table: str, prefix: str) -> None:
    connection = op.get_bind()
    for row_id in connection.execute(sa.text(f"SELECT id FROM {table}")).scalars():
        connection.execute(sa.text(f"UPDATE {table} SET reference_code = :code WHERE id = :id"), {"id": row_id, "code": _code(prefix)})


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=10), type_=sa.String(length=14), nullable=False)
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=10), type_=sa.String(length=13), nullable=False)
    _replace_codes("users", "USR")
    _replace_codes("crime_reports", "CR")


def downgrade():
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=13), type_=sa.String(length=10), nullable=False)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("reference_code", existing_type=sa.String(length=14), type_=sa.String(length=10), nullable=False)
