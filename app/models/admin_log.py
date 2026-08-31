"""Auditable administrator actions."""

from app.extensions import db


class AdminLog(db.Model):
    __tablename__ = "admin_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    action = db.Column(db.String(255), nullable=False)
    target_report_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("crime_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)

    admin = db.relationship("User", back_populates="admin_logs", foreign_keys=[admin_id])
    target_report = db.relationship("CrimeReport", back_populates="admin_logs", foreign_keys=[target_report_id])

    def __repr__(self) -> str:
        return f"<AdminLog id={self.id} admin_id={self.admin_id} action={self.action!r}>"
