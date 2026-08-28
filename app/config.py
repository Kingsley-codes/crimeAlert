"""Environment-driven configuration for CrimeAlert."""

import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Base configuration. Secrets and connection details are never hardcoded."""

    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("DATABASE_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
