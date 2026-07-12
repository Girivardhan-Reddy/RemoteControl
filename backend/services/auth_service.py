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
    def _commit() -> None:
        """Commit the current SQLAlchemy unit of work or reset it on failure."""
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def _close() -> None:
        """Return the scoped SQLAlchemy session to a clean state."""
        db.session.close()

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
        user_id: str | None = None
        response: dict | None = None
        try:
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
            AuthService._commit()
            user_id = user.id
            response = {"user": user.to_dict(), **build_token_pair(user)}
        except Exception:
            db.session.rollback()
            raise
        finally:
            AuthService._close()

        write_audit_log("user.registered", "User registered.", user_id=user_id)
        return response

    @staticmethod
    def login(data: dict, request_metadata: dict[str, Any] | None = None) -> dict:
        """Authenticate a user and issue tokens."""
        metadata = request_metadata or {}
        audit_event: tuple[str, str, dict[str, Any]] | None = None
        try:
            email = validate_email(require_string(data, "email", max_len=255))
            password = require_string(data, "password", min_len=1, max_len=128)

            user = User.query.filter_by(email=email).first()
            if not user or not bcrypt.check_password_hash(user.password_hash, password):
                AuthService._record_login_attempt(
                    email=email,
                    user=user,
                    result=LoginAttemptResult.FAILURE,
                    reason="invalid_credentials",
                    request_metadata=metadata,
                )
                AuthService._commit()
                audit_event = (
                    "user.login_failed",
                    "Login failed.",
                    {"user_id": user.id if user else None, "email": email},
                )
                raise ValidationError("Invalid email or password.")

            if not user.is_active:
                AuthService._record_login_attempt(
                    email=email,
                    user=user,
                    result=LoginAttemptResult.FAILURE,
                    reason="inactive_account",
                    request_metadata=metadata,
                )
                AuthService._commit()
                raise ValidationError("Account is disabled.")

            user.last_login_at = datetime.now(timezone.utc)
            AuthService._record_login_attempt(
                email=email,
                user=user,
                result=LoginAttemptResult.SUCCESS,
                request_metadata=metadata,
            )
            AuthService._commit()
            response = {"user": user.to_dict(), **build_token_pair(user)}
            audit_event = ("user.login", "User logged in.", {"user_id": user.id})
            return response
        except Exception:
            db.session.rollback()
            raise
        finally:
            AuthService._close()
            if audit_event:
                write_audit_log(audit_event[0], audit_event[1], **audit_event[2])

    @staticmethod
    def refresh(user_id: str) -> dict:
        """Issue a new token pair for a refresh token identity."""
        try:
            user = User.query.get(user_id)
            if not user or not user.is_active:
                raise ValidationError("Account is unavailable.")
            return {"user": user.to_dict(), **build_token_pair(user)}
        except Exception:
            db.session.rollback()
            raise
        finally:
            AuthService._close()

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
        try:
            return AuthService.get_active_user(user_id).to_dict()
        except Exception:
            db.session.rollback()
            raise
        finally:
            AuthService._close()

    @staticmethod
    def update_profile(user_id: str, data: dict) -> dict:
        """Update editable profile fields."""
        try:
            user = AuthService.get_active_user(user_id)
            name = validate_safe_name(require_string(data, "name", max_len=120), "name")
            user.name = name
            AuthService._commit()
            response = user.to_dict()
        except Exception:
            db.session.rollback()
            raise
        finally:
            AuthService._close()

        write_audit_log("user.profile_updated", "User profile updated.", user_id=user_id)
        return response

    @staticmethod
    def change_password(user_id: str, data: dict, current_claims: dict) -> dict:
        """Change a user's password and revoke the current token."""
        try:
            user = AuthService.get_active_user(user_id)
            current_password = require_string(data, "current_password", min_len=1, max_len=128)
            new_password = validate_password(require_string(data, "new_password", min_len=10, max_len=128))

            if not bcrypt.check_password_hash(user.password_hash, current_password):
                raise ValidationError("Current password is incorrect.")
            if bcrypt.check_password_hash(user.password_hash, new_password):
                raise ValidationError("New password must be different from the current password.")

            user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
            AuthService._commit()
        except Exception:
            db.session.rollback()
            raise
        finally:
            AuthService._close()

        revoke_jwt_claims(current_claims, user_id)
        write_audit_log("user.password_changed", "User password changed.", user_id=user_id)
        return {"message": "Password changed. Sign in again on other devices if needed."}

    @staticmethod
    def logout(user_id: str, claims: dict) -> dict:
        """Revoke the presented JWT."""
        AuthService.get_active_user(user_id)
        revoke_jwt_claims(claims, user_id)
        write_audit_log("user.logout", "User logged out.", user_id=user_id)
        AuthService._close()
        return {"message": "Logged out."}

    @staticmethod
    def request_metadata() -> dict[str, str | None]:
        """Collect request metadata used by authentication audit records."""
        from flask import request

        return {
            "ip_address": request_ip_address(),
            "user_agent": request.headers.get("User-Agent", "")[:255],
        }
