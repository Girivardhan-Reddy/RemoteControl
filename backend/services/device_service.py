"""Device registration and heartbeat business logic."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from flask import current_app

from extensions import bcrypt, db
from models import Device, DeviceStatus
from utils.middleware import write_audit_log
from utils.validators import ValidationError, optional_string, require_string, validate_safe_name


class DeviceService:
    """Manage user-owned devices."""

    @staticmethod
    def list_devices(user_id: str) -> list[dict]:
        """Return all devices owned by a user."""
        DeviceService.mark_stale_devices_offline()
        return [device.to_dict() for device in Device.query.filter_by(owner_id=user_id).order_by(Device.name).all()]

    @staticmethod
    def register_device(user_id: str, data: dict, ip_address: str | None = None) -> dict:
        """Register or update a device for a user."""
        name = validate_safe_name(require_string(data, "name", max_len=120), "name")
        hostname = require_string(data, "hostname", max_len=255)
        platform = require_string(data, "platform", max_len=80)
        fingerprint = require_string(data, "device_fingerprint", min_len=16, max_len=128)
        agent_version = optional_string(data, "agent_version", max_len=40)
        os_version = optional_string(data, "os_version", max_len=120)
        capabilities = data.get("capabilities") if isinstance(data.get("capabilities"), dict) else {}

        device = Device.query.filter_by(device_fingerprint=fingerprint).first()
        if device and device.owner_id != user_id:
            raise ValidationError("Device is already registered to another account.")
        if not device:
            device = Device(owner_id=user_id, device_fingerprint=fingerprint)
            db.session.add(device)

        device.name = name
        device.hostname = hostname
        device.platform = platform
        device.agent_version = agent_version
        device.os_version = os_version
        device.capabilities = capabilities
        device.ip_address = ip_address
        device.status = DeviceStatus.ONLINE
        device.last_heartbeat_at = datetime.now(timezone.utc)
        pairing_code = secrets.token_urlsafe(18)
        device.pairing_code_hash = bcrypt.generate_password_hash(pairing_code).decode("utf-8")
        db.session.commit()

        write_audit_log("device.registered", "Device registered.", user_id=user_id, device_id=device.id)
        response = device.to_dict()
        response["pairing_code"] = pairing_code
        return response

    @staticmethod
    def update_device(user_id: str, device_id: str, data: dict) -> dict:
        """Update user-editable device metadata."""
        device = DeviceService.get_owned_device(user_id, device_id)
        if "name" in data:
            device.name = validate_safe_name(require_string(data, "name", max_len=120), "name")
        if "capabilities" in data:
            if not isinstance(data["capabilities"], dict):
                raise ValidationError("capabilities must be an object.")
            device.capabilities = data["capabilities"]
        db.session.commit()
        write_audit_log("device.updated", "Device updated.", user_id=user_id, device_id=device.id)
        return device.to_dict()

    @staticmethod
    def delete_device(user_id: str, device_id: str) -> dict:
        """Delete a registered device."""
        device = DeviceService.get_owned_device(user_id, device_id)
        db.session.delete(device)
        db.session.commit()
        write_audit_log("device.deleted", "Device deleted.", user_id=user_id, device_id=device_id)
        return {"message": "Device deleted."}

    @staticmethod
    def get_owned_device(user_id: str, device_id: str) -> Device:
        """Return a device owned by the user or raise a validation error."""
        device = Device.query.filter_by(id=device_id, owner_id=user_id).first()
        if not device:
            raise ValidationError("Device not found.")
        return device

    @staticmethod
    def heartbeat(user_id: str, device_id: str, ip_address: str | None = None) -> dict:
        """Mark a device online and refresh heartbeat time."""
        device = DeviceService.get_owned_device(user_id, device_id)
        device.status = DeviceStatus.ONLINE
        device.ip_address = ip_address
        device.last_heartbeat_at = datetime.now(timezone.utc)
        db.session.commit()
        return device.to_dict()

    @staticmethod
    def pair_device(user_id: str, device_id: str, pairing_code: str) -> dict:
        """Verify a device pairing code and return the paired device."""
        device = DeviceService.get_owned_device(user_id, device_id)
        if not device.pairing_code_hash:
            raise ValidationError("Device does not have an active pairing code.")
        if not bcrypt.check_password_hash(device.pairing_code_hash, pairing_code):
            raise ValidationError("Invalid pairing code.")
        device.pairing_code_hash = None
        device.is_paired = True
        db.session.commit()
        write_audit_log("device.paired", "Device pairing completed.", user_id=user_id, device_id=device.id)
        return device.to_dict()

    @staticmethod
    def regenerate_pairing_code(user_id: str, device_id: str) -> dict:
        """Create a new pairing code for an owned device."""
        device = DeviceService.get_owned_device(user_id, device_id)
        pairing_code = secrets.token_urlsafe(18)
        device.pairing_code_hash = bcrypt.generate_password_hash(pairing_code).decode("utf-8")
        device.is_paired = False
        db.session.commit()
        write_audit_log("device.pairing_regenerated", "Pairing code regenerated.", user_id=user_id, device_id=device.id)
        response = device.to_dict()
        response["pairing_code"] = pairing_code
        return response

    @staticmethod
    def set_socket(device_id: str, sid: str | None) -> None:
        """Associate a device with a Socket.IO session id."""
        device = Device.query.get(device_id)
        if not device:
            return
        device.socket_sid = sid
        device.status = DeviceStatus.ONLINE if sid else DeviceStatus.OFFLINE
        device.last_heartbeat_at = datetime.now(timezone.utc) if sid else device.last_heartbeat_at
        db.session.commit()

    @staticmethod
    def mark_stale_devices_offline() -> None:
        """Mark devices offline when their heartbeat is stale."""
        timeout = current_app.config["DEVICE_HEARTBEAT_TIMEOUT_SECONDS"]
        now = datetime.now(timezone.utc)
        devices = Device.query.filter(Device.status != DeviceStatus.OFFLINE).all()
        changed = False
        for device in devices:
            if device.last_heartbeat_at and (now - device.last_heartbeat_at).total_seconds() > timeout:
                device.status = DeviceStatus.OFFLINE
                device.socket_sid = None
                changed = True
        if changed:
            db.session.commit()
