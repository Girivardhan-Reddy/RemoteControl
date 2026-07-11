"""Configuration for the Remote Control backend."""

from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SQLITE_DEV_URI = (
    f"sqlite:///{os.path.join(BASE_DIR, 'remote_control_dev.sqlite3')}"
)

if load_dotenv:
    load_dotenv(os.path.join(BASE_DIR, ".env"))


def _csv_env(name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(name, default)
    return [
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    ]


def _is_truthy(name: str) -> bool:
    return os.getenv(name, "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def normalize_database_url(
    raw_url: str | None,
    *,
    production: bool,
) -> str:
    """
    Normalize DATABASE_URL.

    Development:
        Uses SQLite if DATABASE_URL is missing.

    Production:
        Requires PostgreSQL.
    """

    if not raw_url:
        if production:
            raise RuntimeError(
                "DATABASE_URL must be set in production."
            )

        return SQLITE_DEV_URI

    database_url = raw_url.strip()

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1,
        )

    if production and not database_url.startswith(
        ("postgresql://", "postgresql+psycopg://")
    ):
        raise RuntimeError(
            "Production DATABASE_URL must be PostgreSQL."
        )

    if (
        database_url.startswith(
            ("postgresql://", "postgresql+psycopg://")
        )
        and "sslmode=" not in database_url
    ):
        parts = urlsplit(database_url)

        query = dict(
            parse_qsl(
                parts.query,
                keep_blank_values=True,
            )
        )

        query["sslmode"] = "require"

        database_url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

    return database_url


def masked_database_url(database_url: str) -> str:
    parts = urlsplit(database_url)

    if "@" not in parts.netloc:
        return database_url

    host = parts.netloc.split("@", 1)[1]

    return urlunsplit(
        (
            parts.scheme,
            f"***:***@{host}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


class Config:
    APP_NAME = "Remote Control System"

    API_PREFIX = "/api/v1"

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-only-change-this-secret",
    )

    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "dev-only-change-this-jwt-secret",
    )

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(
            os.getenv(
                "JWT_ACCESS_MINUTES",
                "30",
            )
        )
    )

    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(
            os.getenv(
                "JWT_REFRESH_DAYS",
                "30",
            )
        )
    )

    JWT_TOKEN_LOCATION = ["headers"]

    JWT_ERROR_MESSAGE_KEY = "error"

    ENV = "base"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(
            os.getenv(
                "SQLALCHEMY_POOL_RECYCLE",
                "280",
            )
        ),
    }

    CORS_ORIGINS = _csv_env(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )

    SOCKETIO_CORS_ORIGINS = _csv_env(
        "SOCKETIO_CORS_ORIGINS",
        ",".join(CORS_ORIGINS),
    )

    BCRYPT_LOG_ROUNDS = int(
        os.getenv(
            "BCRYPT_LOG_ROUNDS",
            "12",
        )
    )

    RATE_LIMIT_DEFAULT = os.getenv(
        "RATE_LIMIT_DEFAULT",
        "200 per hour",
    )

    RATE_LIMIT_AUTH = os.getenv(
        "RATE_LIMIT_AUTH",
        "10 per minute",
    )

    LOG_LEVEL = os.getenv(
        "LOG_LEVEL",
        "INFO",
    )

    LOG_DIR = os.getenv(
        "LOG_DIR",
        os.path.join(BASE_DIR, "logs"),
    )

    LOG_MAX_BYTES = int(
        os.getenv(
            "LOG_MAX_BYTES",
            str(10 * 1024 * 1024),
        )
    )

    LOG_BACKUP_COUNT = int(
        os.getenv(
            "LOG_BACKUP_COUNT",
            "5",
        )
    )

    DEVICE_HEARTBEAT_TIMEOUT_SECONDS = int(
        os.getenv(
            "DEVICE_HEARTBEAT_TIMEOUT_SECONDS",
            "90",
        )
    )

    MAX_CONTENT_LENGTH = int(
        os.getenv(
            "MAX_CONTENT_LENGTH",
            str(25 * 1024 * 1024),
        )
    )

    AUTO_CREATE_DEV_DB = (
        os.getenv(
            "AUTO_CREATE_DEV_DB",
            "true",
        ).lower()
        == "true"
    )

    AUTO_CREATE_MISSING_TABLES = (
        os.getenv(
            "AUTO_CREATE_MISSING_TABLES",
            "false",
        ).lower()
        == "true"
    )

    SKIP_STARTUP_DB_CHECK = (
        os.getenv(
            "SKIP_STARTUP_DB_CHECK",
            "false",
        ).lower()
        == "true"
    )


class DevelopmentConfig(Config):
    DEBUG = True

    ENV = "development"

    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("DATABASE_URL")
        if _is_truthy(
            "USE_DATABASE_URL_IN_DEVELOPMENT"
        )
        else None,
        production=False,
    )


class ProductionConfig(Config):
    DEBUG = False

    ENV = "production"

    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("DATABASE_URL"),
        production=True,
    )

    @classmethod
    def validate(cls) -> None:
        insecure_values = {
            "dev-only-change-this-secret",
            "dev-only-change-this-jwt-secret",
        }

        if cls.SECRET_KEY in insecure_values:
            raise RuntimeError(
                "SECRET_KEY must be set in production."
            )

        if cls.JWT_SECRET_KEY in insecure_values:
            raise RuntimeError(
                "JWT_SECRET_KEY must be set in production."
            )

        if not os.getenv("DATABASE_URL"):
            raise RuntimeError(
                "DATABASE_URL must be set in production."
            )

        print("\n========== DATABASE DEBUG ==========")

        print(
            "APP_ENV =",
            os.getenv("APP_ENV"),
        )

        print(
            "FLASK_ENV =",
            os.getenv("FLASK_ENV"),
        )

        print(
            "DATABASE_URL =",
            masked_database_url(
                os.getenv(
                    "DATABASE_URL",
                    "",
                )
            ),
        )

        print(
            "SQLALCHEMY_DATABASE_URI =",
            masked_database_url(
                cls.SQLALCHEMY_DATABASE_URI
            ),
        )

        print(
            "====================================\n"
        )


class TestingConfig(Config):
    TESTING = True

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///:memory:"
    )

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=5
    )


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type[Config]:
    env_name = (
        os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
    )

    if (
        not env_name
        and (
            _is_truthy("RENDER")
            or os.getenv("RENDER_SERVICE_ID")
        )
    ):
        env_name = "production"

    env_name = (
        env_name or "development"
    ).lower()

    return CONFIG_BY_NAME.get(
        env_name,
        DevelopmentConfig,
    )