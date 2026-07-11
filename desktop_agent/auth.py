"""Authentication and device registration for the desktop agent."""

from __future__ import annotations

import hashlib
import json
import platform
import socket
import uuid
from pathlib import Path

import psutil
import requests

from config import APP_VERSION, DEVICE_FILE, TOKEN_FILE, AgentConfig, ensure_directories
from logger import get_logger

LOGGER = get_logger(__name__)


class AuthError(RuntimeError):
    """Raised when authentication fails."""


class AuthClient:
    """REST client for login, refresh, and device registration."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        ensure_directories()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Send a REST request with consistent timeout and error handling."""
        url = f"{self.config.api_url}{path}"
        response = requests.request(method, url, timeout=self.config.request_timeout_seconds, **kwargs)
        if response.status_code >= 400:
            raise AuthError(f"{method} {path} failed: {response.status_code} {response.text}")
        return response

    def load_tokens(self) -> dict | None:
        """Load persisted tokens."""
        return self._load_json(TOKEN_FILE)

    def save_tokens(self, tokens: dict) -> None:
        """Persist tokens with restricted user file permissions where supported."""
        self._save_json(TOKEN_FILE, tokens)

    def load_device(self) -> dict | None:
        """Load persisted device metadata."""
        return self._load_json(DEVICE_FILE)

    def save_device(self, device: dict) -> None:
        """Persist device metadata."""
        self._save_json(DEVICE_FILE, device)

    def login(self, email: str, password: str) -> dict:
        """Log in with account credentials and persist token pair."""
        payload = {"email": email, "password": password}
        tokens = self._request("POST", "/auth/login", json=payload).json()
        self.save_tokens(tokens)
        return tokens

    def refresh(self) -> dict:
        """Refresh credentials using the saved refresh token."""
        tokens = self.load_tokens()
        if not tokens or not tokens.get("refresh_token"):
            raise AuthError("No refresh token is available.")
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
        refreshed = self._request("POST", "/auth/refresh", headers=headers).json()
        self.save_tokens(refreshed)
        return refreshed

    def register_device(self) -> dict:
        """Register this computer with the backend."""
        tokens = self.load_tokens()
        if not tokens:
            raise AuthError("Login is required before device registration.")
        payload = {
            "name": socket.gethostname(),
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "os_version": platform.platform(),
            "agent_version": APP_VERSION,
            "device_fingerprint": self.device_fingerprint(),
            "capabilities": {
                "screen": True,
                "mouse": True,
                "keyboard": True,
                "clipboard": True,
                "file_manager": True,
                "system_info": True,
                "power": True,
            },
        }
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        device = self._request("POST", "/devices", json=payload, headers=headers).json()
        self.save_device(device)
        return device

    def heartbeat(self) -> None:
        """Send a REST heartbeat for the registered device."""
        tokens = self.load_tokens()
        device = self.load_device()
        if not tokens or not device:
            return
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        self._request("POST", f"/devices/{device['id']}/heartbeat", headers=headers)

    @staticmethod
    def device_fingerprint() -> str:
        """Build a stable device fingerprint from local non-secret identifiers."""
        parts = [platform.node(), platform.system(), platform.machine(), str(uuid.getnode())]
        for disk in psutil.disk_partitions(all=False):
            parts.append(disk.device)
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return digest

    @staticmethod
    def _load_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.error("Failed to read %s: %s", path, exc)
            return None

    @staticmethod
    def _save_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
