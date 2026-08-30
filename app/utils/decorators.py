"""Reusable authorization decorators."""

from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def admin_required(view):  # type: ignore[no-untyped-def]
    """Require an active authenticated administrator for a protected endpoint."""

    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):  # type: ignore[no-untyped-def]
        if not current_user.is_active or current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def user_required(view):  # type: ignore[no-untyped-def]
    """Require an active standard user for a protected user-dashboard endpoint."""

    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):  # type: ignore[no-untyped-def]
        if not current_user.is_active or current_user.role != "user":
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view
