"""Configuration for the Remote Control backend."""

from __future__ import annotations

import os
from datetime import timedelta


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _csv_env(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable as a trimmed list."""
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


class Config:
    """Base configuration shared by all environments."""

    APP_NAME = "Remote Control System"
    API_PREFIX = "/api/v1"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "30")))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ERROR_MESSAGE_KEY = "error"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'remote_control_dev.sqlite3')}",
    )
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://",
            "postgresql://",
            1,
        )

    CORS_ORIGINS = _csv_env("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    SOCKETIO_CORS_ORIGINS = _csv_env("SOCKETIO_CORS_ORIGINS", ",".join(CORS_ORIGINS))
    BCRYPT_LOG_ROUNDS = int(os.getenv("BCRYPT_LOG_ROUNDS", "12"))
    RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "200 per hour")
    RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "10 per minute")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    DEVICE_HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("DEVICE_HEARTBEAT_TIMEOUT_SECONDS", "90"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(25 * 1024 * 1024)))
    AUTO_CREATE_DEV_DB = os.getenv("AUTO_CREATE_DEV_DB", "true").lower() == "true"


class DevelopmentConfig(Config):
    """Developer-friendly configuration."""

    DEBUG = True
    ENV = "development"


class ProductionConfig(Config):
    """Production configuration with strict secret validation."""

    DEBUG = False
    ENV = "production"

    @classmethod
    def validate(cls) -> None:
        """Fail fast when production secrets are not configured."""
        insecure_values = {
            "dev-only-change-this-secret",
            "dev-only-change-this-jwt-secret",
        }
        if cls.SECRET_KEY in insecure_values or cls.JWT_SECRET_KEY in insecure_values:
            raise RuntimeError("SECRET_KEY and JWT_SECRET_KEY must be set in production.")


class TestingConfig(Config):
    """Test configuration using an in-memory database."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type[Config]:
    """Resolve the active configuration class."""
    env_name = os.getenv("FLASK_ENV", os.getenv("APP_ENV", "development")).lower()
    return CONFIG_BY_NAME.get(env_name, DevelopmentConfig)
