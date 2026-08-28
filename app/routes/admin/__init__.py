"""Administrator authentication routes; dashboard routes are intentionally deferred."""

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_user

from app.forms.auth import LoginForm
from app.services.auth_service import authenticate_user


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated and current_user.role == "admin" and current_user.is_active:
        return redirect(url_for("web.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(email=form.email.data, password=form.password.data, required_role="admin")
        if user is None:
            flash("Invalid credentials or account access.", "error")
        else:
            login_user(user, remember=form.remember.data)
            flash("Admin sign-in successful.", "success")
            return redirect(url_for("web.home"))
    return render_template("auth/admin_login.html", form=form)
