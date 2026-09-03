"""Safe Cloudinary upload helpers for crime report media."""

from pathlib import PurePath
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage


MIME_BY_EXTENSION = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
    "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
}


def detect_media_mime(upload: FileStorage) -> str | None:
    """Identify only the limited image/video formats accepted by the application.

    Browser-provided MIME metadata is attacker controlled, so it is never trusted alone.
    """
    stream = upload.stream
    position = stream.tell()
    try:
        header = stream.read(32)
    finally:
        stream.seek(position)
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/quicktime" if header[8:12] == b"qt  " else "video/mp4"
    return None


def validate_report_media(upload: FileStorage) -> tuple[str, str]:
    """Validate size, extension, declared type and file signature before upload."""
    extension = PurePath(upload.filename or "").suffix.lower().lstrip(".")
    expected_mime = MIME_BY_EXTENSION.get(extension)
    declared_mime = (upload.mimetype or "").lower()
    detected_mime = detect_media_mime(upload)
    if not expected_mime or detected_mime != expected_mime or declared_mime != expected_mime:
        raise ValueError("The uploaded file type could not be verified.")
    allowed = current_app.config["REPORT_ALLOWED_IMAGE_MIME_TYPES"] | current_app.config["REPORT_ALLOWED_VIDEO_MIME_TYPES"]
    if detected_mime not in allowed:
        raise ValueError("This media type is not allowed.")
    stream = upload.stream
    position = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(position)
    if size <= 0 or size > current_app.config["REPORT_MAX_MEDIA_FILE_SIZE"]:
        raise ValueError("The media file exceeds the allowed size.")
    return extension, detected_mime


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
    """Upload private media under a generated ID; callers must authorize delivery."""
    configure_cloudinary()
    try:
        import cloudinary.uploader
    except ImportError as error:  # Defensive: configure_cloudinary has already checked this package.
        raise ValueError("Media uploads are not available until the application dependencies are installed.") from error
    extension, mimetype = validate_report_media(upload)
    is_image = mimetype in current_app.config["REPORT_ALLOWED_IMAGE_MIME_TYPES"]
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
        type="authenticated",
    )
    # Persist an opaque provider identifier, never an externally retrievable URL.
    return result["public_id"], "image" if is_image else "video"
