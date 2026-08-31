"""add system settings

Revision ID: a92e7d1f4b3c
Revises: f91a2b3c4d5e
"""

from alembic import op
import sqlalchemy as sa

revision = "a92e7d1f4b3c"
down_revision = "f91a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("system_settings")
