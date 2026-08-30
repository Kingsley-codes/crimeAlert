"""Administrator authentication, dashboard, and report-management routes."""

from datetime import date, datetime, time, timedelta, timezone
import re

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_user
from sqlalchemy import String, cast, or_

from app.extensions import db
from app.forms.auth import LoginForm
from app.models.admin_log import AdminLog
from app.models.crime_type import CrimeType
from app.models.crime_report import CrimeReport
from app.models.notification import Notification
from app.models.user import User
from app.services.auth_service import authenticate_user
from app.utils.decorators import admin_required


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
VALID_STATUSES = {"approved", "rejected"}
VALID_RISK_LEVELS = {"high", "medium", "low"}
VALID_USER_STATUSES = {"active", "suspended"}


def _report_payload(report: CrimeReport) -> dict[str, object]:
    """Return the client-safe report fields used by management AJAX updates."""
    return {"id": report.id, "status": report.status, "risk_level": report.risk_level, "crime_type": report.crime_type}


def _json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _parse_filter_date(value: str | None) -> date | None:
    if not value:
        return None


def _report_filters():  # type: ignore[no-untyped-def]
    """Apply report-management filters consistently to full and asynchronous table views."""
    status = request.args.get("status", "").strip().lower()
    crime_type = request.args.get("crime_type", "").strip().lower()
    risk_level = request.args.get("risk_level", "").strip().lower()
    search = request.args.get("search", "").strip()
    period = request.args.get("period", "").strip().lower()
    today = datetime.now(timezone.utc).date()
    date_from = _parse_filter_date(request.args.get("date_from"))
    date_to = _parse_filter_date(request.args.get("date_to"))
    if period == "today":
        date_from = date_to = today
    elif period == "yesterday":
        date_from = date_to = today - timedelta(days=1)
    elif period == "last_7_days":
        date_from, date_to = today - timedelta(days=6), today
    elif period == "last_30_days":
        date_from, date_to = today - timedelta(days=29), today
    elif period == "this_month":
        date_from, date_to = today.replace(day=1), today
    elif period != "custom":
        date_from = date_to = None
    statement = db.select(CrimeReport)
    if status in {"pending", "approved", "rejected"}:
        statement = statement.where(CrimeReport.status == status)
    if crime_type:
        statement = statement.where(CrimeReport.crime_type == crime_type)
    if risk_level in VALID_RISK_LEVELS:
        statement = statement.where(CrimeReport.risk_level == risk_level)
    if date_from:
        statement = statement.where(CrimeReport.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        statement = statement.where(CrimeReport.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    reference_match = re.fullmatch(r"(?:CR|RPT)-?(\d+)", search, re.IGNORECASE)
    if reference_match:
        statement = statement.where(CrimeReport.id == int(reference_match.group(1)))
    elif search:
        pattern = f"%{search}%"
        statement = statement.where(or_(CrimeReport.description.ilike(pattern), CrimeReport.crime_type.ilike(pattern), cast(CrimeReport.id, String).ilike(pattern)))
    reports = db.session.scalars(statement.order_by(CrimeReport.created_at.desc(), CrimeReport.id.desc())).all()
    crime_types = db.session.scalars(db.select(CrimeType).where(CrimeType.is_active.is_(True)).order_by(CrimeType.name)).all()
    return reports, crime_types


def _map_payload(report: CrimeReport) -> dict[str, object]:
    """Return full-location report data exclusively for the admin analytics map."""
    return {
        "id": report.id,
        "crime_type": report.crime_type,
        "incident_datetime": report.incident_datetime.isoformat(),
        "risk_level": report.risk_level,
        "status": report.status,
        "latitude": float(report.latitude),
        "longitude": float(report.longitude),
    }


def _hotspots(reports: list[CrimeReport]) -> list[dict[str, object]]:
    """Group reports into approximately 5 km coordinate grid cells for quick hotspot ranking."""
    cell_size = 0.05
    cells: dict[tuple[int, int], int] = {}
    for report in reports:
        key = (int(float(report.latitude) // cell_size), int(float(report.longitude) // cell_size))
        cells[key] = cells.get(key, 0) + 1
    return [
        {
            "zone": f"Grid {latitude * cell_size:.2f}°, {longitude * cell_size:.2f}°",
            "count": count,
        }
        for (latitude, longitude), count in sorted(cells.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _notify_reporter(report: CrimeReport, status: str) -> None:
    """Notify the private report owner about a completed review when present."""
    if report.reporter_id is None:
        return
    outcome = "approved" if status == "approved" else "not approved"
    db.session.add(
        Notification(
            recipient_id=report.reporter_id,
            report_id=report.id,
            notification_type=f"report_{status}",
            title=f"Your report was {outcome}",
            message=f"Your {report.crime_type} report has been reviewed and was {outcome}.",
        )
    )


@admin_bp.route("/login", methods=["GET", "POST"])
def login():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated and current_user.role == "admin" and current_user.is_active:
        return redirect(url_for("admin.dashboard"))
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(email=form.email.data, password=form.password.data, required_role="admin")
        if user is None:
            flash("Invalid credentials or account access.", "error")
        else:
            login_user(user, remember=form.remember.data)
            flash("Admin sign-in successful.", "success")
            return redirect(url_for("admin.dashboard"))
    return render_template("auth/admin_login.html", form=form)


@admin_bp.get("/dashboard")
@admin_required
def dashboard():  # type: ignore[no-untyped-def]
    """Show administrators the current review workload and 30-day trend."""
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)
    trend_start = today - timedelta(days=29)
    reports = db.session.scalars(
        db.select(CrimeReport).order_by(CrimeReport.created_at.desc(), CrimeReport.id.desc()).limit(8)
    ).all()
    recent_reports = db.session.scalars(
        db.select(CrimeReport).where(CrimeReport.created_at >= datetime.combine(trend_start, time.min, tzinfo=timezone.utc))
    ).all()
    monthly_reports = db.session.scalars(
        db.select(CrimeReport).where(CrimeReport.created_at >= datetime.combine(month_start, time.min, tzinfo=timezone.utc))
    ).all()
    daily_counts = {trend_start + timedelta(days=offset): 0 for offset in range(30)}
    for report in recent_reports:
        created = report.created_at.date()
        if created in daily_counts:
            daily_counts[created] += 1
    crime_counts: dict[str, int] = {}
    for report in monthly_reports:
        crime_counts[report.crime_type] = crime_counts.get(report.crime_type, 0) + 1
    most_common = max(crime_counts, key=crime_counts.get) if crime_counts else None
    stats = {
        "total": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport)) or 0,
        "pending": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.status == "pending")) or 0,
        "approved": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.status == "approved")) or 0,
        "most_common": most_common.title() if most_common else "No reports yet",
    }
    return render_template(
        "admin/dashboard.html",
        reports=reports,
        stats=stats,
        trend_labels=[day.strftime("%d %b") for day in daily_counts],
        trend_values=list(daily_counts.values()),
    )


@admin_bp.get("/reports")
@admin_required
def report_management():  # type: ignore[no-untyped-def]
    """List reports with server-side filtering for administrative review."""
    reports, crime_types = _report_filters()
    return render_template("admin/report_management.html", reports=reports, crime_types=crime_types)


@admin_bp.get("/reports/table")
@admin_required
def report_management_table():  # type: ignore[no-untyped-def]
    """Render only report results so filtering does not reload the dashboard shell."""
    reports, crime_types = _report_filters()
    return render_template("admin/_report_table.html", reports=reports, crime_types=crime_types)


@admin_bp.get("/map-analytics")
@admin_required
def map_analytics():  # type: ignore[no-untyped-def]
    """Render the administrator-only all-report crime map."""
    return render_template("admin/map_analytics.html")


@admin_bp.get("/map-analytics/data")
@admin_required
def map_analytics_data():  # type: ignore[no-untyped-def]
    """Return all reports and the five busiest coordinate-grid zones for administrators."""
    reports = db.session.scalars(db.select(CrimeReport).order_by(CrimeReport.incident_datetime.desc(), CrimeReport.id.desc())).all()
    return jsonify({"reports": [_map_payload(report) for report in reports], "hotspots": _hotspots(reports)})


@admin_bp.get("/users")
@admin_required
def user_management():  # type: ignore[no-untyped-def]
    """List standard user accounts without ever removing their report history."""
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip().lower()
    statement = db.select(User).where(User.role == "user")
    if status in VALID_USER_STATUSES:
        statement = statement.where(User.is_active.is_(status == "active"))
    if search:
        pattern = f"%{search}%"
        statement = statement.where(or_(User.name.ilike(pattern), User.email.ilike(pattern), cast(User.id, String).ilike(pattern)))
    users = db.session.scalars(statement.order_by(User.created_at.desc(), User.id.desc())).all()
    report_counts = dict(
        db.session.execute(
            db.select(CrimeReport.reporter_id, db.func.count(CrimeReport.id))
            .where(CrimeReport.reporter_id.is_not(None))
            .group_by(CrimeReport.reporter_id)
        ).all()
    )
    return render_template("admin/user_management.html", users=users, report_counts=report_counts)


@admin_bp.get("/users/<int:user_id>")
@admin_required
def user_report_history(user_id: int):  # type: ignore[no-untyped-def]
    """Show an administrator the full retained report history for one standard user."""
    user = db.session.scalar(db.select(User).where(User.id == user_id, User.role == "user"))
    if user is None:
        from flask import abort

        abort(404)
    reports = db.session.scalars(
        db.select(CrimeReport).where(CrimeReport.reporter_id == user.id).order_by(CrimeReport.created_at.desc(), CrimeReport.id.desc())
    ).all()
    return render_template("admin/user_report_history.html", user=user, reports=reports)


@admin_bp.post("/users/<int:user_id>/status")
@admin_required
def update_user_status(user_id: int):  # type: ignore[no-untyped-def]
    """Suspend or reactivate a standard user while retaining every related report."""
    payload = request.get_json(silent=True)
    action = str(payload.get("action", "")).strip().lower() if isinstance(payload, dict) else ""
    if action not in {"suspend", "reactivate"}:
        return _json_error("Choose suspend or reactivate.")
    user = db.session.scalar(db.select(User).where(User.id == user_id, User.role == "user"))
    if user is None:
        return _json_error("User not found.", 404)
    new_active = action == "reactivate"
    if user.is_active == new_active:
        return _json_error(f"User is already {'active' if new_active else 'suspended'}.")
    try:
        user.is_active = new_active
        db.session.add(AdminLog(admin_id=current_user.id, action=f"user.{action}:{user.id}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _json_error("The user account could not be updated.", 500)
    return jsonify({"ok": True, "message": f"{user.name}'s account was {'reactivated' if new_active else 'suspended'}.", "is_active": user.is_active})


@admin_bp.post("/reports/<int:report_id>/actions")
@admin_required
def update_report(report_id: int):  # type: ignore[no-untyped-def]
    """Apply one validated administrative report action and return a JSON result."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("A JSON request body is required.")
    action = str(payload.get("action", "")).strip().lower()
    report = db.session.get(CrimeReport, report_id)
    if report is None:
        return _json_error("Report not found.", 404)

    try:
        if action in {"approve", "reject"}:
            new_status = "approved" if action == "approve" else "rejected"
            if report.status == new_status:
                return _json_error(f"Report is already {new_status}.")
            report.status = new_status
            db.session.add(AdminLog(admin_id=current_user.id, action=f"report.{new_status}", target_report_id=report.id))
            _notify_reporter(report, new_status)
            message = f"Report {new_status}."
        elif action == "risk_level":
            risk_level = str(payload.get("risk_level", "")).strip().lower()
            if risk_level not in VALID_RISK_LEVELS:
                return _json_error("Risk level must be high, medium, or low.")
            if report.risk_level == risk_level:
                return _json_error("Report already has that risk level.")
            report.risk_level = risk_level
            db.session.add(AdminLog(admin_id=current_user.id, action=f"report.risk_level_changed:{risk_level}", target_report_id=report.id))
            message = "Risk level updated."
        elif action == "classification":
            crime_type = str(payload.get("crime_type", "")).strip().lower()
            is_valid_type = db.session.scalar(db.select(CrimeType.id).where(CrimeType.name == crime_type, CrimeType.is_active.is_(True)))
            if is_valid_type is None:
                return _json_error("Choose an active crime type.")
            if report.crime_type == crime_type:
                return _json_error("Report already has that crime type.")
            report.crime_type = crime_type
            db.session.add(AdminLog(admin_id=current_user.id, action=f"report.classification_changed:{crime_type}", target_report_id=report.id))
            message = "Classification updated."
        else:
            return _json_error("Unsupported administrative action.")
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _json_error("The report could not be updated.", 500)

    return jsonify({"ok": True, "message": message, "report": _report_payload(report)})
