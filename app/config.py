"""Environment-driven configuration for CrimeAlert."""

import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Base configuration. Secrets and connection details are never hardcoded."""

    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("DATABASE_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = 3600
    # Cloudinary credentials are intentionally provided only through environment variables.
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
    REPORT_MAX_MEDIA_FILE_SIZE = int(os.getenv("REPORT_MAX_MEDIA_FILE_SIZE", str(25 * 1024 * 1024)))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(30 * 1024 * 1024)))
    REPORT_ALLOWED_IMAGE_MIME_TYPES = frozenset(
        value.strip() for value in os.getenv("REPORT_ALLOWED_IMAGE_MIME_TYPES", "image/jpeg,image/png,image/webp").split(",") if value.strip()
    )
    REPORT_ALLOWED_VIDEO_MIME_TYPES = frozenset(
        value.strip() for value in os.getenv("REPORT_ALLOWED_VIDEO_MIME_TYPES", "video/mp4,video/webm,video/quicktime").split(",") if value.strip()
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
