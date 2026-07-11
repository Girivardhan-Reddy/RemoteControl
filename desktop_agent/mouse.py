"""Mouse control commands."""

from __future__ import annotations

import pyautogui

from logger import get_logger

LOGGER = get_logger(__name__)
pyautogui.FAILSAFE = True


class MouseController:
    """Execute validated mouse commands."""

    def handle(self, command: dict) -> dict:
        """Dispatch a mouse command."""
        action = command.get("action")
        try:
            if action == "move":
                pyautogui.moveTo(int(command["x"]), int(command["y"]), duration=float(command.get("duration", 0)))
            elif action == "left_click":
                pyautogui.click(button="left")
            elif action == "right_click":
                pyautogui.click(button="right")
            elif action == "double_click":
                pyautogui.doubleClick()
            elif action == "scroll":
                pyautogui.scroll(int(command.get("amount", 0)))
            elif action == "drag":
                pyautogui.dragTo(int(command["x"]), int(command["y"]), duration=float(command.get("duration", 0.2)))
            elif action == "drop":
                pyautogui.mouseUp()
            else:
                return {"ok": False, "error": "Unsupported mouse action."}
            return {"ok": True}
        except Exception as exc:
            LOGGER.exception("Mouse command failed")
            return {"ok": False, "error": str(exc)}
