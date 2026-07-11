"""Authenticated Socket.IO event handlers for agents and controllers."""

from __future__ import annotations

from flask import current_app, request
from flask_jwt_extended import decode_token
from flask_socketio import disconnect, emit, join_room, leave_room

from extensions import db, socketio
from models import Device, RemoteSession, RevokedToken, SessionStatus
from services.connection_service import ConnectionService
from services.device_service import DeviceService


def _identity_from_token(token: str | None) -> str | None:
    """Decode a JWT and return its subject."""
    if not token:
        return None
    try:
        claims = decode_token(token)
        if RevokedToken.query.filter_by(jti=claims["jti"]).first():
            return None
        return claims.get("sub")
    except Exception as exc:
        current_app.logger.warning("Socket authentication failed: %s", exc)
        return None


def register_socket_events() -> None:
    """Register Socket.IO event callbacks."""

    @socketio.on("agent_connect")
    def agent_connect(data):
        """Authenticate a desktop agent and mark the device online."""
        user_id = _identity_from_token((data or {}).get("token"))
        device_id = (data or {}).get("device_id")
        if not user_id or not device_id:
            disconnect()
            return
        device = Device.query.filter_by(id=device_id, owner_id=user_id).first()
        if not device or not device.is_paired:
            disconnect()
            return
        DeviceService.set_socket(device_id, request.sid)
        join_room(f"device:{device_id}")
        emit("agent_connected", {"device": device.to_dict()})

    @socketio.on("controller_join")
    def controller_join(data):
        """Attach a controller to an active session."""
        user_id = _identity_from_token((data or {}).get("token"))
        session_id = (data or {}).get("session_id")
        if not user_id or not session_id:
            disconnect()
            return
        try:
            session = ConnectionService.attach_controller(session_id, user_id, request.sid)
            join_room(f"session:{session.id}")
            emit("controller_joined", {"session": session.to_dict()})
            if session.agent_sid:
                socketio.emit("controller_ready", {"session_id": session.id}, to=session.agent_sid)
        except Exception as exc:
            current_app.logger.warning("Controller join rejected: %s", exc)
            emit("error", {"error": str(exc)})
            disconnect()

    @socketio.on("agent_heartbeat")
    def agent_heartbeat(data):
        """Process an agent heartbeat."""
        device_id = (data or {}).get("device_id")
        device = Device.query.filter_by(id=device_id, socket_sid=request.sid).first()
        if not device:
            disconnect()
            return
        DeviceService.set_socket(device.id, request.sid)
        emit("heartbeat_ack", {"device_id": device.id})

    @socketio.on("remote_command")
    def remote_command(data):
        """Relay a controller command to the session's agent."""
        session = ConnectionService.get_active_by_controller_sid(request.sid)
        if not session or not session.agent_sid:
            emit("error", {"error": "No active session."})
            return
        payload = data or {}
        payload["session_id"] = session.id
        socketio.emit("remote_command", payload, to=session.agent_sid)

    @socketio.on("agent_frame")
    def agent_frame(data):
        """Relay a screen frame from agent to controller."""
        payload = data or {}
        session_id = payload.get("session_id")
        sessions = ConnectionService.get_active_by_agent_sid(request.sid)
        for session in sessions:
            if session_id and session.id != session_id:
                continue
            if session.controller_sid:
                socketio.emit("agent_frame", payload, to=session.controller_sid)

    @socketio.on("agent_event")
    def agent_event(data):
        """Relay agent events and command responses to controllers."""
        payload = data or {}
        session_id = payload.get("session_id")
        for session in ConnectionService.get_active_by_agent_sid(request.sid):
            if session_id and session.id != session_id:
                continue
            if session.controller_sid:
                socketio.emit("agent_event", payload, to=session.controller_sid)

    @socketio.on("disconnect")
    def on_disconnect():
        """Clean up device and session state when sockets disconnect."""
        device = Device.query.filter_by(socket_sid=request.sid).first()
        if device:
            DeviceService.set_socket(device.id, None)
            leave_room(f"device:{device.id}")

        sessions = RemoteSession.query.filter(
            ((RemoteSession.controller_sid == request.sid) | (RemoteSession.agent_sid == request.sid)),
            RemoteSession.status == SessionStatus.ACTIVE,
        ).all()
        for session in sessions:
            session.status = SessionStatus.ENDED
            if session.controller_sid == request.sid:
                session.controller_sid = None
            if session.agent_sid == request.sid:
                session.agent_sid = None
        if sessions:
            db.session.commit()
