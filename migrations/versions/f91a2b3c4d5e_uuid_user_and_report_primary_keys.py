"""use UUID primary keys for users and crime reports

Revision ID: f91a2b3c4d5e
Revises: e80f4a1c2d3e
Create Date: 2026-08-31
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "f91a2b3c4d5e"
down_revision = "e80f4a1c2d3e"
branch_labels = None
depends_on = None


def _map_ids(table: str, new_column: str) -> None:
    connection = op.get_bind()
    for old_id in connection.execute(sa.text(f"SELECT id FROM {table}")).scalars():
        connection.execute(sa.text(f"UPDATE {table} SET {new_column} = :new_id WHERE id = :old_id"), {"new_id": str(uuid4()), "old_id": old_id})


def upgrade():
    """Migrate existing PostgreSQL records while retaining every relationship."""
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("This production migration requires PostgreSQL.")
    user_id_type = next(column["type"] for column in sa.inspect(op.get_bind()).get_columns("users") if column["name"] == "id")
    if isinstance(user_id_type, sa.Uuid):
        # A new database used the UUID-aware initial schema, so no data conversion is needed.
        return

    op.add_column("users", sa.Column("uuid_id", sa.Uuid(), nullable=True))
    op.add_column("crime_reports", sa.Column("uuid_id", sa.Uuid(), nullable=True))
    op.add_column("crime_reports", sa.Column("uuid_reporter_id", sa.Uuid(), nullable=True))
    op.add_column("admin_logs", sa.Column("uuid_admin_id", sa.Uuid(), nullable=True))
    op.add_column("admin_logs", sa.Column("uuid_target_report_id", sa.Uuid(), nullable=True))
    op.add_column("notifications", sa.Column("uuid_recipient_id", sa.Uuid(), nullable=True))
    op.add_column("notifications", sa.Column("uuid_report_id", sa.Uuid(), nullable=True))
    op.add_column("report_media", sa.Column("uuid_report_id", sa.Uuid(), nullable=True))
    op.add_column("crime_reports", sa.Column("title", sa.String(length=200), nullable=True))
    _map_ids("users", "uuid_id")
    _map_ids("crime_reports", "uuid_id")
    connection = op.get_bind()
    for table, column, source_table, source_column in [
        ("crime_reports", "uuid_reporter_id", "users", "uuid_id"), ("admin_logs", "uuid_admin_id", "users", "uuid_id"),
        ("admin_logs", "uuid_target_report_id", "crime_reports", "uuid_id"), ("notifications", "uuid_recipient_id", "users", "uuid_id"),
        ("notifications", "uuid_report_id", "crime_reports", "uuid_id"), ("report_media", "uuid_report_id", "crime_reports", "uuid_id"),
    ]:
        old_column = column.removeprefix("uuid_")
        connection.execute(sa.text(f"UPDATE {table} target SET {column} = source.{source_column} FROM {source_table} source WHERE target.{old_column} = source.id"))
    connection.execute(sa.text("UPDATE crime_reports SET title = INITCAP(crime_type) || ' report'"))
    for index in ["ix_crime_reports_reporter_id", "ix_admin_logs_admin_id", "ix_admin_logs_target_report_id", "ix_notifications_recipient_id", "ix_notifications_report_id", "ix_report_media_report_id"]:
        connection.execute(sa.text(f"DROP INDEX {index}"))
    for table, constraint in [("crime_reports", "crime_reports_reporter_id_fkey"), ("admin_logs", "admin_logs_admin_id_fkey"), ("admin_logs", "admin_logs_target_report_id_fkey"), ("notifications", "notifications_recipient_id_fkey"), ("notifications", "notifications_report_id_fkey"), ("report_media", "report_media_report_id_fkey")]:
        connection.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}"))
    # Replace old integer identity and foreign-key columns with UUID equivalents.
    for table in ["users", "crime_reports"]:
        connection.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey"))
    for table, old, new in [("users", "id", "uuid_id"), ("crime_reports", "id", "uuid_id"), ("crime_reports", "reporter_id", "uuid_reporter_id"), ("admin_logs", "admin_id", "uuid_admin_id"), ("admin_logs", "target_report_id", "uuid_target_report_id"), ("notifications", "recipient_id", "uuid_recipient_id"), ("notifications", "report_id", "uuid_report_id"), ("report_media", "report_id", "uuid_report_id")]:
        connection.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN {old}"))
        connection.execute(sa.text(f"ALTER TABLE {table} RENAME COLUMN {new} TO {old}"))
    connection.execute(sa.text("ALTER TABLE users ADD PRIMARY KEY (id); ALTER TABLE crime_reports ADD PRIMARY KEY (id)"))
    connection.execute(sa.text("ALTER TABLE crime_reports ALTER COLUMN title SET NOT NULL; ALTER TABLE admin_logs ALTER COLUMN admin_id SET NOT NULL; ALTER TABLE notifications ALTER COLUMN recipient_id SET NOT NULL; ALTER TABLE report_media ALTER COLUMN report_id SET NOT NULL"))
    connection.execute(sa.text("ALTER TABLE crime_reports ADD FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE SET NULL; ALTER TABLE admin_logs ADD FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE RESTRICT; ALTER TABLE admin_logs ADD FOREIGN KEY (target_report_id) REFERENCES crime_reports(id) ON DELETE SET NULL; ALTER TABLE notifications ADD FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE; ALTER TABLE notifications ADD FOREIGN KEY (report_id) REFERENCES crime_reports(id) ON DELETE SET NULL; ALTER TABLE report_media ADD FOREIGN KEY (report_id) REFERENCES crime_reports(id) ON DELETE CASCADE"))
    for table, column in [("crime_reports", "reporter_id"), ("admin_logs", "admin_id"), ("admin_logs", "target_report_id"), ("notifications", "recipient_id"), ("notifications", "report_id"), ("report_media", "report_id")]:
        connection.execute(sa.text(f"CREATE INDEX ix_{table}_{column} ON {table} ({column})"))


def downgrade():
    raise RuntimeError("Downgrading UUID primary keys is not supported; restore from backup instead.")
