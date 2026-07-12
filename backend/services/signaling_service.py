"""Runtime signaling state for Socket.IO/WebRTC sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from flask_socketio import close_room, join_room, leave_room

from extensions import db
from models import Device, DeviceStatus, RemoteSession, SessionStatus


class SignalingError(RuntimeError):
    """Raised when a socket signaling request is invalid or unauthorized."""


class SignalingService:
    """Coordinate active agents, controllers, and WebRTC signaling routes."""

    _lock = RLock()
    _devices: dict[str, dict[str, Any]] = {}
    _sid_to_device: dict[str, str] = {}
    _controller_sessions: dict[str, dict[str, str]] = {}

    @staticmethod
    def user_room(user_id: str) -> str:
        return f"user:{user_id}"

    @classmethod
    def register_agent(cls, *, user_id: str, device_id: str | None, sid: str, ip_address: str | None = None) -> dict:
        device = cls._owned_device(user_id, device_id)
        with cls._lock:
            previous_sid = (cls._devices.get(device.id) or {}).get("agent_sid")
            if previous_sid and previous_sid != sid:
                cls._sid_to_device.pop(previous_sid, None)
            cls._devices.setdefault(device.id, {"controllers": {}})
            cls._devices[device.id]["agent_sid"] = sid
            cls._devices[device.id]["user_id"] = user_id
            cls._sid_to_device[sid] = device.id

        device.socket_sid = sid
        device.status = DeviceStatus.ONLINE
        device.ip_address = ip_address
        device.last_heartbeat_at = datetime.now(timezone.utc)
        db.session.commit()
        join_room(cls.user_room(user_id), sid=sid)
        join_room(cls.device_room(device.id), sid=sid)
        return {"status": "success", "device_id": device.id, "device": device.to_dict()}

    @classmethod
    def register_controller(cls, *, user_id: str, device_id: str | None, sid: str) -> dict:
        device = cls._owned_device(user_id, device_id)
        with cls._lock:
            state = cls._devices.get(device.id)
            agent_sid = state.get("agent_sid") if state else device.socket_sid
            if not agent_sid:
                raise SignalingError("Device agent is offline.")
            session_id = str(uuid.uuid4())
            state = cls._devices.setdefault(device.id, {"controllers": {}})
            state.setdefault("controllers", {})[sid] = session_id
            state["user_id"] = user_id
            cls._controller_sessions[sid] = {"device_id": device.id, "session_id": session_id, "agent_sid": agent_sid}

        db.session.add(
            RemoteSession(
                id=session_id,
                user_id=user_id,
                device_id=device.id,
                controller_sid=sid,
                agent_sid=agent_sid,
                status=SessionStatus.ACTIVE,
            )
        )
        db.session.commit()
        join_room(cls.user_room(user_id), sid=sid)
        join_room(cls.device_room(device.id), sid=sid)
        return {"status": "success", "device_id": device.id, "session_id": session_id, "agent_sid": agent_sid}

    @classmethod
    def agent_heartbeat(cls, user_id: str, device_id: str | None, sid: str) -> dict:
        device = cls._owned_device(user_id, device_id)
        if cls._devices.get(device.id, {}).get("agent_sid") != sid:
            cls.register_agent(user_id=user_id, device_id=device.id, sid=sid)
        device.status = DeviceStatus.ONLINE
        device.socket_sid = sid
        device.last_heartbeat_at = datetime.now(timezone.utc)
        db.session.commit()
        return device.to_dict()

    @classmethod
    def assert_controller(cls, user_id: str, device_id: str | None, sid: str) -> str:
        device = cls._owned_device(user_id, device_id)
        with cls._lock:
            session = cls._controller_sessions.get(sid)
            agent_sid = cls._devices.get(device.id, {}).get("agent_sid")
        if not session or session.get("device_id") != device.id:
            raise SignalingError("Controller has not joined this device.")
        if not agent_sid:
            raise SignalingError("Device agent is offline.")
        return agent_sid

    @classmethod
    def assert_agent(cls, user_id: str, device_id: str | None, sid: str, controller_sid: str | None = None) -> None:
        device = cls._owned_device(user_id, device_id)
        with cls._lock:
            state = cls._devices.get(device.id) or {}
            if state.get("agent_sid") != sid:
                raise SignalingError("Socket is not the active agent for this device.")
            if controller_sid and controller_sid not in state.get("controllers", {}):
                raise SignalingError("Controller is not attached to this device.")

    @classmethod
    def resolve_ice_target(cls, *, user_id: str, device_id: str | None, sender_sid: str, target_sid: str | None) -> str:
        device = cls._owned_device(user_id, device_id)
        with cls._lock:
            state = cls._devices.get(device.id) or {}
            agent_sid = state.get("agent_sid")
            controllers = state.get("controllers", {})
        if sender_sid == agent_sid:
            if not target_sid or target_sid not in controllers:
                raise SignalingError("Invalid controller ICE target.")
            return target_sid
        if sender_sid in controllers:
            return agent_sid
        raise SignalingError("Socket is not part of this signaling session.")

    @classmethod
    def session_id_for_controller(cls, controller_sid: str) -> str | None:
        return (cls._controller_sessions.get(controller_sid) or {}).get("session_id")

    @classmethod
    def controller_for_session(cls, session_id: str | None) -> str | None:
        if not session_id:
            return None
        with cls._lock:
            for controller_sid, session in cls._controller_sessions.items():
                if session.get("session_id") == session_id:
                    return controller_sid
        return None

    @classmethod
    def disconnect(cls, sid: str) -> list[dict]:
        events: list[dict] = []
        now = datetime.now(timezone.utc)
        with cls._lock:
            device_id = cls._sid_to_device.pop(sid, None)
            if device_id:
                state = cls._devices.pop(device_id, {"controllers": {}})
                for controller_sid, session_id in state.get("controllers", {}).items():
                    cls._controller_sessions.pop(controller_sid, None)
                    events.append({"name": "agent_disconnected", "room": controller_sid, "payload": {"device_id": device_id, "session_id": session_id}})
                device = Device.query.get(device_id)
                if device:
                    device.status = DeviceStatus.OFFLINE
                    device.socket_sid = None
                RemoteSession.query.filter_by(device_id=device_id, status=SessionStatus.ACTIVE).update({"status": SessionStatus.ENDED, "ended_at": now})
                db.session.commit()
                close_room(cls.device_room(device_id))
                return events

            session = cls._controller_sessions.pop(sid, None)
            if session:
                device_id = session["device_id"]
                state = cls._devices.get(device_id) or {}
                state.get("controllers", {}).pop(sid, None)
                RemoteSession.query.filter_by(id=session["session_id"]).update({"status": SessionStatus.ENDED, "ended_at": now})
                db.session.commit()
                leave_room(cls.device_room(device_id), sid=sid)
                events.append({"name": "controller_disconnected", "room": session["agent_sid"], "payload": {"device_id": device_id, "session_id": session["session_id"], "controller_sid": sid}})
        return events

    @staticmethod
    def device_room(device_id: str) -> str:
        return f"device:{device_id}"

    @staticmethod
    def _owned_device(user_id: str, device_id: str | None) -> Device:
        if not device_id:
            raise SignalingError("device_id is required.")
        device = Device.query.filter_by(id=device_id, owner_id=user_id).first()
        if not device:
            raise SignalingError("Device not found or unauthorized.")
        return device
