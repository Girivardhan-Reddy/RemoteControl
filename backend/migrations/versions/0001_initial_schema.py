"""Initial database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

user_role = sa.Enum("USER", "ADMIN", name="userrole")
device_status = sa.Enum("OFFLINE", "ONLINE", "CONNECTING", name="devicestatus")
session_status = sa.Enum("ACTIVE", "ENDED", "FAILED", name="sessionstatus")
log_level = sa.Enum("INFO", "WARNING", "ERROR", name="loglevel")


def upgrade() -> None:
    """Create the initial production schema."""
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    device_status.create(bind, checkfirst=True)
    session_status.create(bind, checkfirst=True)
    log_level.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(email) >= 5", name="ck_users_users_email_min_length"),
        sa.CheckConstraint("length(name) >= 1", name="ck_users_users_name_min_length"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role_active", "users", ["role", "is_active"])

    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("pairing_code_hash", sa.String(length=255), nullable=True),
        sa.Column("status", device_status, nullable=False),
        sa.Column("agent_version", sa.String(length=40), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("socket_sid", sa.String(length=120), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(device_fingerprint) >= 16", name="ck_devices_devices_fingerprint_min_length"),
        sa.CheckConstraint("length(hostname) >= 1", name="ck_devices_devices_hostname_min_length"),
        sa.CheckConstraint("length(name) >= 1", name="ck_devices_devices_name_min_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_devices_owner_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        sa.UniqueConstraint("device_fingerprint", name="uq_devices_device_fingerprint"),
    )
    op.create_index("ix_devices_device_fingerprint", "devices", ["device_fingerprint"])
    op.create_index("ix_devices_heartbeat", "devices", ["last_heartbeat_at"])
    op.create_index("ix_devices_owner_id", "devices", ["owner_id"])
    op.create_index("ix_devices_owner_status", "devices", ["owner_id", "status"])
    op.create_index("ix_devices_socket_sid", "devices", ["socket_sid"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("status", session_status, nullable=False),
        sa.Column("controller_sid", sa.String(length=120), nullable=True),
        sa.Column("agent_sid", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(ended_at IS NULL) OR (ended_at >= started_at)", name="ck_sessions_sessions_end_after_start"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="fk_sessions_device_id_devices", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
    )
    op.create_index("ix_sessions_agent_sid", "sessions", ["agent_sid"])
    op.create_index("ix_sessions_controller_sid", "sessions", ["controller_sid"])
    op.create_index("ix_sessions_device_id", "sessions", ["device_id"])
    op.create_index("ix_sessions_device_status", "sessions", ["device_id", "status"])
    op.create_index("ix_sessions_started_at", "sessions", ["started_at"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_user_status", "sessions", ["user_id", "status"])

    op.create_table(
        "logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("level", log_level, nullable=False),
        sa.Column("event", sa.String(length=120), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_logs"),
    )
    op.create_index("ix_logs_device_created", "logs", ["device_id", "created_at"])
    op.create_index("ix_logs_device_id", "logs", ["device_id"])
    op.create_index("ix_logs_event", "logs", ["event"])
    op.create_index("ix_logs_event_created", "logs", ["event", "created_at"])
    op.create_index("ix_logs_user_created", "logs", ["user_id", "created_at"])
    op.create_index("ix_logs_user_id", "logs", ["user_id"])

    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("jti", sa.String(length=120), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_revoked_tokens"),
        sa.UniqueConstraint("jti", name="uq_revoked_tokens_jti"),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"])
    op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])
    op.create_index("ix_revoked_tokens_user_revoked", "revoked_tokens", ["user_id", "revoked_at"])


def downgrade() -> None:
    """Drop the initial production schema."""
    op.drop_index("ix_revoked_tokens_user_revoked", table_name="revoked_tokens")
    op.drop_index("ix_revoked_tokens_user_id", table_name="revoked_tokens")
    op.drop_index("ix_revoked_tokens_jti", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")

    op.drop_index("ix_logs_user_id", table_name="logs")
    op.drop_index("ix_logs_user_created", table_name="logs")
    op.drop_index("ix_logs_event_created", table_name="logs")
    op.drop_index("ix_logs_event", table_name="logs")
    op.drop_index("ix_logs_device_id", table_name="logs")
    op.drop_index("ix_logs_device_created", table_name="logs")
    op.drop_table("logs")

    op.drop_index("ix_sessions_user_status", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_started_at", table_name="sessions")
    op.drop_index("ix_sessions_device_status", table_name="sessions")
    op.drop_index("ix_sessions_device_id", table_name="sessions")
    op.drop_index("ix_sessions_controller_sid", table_name="sessions")
    op.drop_index("ix_sessions_agent_sid", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_devices_socket_sid", table_name="devices")
    op.drop_index("ix_devices_owner_status", table_name="devices")
    op.drop_index("ix_devices_owner_id", table_name="devices")
    op.drop_index("ix_devices_heartbeat", table_name="devices")
    op.drop_index("ix_devices_device_fingerprint", table_name="devices")
    op.drop_table("devices")

    op.drop_index("ix_users_role_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    log_level.drop(bind, checkfirst=True)
    session_status.drop(bind, checkfirst=True)
    device_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
