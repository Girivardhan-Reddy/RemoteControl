"""Settings page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from gui.app_settings import GuiSettings, SettingsStore
from startup import StartupManager
from update import UpdateManager


class SettingsWindow(QWidget):
    """Application settings page."""

    settings_saved = Signal(GuiSettings)
    notify = Signal(str)

    def __init__(self, settings: GuiSettings, startup: StartupManager, updater: UpdateManager | None = None) -> None:
        super().__init__()
        self.settings = settings
        self.startup = startup
        self.updater = updater
        self.backend_url = QLineEdit(settings.backend_url)
        self.theme = QComboBox()
        self.theme.addItems(["dark"])
        self.auto_startup = QCheckBox()
        self.auto_startup.setChecked(settings.auto_startup)
        self.auto_login = QCheckBox()
        self.auto_login.setChecked(settings.auto_login)
        self.jpeg_quality = QSpinBox()
        self.jpeg_quality.setRange(35, 85)
        self.jpeg_quality.setValue(settings.jpeg_quality)
        self.fps = QSpinBox()
        self.fps.setRange(1, 30)
        self.fps.setValue(settings.fps)
        self.reconnect = QSpinBox()
        self.reconnect.setRange(1, 120)
        self.reconnect.setValue(settings.reconnect_delay)
        self.heartbeat = QSpinBox()
        self.heartbeat.setRange(5, 300)
        self.heartbeat.setValue(settings.heartbeat_interval)
        self.update_url = QLineEdit()
        self.update_url.setPlaceholderText("Update URL")
        self.update_sha = QLineEdit()
        self.update_sha.setPlaceholderText("SHA-256")
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.addRow("Backend URL", self.backend_url)
        form.addRow("Theme", self.theme)
        form.addRow("Auto Startup", self.auto_startup)
        form.addRow("Auto Login", self.auto_login)
        form.addRow("JPEG Quality", self.jpeg_quality)
        form.addRow("FPS", self.fps)
        form.addRow("Reconnect Delay", self.reconnect)
        form.addRow("Heartbeat Interval", self.heartbeat)
        form.addRow("Update URL", self.update_url)
        form.addRow("Update SHA-256", self.update_sha)
        layout.addLayout(form)
        save = QPushButton("Save Settings")
        update = QPushButton("Check / Download Update")
        layout.addWidget(save)
        layout.addWidget(update)
        layout.addStretch()
        save.clicked.connect(self.save)
        update.clicked.connect(self.download_update)

    def save(self) -> None:
        """Persist settings and apply startup preference."""
        self.settings.backend_url = self.backend_url.text().strip().rstrip("/")
        self.settings.theme = self.theme.currentText()
        self.settings.auto_startup = self.auto_startup.isChecked()
        self.settings.auto_login = self.auto_login.isChecked()
        self.settings.jpeg_quality = self.jpeg_quality.value()
        self.settings.fps = self.fps.value()
        self.settings.reconnect_delay = self.reconnect.value()
        self.settings.heartbeat_interval = self.heartbeat.value()
        SettingsStore().save(self.settings)
        result = self.startup.enable() if self.settings.auto_startup else self.startup.disable()
        if not result.get("ok"):
            self.notify.emit(result.get("error", "Startup setting was not applied."))
        self.notify.emit("Settings saved.")
        self.settings_saved.emit(self.settings)

    def download_update(self) -> None:
        """Download and verify an update artifact."""
        if not self.updater:
            self.notify.emit("Updater is not available.")
            return
        try:
            result = self.updater.download(self.update_url.text().strip(), self.update_sha.text().strip())
            if result.get("ok"):
                self.notify.emit(f"Update downloaded: {result.get('path')}")
            else:
                self.notify.emit(result.get("error", "Update failed."))
        except Exception as exc:
            self.notify.emit(str(exc))
