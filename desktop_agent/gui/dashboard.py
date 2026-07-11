"""Main dashboard shell for the desktop agent GUI."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from auth import AuthClient
from file_manager import FileManager
from gui.app_settings import GuiSettings
from gui.device_window import DeviceWindow
from gui.file_manager import FileManagerPage
from gui.login_window import LoginPage, RegisterPage, SetupWizard
from gui.logs_window import LogsWindow
from gui.profile_window import ProfileWindow
from gui.remote_desktop import RemoteDesktopPage
from gui.settings_window import SettingsWindow
from gui.system_monitor import SystemMonitor
from gui.widgets import NavButton, StatCard, Toast
from network import NetworkMonitor
from startup import StartupManager
from system_info import SystemInfo
from update import UpdateManager
from websocket_client import AgentSocketClient


class DashboardHome(QWidget):
    """Home dashboard summary."""

    def __init__(self, auth_client: AuthClient, socket_client: AgentSocketClient) -> None:
        super().__init__()
        self.auth_client = auth_client
        self.socket_client = socket_client
        self.status = StatCard("Connection", "Disconnected")
        self.device = StatCard("Device", "Not registered")
        self.backend = StatCard("Backend", socket_client.config.server_url)
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        row = QHBoxLayout()
        row.addWidget(self.status)
        row.addWidget(self.device)
        row.addWidget(self.backend)
        layout.addLayout(row)
        reconnect = QPushButton("Reconnect Agent")
        reconnect.clicked.connect(self._reconnect)
        layout.addWidget(reconnect, alignment=Qt.AlignLeft)
        layout.addStretch()

    def refresh(self) -> None:
        device = self.auth_client.load_device() or {}
        self.device.value.setText(device.get("name") or device.get("id") or "Not registered")
        self.status.value.setText("Connected" if self.socket_client.sio.connected else "Disconnected")

    def _reconnect(self) -> None:
        thread = threading.Thread(target=self.socket_client.run_forever, daemon=True)
        thread.start()


class MainWindow(QMainWindow):
    """Professional dark dashboard similar to remote support tools."""

    def __init__(
        self,
        settings: GuiSettings,
        auth_client: AuthClient,
        socket_client: AgentSocketClient,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.auth_client = auth_client
        self.socket_client = socket_client
        self.setWindowTitle("Remote Control Agent")
        icon_path = Path(__file__).resolve().parent.parent / "resources" / "icons" / "app_icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1240, 780)
        self.root = QWidget()
        self.root.setObjectName("Root")
        self.setCentralWidget(self.root)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.stack = QStackedWidget()
        self.toast = Toast(self)
        self.buttons: list[NavButton] = []
        self.tray = self._create_tray()
        self._build()
        self._start_auto_socket()

    def _build(self) -> None:
        root_layout = QHBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, stretch=1)
        side_layout = QVBoxLayout(self.sidebar)
        title = QLabel("Remote Agent")
        title.setObjectName("AppTitle")
        side_layout.addWidget(title)

        pages = [
            ("Dashboard", DashboardHome(self.auth_client, self.socket_client)),
            ("Devices", DeviceWindow(self.auth_client)),
            ("Remote Desktop", RemoteDesktopPage(self.socket_client, self.socket_client.config)),
            ("File Manager", FileManagerPage(FileManager())),
            ("System Monitor", SystemMonitor(SystemInfo(), NetworkMonitor(self.socket_client.config))),
            ("Settings", SettingsWindow(self.settings, StartupManager(), UpdateManager(self.socket_client.config))),
            ("Logs", LogsWindow()),
            ("Profile", ProfileWindow(self.auth_client)),
            ("Setup Wizard", SetupWizard(self.settings, self.auth_client)),
        ]
        for index, (label, page) in enumerate(pages):
            if hasattr(page, "notify"):
                page.notify.connect(self.notify)
            button = NavButton(label)
            button.clicked.connect(lambda checked=False, idx=index: self.navigate(idx))
            self.buttons.append(button)
            side_layout.addWidget(button)
            self.stack.addWidget(page)
        side_layout.addStretch()
        self.buttons[0].setChecked(True)

    def navigate(self, index: int) -> None:
        """Navigate with a subtle page slide animation."""
        for idx, button in enumerate(self.buttons):
            button.setChecked(idx == index)
        old_rect = self.stack.geometry()
        self.stack.setCurrentIndex(index)
        animation = QPropertyAnimation(self.stack, b"geometry", self)
        animation.setDuration(180)
        animation.setStartValue(QRect(old_rect.x() + 18, old_rect.y(), old_rect.width(), old_rect.height()))
        animation.setEndValue(old_rect)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()

    def notify(self, message: str) -> None:
        """Show an in-app and system notification."""
        self.toast.show_message(message)
        if self.tray.isVisible():
            self.tray.showMessage("Remote Control Agent", message, QSystemTrayIcon.Information, 3000)

    def _create_tray(self) -> QSystemTrayIcon:
        icon_path = Path(__file__).resolve().parent.parent / "resources" / "icons" / "app_icon.svg"
        tray = QSystemTrayIcon(QIcon(str(icon_path)) if icon_path.exists() else QIcon(), self)
        menu = QMenu()
        open_action = QAction("Open", self)
        reconnect_action = QAction("Reconnect", self)
        settings_action = QAction("Settings", self)
        quit_action = QAction("Quit", self)
        open_action.triggered.connect(self.showNormal)
        reconnect_action.triggered.connect(lambda: threading.Thread(target=self.socket_client.run_forever, daemon=True).start())
        settings_action.triggered.connect(lambda: self.navigate(5))
        quit_action.triggered.connect(QApplication.quit)
        for action in (open_action, reconnect_action, settings_action, quit_action):
            menu.addAction(action)
        tray.setContextMenu(menu)
        tray.setToolTip("Remote Control Agent")
        tray.show()
        return tray

    def _start_auto_socket(self) -> None:
        if self.settings.auto_login and self.auth_client.load_tokens() and self.auth_client.load_device():
            threading.Thread(target=self.socket_client.run_forever, daemon=True).start()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimize to tray when configured."""
        if self.settings.minimize_to_tray and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.notify("Remote Control Agent is running in the background.")
        else:
            super().closeEvent(event)
