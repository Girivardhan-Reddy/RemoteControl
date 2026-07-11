"""Agent update support with SHA-256 verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from config import APP_DIR, AgentConfig


class UpdateManager:
    """Download verified update artifacts."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def download(self, url: str, sha256: str) -> dict:
        """Download an update file and verify its SHA-256 digest."""
        target = APP_DIR / "updates" / Path(url).name
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with requests.get(url, stream=True, timeout=self.config.request_timeout_seconds) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        handle.write(chunk)
        actual = digest.hexdigest()
        if actual.lower() != sha256.lower():
            target.unlink(missing_ok=True)
            return {"ok": False, "error": "Update digest verification failed."}
        return {"ok": True, "path": str(target), "sha256": actual}
