"""Notification creation and safe presentation helpers."""
from app.extensions import db
from app.models.notification import Notification
from app.models.user import User

def create_notification(recipient_id, notification_type: str, title: str, message: str, report_id=None) -> Notification:
    notification = Notification(recipient_id=recipient_id, report_id=report_id, notification_type=notification_type, title=title, message=message)
    db.session.add(notification)
    return notification

def notify_admins_of_report(report) -> None:
    for admin_id in db.session.scalars(db.select(User.id).where(User.role == "admin", User.is_active.is_(True))):
        create_notification(admin_id, "report_submitted", "New report submitted", f"{report.crime_type.title()} report {report.reference_code} is awaiting review.", report.id)

def notify_reporter_of_status(report) -> None:
    if report.reporter_id and not report.is_anonymous:
        create_notification(report.reporter_id, f"report_{report.status}", f"Your report was {report.status}", f"Report {report.reference_code} has been {report.status}.", report.id)
