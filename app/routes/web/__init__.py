"""Public web routes."""

from flask import Blueprint, render_template


web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def home():  # type: ignore[no-untyped-def]
    return render_template("user/home.html")
