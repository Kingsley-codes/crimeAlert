"""CrimeAlert application factory."""

import click
from flask import Flask, render_template
from werkzeug.security import generate_password_hash

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
    from app.routes.api import api_bp
    from app.routes.web import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

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
