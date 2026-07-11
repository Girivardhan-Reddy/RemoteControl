-- Supabase schema repair for Remote Control.
-- Run this in the Supabase SQL editor when Alembic reports that tables,
-- indexes, columns, or enum types already exist.

DO $$
BEGIN
    CREATE TYPE userrole AS ENUM ('USER', 'ADMIN');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE devicestatus AS ENUM ('OFFLINE', 'ONLINE', 'CONNECTING');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE sessionstatus AS ENUM ('ACTIVE', 'ENDED', 'FAILED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE loglevel AS ENUM ('INFO', 'WARNING', 'ERROR');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE loginattemptresult AS ENUM ('SUCCESS', 'FAILURE');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role userrole NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT ck_users_users_email_min_length CHECK (length(email) >= 5),
    CONSTRAINT ck_users_users_name_min_length CHECK (length(name) >= 1)
);

CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    platform VARCHAR(80) NOT NULL,
    device_fingerprint VARCHAR(128) NOT NULL UNIQUE,
    pairing_code_hash VARCHAR(255),
    is_paired BOOLEAN NOT NULL DEFAULT FALSE,
    os_version VARCHAR(120),
    capabilities JSONB,
    status devicestatus NOT NULL DEFAULT 'OFFLINE',
    agent_version VARCHAR(40),
    ip_address VARCHAR(64),
    socket_sid VARCHAR(120),
    last_heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_devices_devices_name_min_length CHECK (length(name) >= 1),
    CONSTRAINT ck_devices_devices_hostname_min_length CHECK (length(hostname) >= 1),
    CONSTRAINT ck_devices_devices_fingerprint_min_length CHECK (length(device_fingerprint) >= 16)
);

ALTER TABLE devices ADD COLUMN IF NOT EXISTS is_paired BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS os_version VARCHAR(120);
ALTER TABLE devices ADD COLUMN IF NOT EXISTS capabilities JSONB;

CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(36) NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    status sessionstatus NOT NULL DEFAULT 'ACTIVE',
    controller_sid VARCHAR(120),
    agent_sid VARCHAR(120),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    CONSTRAINT ck_sessions_sessions_end_after_start CHECK ((ended_at IS NULL) OR (ended_at >= started_at))
);

CREATE TABLE IF NOT EXISTS logs (
    id VARCHAR(36) PRIMARY KEY,
    level loglevel NOT NULL DEFAULT 'INFO',
    event VARCHAR(120) NOT NULL,
    message VARCHAR(500) NOT NULL,
    user_id VARCHAR(36),
    device_id VARCHAR(36),
    ip_address VARCHAR(64),
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revoked_tokens (
    id VARCHAR(36) PRIMARY KEY,
    jti VARCHAR(120) NOT NULL UNIQUE,
    token_type VARCHAR(20) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    ip_address VARCHAR(64),
    user_agent VARCHAR(255),
    result loginattemptresult NOT NULL,
    reason VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_role_active ON users(role, is_active);
CREATE INDEX IF NOT EXISTS ix_devices_device_fingerprint ON devices(device_fingerprint);
CREATE INDEX IF NOT EXISTS ix_devices_heartbeat ON devices(last_heartbeat_at);
CREATE INDEX IF NOT EXISTS ix_devices_owner_id ON devices(owner_id);
CREATE INDEX IF NOT EXISTS ix_devices_owner_status ON devices(owner_id, status);
CREATE INDEX IF NOT EXISTS ix_devices_socket_sid ON devices(socket_sid);
CREATE INDEX IF NOT EXISTS ix_sessions_agent_sid ON sessions(agent_sid);
CREATE INDEX IF NOT EXISTS ix_sessions_controller_sid ON sessions(controller_sid);
CREATE INDEX IF NOT EXISTS ix_sessions_device_id ON sessions(device_id);
CREATE INDEX IF NOT EXISTS ix_sessions_device_status ON sessions(device_id, status);
CREATE INDEX IF NOT EXISTS ix_sessions_started_at ON sessions(started_at);
CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_sessions_user_status ON sessions(user_id, status);
CREATE INDEX IF NOT EXISTS ix_logs_device_created ON logs(device_id, created_at);
CREATE INDEX IF NOT EXISTS ix_logs_device_id ON logs(device_id);
CREATE INDEX IF NOT EXISTS ix_logs_event ON logs(event);
CREATE INDEX IF NOT EXISTS ix_logs_event_created ON logs(event, created_at);
CREATE INDEX IF NOT EXISTS ix_logs_user_created ON logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_logs_user_id ON logs(user_id);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_jti ON revoked_tokens(jti);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_user_id ON revoked_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_user_revoked ON revoked_tokens(user_id, revoked_at);
CREATE INDEX IF NOT EXISTS ix_login_attempts_email ON login_attempts(email);
CREATE INDEX IF NOT EXISTS ix_login_attempts_email_created ON login_attempts(email, created_at);
CREATE INDEX IF NOT EXISTS ix_login_attempts_ip_address ON login_attempts(ip_address);
CREATE INDEX IF NOT EXISTS ix_login_attempts_ip_created ON login_attempts(ip_address, created_at);
CREATE INDEX IF NOT EXISTS ix_login_attempts_result_created ON login_attempts(result, created_at);
CREATE INDEX IF NOT EXISTS ix_login_attempts_user_id ON login_attempts(user_id);

CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

INSERT INTO alembic_version (version_num)
VALUES ('0003_device_registration')
ON CONFLICT (version_num) DO NOTHING;
