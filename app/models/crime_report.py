"""Crime report persistence model."""

from app.extensions import db


class CrimeReport(db.Model):
    __tablename__ = "crime_reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    crime_type = db.Column(db.String(100), db.ForeignKey("crime_types.name", onupdate="CASCADE"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Numeric(8, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    incident_datetime = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(20), nullable=False, server_default="pending")
    risk_level = db.Column(db.String(20), nullable=False, server_default="low")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    reporter = db.relationship("User", back_populates="reports", foreign_keys=[reporter_id])
    crime_type_definition = db.relationship("CrimeType", back_populates="reports", foreign_keys=[crime_type])
    media = db.relationship("ReportMedia", back_populates="report", cascade="all, delete-orphan")
    admin_logs = db.relationship("AdminLog", back_populates="target_report")
    notifications = db.relationship("Notification", back_populates="report")

    __table_args__ = (
        db.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_crime_reports_latitude_range"),
        db.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_crime_reports_longitude_range"),
        db.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_crime_reports_status"),
        db.CheckConstraint("risk_level IN ('high', 'medium', 'low')", name="ck_crime_reports_risk_level"),
        db.Index("ix_crime_reports_status", "status"),
        db.Index("ix_crime_reports_crime_type", "crime_type"),
        db.Index("ix_crime_reports_risk_level", "risk_level"),
        db.Index("ix_crime_reports_incident_datetime", "incident_datetime"),
        db.Index("ix_crime_reports_latitude_longitude", "latitude", "longitude"),
    )

    def __repr__(self) -> str:
        return f"<CrimeReport id={self.id} status={self.status!r} crime_type={self.crime_type!r}>"
