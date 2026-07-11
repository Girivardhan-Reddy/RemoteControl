"""Authentication API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from extensions import limiter
from services.auth_service import AuthService
from utils.validators import require_json

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
@limiter.limit("10 per minute")
def register():
    """Register a user."""
    result = AuthService.register(require_json(request.get_json(silent=True)))
    return jsonify(result), 201


@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():
    """Authenticate a user."""
    return jsonify(AuthService.login(require_json(request.get_json(silent=True)), AuthService.request_metadata())), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """Rotate refresh credentials."""
    result = AuthService.refresh(get_jwt_identity())
    AuthService.logout(get_jwt_identity(), get_jwt())
    return jsonify(result), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    """Revoke the presented access token."""
    return jsonify(AuthService.logout(get_jwt_identity(), get_jwt())), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    """Return the current authenticated user."""
    return jsonify(AuthService.profile(get_jwt_identity())), 200


@auth_bp.patch("/me")
@jwt_required()
def update_me():
    """Update the current user's profile."""
    return jsonify(AuthService.update_profile(get_jwt_identity(), require_json(request.get_json(silent=True)))), 200


@auth_bp.post("/change-password")
@jwt_required()
@limiter.limit("5 per minute")
def change_password():
    """Change the current user's password."""
    return jsonify(
        AuthService.change_password(
            get_jwt_identity(),
            require_json(request.get_json(silent=True)),
            get_jwt(),
        ),
    ), 200
