"""Validated crime-report submission form."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError


CRIME_TYPES = ("theft", "robbery", "kidnapping", "assault", "other")
MEDIA_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "mp4", "webm", "mov"}
EXECUTABLE_EXTENSIONS = {"bat", "cmd", "com", "dll", "exe", "js", "msi", "php", "ps1", "py", "sh", "vbs"}


class CrimeReportForm(FlaskForm):
    crime_type = SelectField("Crime type", choices=[(value, value.title()) for value in CRIME_TYPES], validators=[DataRequired()])
    description = TextAreaField("What happened?", validators=[DataRequired(), Length(min=10, max=5000)])
    incident_datetime = StringField("Date and time of incident", validators=[DataRequired(), Length(max=32)])
    latitude = StringField("Latitude", validators=[DataRequired(), Length(max=20)])
    longitude = StringField("Longitude", validators=[DataRequired(), Length(max=20)])
    is_anonymous = BooleanField("Submit anonymously", default=True)
    media = FileField("Photo or video", validators=[Optional()])
    submit = SubmitField("Submit report")

    def validate_incident_datetime(self, field: StringField) -> None:
        try:
            self.parsed_incident_datetime = datetime.fromisoformat(field.data)
        except (TypeError, ValueError):
            raise ValidationError("Enter a valid date and time.")

    @staticmethod
    def _coordinate(field: StringField, lower: Decimal, upper: Decimal, label: str) -> Decimal:
        try:
            value = Decimal(field.data)
        except (InvalidOperation, TypeError):
            raise ValidationError(f"Enter a valid {label}.")
        if not lower <= value <= upper:
            raise ValidationError(f"{label.title()} must be between {lower} and {upper}.")
        return value

    def validate_latitude(self, field: StringField) -> None:
        self.parsed_latitude = self._coordinate(field, Decimal("-90"), Decimal("90"), "latitude")

    def validate_longitude(self, field: StringField) -> None:
        self.parsed_longitude = self._coordinate(field, Decimal("-180"), Decimal("180"), "longitude")

    def validate_media(self, field: FileField) -> None:
        upload = field.data
        if not upload or not upload.filename:
            return

        extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if extension in EXECUTABLE_EXTENSIONS or extension not in MEDIA_EXTENSIONS:
            raise ValidationError("Upload a JPG, PNG, WebP, MP4, WebM, or MOV file only.")
        mimetype = (upload.mimetype or "").lower()
        allowed_mimetypes = current_app.config["REPORT_ALLOWED_IMAGE_MIME_TYPES"] | current_app.config["REPORT_ALLOWED_VIDEO_MIME_TYPES"]
        if mimetype not in allowed_mimetypes:
            raise ValidationError("This media type is not allowed.")

        upload.stream.seek(0, 2)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size > current_app.config["REPORT_MAX_MEDIA_FILE_SIZE"]:
            raise ValidationError("The media file exceeds the allowed size.")
