"""Profile page."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from auth import AuthClient


class ProfileWindow(QWidget):
    """Show authenticated profile and token state."""

    def __init__(self, auth_client: AuthClient) -> None:
        super().__init__()
        self.auth_client = auth_client
        self.info = QLabel("")
        self.info.setObjectName("Muted")
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Profile")
        title.setObjectName("PageTitle")
        refresh = QPushButton("Refresh")
        layout.addWidget(title)
        layout.addWidget(self.info)
        layout.addWidget(refresh)
        layout.addStretch()
        refresh.clicked.connect(self.refresh)

    def refresh(self) -> None:
        """Display token and device state."""
        tokens = self.auth_client.load_tokens() or {}
        device = self.auth_client.load_device() or {}
        self.info.setText(
            f"Access token: {'saved' if tokens.get('access_token') else 'missing'}\n"
            f"Refresh token: {'saved' if tokens.get('refresh_token') else 'missing'}\n"
            f"Device ID: {device.get('id', 'not registered')}"
        )
