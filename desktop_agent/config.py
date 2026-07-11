"""Desktop agent configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Remote Control Agent"
APP_VERSION = "1.0.0"
APP_DIR = Path(os.getenv("REMOTE_AGENT_DIR", Path.home() / ".remote_control_agent"))
LOG_DIR = APP_DIR / "logs"
TOKEN_FILE = APP_DIR / "auth.json"
DEVICE_FILE = APP_DIR / "device.json"
DOWNLOAD_DIR = APP_DIR / "downloads"


@dataclass(frozen=True)
class AgentConfig:
    """Runtime configuration for the desktop agent."""

    server_url: str = os.getenv("REMOTE_SERVER_URL", "http://127.0.0.1:5000")
    api_prefix: str = os.getenv("REMOTE_API_PREFIX", "/api/v1")
    reconnect_delay_seconds: int = int(os.getenv("REMOTE_RECONNECT_DELAY", "5"))
    heartbeat_interval_seconds: int = int(os.getenv("REMOTE_HEARTBEAT_INTERVAL", "30"))
    screen_fps: int = int(os.getenv("REMOTE_SCREEN_FPS", "20"))
    jpeg_quality: int = int(os.getenv("REMOTE_JPEG_QUALITY", "65"))
    min_jpeg_quality: int = int(os.getenv("REMOTE_MIN_JPEG_QUALITY", "35"))
    max_jpeg_quality: int = int(os.getenv("REMOTE_MAX_JPEG_QUALITY", "85"))
    frame_width: int = int(os.getenv("REMOTE_FRAME_WIDTH", "1280"))
    request_timeout_seconds: int = int(os.getenv("REMOTE_REQUEST_TIMEOUT", "20"))
    allow_power_commands: bool = os.getenv("REMOTE_ALLOW_POWER", "true").lower() == "true"

    @property
    def api_url(self) -> str:
        """Return the REST API base URL."""
        return f"{self.server_url.rstrip('/')}{self.api_prefix}"


def ensure_directories() -> None:
    """Create agent runtime directories."""
    for path in (APP_DIR, LOG_DIR, DOWNLOAD_DIR):
        path.mkdir(parents=True, exist_ok=True)
