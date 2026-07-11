"""Request middleware and API error handlers."""

from __future__ import annotations

from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from extensions import db
from models import AuditLog, LogLevel, UserRole
from utils.validators import ValidationError


def register_error_handlers(app) -> None:
    """Attach JSON error handlers to the Flask app."""

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({"error": error.description}), error.code

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        db.session.rollback()
        app.logger.exception("Database error: %s", error)
        return jsonify({"error": "A database error occurred."}), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled error: %s", error)
        return jsonify({"error": "An unexpected error occurred."}), 500


def role_required(*roles: UserRole):
    """Require a JWT with one of the supplied roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") not in {role.value for role in roles}:
                return jsonify({"error": "Insufficient permissions."}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def write_audit_log(event: str, message: str, *, level: LogLevel = LogLevel.INFO, **metadata) -> None:
    """Persist an audit log without leaking exceptions to request handlers."""
    try:
        entry = AuditLog(
            event=event,
            message=message,
            level=level,
            user_id=metadata.pop("user_id", None),
            device_id=metadata.pop("device_id", None),
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr) if request else None,
            metadata_json=metadata or None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
