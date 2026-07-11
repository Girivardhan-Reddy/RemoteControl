"""Authentication business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from extensions import bcrypt, db
from models import LoginAttempt, LoginAttemptResult, User, UserRole
from utils.jwt import build_token_pair, request_ip_address, revoke_jwt_claims
from utils.middleware import write_audit_log
from utils.validators import (
    ValidationError,
    require_string,
    validate_email,
    validate_password,
    validate_safe_name,
)


class AuthService:
    """User registration and login service."""

    @staticmethod
    def _record_login_attempt(
        *,
        email: str,
        result: LoginAttemptResult,
        user: User | None = None,
        reason: str | None = None,
        request_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store an authentication attempt for audit and abuse investigation."""
        metadata = request_metadata or {}
        attempt = LoginAttempt(
            email=email,
            user_id=user.id if user else None,
            ip_address=metadata.get("ip_address"),
            user_agent=metadata.get("user_agent"),
            result=result,
            reason=reason,
        )
        db.session.add(attempt)

    @staticmethod
    def register(data: dict) -> dict:
        """Create a new active user."""
        email = validate_email(require_string(data, "email", max_len=255))
        name = validate_safe_name(require_string(data, "name", max_len=120), "name")
        password = validate_password(require_string(data, "password", min_len=10, max_len=128))

        if User.query.filter_by(email=email).first():
            raise ValidationError("Email is already registered.")

        user = User(
            email=email,
            name=name,
            role=UserRole.USER,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        )
        db.session.add(user)
        db.session.commit()
        write_audit_log("user.registered", "User registered.", user_id=user.id)
        return {"user": user.to_dict(), **build_token_pair(user)}

    @staticmethod
    def login(data: dict, request_metadata: dict[str, Any] | None = None) -> dict:
        """Authenticate a user and issue tokens."""
        email = validate_email(require_string(data, "email", max_len=255))
        password = require_string(data, "password", min_len=1, max_len=128)
        metadata = request_metadata or {}

        user = User.query.filter_by(email=email).first()
        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            AuthService._record_login_attempt(
                email=email,
                user=user,
                result=LoginAttemptResult.FAILURE,
                reason="invalid_credentials",
                request_metadata=metadata,
            )
            db.session.commit()
            write_audit_log("user.login_failed", "Login failed.", user_id=user.id if user else None, email=email)
            raise ValidationError("Invalid email or password.")
        if not user.is_active:
            AuthService._record_login_attempt(
                email=email,
                user=user,
                result=LoginAttemptResult.FAILURE,
                reason="inactive_account",
                request_metadata=metadata,
            )
            db.session.commit()
            raise ValidationError("Account is disabled.")

        user.last_login_at = datetime.now(timezone.utc)
        AuthService._record_login_attempt(
            email=email,
            user=user,
            result=LoginAttemptResult.SUCCESS,
            request_metadata=metadata,
        )
        db.session.commit()
        write_audit_log("user.login", "User logged in.", user_id=user.id)
        return {"user": user.to_dict(), **build_token_pair(user)}

    @staticmethod
    def refresh(user_id: str) -> dict:
        """Issue a new token pair for a refresh token identity."""
        user = User.query.get(user_id)
        if not user or not user.is_active:
            raise ValidationError("Account is unavailable.")
        return {"user": user.to_dict(), **build_token_pair(user)}

    @staticmethod
    def get_active_user(user_id: str) -> User:
        """Return an active user or raise a validation error."""
        user = User.query.get(user_id)
        if not user or not user.is_active:
            raise ValidationError("Account is unavailable.")
        return user

    @staticmethod
    def profile(user_id: str) -> dict:
        """Return the current user's safe profile."""
        return AuthService.get_active_user(user_id).to_dict()

    @staticmethod
    def update_profile(user_id: str, data: dict) -> dict:
        """Update editable profile fields."""
        user = AuthService.get_active_user(user_id)
        name = validate_safe_name(require_string(data, "name", max_len=120), "name")
        user.name = name
        db.session.commit()
        write_audit_log("user.profile_updated", "User profile updated.", user_id=user.id)
        return user.to_dict()

    @staticmethod
    def change_password(user_id: str, data: dict, current_claims: dict) -> dict:
        """Change a user's password and revoke the current token."""
        user = AuthService.get_active_user(user_id)
        current_password = require_string(data, "current_password", min_len=1, max_len=128)
        new_password = validate_password(require_string(data, "new_password", min_len=10, max_len=128))

        if not bcrypt.check_password_hash(user.password_hash, current_password):
            write_audit_log("user.password_change_failed", "Password change failed.", user_id=user.id)
            raise ValidationError("Current password is incorrect.")
        if bcrypt.check_password_hash(user.password_hash, new_password):
            raise ValidationError("New password must be different from the current password.")

        user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
        db.session.commit()
        revoke_jwt_claims(current_claims, user.id)
        write_audit_log("user.password_changed", "User password changed.", user_id=user.id)
        return {"message": "Password changed. Sign in again on other devices if needed."}

    @staticmethod
    def logout(user_id: str, claims: dict) -> dict:
        """Revoke the presented JWT."""
        AuthService.get_active_user(user_id)
        revoke_jwt_claims(claims, user_id)
        write_audit_log("user.logout", "User logged out.", user_id=user_id)
        return {"message": "Logged out."}

    @staticmethod
    def request_metadata() -> dict[str, str | None]:
        """Collect request metadata used by authentication audit records."""
        from flask import request

        return {
            "ip_address": request_ip_address(),
            "user_agent": request.headers.get("User-Agent", "")[:255],
        }
