"""Power management commands."""

from __future__ import annotations

import ctypes
import os
import subprocess

from config import AgentConfig


class PowerManager:
    """Execute explicit power commands when enabled."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def handle(self, action: str) -> dict:
        """Run a power command."""
        if not self.config.allow_power_commands:
            return {"ok": False, "error": "Power commands are disabled."}
        if os.name != "nt":
            return {"ok": False, "error": "Power commands are implemented for Windows agents."}
        if action == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "0"], shell=False)
        elif action == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", "0"], shell=False)
        elif action == "lock":
            ctypes.windll.user32.LockWorkStation()
        elif action == "sleep":
            ctypes.windll.PowrProf.SetSuspendState(False, True, False)
        elif action == "hibernate":
            ctypes.windll.PowrProf.SetSuspendState(True, True, False)
        else:
            return {"ok": False, "error": "Unsupported power action."}
        return {"ok": True}
