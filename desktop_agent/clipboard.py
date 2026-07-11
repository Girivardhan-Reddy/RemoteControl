"""Clipboard synchronization."""

from __future__ import annotations

import pyperclip

from logger import get_logger

LOGGER = get_logger(__name__)


class ClipboardManager:
    """Read and write clipboard text."""

    def get_text(self) -> dict:
        """Return current clipboard text."""
        try:
            return {"ok": True, "text": pyperclip.paste()}
        except Exception as exc:
            LOGGER.exception("Clipboard read failed")
            return {"ok": False, "error": str(exc)}

    def set_text(self, text: str) -> dict:
        """Set clipboard text."""
        try:
            pyperclip.copy(text)
            return {"ok": True}
        except Exception as exc:
            LOGGER.exception("Clipboard write failed")
            return {"ok": False, "error": str(exc)}
