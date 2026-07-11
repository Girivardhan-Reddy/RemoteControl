"""Remote session business logic."""

from __future__ import annotations

from datetime import datetime, timezone

from extensions import db
from models import Device, DeviceStatus, RemoteSession, SessionStatus
from services.device_service import DeviceService
from utils.middleware import write_audit_log
from utils.validators import ValidationError


class ConnectionService:
    """Create and close controller-to-agent sessions."""

    @staticmethod
    def create_session(user_id: str, device_id: str, controller_sid: str | None = None) -> dict:
        """Start a remote session for an online owned device."""
        device = DeviceService.get_owned_device(user_id, device_id)
        if not device.is_paired:
            raise ValidationError("Device must be paired before starting a remote session.")
        if device.status != DeviceStatus.ONLINE or not device.socket_sid:
            raise ValidationError("Device is not online.")

        session = RemoteSession(
            user_id=user_id,
            device_id=device.id,
            controller_sid=controller_sid,
            agent_sid=device.socket_sid,
            status=SessionStatus.ACTIVE,
        )
        db.session.add(session)
        db.session.commit()
        write_audit_log("session.started", "Remote session started.", user_id=user_id, device_id=device.id)
        return session.to_dict()

    @staticmethod
    def end_session(user_id: str, session_id: str) -> dict:
        """End an active remote session."""
        session = RemoteSession.query.filter_by(id=session_id, user_id=user_id).first()
        if not session:
            raise ValidationError("Session not found.")
        session.status = SessionStatus.ENDED
        session.ended_at = datetime.now(timezone.utc)
        db.session.commit()
        write_audit_log("session.ended", "Remote session ended.", user_id=user_id, device_id=session.device_id)
        return session.to_dict()

    @staticmethod
    def get_active_by_controller_sid(sid: str) -> RemoteSession | None:
        """Find an active session by controller Socket.IO sid."""
        return RemoteSession.query.filter_by(controller_sid=sid, status=SessionStatus.ACTIVE).first()

    @staticmethod
    def get_active_by_agent_sid(sid: str) -> list[RemoteSession]:
        """Find active sessions attached to an agent Socket.IO sid."""
        return RemoteSession.query.filter_by(agent_sid=sid, status=SessionStatus.ACTIVE).all()

    @staticmethod
    def attach_controller(session_id: str, user_id: str, controller_sid: str) -> RemoteSession:
        """Attach a controller Socket.IO sid to an existing session."""
        session = RemoteSession.query.filter_by(id=session_id, user_id=user_id, status=SessionStatus.ACTIVE).first()
        if not session:
            raise ValidationError("Active session not found.")
        device = Device.query.get(session.device_id)
        if not device or not device.socket_sid:
            raise ValidationError("Device is not connected.")
        if not device.is_paired:
            raise ValidationError("Device must be paired before a controller can join.")
        session.controller_sid = controller_sid
        session.agent_sid = device.socket_sid
        db.session.commit()
        return session
