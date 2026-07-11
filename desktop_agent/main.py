"""Graphical Windows desktop entrypoint for Remote Control Agent."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QStackedWidget

from auth import AuthClient
from config import ensure_directories
from gui.app_settings import SettingsStore
from gui.dashboard import MainWindow
from gui.login_window import LoginPage, RegisterPage
from logger import get_logger
from websocket_client import AgentSocketClient

LOGGER = get_logger(__name__)


class AgentGuiApp:
    """Application coordinator for authentication and dashboard windows."""

    def __init__(self) -> None:
        ensure_directories()
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Remote Control Agent")
        self.qt_app.setOrganizationName("RemoteControl")
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.config = self.settings.to_agent_config()
        self.auth_client = AuthClient(self.config)
        self.socket_client = AgentSocketClient(self.config, self.auth_client)
        self.auth_stack = QStackedWidget()
        self.dashboard: MainWindow | None = None
        self._load_style()

    def run(self) -> int:
        """Start the GUI application."""
        if self.settings.auto_login and self.auth_client.load_tokens():
            self._show_dashboard()
        else:
            self._show_auth()
        return self.qt_app.exec()

    def _show_auth(self) -> None:
        login = LoginPage(self.auth_client, self.settings)
        register = RegisterPage(self.auth_client)
        login.logged_in.connect(lambda result: self._show_dashboard())
        login.show_register.connect(lambda: self.auth_stack.setCurrentWidget(register))
        login.notify.connect(self._notify_auth)
        register.registered.connect(lambda result: self._show_dashboard())
        register.show_login.connect(lambda: self.auth_stack.setCurrentWidget(login))
        register.notify.connect(self._notify_auth)
        self.auth_stack.addWidget(login)
        self.auth_stack.addWidget(register)
        self.auth_stack.setWindowTitle("Remote Control Agent")
        self.auth_stack.resize(880, 620)
        self.auth_stack.show()

    def _show_dashboard(self) -> None:
        if self.auth_stack:
            self.auth_stack.hide()
        self.settings = self.settings_store.load()
        self.config = self.settings.to_agent_config()
        self.auth_client = AuthClient(self.config)
        self.socket_client = AgentSocketClient(self.config, self.auth_client)
        self.dashboard = MainWindow(self.settings, self.auth_client, self.socket_client)
        self.dashboard.show()

    def _notify_auth(self, message: str) -> None:
        LOGGER.info(message)

    def _load_style(self) -> None:
        style_path = Path(__file__).parent / "resources" / "styles" / "dark.qss"
        if not style_path.exists():
            style_path = Path(__file__).parent / "resources" / "styles" / "dark.qss"
        if not style_path.exists():
            style_path = Path(__file__).parent.parent / "resources" / "styles" / "dark.qss"
        if style_path.exists():
            self.qt_app.setStyleSheet(style_path.read_text(encoding="utf-8"))


def main() -> int:
    """Run the graphical agent."""
    QCoreApplication.setQuitLockEnabled(False)
    return AgentGuiApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
