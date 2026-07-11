"""System and health routes."""

from __future__ import annotations

from flask import Blueprint, jsonify

system_bp = Blueprint("system", __name__)


@system_bp.get("/health")
def health():
    """Service health check."""
    return jsonify({"status": "ok", "service": "remote-control-backend"}), 200
