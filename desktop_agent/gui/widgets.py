"""Reusable modern Qt widgets."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StatCard(QFrame):
    """Compact dashboard card with a label, value, and progress bar."""

    def __init__(self, title: str, value: str = "0%") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.value = QLabel(value)
        self.value.setObjectName("CardValue")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.progress)

    def update_value(self, value: float, suffix: str = "%") -> None:
        """Update the visible value and progress."""
        bounded = max(0, min(100, int(value)))
        self.value.setText(f"{value:.1f}{suffix}")
        self.progress.setValue(bounded)


class NavButton(QPushButton):
    """Sidebar navigation button."""

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)


class Toast(QFrame):
    """Small notification panel shown inside the main window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.label = QLabel("")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.hide()
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.animation = QPropertyAnimation(self.opacity, b"opacity")
        self.animation.setDuration(260)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def show_message(self, message: str) -> None:
        """Display a message with a fade animation."""
        self.label.setText(message)
        self.adjustSize()
        parent_rect = self.parentWidget().rect()
        self.move(parent_rect.right() - self.width() - 24, 24)
        self.show()
        self.raise_()
        self.animation.stop()
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()
