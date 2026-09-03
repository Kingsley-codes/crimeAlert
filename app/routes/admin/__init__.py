"""Administrator authentication, dashboard, and report-management routes."""

import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
import re
from uuid import UUID

from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user
from sqlalchemy import String, cast, or_

from app.extensions import db
from app.forms.auth import LoginForm
from app.models.admin_log import AdminLog
from app.models.crime_type import CrimeType
from app.models.crime_report import CrimeReport
from app.models.emergency_contact import EmergencyContact
from app.models.notification import Notification
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.services.auth_service import authenticate_user
from app.services.report_service import change_report
from app.utils.decorators import admin_required
from app.security import rate_limiter


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
VALID_STATUSES = {"approved", "rejected"}
VALID_RISK_LEVELS = {"high", "medium", "low"}
VALID_USER_STATUSES = {"active", "suspended"}
NIGERIAN_STATES = (
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
    "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "Federal Capital Territory",
    "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara",
    "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
    "Sokoto", "Taraba", "Yobe", "Zamfara",
)


def _report_payload(report: CrimeReport) -> dict[str, object]:
    """Return the client-safe report fields used by management AJAX updates."""
    return {"id": str(report.id), "status": report.status, "risk_level": report.risk_level, "crime_type": report.crime_type, "title": report.title}


def _json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _parse_filter_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalise_nigerian_phone(value: str) -> str:
    """Validate a Nigerian mobile number and store it in an unambiguous format."""
    raw_value = value.strip()
    if not re.fullmatch(r"\+?[0-9\s()\-]+", raw_value):
        raise ValueError("Enter a Nigerian phone number using digits only.")
    digits = re.sub(r"\D", "", raw_value)
    if digits.startswith("234") and len(digits) == 13:
        local_number = f"0{digits[3:]}"
    elif len(digits) == 11:
        local_number = digits
    else:
        raise ValueError("Enter an 11-digit Nigerian mobile number, e.g. 0801 234 5678.")
    if not re.fullmatch(r"0[789][0-9]{9}", local_number):
        raise ValueError("Enter a valid Nigerian mobile number, e.g. 0801 234 5678.")
    return f"+234 {local_number[1:4]} {local_number[4:7]} {local_number[7:]}"


def _period_bounds(period: str, today: date) -> tuple[date | None, date | None]:
    """Return inclusive calendar-date boundaries for an admin filter preset."""
    if period == "today":
        return today, today
    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if period == "this_week":
        return today - timedelta(days=today.weekday()), today
    if period == "last_week":
        this_week_start = today - timedelta(days=today.weekday())
        return this_week_start - timedelta(days=7), this_week_start - timedelta(days=1)
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        return last_month_end.replace(day=1), last_month_end
    return None, None


def _report_filters():  # type: ignore[no-untyped-def]
    """Apply report-management filters consistently to full and asynchronous table views."""
    status = request.args.get("status", "").strip().lower()
    crime_type = request.args.get("crime_type", "").strip().lower()
    risk_level = request.args.get("risk_level", "").strip().lower()
    search = request.args.get("search", "").strip()
    period = request.args.get("period", "today").strip().lower()
    today = datetime.now(timezone.utc).date()
    date_from = _parse_filter_date(request.args.get("date_from"))
    date_to = _parse_filter_date(request.args.get("date_to"))
    # Keep legacy URLs working while standardising the UI on calendar periods.
    period = {"last_7_days": "this_week", "last_30_days": "this_month"}.get(period, period)
    period_from, period_to = _period_bounds(period, today)
    if period_from:
        date_from, date_to = period_from, period_to
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
    reference_match = re.fullmatch(r"CR-[0-9a-f]{10}", search, re.IGNORECASE)
    if reference_match:
        statement = statement.where(CrimeReport.reference_code == search.upper())
    elif search:
        pattern = f"%{search}%"
        statement = statement.where(or_(CrimeReport.title.ilike(pattern), CrimeReport.description.ilike(pattern), CrimeReport.crime_type.ilike(pattern)))
    reports = db.session.scalars(statement.order_by(CrimeReport.created_at.desc())).all()
    crime_types = db.session.scalars(db.select(CrimeType).where(CrimeType.is_active.is_(True)).order_by(CrimeType.name)).all()
    return reports, crime_types


def _map_payload(report: CrimeReport) -> dict[str, object]:
    """Return full-location report data exclusively for the admin analytics map."""
    return {
        "id": str(report.id),
        "reference_code": report.reference_code,
        "title": report.title,
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
            "latitude": (latitude + 0.5) * cell_size,
            "longitude": (longitude + 0.5) * cell_size,
        }
        for (latitude, longitude), count in sorted(cells.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]


def _setting(key: str, default: str) -> str:
    setting = db.session.get(SystemSetting, key)
    return setting.value if setting is not None else default


def _set_setting(key: str, value: str) -> None:
    setting = db.session.get(SystemSetting, key)
    if setting is None:
        db.session.add(SystemSetting(key=key, value=value))
    else:
        setting.value = value


def _trend_reports() -> tuple[list[CrimeReport], str, date | None, date | None]:
    """Return the admin-authorized report dataset used by trends and CSV exports."""
    period = request.args.get("period", "this_month").strip().lower()
    today = datetime.now(timezone.utc).date()
    date_from = _parse_filter_date(request.args.get("date_from"))
    date_to = _parse_filter_date(request.args.get("date_to"))
    # Accept former preset names in saved links, while using clearer calendar periods.
    period = {"daily": "today", "weekly": "this_week", "monthly": "this_month"}.get(period, period)
    period_from, period_to = _period_bounds(period, today)
    if period_from:
        date_from, date_to = period_from, period_to
    elif period != "custom":
        period, date_from, date_to = "this_month", today.replace(day=1), today
    statement = db.select(CrimeReport)
    crime_type = request.args.get("crime_type", "").strip().lower()
    risk_level = request.args.get("risk_level", "").strip().lower()
    if crime_type:
        statement = statement.where(CrimeReport.crime_type == crime_type)
    if risk_level in VALID_RISK_LEVELS:
        statement = statement.where(CrimeReport.risk_level == risk_level)
    if date_from:
        statement = statement.where(CrimeReport.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        statement = statement.where(CrimeReport.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    return db.session.scalars(statement.order_by(CrimeReport.created_at.asc())).all(), period, date_from, date_to


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
        if not rate_limiter.allow("admin-login", current_app.config["RATE_LIMIT_LOGIN"]):
            abort(429)
        user = authenticate_user(email=form.email.data, password=form.password.data, required_role="admin")
        if user is None:
            flash("Invalid credentials or account access.", "error")
        else:
            session.clear()
            session.permanent = True
            login_user(user, remember=form.remember.data)
            flash("Admin sign-in successful.", "success")
            return redirect(url_for("admin.dashboard"))
    return render_template("auth/admin_login.html", form=form)


@admin_bp.get("/dashboard")
@admin_required
def dashboard():  # type: ignore[no-untyped-def]
    """Show the overview, including the project-required trend analytics."""
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)
    trend_start = today - timedelta(days=29)
    reports = db.session.scalars(
        db.select(CrimeReport).order_by(CrimeReport.created_at.desc()).limit(8)
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
    trend_reports, trend_period, trend_from, trend_to = _trend_reports()
    trend_volume: dict[str, int] = {}
    trend_crimes: dict[str, int] = {}
    trend_risks = {level: 0 for level in ("high", "medium", "low")}
    for report in trend_reports:
        label = report.created_at.strftime("%d %b")
        trend_volume[label] = trend_volume.get(label, 0) + 1
        trend_crimes[report.crime_type] = trend_crimes.get(report.crime_type, 0) + 1
        trend_risks[report.risk_level] = trend_risks.get(report.risk_level, 0) + 1
    crime_types = db.session.scalars(db.select(CrimeType).where(CrimeType.is_active.is_(True)).order_by(CrimeType.name)).all()
    return render_template(
        "admin/dashboard.html",
        reports=reports,
        stats=stats,
        trend_labels=[day.strftime("%d %b") for day in daily_counts],
        trend_values=list(daily_counts.values()),
        analytics_period=trend_period,
        analytics_from=trend_from,
        analytics_to=trend_to,
        analytics_crime_types=crime_types,
        analytics_volume_labels=list(trend_volume),
        analytics_volume_values=list(trend_volume.values()),
        analytics_crime_counts=trend_crimes,
        analytics_risk_counts=trend_risks,
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


@admin_bp.get("/reports/<uuid:report_id>/details")
@admin_required
def report_details(report_id: UUID):  # type: ignore[no-untyped-def]
    """Return the full private detail needed by the report-review dialog."""
    report = db.session.get(CrimeReport, report_id)
    if report is None:
        return _json_error("Report not found.", 404)
    return jsonify({
        **_report_payload(report),
        "reference_code": report.reference_code,
        "description": report.description,
        "incident_datetime": report.incident_datetime.isoformat(),
        "created_at": report.created_at.isoformat(),
        "latitude": float(report.latitude),
        "longitude": float(report.longitude),
        "is_anonymous": report.is_anonymous,
        "reporter": None if report.reporter is None or report.is_anonymous else {"name": report.reporter.name, "email": report.reporter.email},
    })


@admin_bp.get("/map-analytics")
@admin_required
def map_analytics():  # type: ignore[no-untyped-def]
    """Render the administrator-only all-report crime map."""
    return render_template("admin/map_analytics.html")


@admin_bp.get("/map-analytics/data")
@admin_required
def map_analytics_data():  # type: ignore[no-untyped-def]
    """Return all reports and the five busiest coordinate-grid zones for administrators."""
    reports = db.session.scalars(db.select(CrimeReport).order_by(CrimeReport.incident_datetime.desc())).all()
    return jsonify({"reports": [_map_payload(report) for report in reports], "hotspots": _hotspots(reports)})


@admin_bp.get("/trend-reports")
@admin_required
def trend_reports():  # type: ignore[no-untyped-def]
    """Keep old links working while analytics lives on the Overview screen."""
    return redirect(url_for("admin.dashboard", **request.args))


@admin_bp.get("/dashboard/export.csv")
@admin_required
def trend_reports_export():  # type: ignore[no-untyped-def]
    """Export only the current filtered admin analytics dataset, without reporter data."""
    reports, _, _, _ = _trend_reports()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["reference_code", "reported_at", "crime_type", "risk_level", "status", "latitude", "longitude"])
    for report in reports:
        writer.writerow([report.reference_code, report.created_at.isoformat(), report.crime_type, report.risk_level, report.status, float(report.latitude), float(report.longitude)])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=crimealert-trend-reports.csv"})


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():  # type: ignore[no-untyped-def]
    """Manage categories, contacts, and intentionally manual risk configuration."""
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "save_system":
                low_max, medium_max = int(request.form.get("low_max", "")), int(request.form.get("medium_max", ""))
                if not 0 <= low_max < medium_max <= 100:
                    raise ValueError("Thresholds must be 0–100, with low below medium.")
                _set_setting("anonymous_reporting_allowed", "true" if request.form.get("anonymous_reporting_allowed") else "false")
                _set_setting("risk_low_max", str(low_max))
                _set_setting("risk_medium_max", str(medium_max))
                db.session.add(AdminLog(admin_id=current_user.id, action="settings.system_updated"))
                flash("System settings saved. Risk levels remain administrator-assigned.", "success")
            elif action == "save_crime_type":
                name, description = request.form.get("name", "").strip().lower(), request.form.get("description", "").strip() or None
                category_id = request.form.get("category_id", type=int)
                if not name or len(name) > 100:
                    raise ValueError("Enter a category name of up to 100 characters.")
                duplicate = db.session.scalar(db.select(CrimeType).where(CrimeType.name == name, CrimeType.id != (category_id or 0)))
                if duplicate:
                    raise ValueError("That crime category already exists.")
                category = db.session.get(CrimeType, category_id) if category_id else CrimeType(name=name)
                if category is None:
                    raise ValueError("Crime category not found.")
                category.name, category.description, category.is_active = name, description, bool(request.form.get("is_active"))
                db.session.add(category)
                db.session.add(AdminLog(admin_id=current_user.id, action=f"settings.crime_type_saved:{name}"))
                flash("Crime category saved.", "success")
            elif action == "remove_crime_type":
                category = db.session.get(CrimeType, request.form.get("category_id", type=int))
                if category is None:
                    raise ValueError("Crime category not found.")
                if db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.crime_type == category.name)):
                    category.is_active = False
                    flash("Category has existing reports and was deactivated to preserve history.", "success")
                else:
                    db.session.delete(category)
                    flash("Crime category removed.", "success")
                db.session.add(AdminLog(admin_id=current_user.id, action=f"settings.crime_type_removed:{category.name}"))
            elif action == "save_contact":
                contact_id = request.form.get("contact_id", type=int)
                contact = db.session.get(EmergencyContact, contact_id) if contact_id else EmergencyContact()
                if contact is None:
                    raise ValueError("Emergency contact not found.")
                contact.name = request.form.get("name", "").strip()
                contact.phone = _normalise_nigerian_phone(request.form.get("phone", ""))
                contact.description = request.form.get("description", "").strip() or None
                contact.location = request.form.get("location", "").strip()
                contact.is_active = bool(request.form.get("is_active"))
                if not contact.name:
                    raise ValueError("Contact name is required.")
                if contact.location not in NIGERIAN_STATES:
                    raise ValueError("Choose a Nigerian state or the Federal Capital Territory.")
                db.session.add(contact)
                db.session.add(AdminLog(admin_id=current_user.id, action=f"settings.emergency_contact_saved:{contact.name}"))
                flash("Emergency contact saved.", "success")
            elif action == "remove_contact":
                contact = db.session.get(EmergencyContact, request.form.get("contact_id", type=int))
                if contact is None:
                    raise ValueError("Emergency contact not found.")
                db.session.delete(contact)
                db.session.add(AdminLog(admin_id=current_user.id, action=f"settings.emergency_contact_removed:{contact.id}"))
                flash("Emergency contact removed.", "success")
            else:
                raise ValueError("Unsupported settings action.")
            db.session.commit()
        except (ValueError, TypeError) as error:
            db.session.rollback()
            flash(str(error), "error")
        except Exception:
            db.session.rollback()
            flash("The settings change could not be saved.", "error")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", crime_types=db.session.scalars(db.select(CrimeType).order_by(CrimeType.name)).all(), contacts=db.session.scalars(db.select(EmergencyContact).order_by(EmergencyContact.name)).all(), nigerian_states=NIGERIAN_STATES, anonymous_reporting_allowed=_setting("anonymous_reporting_allowed", "true") == "true", low_max=_setting("risk_low_max", "30"), medium_max=_setting("risk_medium_max", "70"))


@admin_bp.get("/users")
@admin_required
def user_management():  # type: ignore[no-untyped-def]
    """List standard user accounts without ever removing their report history."""
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip().lower()
    statement = db.select(User).where(User.role == "user")
    if status in VALID_USER_STATUSES:
        statement = statement.where(User.is_active.is_(status == "active"))
    user_reference_match = re.fullmatch(r"USR-[0-9a-f]{10}", search, re.IGNORECASE)
    if user_reference_match:
        statement = statement.where(User.reference_code == search.upper())
    elif search:
        pattern = f"%{search}%"
        statement = statement.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    users = db.session.scalars(statement.order_by(User.created_at.desc())).all()
    report_counts = dict(
        db.session.execute(
            db.select(CrimeReport.reporter_id, db.func.count(CrimeReport.id))
            .where(CrimeReport.reporter_id.is_not(None))
            .group_by(CrimeReport.reporter_id)
        ).all()
    )
    return render_template("admin/user_management.html", users=users, report_counts=report_counts)


@admin_bp.get("/users/<uuid:user_id>")
@admin_required
def user_report_history(user_id: UUID):  # type: ignore[no-untyped-def]
    """Show an administrator the full retained report history for one standard user."""
    user = db.session.scalar(db.select(User).where(User.id == user_id, User.role == "user"))
    if user is None:
        from flask import abort

        abort(404)
    reports = db.session.scalars(
        db.select(CrimeReport).where(CrimeReport.reporter_id == user.id).order_by(CrimeReport.created_at.desc())
    ).all()
    return render_template("admin/user_report_history.html", user=user, reports=reports)


@admin_bp.post("/users/<uuid:user_id>/status")
@admin_required
def update_user_status(user_id: UUID):  # type: ignore[no-untyped-def]
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


@admin_bp.post("/reports/<uuid:report_id>/actions")
@admin_required
def update_report(report_id: UUID):  # type: ignore[no-untyped-def]
    """Apply one validated administrative report action and return a JSON result."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("A JSON request body is required.")
    action = str(payload.get("action", "")).strip().lower()
    report = db.session.get(CrimeReport, report_id)
    if report is None:
        return _json_error("Report not found.", 404)

    try:
        value = str(payload.get("risk_level" if action == "risk_level" else "crime_type", "")).strip().lower()
        change_report(report, action, current_user.id, value if action in {"risk_level", "classification"} else None)
        db.session.commit()
        message = "Report status updated." if action in {"approve", "reject"} else "Report updated."
    except ValueError as error:
        db.session.rollback()
        return _json_error(str(error))
    except Exception:
        db.session.rollback()
        return _json_error("The report could not be updated.", 500)

    return jsonify({"ok": True, "message": message, "report": _report_payload(report)})
