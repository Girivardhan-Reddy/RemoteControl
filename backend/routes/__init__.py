"""Route registration helpers."""

from routes.auth import auth_bp
from routes.connect import connect_bp
from routes.devices import devices_bp
from routes.system import system_bp


def register_blueprints(app) -> None:
    """Register all API blueprints."""
    prefix = app.config["API_PREFIX"]
    app.register_blueprint(system_bp, url_prefix=prefix)
    app.register_blueprint(auth_bp, url_prefix=f"{prefix}/auth")
    app.register_blueprint(devices_bp, url_prefix=f"{prefix}/devices")
    app.register_blueprint(connect_bp, url_prefix=f"{prefix}/connect")
