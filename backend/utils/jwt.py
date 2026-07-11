"""JWT helper utilities."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import request
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from extensions import db
from models import RevokedToken


def _token_expiry(token: str) -> str | None:
    """Return a token expiry timestamp for API clients."""
    decoded = decode_token(token, allow_expired=True)
    expires_at = decoded.get("exp")
    if not expires_at:
        return None
    return datetime.fromtimestamp(expires_at, timezone.utc).isoformat()


def build_token_pair(user) -> dict:
    """Create access and refresh tokens for a user."""
    identity = user.id
    additional_claims = {
        "role": user.role.value,
        "email": user.email,
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=identity, additional_claims=additional_claims)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "access_expires_at": _token_expiry(access_token),
        "refresh_expires_at": _token_expiry(refresh_token),
    }


def revoke_jwt_claims(claims: dict, user_id: str) -> bool:
    """Persist a JWT denylist entry, returning True when a new entry is created."""
    jti = claims["jti"]
    if RevokedToken.query.filter_by(jti=jti).first():
        return False
    db.session.add(
        RevokedToken(
            jti=jti,
            token_type=claims.get("type", "access"),
            user_id=user_id,
        ),
    )
    db.session.commit()
    return True


def request_ip_address() -> str | None:
    """Return the best available client IP address for auth audit records."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.remote_addr
