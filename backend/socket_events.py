"""Socket.IO events for authenticated device signaling and control."""

from __future__ import annotations

from flask import current_app, request
from flask_jwt_extended import decode_token
from flask_socketio import emit

from extensions import socketio
from services.signaling_service import SignalingService, SignalingError


def _extract_token(data: dict | None = None) -> str | None:
    payload = data or {}
    token = payload.get("token") or payload.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.args.get("token")
    return token


def _authenticate(data: dict | None = None) -> str:
    token = _extract_token(data)
    if not token:
        raise SignalingError("Authentication required.")
    try:
        claims = decode_token(token)
    except Exception as exc:  # noqa: BLE001 - normalize auth failure for socket clients.
        current_app.logger.warning("Socket authentication failed: %s", exc)
        raise SignalingError("Invalid or expired token.") from exc
    user_id = claims.get("sub")
    if not user_id:
        raise SignalingError("Invalid token subject.")
    return str(user_id)


def _emit_error(message: str) -> None:
    emit("error", {"message": message})


def _handle_error(exc: Exception, fallback: str) -> None:
    if isinstance(exc, SignalingError):
        _emit_error(str(exc))
    else:
        current_app.logger.exception(fallback)
        _emit_error(fallback)


def register_socket_events() -> None:
    """Register Socket.IO handlers used by agents and Android controllers."""

    @socketio.on("connect")
    def on_connect(auth=None):
        try:
            _authenticate(auth if isinstance(auth, dict) else None)
            emit("socket_ready", {"sid": request.sid})
        except SignalingError as exc:
            current_app.logger.info("Rejecting unauthenticated socket: %s", exc)
            return False

    @socketio.on("agent_connect")
    def on_agent_connect(data):
        try:
            user_id = _authenticate(data)
            payload = SignalingService.register_agent(
                user_id=user_id,
                device_id=(data or {}).get("device_id"),
                sid=request.sid,
                ip_address=request.remote_addr,
            )
            emit("agent_connected", payload)
            socketio.emit("device_status", payload["device"], room=SignalingService.user_room(user_id))
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to register agent.")

    @socketio.on("controller_join")
    def on_controller_join(data):
        try:
            user_id = _authenticate(data)
            payload = SignalingService.register_controller(
                user_id=user_id,
                device_id=(data or {}).get("device_id"),
                sid=request.sid,
            )
            emit("join_accepted", payload)
            socketio.emit(
                "controller_connected",
                {
                    "session_id": payload["session_id"],
                    "controller_sid": request.sid,
                    "device_id": payload["device_id"],
                    "quality": (data or {}).get("quality", "medium"),
                },
                room=payload["agent_sid"],
            )
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to join remote session.")

    @socketio.on("agent_heartbeat")
    def on_agent_heartbeat(data):
        try:
            user_id = _authenticate(data)
            device = SignalingService.agent_heartbeat(user_id, (data or {}).get("device_id"), request.sid)
            emit("heartbeat_ack", {"device_id": device["id"], "status": device["status"]})
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Heartbeat failed.")

    @socketio.on("webrtc_offer")
    def on_webrtc_offer(data):
        try:
            user_id = _authenticate(data)
            target_sid = SignalingService.assert_controller(user_id, (data or {}).get("device_id"), request.sid)
            socketio.emit(
                "webrtc_offer",
                {
                    "device_id": data.get("device_id"),
                    "session_id": SignalingService.session_id_for_controller(request.sid),
                    "controller_sid": request.sid,
                    "offer": data.get("offer"),
                },
                room=target_sid,
            )
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to relay WebRTC offer.")

    @socketio.on("webrtc_answer")
    def on_webrtc_answer(data):
        try:
            user_id = _authenticate(data)
            controller_sid = (data or {}).get("controller_sid")
            SignalingService.assert_agent(user_id, (data or {}).get("device_id"), request.sid, controller_sid)
            socketio.emit(
                "webrtc_answer",
                {
                    "device_id": data.get("device_id"),
                    "agent_sid": request.sid,
                    "answer": data.get("answer"),
                },
                room=controller_sid,
            )
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to relay WebRTC answer.")

    @socketio.on("webrtc_ice_candidate")
    def on_webrtc_ice_candidate(data):
        try:
            user_id = _authenticate(data)
            target_sid = SignalingService.resolve_ice_target(
                user_id=user_id,
                device_id=(data or {}).get("device_id"),
                sender_sid=request.sid,
                target_sid=(data or {}).get("target_sid"),
            )
            socketio.emit(
                "webrtc_ice_candidate",
                {
                    "device_id": data.get("device_id"),
                    "from_sid": request.sid,
                    "candidate": data.get("candidate"),
                },
                room=target_sid,
            )
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to relay ICE candidate.")

    @socketio.on("remote_command")
    def on_remote_command(data):
        try:
            user_id = _authenticate(data)
            agent_sid = SignalingService.assert_controller(user_id, (data or {}).get("device_id"), request.sid)
            command = {
                "session_id": SignalingService.session_id_for_controller(request.sid),
                "controller_sid": request.sid,
                "type": (data or {}).get("type") or (data or {}).get("command"),
                **((data or {}).get("params") or {}),
            }
            for key, value in (data or {}).items():
                if key not in {"token", "access_token", "device_id", "params", "command"}:
                    command[key] = value
            socketio.emit("remote_command", command, room=agent_sid)
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to relay remote command.")

    @socketio.on("agent_event")
    def on_agent_event(data):
        try:
            user_id = _authenticate(data)
            controller_sid = (data or {}).get("controller_sid") or SignalingService.controller_for_session((data or {}).get("session_id"))
            SignalingService.assert_agent(user_id, (data or {}).get("device_id"), request.sid, controller_sid)
            socketio.emit("agent_event", data or {}, room=controller_sid)
        except Exception as exc:  # noqa: BLE001
            _handle_error(exc, "Failed to relay agent event.")

    @socketio.on("disconnect")
    def on_disconnect():
        status_events = SignalingService.disconnect(request.sid)
        for event in status_events:
            socketio.emit(event["name"], event["payload"], room=event["room"])


# Backward-compatible alias for older imports/tests.
def init_socket_events(_socketio=None) -> None:
    register_socket_events()
