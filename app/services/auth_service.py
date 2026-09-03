"""Reusable authentication operations; routes only coordinate requests and responses."""

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.user import User


# Equalize the expensive password check when an email does not exist, reducing
# account-enumeration timing differences without logging credentials.
DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-password")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(*, name: str, email: str, password: str) -> User:
    """Create a standard active user with a securely hashed password."""
    normalized_email = normalize_email(email)
    if db.session.scalar(db.select(User).where(User.email == normalized_email)) is not None:
        raise ValueError("An account already exists for this email address.")

    user = User(
        name=name.strip(),
        email=normalized_email,
        password_hash=generate_password_hash(password),
        role="user",
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(*, email: str, password: str, required_role: str | None = None) -> User | None:
    """Return an active, password-verified user, optionally constrained to a role."""
    user = db.session.scalar(db.select(User).where(User.email == normalize_email(email)))
    if user is None:
        check_password_hash(DUMMY_PASSWORD_HASH, password)
        return None
    if not user.can_authenticate:
        check_password_hash(user.password_hash, password)
        return None
    if required_role is not None and user.role != required_role:
        return None
    return user if check_password_hash(user.password_hash, password) else None
