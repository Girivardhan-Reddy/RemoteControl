"""Windows startup registration."""

from __future__ import annotations

import os
import sys

from config import APP_NAME


class StartupManager:
    """Manage per-user Windows auto-start registration."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def enable(self) -> dict:
        """Enable startup for the current user."""
        if os.name != "nt":
            return {"ok": False, "error": "Startup registration is only supported on Windows."}
        import winreg

        command = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        return {"ok": True}

    def disable(self) -> dict:
        """Disable startup for the current user."""
        if os.name != "nt":
            return {"ok": False, "error": "Startup registration is only supported on Windows."}
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        return {"ok": True}
