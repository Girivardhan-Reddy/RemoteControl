"""Remote Control backend entrypoint."""

from __future__ import annotations

import eventlet

eventlet.monkey_patch()

from flask import Flask, jsonify

from config import ProductionConfig, get_config
from database import create_database_schema, init_database, startup_database_check
from extensions import bcrypt, cors, jwt, limiter, socketio
from models import RevokedToken, User
from routes import register_blueprints
from socket_events import register_socket_events
from utils.logger import configure_logging
from utils.middleware import register_error_handlers


def create_app() -> Flask:
    """Create and configure the Flask application."""
    config_class = get_config()
    if issubclass(config_class, ProductionConfig):
        config_class.validate()

    app = Flask(__name__)
    app.config.from_object(config_class)

    configure_logging(app)
    init_database(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    socketio.init_app(
<<<<<<< HEAD
    app,
    cors_allowed_origins="*",
    async_mode="threading"
    )
register_error_handlers(app)
=======
        app,
        cors_allowed_origins=app.config["SOCKETIO_CORS_ORIGINS"],
        async_mode="eventlet",
        logger=True,
        engineio_logger=True,
    )
    register_error_handlers(app)
>>>>>>> 51163e4 (Fixed backend and Socket.IO issues)
    register_blueprints(app)
    register_socket_events()

    @jwt.token_in_blocklist_loader
    def is_token_revoked(jwt_header, jwt_payload):
        """Reject logged-out JWTs."""
        return RevokedToken.query.filter_by(jti=jwt_payload["jti"]).first() is not None

    @jwt.user_lookup_loader
    def load_jwt_user(jwt_header, jwt_payload):
        """Load the current user for protected endpoints."""
        return User.query.get(jwt_payload["sub"])

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Return JSON for expired tokens."""
        return jsonify({"error": "Token has expired."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        """Return JSON for invalid tokens."""
        return jsonify({"error": "Invalid token.", "detail": reason}), 422

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        """Return JSON for missing tokens."""
        return jsonify({"error": "Authorization token is required.", "detail": reason}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Return JSON for revoked tokens."""
        return jsonify({"error": "Token has been revoked."}), 401

    @jwt.user_lookup_error_loader
    def user_lookup_error_callback(jwt_header, jwt_payload):
        """Return JSON when a token subject no longer exists."""
        return jsonify({"error": "Token subject is unavailable."}), 401

    @app.get("/")
    def index():
        """Root endpoint."""
        return jsonify({"service": app.config["APP_NAME"], "status": "running"}), 200

    if app.config.get("ENV") == "development" and app.config.get("AUTO_CREATE_DEV_DB"):
        create_database_schema(app)

    if not app.config.get("SKIP_STARTUP_DB_CHECK"):
        startup_database_check(app)
    app.logger.info("Remote Control backend started.")
    return app


app = create_app()

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
