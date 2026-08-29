"""seed report crime types

Revision ID: b21d9d4e7c8f
Revises: f874f7a9f34e
Create Date: 2026-08-29
"""

from alembic import op


revision = "b21d9d4e7c8f"
down_revision = "f874f7a9f34e"
branch_labels = None
depends_on = None


def upgrade():
    for crime_type in ("theft", "robbery", "kidnapping", "assault", "other"):
        op.execute(f"INSERT INTO crime_types (name) VALUES ('{crime_type}') ON CONFLICT (name) DO NOTHING")


def downgrade():
    op.execute("DELETE FROM crime_types WHERE name IN ('theft', 'robbery', 'kidnapping', 'assault', 'other')")
