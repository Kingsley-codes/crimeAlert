"""Shared report validation, persistence, and administrative transitions."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.models.crime_report import CrimeReport
from app.models.crime_type import CrimeType
from app.models.admin_log import AdminLog
from app.services.notification_service import notify_admins_of_report, notify_reporter_of_status

def create_report(data: dict, reporter_id=None) -> CrimeReport:
    required = ("crime_type", "title", "description", "incident_datetime", "latitude", "longitude")
    if not all(isinstance(data.get(key), str) and data[key].strip() for key in required): raise ValueError("crime_type, title, description, incident_datetime, latitude, and longitude are required.")
    crime_type = data["crime_type"].strip().lower()
    if not db.session.scalar(db.select(CrimeType).where(CrimeType.name == crime_type, CrimeType.is_active.is_(True))): raise ValueError("Choose an active crime type.")
    title, description = data["title"].strip(), data["description"].strip()
    if not 5 <= len(title) <= 200 or not 10 <= len(description) <= 5000: raise ValueError("Title must be 5-200 characters and description 10-5000 characters.")
    try: latitude, longitude = Decimal(str(data["latitude"])), Decimal(str(data["longitude"])); incident = datetime.fromisoformat(data["incident_datetime"].replace("Z", "+00:00"))
    except (InvalidOperation, ValueError): raise ValueError("Use valid ISO 8601 incident_datetime and numeric coordinates.")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180: raise ValueError("Coordinates are out of range.")
    # A public submission never gains an identity merely by sending a JSON flag.
    anonymous = reporter_id is None or bool(data.get("is_anonymous", False))
    report = CrimeReport(reporter_id=reporter_id, is_anonymous=anonymous, crime_type=crime_type, title=title, description=description, latitude=latitude, longitude=longitude, incident_datetime=incident if incident.tzinfo else incident.replace(tzinfo=timezone.utc), status="pending")
    db.session.add(report); db.session.flush(); notify_admins_of_report(report); return report

def change_report(report: CrimeReport, action: str, admin_id, value: str | None = None) -> CrimeReport:
    if action in {"approve", "reject"}:
        if report.status != "pending": raise ValueError("Report review is already complete.")
        report.status = "approved" if action == "approve" else "rejected"; notify_reporter_of_status(report)
    elif action == "risk_level":
        if value not in {"low", "medium", "high"}: raise ValueError("Choose a valid risk level.")
        report.risk_level = value
    elif action == "classification":
        if not value or not db.session.scalar(db.select(CrimeType).where(CrimeType.name == value, CrimeType.is_active.is_(True))): raise ValueError("Choose an active crime type.")
        report.crime_type = value
    else: raise ValueError("Unsupported report action.")
    db.session.add(AdminLog(admin_id=admin_id, action=f"report.{action}:{report.id}", target_report_id=report.id)); return report
