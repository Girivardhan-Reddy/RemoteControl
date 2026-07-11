"""Database initialization and operational helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from flask import Flask
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, migrate


@dataclass(frozen=True)
class DatabaseStatus:
    """Database health information suitable for logs and admin tooling."""

    connected: bool
    dialect: str
    checked_at: str
    table_count: int
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
            )
        except SQLAlchemyError as exc:
            db.session.rollback()
            return DatabaseStatus(
                connected=False,
                dialect=getattr(db.engine.dialect, "name", "unknown"),
                checked_at=checked_at,
                table_count=0,
                error=str(exc),
            )
