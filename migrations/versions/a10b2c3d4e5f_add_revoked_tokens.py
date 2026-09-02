"""add persisted JWT token revocations

Revision ID: a10b2c3d4e5f
Revises: f91a2b3c4d5e
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa


revision = "a10b2c3d4e5f"
down_revision = "f91a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=36), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade():
    op.drop_index("ix_revoked_tokens_expires_at", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
