"""Device REST API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.device_service import DeviceService
from utils.validators import require_json, require_string

devices_bp = Blueprint("devices", __name__)


@devices_bp.get("")
@jwt_required()
def list_devices():
    """List devices owned by the current user."""
    return jsonify({"devices": DeviceService.list_devices(get_jwt_identity())}), 200


@devices_bp.post("")
@jwt_required()
def register_device():
    """Register an agent device for the current user."""
    result = DeviceService.register_device(
        get_jwt_identity(),
        require_json(request.get_json(silent=True)),
        request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    return jsonify(result), 201


@devices_bp.get("/<device_id>")
@jwt_required()
def get_device(device_id: str):
    """Return a single owned device."""
    return jsonify(DeviceService.get_owned_device(get_jwt_identity(), device_id).to_dict()), 200


@devices_bp.patch("/<device_id>")
@jwt_required()
def update_device(device_id: str):
    """Update device metadata."""
    return jsonify(DeviceService.update_device(get_jwt_identity(), device_id, require_json(request.get_json(silent=True)))), 200


@devices_bp.delete("/<device_id>")
@jwt_required()
def delete_device(device_id: str):
    """Delete a device."""
    return jsonify(DeviceService.delete_device(get_jwt_identity(), device_id)), 200


@devices_bp.post("/<device_id>/heartbeat")
@jwt_required()
def heartbeat(device_id: str):
    """Refresh device online state."""
    result = DeviceService.heartbeat(
        get_jwt_identity(),
        device_id,
        request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    return jsonify(result), 200


@devices_bp.post("/<device_id>/pair")
@jwt_required()
def pair_device(device_id: str):
    """Verify and consume a device pairing code."""
    data = require_json(request.get_json(silent=True))
    pairing_code = data.get("pairing_code")
    if not isinstance(pairing_code, str):
        return jsonify({"error": "pairing_code is required."}), 400
    return jsonify(DeviceService.pair_device(get_jwt_identity(), device_id, pairing_code.strip())), 200


@devices_bp.post("/<device_id>/pairing-code")
@jwt_required()
def regenerate_pairing_code(device_id: str):
    """Regenerate a pairing code for a device."""
    return jsonify(DeviceService.regenerate_pairing_code(get_jwt_identity(), device_id)), 200
