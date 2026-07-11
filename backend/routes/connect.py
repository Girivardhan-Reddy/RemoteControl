"""Remote connection REST API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.connection_service import ConnectionService
from utils.validators import require_json, require_string

connect_bp = Blueprint("connect", __name__)


@connect_bp.post("/sessions")
@jwt_required()
def create_session():
    """Create a remote session for a device."""
    data = require_json(request.get_json(silent=True))
    device_id = require_string(data, "device_id", min_len=36, max_len=36)
    return jsonify(ConnectionService.create_session(get_jwt_identity(), device_id)), 201


@connect_bp.delete("/sessions/<session_id>")
@jwt_required()
def end_session(session_id: str):
    """End a remote session."""
    return jsonify(ConnectionService.end_session(get_jwt_identity(), session_id)), 200
