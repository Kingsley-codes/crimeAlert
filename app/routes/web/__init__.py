"""Public web and authentication routes."""

from urllib.parse import urljoin, urlparse
from uuid import UUID

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from app.forms.auth import LoginForm, RegistrationForm
from app.forms.report import CrimeReportForm
from app.extensions import db
from app.models.crime_report import CrimeReport
from app.models.crime_type import CrimeType
from app.models.report_media import ReportMedia
from app.models.system_setting import SystemSetting
from app.models.emergency_contact import EmergencyContact
from app.models.notification import Notification
from app.services.auth_service import authenticate_user, register_user
from app.services.media_service import upload_report_media
from app.services.report_service import create_report
from app.utils.decorators import user_required


web_bp = Blueprint("web", __name__)


def _report_form() -> CrimeReportForm:
    form = CrimeReportForm()
    crime_types = db.session.scalars(
        db.select(CrimeType.name).where(CrimeType.is_active.is_(True)).order_by(CrimeType.name)
    ).all()
    if crime_types:
        form.set_crime_type_choices(crime_types)
    return form


def _anonymous_reporting_allowed() -> bool:
    setting = db.session.get(SystemSetting, "anonymous_reporting_allowed")
    return setting is None or setting.value.lower() == "true"


@web_bp.get("/")
def home():  # type: ignore[no-untyped-def]
    return render_template("user/home.html")


@web_bp.get("/map")
def public_map():  # type: ignore[no-untyped-def]
    return render_template("public/map.html")


@web_bp.get("/about")
def about():  # type: ignore[no-untyped-def]
    return render_template("public/about.html")


@web_bp.get("/how-it-works")
def how_it_works():  # type: ignore[no-untyped-def]
    return render_template("public/how_it_works.html")


@web_bp.get("/safety-guidance")
def safety_guidance():  # type: ignore[no-untyped-def]
    return render_template("public/safety_guidance.html")


@web_bp.get("/emergency-contacts")
def emergency_contacts():  # type: ignore[no-untyped-def]
    """Show only administrator-maintained active emergency contacts."""
    contacts = db.session.scalars(db.select(EmergencyContact).where(EmergencyContact.is_active.is_(True)).order_by(EmergencyContact.location, EmergencyContact.name)).all()
    return render_template("public/emergency_contacts.html", contacts=contacts)


@web_bp.get("/dashboard/notifications")
@login_required
def notifications():  # type: ignore[no-untyped-def]
    """Dedicated notification history required by the mobile-first UI."""
    notices = db.session.scalars(
        db.select(Notification).where(Notification.recipient_id == current_user.id).order_by(Notification.created_at.desc())
    ).all()
    return render_template("user/notifications.html", notifications=notices)


def _dashboard_url() -> str:
    """Return the correct landing page for the current authenticated role."""
    return url_for("admin.dashboard") if current_user.role == "admin" else url_for("web.dashboard")


@web_bp.get("/dashboard")
@login_required
def dashboard():  # type: ignore[no-untyped-def]
    if current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    reports = db.session.scalars(
        db.select(CrimeReport)
        .where(CrimeReport.reporter_id == current_user.id)
        .order_by(CrimeReport.created_at.desc(), CrimeReport.id.desc())
        .limit(5)
    ).all()
    stats = {
        "total": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.reporter_id == current_user.id)) or 0,
        "pending": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.reporter_id == current_user.id, CrimeReport.status == "pending")) or 0,
        "approved": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.reporter_id == current_user.id, CrimeReport.status == "approved")) or 0,
    }
    return render_template("user/dashboard.html", reports=reports, stats=stats)


@web_bp.get("/dashboard/reports")
@user_required
def my_reports():  # type: ignore[no-untyped-def]
    """Show only the signed-in user's reports, including their anonymous ones."""
    reports = db.session.scalars(
        db.select(CrimeReport)
        .where(CrimeReport.reporter_id == current_user.id)
        .order_by(CrimeReport.created_at.desc(), CrimeReport.id.desc())
    ).all()
    return render_template("user/my_reports.html", reports=reports)


@web_bp.get("/dashboard/reports/<uuid:report_id>")
@user_required
def my_report_detail(report_id: UUID):  # type: ignore[no-untyped-def]
    """Return a report only when it belongs to the signed-in user."""
    report = db.session.scalar(
        db.select(CrimeReport).where(CrimeReport.id == report_id, CrimeReport.reporter_id == current_user.id)
    )
    if report is None:
        abort(404)
    return render_template("user/report_detail.html", report=report)


@web_bp.get("/my-reports")
@login_required
def legacy_my_reports():  # type: ignore[no-untyped-def]
    return redirect(_dashboard_url()) if current_user.role == "admin" else redirect(url_for("web.my_reports"))


@web_bp.get("/my-reports/<uuid:report_id>")
@login_required
def legacy_my_report_detail(report_id: UUID):  # type: ignore[no-untyped-def]
    if current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("web.my_report_detail", report_id=report_id))


@web_bp.route("/dashboard/report-crime", methods=["GET", "POST"])
@user_required
def report_crime():  # type: ignore[no-untyped-def]
    form = _report_form()
    if form.validate_on_submit():
        try:
            report = create_report({"crime_type": form.crime_type.data, "title": form.title.data, "description": form.description.data, "latitude": str(form.parsed_latitude), "longitude": str(form.parsed_longitude), "incident_datetime": form.parsed_incident_datetime.isoformat(), "is_anonymous": bool(form.is_anonymous.data)}, current_user.id)
            if form.media.data and form.media.data.filename:
                file_path, media_type = upload_report_media(form.media.data)
                report.media.append(ReportMedia(file_path=file_path, media_type=media_type))
            db.session.commit()
        except (ValueError, SQLAlchemyError):
            db.session.rollback()
            flash("We could not submit this report. Please try again.", "error")
        except Exception:
            db.session.rollback()
            flash("Media upload failed. Your report was not submitted.", "error")
        else:
            return render_template("user/report_submission_success.html", dashboard_url=url_for("web.dashboard"))
    return render_template("user/report_crime.html", form=form)


@web_bp.route("/report-crime", methods=["GET", "POST"])
def public_report_crime():  # type: ignore[no-untyped-def]
    """Accept anonymous public reports without requiring an account."""
    if not _anonymous_reporting_allowed():
        flash("Anonymous reporting is currently unavailable. Please sign in to submit a report.", "warning")
        return redirect(url_for("web.login"))
    form = _report_form()
    if form.validate_on_submit():
        try:
            report = create_report({"crime_type": form.crime_type.data, "title": form.title.data, "description": form.description.data, "latitude": str(form.parsed_latitude), "longitude": str(form.parsed_longitude), "incident_datetime": form.parsed_incident_datetime.isoformat(), "is_anonymous": True})
            if form.media.data and form.media.data.filename:
                file_path, media_type = upload_report_media(form.media.data)
                report.media.append(ReportMedia(file_path=file_path, media_type=media_type))
            db.session.commit()
        except (ValueError, SQLAlchemyError):
            db.session.rollback()
            flash("We could not submit this report. Please try again.", "error")
        except Exception:
            db.session.rollback()
            flash("Media upload failed. Your report was not submitted.", "error")
        else:
            flash("Your anonymous report was submitted for review.", "success")
            return redirect(url_for("web.home"))
    return render_template("public/report_crime.html", form=form)


def _safe_next_url(target: str | None) -> str | None:
    if not target:
        return None
    reference = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    return target if candidate.scheme in {"http", "https"} and candidate.netloc == reference.netloc else None


@web_bp.route("/register", methods=["GET", "POST"])
def register():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated:
        return redirect(_dashboard_url())

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = register_user(name=form.name.data, email=form.email.data, password=form.password.data)
        except ValueError as error:
            flash(str(error), "error")
        else:
            login_user(user)
            flash("Your account has been created.", "success")
            return redirect(url_for("web.dashboard"))
    return render_template("auth/register.html", form=form)


@web_bp.route("/login", methods=["GET", "POST"])
def login():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated:
        return redirect(_dashboard_url())

    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(email=form.email.data, password=form.password.data, required_role="user")
        if user is None:
            flash("Invalid credentials, inactive account, or incorrect sign-in portal.", "error")
        else:
            login_user(user, remember=form.remember.data)
            flash("Signed in successfully.", "success")
            next_url = _safe_next_url(request.args.get("next"))
            if next_url and not (user.role == "admin" and next_url.startswith("/dashboard")):
                return redirect(next_url)
            return redirect(_dashboard_url())
    return render_template("auth/login.html", form=form)


@web_bp.post("/logout")
@login_required
def logout():  # type: ignore[no-untyped-def]
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("web.home"))
