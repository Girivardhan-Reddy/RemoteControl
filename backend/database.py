"""Database initialization and operational helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from flask import Flask
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, migrate
from config import masked_database_url


@dataclass(frozen=True)
class DatabaseStatus:
    """Database health information suitable for logs and admin tooling."""

    connected: bool
    dialect: str
    checked_at: str
    table_count: int
    database_url: str
    missing_tables: list[str]
    error: str | None = None

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation."""
        return asdict(self)


def init_database(app: Flask) -> None:
    """Initialize SQLAlchemy and migrations for an app instance."""
    db.init_app(app)
    migrate.init_app(app, db)


def create_database_schema(app: Flask) -> None:
    """Create all tables.

    This is useful for local development and small deployments. Production
    deployments should use Flask-Migrate migrations after the first module.
    """
    with app.app_context():
        db.create_all()


def missing_tables(app: Flask) -> list[str]:
    """Return model tables that do not exist in the connected database."""
    with app.app_context():
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        expected = set(db.metadata.tables.keys())
        return sorted(expected - existing)


def startup_database_check(app: Flask) -> DatabaseStatus:
    """Validate and log database connectivity during app startup."""
    status = check_database_health(app)
    app.logger.info("Database URL: %s", status.database_url)
    app.logger.info("Database type: %s", status.dialect)
    app.logger.info("Database connected: %s", status.connected)
    app.logger.info("Database table count: %s", status.table_count)
    if status.missing_tables:
        app.logger.warning("Missing database tables: %s", ", ".join(status.missing_tables))
        safe_empty_database = status.dialect == "postgresql" and status.table_count == 0
        if app.config.get("ENV") == "development" or app.config.get("AUTO_CREATE_MISSING_TABLES") or safe_empty_database:
            app.logger.warning("Creating missing database tables because this is configured as safe.")
            create_database_schema(app)
            status = check_database_health(app)
        else:
            message = "Missing tables were not auto-created. Run flask db upgrade or backend/sql/supabase_schema_repair.sql."
            app.logger.error(message)
            if app.config.get("ENV") == "production":
                raise RuntimeError(message)
    if not status.connected:
        raise RuntimeError(f"Database connection failed: {status.error}")
    if app.config.get("ENV") == "production" and status.dialect != "postgresql":
        raise RuntimeError("Production backend must be connected to PostgreSQL.")
    return status


def drop_database_schema(app: Flask) -> None:
    """Drop all tables for local test and development resets."""
    if app.config.get("ENV") == "production":
        raise RuntimeError("Refusing to drop the production database schema.")
    with app.app_context():
        db.drop_all()


def check_database_health(app: Flask) -> DatabaseStatus:
    """Run a lightweight connectivity and table-inspection check."""
    with app.app_context():
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            db.session.execute(text("SELECT 1"))
            inspector = inspect(db.engine)
            return DatabaseStatus(
                connected=True,
                dialect=db.engine.dialect.name,
                checked_at=checked_at,
                table_count=len(inspector.get_table_names()),
                database_url=masked_database_url(str(db.engine.url)),
                missing_tables=missing_tables(app),
            )
        except SQLAlchemyError as exc:
            db.session.rollback()
            return DatabaseStatus(
                connected=False,
                dialect=getattr(db.engine.dialect, "name", "unknown"),
                checked_at=checked_at,
                table_count=0,
                database_url=masked_database_url(str(db.engine.url)),
                missing_tables=[],
                error=str(exc),
            )
