"""CSRF-protected authentication forms."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
PASSWORD_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$"


class RegistrationForm(FlaskForm):
    name = StringField(
        "Full name", validators=[DataRequired(message="Enter your full name."), Length(min=2, max=150)],
        render_kw={"autocomplete": "name", "minlength": 2, "maxlength": 150, "required": True},
    )
    email = StringField(
        "Email address", validators=[DataRequired(message="Enter your email address."), Length(max=255), Regexp(EMAIL_PATTERN, message="Enter a valid email address.")],
        render_kw={"type": "email", "autocomplete": "email", "maxlength": 255, "required": True},
    )
    password = PasswordField(
        "Password", validators=[DataRequired(message="Create a password."), Length(min=12, max=128), Regexp(PASSWORD_PATTERN, message="Use at least one uppercase letter, lowercase letter, and number.")],
        render_kw={"autocomplete": "new-password", "minlength": 12, "maxlength": 128, "required": True, "data_password_rule": "strong"},
    )
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(message="Confirm your password."), EqualTo("password", message="Passwords must match.")],
        render_kw={"autocomplete": "new-password", "minlength": 12, "maxlength": 128, "required": True, "data_password_confirm": "password"},
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField(
        "Email address", validators=[DataRequired(message="Enter your email address."), Length(max=255), Regexp(EMAIL_PATTERN, message="Enter a valid email address.")],
        render_kw={"type": "email", "autocomplete": "email", "maxlength": 255, "required": True},
    )
    password = PasswordField(
        "Password", validators=[DataRequired(message="Enter your password."), Length(max=128)],
        render_kw={"autocomplete": "current-password", "maxlength": 128, "required": True},
    )
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")
