"""User notification persistence model."""

from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id = db.Column(db.Integer, db.ForeignKey("crime_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    notification_type = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, server_default=db.false(), index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    recipient = db.relationship("User", back_populates="notifications", foreign_keys=[recipient_id])
    report = db.relationship("CrimeReport", back_populates="notifications", foreign_keys=[report_id])

    def __repr__(self) -> str:
        return f"<Notification id={self.id} recipient_id={self.recipient_id} read={self.is_read}>"
