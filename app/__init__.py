"""CrimeAlert application factory."""

from flask import Flask, render_template

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_overrides: dict | None = None) -> Flask:
    """Create and configure a CrimeAlert Flask application instance."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "web.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    # Import models after extensions are ready so Flask-Migrate sees all metadata.
    from app import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id: str):  # type: ignore[no-untyped-def]
        """Reject suspended accounts whenever Flask-Login restores a session."""
        from app.models.user import User

        if not user_id.isdigit():
            return None
        user = db.session.get(User, int(user_id))
        return user if user is not None and user.can_authenticate else None

    from app.routes.admin import admin_bp
    from app.routes.web import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(admin_bp)

    register_error_handlers(app)
    return app


def register_error_handlers(app: Flask) -> None:
    """Register minimal error pages shared by every blueprint."""

    @app.errorhandler(404)
    def not_found(error):  # type: ignore[no-untyped-def]
        return render_template("errors/404.html"), 404
