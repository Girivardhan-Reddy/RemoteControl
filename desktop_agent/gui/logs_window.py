"""Logs viewer page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget

from config import LOG_DIR


class LogsWindow(QWidget):
    """View, search, export, and clear logs.txt."""

    notify = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.log_file = LOG_DIR / "logs.txt"
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search logs")
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Logs")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        controls = QHBoxLayout()
        refresh = QPushButton("Refresh")
        export = QPushButton("Export Logs")
        clear = QPushButton("Clear Logs")
        controls.addWidget(self.search)
        controls.addWidget(refresh)
        controls.addWidget(export)
        controls.addWidget(clear)
        layout.addLayout(controls)
        layout.addWidget(self.viewer)
        self.search.textChanged.connect(self.refresh)
        refresh.clicked.connect(self.refresh)
        export.clicked.connect(self.export)
        clear.clicked.connect(self.clear)

    def refresh(self) -> None:
        """Reload logs from disk."""
        if not self.log_file.exists():
            self.viewer.setPlainText("")
            return
        content = self.log_file.read_text(encoding="utf-8", errors="replace")
        query = self.search.text().lower().strip()
        if query:
            lines = [line for line in content.splitlines() if query in line.lower()]
            content = "\n".join(lines)
        self.viewer.setPlainText(content)

    def export(self) -> None:
        """Export logs to a selected file."""
        path, _ = QFileDialog.getSaveFileName(self, "Export Logs", "logs.txt", "Text Files (*.txt)")
        if path:
            Path(path).write_text(self.viewer.toPlainText(), encoding="utf-8")
            self.notify.emit("Logs exported.")

    def clear(self) -> None:
        """Clear the log file."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text("", encoding="utf-8")
        self.refresh()
        self.notify.emit("Logs cleared.")
