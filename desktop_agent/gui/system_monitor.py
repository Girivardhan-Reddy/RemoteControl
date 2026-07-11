"""System monitor page with live charts."""

from __future__ import annotations

import getpass
import socket
from collections import deque

import psutil
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from gui.widgets import StatCard
from network import NetworkMonitor
from system_info import SystemInfo


class LineChart(QWidget):
    """Tiny real-time line chart."""

    def __init__(self, color: str) -> None:
        super().__init__()
        self.values = deque([0.0] * 60, maxlen=60)
        self.color = color
        self.setMinimumHeight(120)

    def add_value(self, value: float) -> None:
        """Append a value and repaint."""
        self.values.append(max(0.0, min(100.0, value)))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), Qt.transparent)
        pen = QPen(self.color)
        pen.setWidth(2)
        painter.setPen(pen)
        width = max(1, self.width() - 1)
        height = max(1, self.height() - 1)
        points = []
        for index, value in enumerate(self.values):
            x = int(index * width / max(1, len(self.values) - 1))
            y = int(height - (value / 100.0) * height)
            points.append((x, y))
        for index in range(1, len(points)):
            painter.drawLine(points[index - 1][0], points[index - 1][1], points[index][0], points[index][1])


class SystemMonitor(QWidget):
    """Real-time CPU, memory, disk, network, GPU, and host details."""

    def __init__(self, system_info: SystemInfo, network: NetworkMonitor) -> None:
        super().__init__()
        self.system_info = system_info
        self.network = network
        self.cpu = StatCard("CPU Usage")
        self.ram = StatCard("RAM Usage")
        self.disk = StatCard("Disk Usage")
        self.net = StatCard("Network Speed", "0 KB/s")
        self.gpu = StatCard("GPU Usage", "N/A")
        self.cpu_chart = LineChart("#58A6FF")
        self.ram_chart = LineChart("#2EA043")
        self.last_net = psutil.net_io_counters()
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("System Monitor")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        grid = QGridLayout()
        for index, card in enumerate((self.cpu, self.ram, self.disk, self.net, self.gpu)):
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
        charts = QFrame()
        charts.setObjectName("Panel")
        chart_layout = QGridLayout(charts)
        chart_layout.addWidget(QLabel("CPU"), 0, 0)
        chart_layout.addWidget(self.cpu_chart, 1, 0)
        chart_layout.addWidget(QLabel("RAM"), 0, 1)
        chart_layout.addWidget(self.ram_chart, 1, 1)
        layout.addWidget(charts)
        self.host = QLabel("")
        self.host.setObjectName("Muted")
        layout.addWidget(self.host)

    def refresh(self) -> None:
        """Update live statistics."""
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net_now = psutil.net_io_counters()
        speed = ((net_now.bytes_sent + net_now.bytes_recv) - (self.last_net.bytes_sent + self.last_net.bytes_recv)) / 1024 / 1.5
        self.last_net = net_now
        self.cpu.update_value(cpu)
        self.ram.update_value(memory.percent)
        self.disk.update_value(disk.percent)
        self.net.value.setText(f"{speed:.1f} KB/s")
        self.gpu.value.setText("N/A")
        self.cpu_chart.add_value(cpu)
        self.ram_chart.add_value(memory.percent)
        network = self.network.status()
        self.host.setText(f"Hostname: {socket.gethostname()}    Username: {getpass.getuser()}    IP Address: {network.get('local_ip') or 'Unknown'}")
