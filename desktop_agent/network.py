"""Network health helpers."""

from __future__ import annotations

import socket

import requests

from config import AgentConfig


class NetworkMonitor:
    """Check local and backend connectivity."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def status(self) -> dict:
        """Return network status."""
        local_ip = None
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                local_ip = sock.getsockname()[0]
        except OSError:
            local_ip = None
        try:
            response = requests.get(f"{self.config.api_url}/health", timeout=5)
            backend_ok = response.status_code == 200
        except requests.RequestException:
            backend_ok = False
        return {"ok": True, "local_ip": local_ip, "backend_ok": backend_ok}
