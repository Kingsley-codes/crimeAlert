"""User persistence model."""

from flask_login import UserMixin

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, server_default="user")
    is_active = db.Column(db.Boolean, nullable=False, server_default=db.true())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    reports = db.relationship("CrimeReport", back_populates="reporter", foreign_keys="CrimeReport.reporter_id")
    admin_logs = db.relationship("AdminLog", back_populates="admin", foreign_keys="AdminLog.admin_id")
    notifications = db.relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    @property
    def can_authenticate(self) -> bool:
        """Return whether the account may establish or retain a session."""
        return bool(self.is_active)

    @property
    def reference_code(self) -> str:
        """Return the stable, human-readable identifier used in administration views."""
        return f"USR-{self.id:06d}"

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
