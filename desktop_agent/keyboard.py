"""Keyboard command execution."""

from __future__ import annotations

import pyautogui

from logger import get_logger

LOGGER = get_logger(__name__)


SPECIAL_KEYS = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "win",
    "windows": "win",
    "enter": "enter",
    "tab": "tab",
    "escape": "esc",
    "esc": "esc",
    "backspace": "backspace",
    "delete": "delete",
    "space": "space",
}


class KeyboardController:
    """Execute typing, hotkey, and special-key commands."""

    def handle(self, command: dict) -> dict:
        """Dispatch a keyboard command."""
        action = command.get("action")
        try:
            if action == "type":
                pyautogui.write(str(command.get("text", "")), interval=float(command.get("interval", 0)))
            elif action == "press":
                pyautogui.press(self._key(command.get("key")))
            elif action == "hotkey":
                keys = [self._key(key) for key in command.get("keys", [])]
                if not keys:
                    return {"ok": False, "error": "At least one key is required."}
                pyautogui.hotkey(*keys)
            elif action == "unicode":
                pyautogui.write(str(command.get("text", "")))
            else:
                return {"ok": False, "error": "Unsupported keyboard action."}
            return {"ok": True}
        except Exception as exc:
            LOGGER.exception("Keyboard command failed")
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _key(value: object) -> str:
        key = str(value or "").lower()
        return SPECIAL_KEYS.get(key, key)
