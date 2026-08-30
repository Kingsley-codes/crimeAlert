"""add random hexadecimal reference codes

Revision ID: c31e8a4d9f02
Revises: b21d9d4e7c8f
Create Date: 2026-08-30
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "c31e8a4d9f02"
down_revision = "b21d9d4e7c8f"
branch_labels = None
depends_on = None


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reference_code", sa.String(length=36), nullable=True))
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reference_code", sa.String(length=35), nullable=True))

    connection = op.get_bind()
    for user_id in connection.execute(sa.text("SELECT id FROM users")).scalars():
        connection.execute(sa.text("UPDATE users SET reference_code = :code WHERE id = :id"), {"id": user_id, "code": _code("USR")})
    for report_id in connection.execute(sa.text("SELECT id FROM crime_reports")).scalars():
        connection.execute(sa.text("UPDATE crime_reports SET reference_code = :code WHERE id = :id"), {"id": report_id, "code": _code("CR")})

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("reference_code", nullable=False)
        batch_op.create_index("ix_users_reference_code", ["reference_code"], unique=True)
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.alter_column("reference_code", nullable=False)
        batch_op.create_index("ix_crime_reports_reference_code", ["reference_code"], unique=True)


def downgrade():
    with op.batch_alter_table("crime_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_crime_reports_reference_code")
        batch_op.drop_column("reference_code")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_reference_code")
        batch_op.drop_column("reference_code")
