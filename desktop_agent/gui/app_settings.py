"""Persistent GUI settings for the desktop application."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from config import APP_DIR, AgentConfig
from logger import get_logger

LOGGER = get_logger(__name__)
SETTINGS_FILE = APP_DIR / "gui_settings.json"


@dataclass
class GuiSettings:
    """User-configurable desktop agent settings."""

    backend_url: str = "https://remotecontrol-ef6d.onrender.com"
    theme: str = "dark"
    auto_startup: bool = False
    auto_login: bool = True
    remember_me: bool = True
    jpeg_quality: int = 65
    fps: int = 20
    reconnect_delay: int = 5
    heartbeat_interval: int = 30
    minimize_to_tray: bool = True

    def to_agent_config(self) -> AgentConfig:
        """Convert GUI settings into the existing agent configuration."""
        return AgentConfig(
            server_url=self.backend_url,
            reconnect_delay_seconds=self.reconnect_delay,
            heartbeat_interval_seconds=self.heartbeat_interval,
            screen_fps=self.fps,
            jpeg_quality=self.jpeg_quality,
        )


class SettingsStore:
    """Load and save GUI settings as JSON."""

    def load(self) -> GuiSettings:
        """Load settings, returning defaults when the file is absent or invalid."""
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                return GuiSettings(**{**asdict(GuiSettings()), **data})
        except Exception as exc:
            LOGGER.error("Failed to load GUI settings: %s", exc)
        return GuiSettings()

    def save(self, settings: GuiSettings) -> None:
        """Persist settings."""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
