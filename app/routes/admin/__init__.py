"""Administrator authentication and dashboard routes."""

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_user

from app.extensions import db
from app.forms.auth import LoginForm
from app.models.crime_report import CrimeReport
from app.services.auth_service import authenticate_user
from app.utils.decorators import admin_required


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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
    """Show administrators an at-a-glance view of report-review work."""
    reports = db.session.scalars(
        db.select(CrimeReport).order_by(CrimeReport.created_at.desc(), CrimeReport.id.desc()).limit(8)
    ).all()
    stats = {
        "pending": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.status == "pending")) or 0,
        "approved": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.status == "approved")) or 0,
        "rejected": db.session.scalar(db.select(db.func.count()).select_from(CrimeReport).where(CrimeReport.status == "rejected")) or 0,
    }
    return render_template("admin/dashboard.html", reports=reports, stats=stats)
