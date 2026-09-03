"""CrimeAlert application factory."""

import secrets
from uuid import UUID
import click
from flask import Flask, g, jsonify, render_template, request
from werkzeug.security import generate_password_hash

from app.config import Config
from app.extensions import csrf, db, jwt, login_manager, migrate


def create_app(config_overrides: dict | None = None) -> Flask:
    """Create and configure a CrimeAlert Flask application instance."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if config_overrides:
        app.config.update(config_overrides)

    if not app.config.get("TESTING"):
        for key in ("SECRET_KEY", "JWT_SECRET_KEY", "SQLALCHEMY_DATABASE_URI"):
            value = app.config.get(key)
            if not value or str(value).startswith("replace-with-"):
                raise RuntimeError(f"{key} must be configured securely before the application starts.")
            if key != "SQLALCHEMY_DATABASE_URI" and len(str(value)) < 32:
                raise RuntimeError(f"{key} must be at least 32 characters long.")
        if app.config["SECRET_KEY"] == app.config["JWT_SECRET_KEY"]:
            raise RuntimeError("SECRET_KEY and JWT_SECRET_KEY must be different values.")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    jwt.init_app(app)
    login_manager.login_view = "web.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    # Import models after extensions are ready so Flask-Migrate sees all metadata.
    from app import models  # noqa: F401

    @jwt.token_in_blocklist_loader
    def revoked_jwt_token(_jwt_header, jwt_payload):  # type: ignore[no-untyped-def]
        from app.models.revoked_token import RevokedToken
        return db.session.get(RevokedToken, jwt_payload["jti"]) is not None

    @jwt.unauthorized_loader
    def missing_jwt(reason: str):  # type: ignore[no-untyped-def]
        return jsonify({"ok": False, "error": {"message": "Authentication is required."}}), 401

    @jwt.invalid_token_loader
    def invalid_jwt(reason: str):  # type: ignore[no-untyped-def]
        return jsonify({"ok": False, "error": {"message": "Invalid authentication token."}}), 401

    @jwt.expired_token_loader
    def expired_jwt(_header, _payload):  # type: ignore[no-untyped-def]
        return jsonify({"ok": False, "error": {"message": "Authentication token has expired."}}), 401

    @jwt.revoked_token_loader
    def revoked_jwt(_header, _payload):  # type: ignore[no-untyped-def]
        return jsonify({"ok": False, "error": {"message": "Authentication token has been revoked."}}), 401

    @app.context_processor
    def dashboard_notifications():  # type: ignore[no-untyped-def]
        from flask_login import current_user
        from app.models.notification import Notification
        if not current_user.is_authenticated:
            return {"nav_notifications": [], "unread_notification_count": 0}
        from app.services.notification_service import purge_expired_read_notifications
        if purge_expired_read_notifications():
            db.session.commit()
        notices = db.session.scalars(db.select(Notification).where(Notification.recipient_id == current_user.id).order_by(Notification.created_at.desc()).limit(8)).all()
        return {"nav_notifications": notices, "unread_notification_count": sum(notice.is_read is False for notice in notices)}

    @login_manager.user_loader
    def load_user(user_id: str):  # type: ignore[no-untyped-def]
        """Reject suspended accounts whenever Flask-Login restores a session."""
        from app.models.user import User

        try:
            user_uuid = UUID(user_id)
        except (TypeError, ValueError):
            return None
        user = db.session.get(User, user_uuid)
        return user if user is not None and user.can_authenticate else None

    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.web import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(admin_bp)
    # Bearer-token clients do not use cookie CSRF. Same-origin session calls are
    # checked explicitly by the API role decorator.
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp)
    # Compatibility for the pre-versioned public-map client; new clients use /api/v1.
    app.add_url_rule("/api/public-reports", endpoint="api_legacy_public_reports", view_func=app.view_functions["api.public_reports"], methods=["GET"])

    @app.before_request
    def assign_request_nonce():  # type: ignore[no-untyped-def]
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def security_context():  # type: ignore[no-untyped-def]
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def apply_security_headers(response):  # type: ignore[no-untyped-def]
        nonce = getattr(g, "csp_nonce", "")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", f"default-src 'self'; script-src 'self' 'nonce-{nonce}' https://unpkg.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://unpkg.com; img-src 'self' data: https://*.tile.openstreetmap.org; font-src 'self' data:; connect-src 'self' https://*.tile.openstreetmap.org; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Administrator name", help="Display name for the administrator.")
    @click.option("--email", prompt="Administrator email", help="Unique administrator email address.")
    @click.password_option(confirmation_prompt=True)
    def create_admin(name: str, email: str, password: str) -> None:
        """Create a new active administrator account."""
        from app.models.user import User
        from app.services.auth_service import normalize_email

        normalized_email = normalize_email(email)
        if db.session.scalar(db.select(User).where(User.email == normalized_email)) is not None:
            raise click.ClickException("An account already exists for this email address.")
        admin = User(name=name.strip(), email=normalized_email, password_hash=generate_password_hash(password), role="admin")
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Administrator created for {normalized_email}.")

    register_error_handlers(app)
    return app


def register_error_handlers(app: Flask) -> None:
    """Register minimal error pages shared by every blueprint."""

    @app.errorhandler(404)
    def not_found(error):  # type: ignore[no-untyped-def]
        return render_template("errors/404.html"), 404

    @app.errorhandler(400)
    def bad_request(error):  # type: ignore[no-untyped-def]
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"message": "Invalid request."}}), 400
        return render_template("errors/404.html"), 400

    @app.errorhandler(403)
    def forbidden(error):  # type: ignore[no-untyped-def]
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"message": "Access denied."}}), 403
        return render_template("errors/404.html"), 403

    @app.errorhandler(413)
    def request_too_large(error):  # type: ignore[no-untyped-def]
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"message": "Request is too large."}}), 413
        return "Request is too large.", 413

    @app.errorhandler(429)
    def rate_limited(error):  # type: ignore[no-untyped-def]
        message = "Too many requests. Please try again later."
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"message": message}}), 429
        return message, 429

    @app.errorhandler(500)
    def internal_error(error):  # type: ignore[no-untyped-def]
        app.logger.exception("Unhandled request error")
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": {"message": "An internal error occurred."}}), 500
        return "An internal error occurred.", 500
