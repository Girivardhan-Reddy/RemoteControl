"""System and health routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from database import check_database_health

system_bp = Blueprint("system", __name__)


@system_bp.get("/health")
def health():
    """Service health check."""
    return jsonify({"status": "ok", "service": "remote-control-backend"}), 200


@system_bp.get("/health/database")
def database_health():
    """Database health check with masked connection details."""
    status = check_database_health(current_app).to_dict()
    http_status = 200 if status["connected"] else 503
    return jsonify(status), http_status
