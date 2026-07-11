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

    def _request(self, method: str, path: str, retry_refresh: bool = True, **kwargs) -> requests.Response:
        """Send a REST request with consistent timeout and error handling."""
        url = f"{self.config.api_url}{path}"

        try:
            response = requests.request(
                method,
                url,
                timeout=self.config.request_timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise AuthError(f"Failed to connect to server: {exc}")

        if response.status_code == 401 and retry_refresh and path != "/auth/refresh":
            LOGGER.info("Access token rejected for %s; attempting refresh.", path)
            try:
                refreshed = self.refresh()
                headers = dict(kwargs.get("headers") or {})
                headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                kwargs["headers"] = headers
                return self._request(method, path, retry_refresh=False, **kwargs)
            except Exception as exc:
                LOGGER.warning("Token refresh failed: %s", exc)

        if response.status_code >= 400:
            LOGGER.error("Server response for %s %s: %s %s", method, url, response.status_code, response.text)
            raise AuthError(
                f"{method} {path} failed: "
                f"{response.status_code} {response.text}"
            )

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
        payload = {
            "email": email,
            "password": password,
        }

        tokens = self._request(
            "POST",
            "/auth/login",
            json=payload,
            retry_refresh=False,
        ).json()

        self.save_tokens(tokens)
        LOGGER.info("Login succeeded for %s", email)
        return tokens

    def refresh(self) -> dict:
        """Refresh credentials using the saved refresh token."""
        tokens = self.load_tokens()

        if not tokens or not tokens.get("refresh_token"):
            raise AuthError("No refresh token is available.")

        headers = {
            "Authorization": f"Bearer {tokens['refresh_token']}"
        }

        refreshed = self._request(
            "POST",
            "/auth/refresh",
            headers=headers,
            retry_refresh=False,
        ).json()

        self.save_tokens(refreshed)
        LOGGER.info("Token refresh succeeded.")
        return refreshed

    def access_token(self) -> str:
        """Return a usable access token, refreshing when possible."""
        tokens = self.load_tokens()
        if not tokens or not tokens.get("access_token"):
            tokens = self.refresh()
        return tokens["access_token"]

    def register_device(self) -> dict:
        """Register this computer with the backend."""
        token = self.access_token()
        if not token:
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

        headers = {
            "Authorization": f"Bearer {token}"
        }

        device = self._request(
            "POST",
            "/devices",
            json=payload,
            headers=headers,
        ).json()

        self.save_device(device)
        LOGGER.info("Device registration succeeded for %s", device.get("id"))
        if device.get("pairing_code"):
            LOGGER.info("Device requires pairing. Pairing code was returned by backend.")
        return device

    def heartbeat(self) -> None:
        """Send a REST heartbeat for the registered device."""
        device = self.load_device()

        if not device:
            return

        headers = {
            "Authorization": f"Bearer {self.access_token()}"
        }

        self._request(
            "POST",
            f"/devices/{device['id']}/heartbeat",
            headers=headers,
        )
        LOGGER.info("Heartbeat sent for device %s", device.get("id"))

    @staticmethod
    def device_fingerprint() -> str:
        """Build a stable device fingerprint from local non-secret identifiers."""
        parts = [
            platform.node(),
            platform.system(),
            platform.machine(),
            str(uuid.getnode()),
        ]

        for disk in psutil.disk_partitions(all=False):
            parts.append(disk.device)

        digest = hashlib.sha256(
            "|".join(parts).encode("utf-8")
        ).hexdigest()

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
        path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
