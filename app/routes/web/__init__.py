"""Public web and authentication routes."""

from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.forms.auth import LoginForm, RegistrationForm
from app.services.auth_service import authenticate_user, register_user


web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def home():  # type: ignore[no-untyped-def]
    return render_template("user/home.html")


def _safe_next_url(target: str | None) -> str | None:
    if not target:
        return None
    reference = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    return target if candidate.scheme in {"http", "https"} and candidate.netloc == reference.netloc else None


@web_bp.route("/register", methods=["GET", "POST"])
def register():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = register_user(name=form.name.data, email=form.email.data, password=form.password.data)
        except ValueError as error:
            flash(str(error), "error")
        else:
            login_user(user)
            flash("Your account has been created.", "success")
            return redirect(url_for("web.home"))
    return render_template("auth/register.html", form=form)


@web_bp.route("/login", methods=["GET", "POST"])
def login():  # type: ignore[no-untyped-def]
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(email=form.email.data, password=form.password.data)
        if user is None:
            flash("Invalid email, password, or inactive account.", "error")
        else:
            login_user(user, remember=form.remember.data)
            flash("Signed in successfully.", "success")
            return redirect(_safe_next_url(request.args.get("next")) or url_for("web.home"))
    return render_template("auth/login.html", form=form)


@web_bp.post("/logout")
@login_required
def logout():  # type: ignore[no-untyped-def]
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("web.home"))
