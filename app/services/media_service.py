"""Safe Cloudinary upload helpers for crime report media."""

from pathlib import PurePath
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage


def configure_cloudinary() -> None:
    """Configure Cloudinary only after confirming all server credentials exist."""
    required = ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    if not all(current_app.config.get(key) for key in required):
        raise ValueError("Media uploads are not configured. Contact an administrator.")
    try:
        import cloudinary
    except ImportError as error:
        raise ValueError("Media uploads are not available until the application dependencies are installed.") from error
    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def upload_report_media(upload: FileStorage) -> tuple[str, str]:
    """Upload one already-validated media file under a generated, unguessable ID."""
    configure_cloudinary()
    try:
        import cloudinary.uploader
    except ImportError as error:  # Defensive: configure_cloudinary has already checked this package.
        raise ValueError("Media uploads are not available until the application dependencies are installed.") from error
    mimetype = (upload.mimetype or "").lower()
    is_image = mimetype in current_app.config["REPORT_ALLOWED_IMAGE_MIME_TYPES"]
    # Never pass the client-provided name to Cloudinary. The extension is allow-listed by the form.
    extension = PurePath(upload.filename or "").suffix.lower().lstrip(".")
    public_id = f"crime-reports/{uuid4().hex}"
    result = cloudinary.uploader.upload(
        upload.stream,
        public_id=public_id,
        resource_type="image" if is_image else "video",
        format=extension,
        use_filename=False,
        unique_filename=False,
        overwrite=False,
        allowed_formats=[extension],
    )
    return result["secure_url"], "image" if is_image else "video"
