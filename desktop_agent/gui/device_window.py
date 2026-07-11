"""Device information page."""

from __future__ import annotations

import socket
import platform

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from auth import AuthClient


class DeviceWindow(QWidget):
    """Show local registered device information."""

    notify = Signal(str)

    def __init__(self, auth_client: AuthClient) -> None:
        super().__init__()
        self.auth_client = auth_client
        self.labels: dict[str, QLabel] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Device")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        panel = QFrame()
        panel.setObjectName("Panel")
        grid = QGridLayout(panel)
        fields = ["Device Name", "Device ID", "Hostname", "OS", "Status", "Pairing Code"]
        for row, field in enumerate(fields):
            grid.addWidget(QLabel(field), row, 0)
            value = QLabel("-")
            value.setTextInteractionFlags(value.textInteractionFlags() | QtTextSelectable())
            self.labels[field] = value
            grid.addWidget(value, row, 1)
        copy_button = QPushButton("Copy Device ID")
        refresh_button = QPushButton("Refresh")
        grid.addWidget(copy_button, len(fields), 0)
        grid.addWidget(refresh_button, len(fields), 1)
        copy_button.clicked.connect(self.copy_device_id)
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(panel)
        layout.addStretch()

    def refresh(self) -> None:
        """Refresh device details from local storage."""
        device = self.auth_client.load_device() or {}
        self.labels["Device Name"].setText(device.get("name") or socket.gethostname())
        self.labels["Device ID"].setText(device.get("id", "Not registered"))
        self.labels["Hostname"].setText(device.get("hostname") or socket.gethostname())
        self.labels["OS"].setText(device.get("os_version") or platform.platform())
        self.labels["Status"].setText(device.get("status", "local"))
        self.labels["Pairing Code"].setText(device.get("pairing_code", "Already paired or not registered"))

    def copy_device_id(self) -> None:
        """Copy the device id to the clipboard."""
        QGuiApplication.clipboard().setText(self.labels["Device ID"].text())
        self.notify.emit("Device ID copied.")


def QtTextSelectable():
    """Return text selection flags without importing Qt at module top for one value."""
    from PySide6.QtCore import Qt

    return Qt.TextSelectableByMouse
