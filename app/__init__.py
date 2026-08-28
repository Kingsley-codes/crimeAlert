"""CrimeAlert application factory."""

from flask import Flask, render_template

from app.config import Config
from app.extensions import db, login_manager, migrate


def create_app(config_overrides: dict | None = None) -> Flask:
    """Create and configure a CrimeAlert Flask application instance."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Import models after extensions are ready so Flask-Migrate sees all metadata.
    from app import models  # noqa: F401

    @login_manager.user_loader
    def load_user(_user_id: str):  # type: ignore[no-untyped-def]
        """Authentication is intentionally not implemented in this scaffold."""
        return None

    from app.routes.web import web_bp

    app.register_blueprint(web_bp)

    register_error_handlers(app)
    return app


def register_error_handlers(app: Flask) -> None:
    """Register minimal error pages shared by every blueprint."""

    @app.errorhandler(404)
    def not_found(error):  # type: ignore[no-untyped-def]
        return render_template("errors/404.html"), 404
