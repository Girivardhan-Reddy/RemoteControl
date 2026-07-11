"""Remote desktop control page."""

from __future__ import annotations

import base64
import threading

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from config import AgentConfig
from screen import ScreenStreamer
from websocket_client import AgentSocketClient


class RemoteDesktopPage(QWidget):
    """Controls for the local agent screen streaming service."""

    notify = Signal(str)

    def __init__(self, socket_client: AgentSocketClient, config: AgentConfig) -> None:
        super().__init__()
        self.socket_client = socket_client
        self.config = config
        self.thread: threading.Thread | None = None
        self.streamer = ScreenStreamer(config)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        self.preview = QLabel("Press Start Streaming to preview local capture and enable remote relay.")
        self.preview.setMinimumHeight(280)
        self.preview.setObjectName("Muted")
        self.preview.setScaledContents(True)
        self.fps = QComboBox()
        self.fps.addItems(["10", "15", "20", "25", "30"])
        self.fps.setCurrentText(str(config.screen_fps))
        self.quality = QSlider()
        self.quality.setRange(config.min_jpeg_quality, config.max_jpeg_quality)
        self.quality.setValue(config.jpeg_quality)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Remote Desktop")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(self.preview)
        controls = QHBoxLayout()
        start = QPushButton("Start Streaming")
        stop = QPushButton("Stop Streaming")
        fullscreen = QPushButton("Fullscreen")
        reconnect = QPushButton("Reconnect")
        controls.addWidget(QLabel("FPS"))
        controls.addWidget(self.fps)
        controls.addWidget(QLabel("Quality"))
        controls.addWidget(self.quality)
        for button in (start, stop, fullscreen, reconnect):
            controls.addWidget(button)
        panel_layout.addLayout(controls)
        layout.addWidget(panel)
        start.clicked.connect(self.start_streaming)
        stop.clicked.connect(self.stop_streaming)
        fullscreen.clicked.connect(lambda: self.notify.emit("Fullscreen is controlled from the Android viewer."))
        reconnect.clicked.connect(self.reconnect)

    def start_streaming(self) -> None:
        """Enable local frame streaming loop."""
        self.socket_client.streaming = True
        self.timer.start(int(1000 / max(1, int(self.fps.currentText()))))
        self.notify.emit("Streaming enabled.")

    def stop_streaming(self) -> None:
        """Stop frame streaming."""
        self.socket_client.streaming = False
        self.timer.stop()
        self.notify.emit("Streaming stopped.")

    def reconnect(self) -> None:
        """Start a reconnecting socket thread if needed."""
        if self.thread and self.thread.is_alive():
            self.notify.emit("Socket client is already running.")
            return
        self.thread = threading.Thread(target=self.socket_client.run_forever, daemon=True)
        self.thread.start()
        self.notify.emit("Reconnect started.")

    def update_preview(self) -> None:
        """Capture one local frame and show it in the preview panel."""
        try:
            self.streamer.quality = self.quality.value()
            frame = self.streamer.capture_frame()
            image = base64.b64decode(frame.image)
            pixmap = QPixmap()
            pixmap.loadFromData(image, "JPEG")
            self.preview.setPixmap(pixmap)
        except Exception as exc:
            self.notify.emit(str(exc))
