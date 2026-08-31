"""Media attached to crime reports."""

from app.extensions import db


class ReportMedia(db.Model):
    __tablename__ = "report_media"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("crime_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = db.Column(db.String(1024), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())

    report = db.relationship("CrimeReport", back_populates="media")

    __table_args__ = (db.CheckConstraint("media_type IN ('image', 'video')", name="ck_report_media_media_type"),)

    def __repr__(self) -> str:
        return f"<ReportMedia id={self.id} report_id={self.report_id} media_type={self.media_type!r}>"
