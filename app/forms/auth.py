"""CSRF-protected authentication forms."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class RegistrationForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=150)])
    email = StringField("Email address", validators=[DataRequired(), Length(max=255), Regexp(EMAIL_PATTERN)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email address", validators=[DataRequired(), Length(max=255), Regexp(EMAIL_PATTERN)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")
