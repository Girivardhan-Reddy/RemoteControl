"""SQLAlchemy models for users, devices, sessions, and audit logs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from extensions import db

try:
    StrEnum = enum.StrEnum
except AttributeError:
    class StrEnum(str, enum.Enum):
        """Python 3.10-compatible StrEnum fallback."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class UserRole(StrEnum):
    """Supported authorization roles."""

    USER = "user"
    ADMIN = "admin"


class DeviceStatus(StrEnum):
    """Device online state."""

    OFFLINE = "offline"
    ONLINE = "online"
    CONNECTING = "connecting"


class SessionStatus(StrEnum):
    """Remote session lifecycle state."""

    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"


class LogLevel(StrEnum):
    """Persisted audit log severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LoginAttemptResult(StrEnum):
    """Result of an authentication attempt."""

    SUCCESS = "success"
    FAILURE = "failure"


class User(db.Model):
    """Application user."""

    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("length(email) >= 5", name="users_email_min_length"),
        db.CheckConstraint("length(name) >= 1", name="users_name_min_length"),
        db.Index("ix_users_role_active", "role", "is_active"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.USER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    devices = db.relationship("Device", back_populates="owner", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Serialize safe user fields."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class LoginAttempt(db.Model):
    """Authentication attempt record for security audit and throttling analysis."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        db.Index("ix_login_attempts_email_created", "email", "created_at"),
        db.Index("ix_login_attempts_ip_created", "ip_address", "created_at"),
        db.Index("ix_login_attempts_result_created", "result", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = db.Column(db.String(64), nullable=True, index=True)
    user_agent = db.Column(db.String(255), nullable=True)
    result = db.Column(db.Enum(LoginAttemptResult), nullable=False)
    reason = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User")


class Device(db.Model):
    """Computer registered by a user."""

    __tablename__ = "devices"
    __table_args__ = (
        db.CheckConstraint("length(name) >= 1", name="devices_name_min_length"),
        db.CheckConstraint("length(hostname) >= 1", name="devices_hostname_min_length"),
        db.CheckConstraint("length(device_fingerprint) >= 16", name="devices_fingerprint_min_length"),
        db.Index("ix_devices_owner_status", "owner_id", "status"),
        db.Index("ix_devices_heartbeat", "last_heartbeat_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    hostname = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(80), nullable=False)
    device_fingerprint = db.Column(db.String(128), nullable=False, unique=True, index=True)
    pairing_code_hash = db.Column(db.String(255), nullable=True)
    is_paired = db.Column(db.Boolean, nullable=False, default=False)
    os_version = db.Column(db.String(120), nullable=True)
    capabilities = db.Column(db.JSON, nullable=True)
    status = db.Column(db.Enum(DeviceStatus), nullable=False, default=DeviceStatus.OFFLINE)
    agent_version = db.Column(db.String(40), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    socket_sid = db.Column(db.String(120), nullable=True, index=True)
    last_heartbeat_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    owner = db.relationship("User", back_populates="devices")
    sessions = db.relationship("RemoteSession", back_populates="device", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Serialize device fields safe for API responses."""
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "name": self.name,
            "hostname": self.hostname,
            "platform": self.platform,
            "status": self.status.value,
            "is_paired": self.is_paired,
            "agent_version": self.agent_version,
            "os_version": self.os_version,
            "capabilities": self.capabilities or {},
            "ip_address": self.ip_address,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RemoteSession(db.Model):
    """A controller-to-device remote connection session."""

    __tablename__ = "sessions"
    __table_args__ = (
        db.CheckConstraint(
            "(ended_at IS NULL) OR (ended_at >= started_at)",
            name="sessions_end_after_start",
        ),
        db.Index("ix_sessions_user_status", "user_id", "status"),
        db.Index("ix_sessions_device_status", "device_id", "status"),
        db.Index("ix_sessions_started_at", "started_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.Enum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    controller_sid = db.Column(db.String(120), nullable=True, index=True)
    agent_sid = db.Column(db.String(120), nullable=True, index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User")
    device = db.relationship("Device", back_populates="sessions")

    def to_dict(self) -> dict:
        """Serialize session fields."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class AuditLog(db.Model):
    """Persisted security and operational event."""

    __tablename__ = "logs"
    __table_args__ = (
        db.Index("ix_logs_event_created", "event", "created_at"),
        db.Index("ix_logs_user_created", "user_id", "created_at"),
        db.Index("ix_logs_device_created", "device_id", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    level = db.Column(db.Enum(LogLevel), nullable=False, default=LogLevel.INFO)
    event = db.Column(db.String(120), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.String(36), nullable=True, index=True)
    device_id = db.Column(db.String(36), nullable=True, index=True)
    ip_address = db.Column(db.String(64), nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def to_dict(self) -> dict:
        """Serialize audit log fields."""
        return {
            "id": self.id,
            "level": self.level.value,
            "event": self.event,
            "message": self.message,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RevokedToken(db.Model):
    """JWT denylist entry used for logout and token revocation."""

    __tablename__ = "revoked_tokens"
    __table_args__ = (
        db.Index("ix_revoked_tokens_user_revoked", "user_id", "revoked_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jti = db.Column(db.String(120), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
