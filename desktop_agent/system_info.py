"""System information collection."""

from __future__ import annotations

import platform

import psutil


class SystemInfo:
    """Collect CPU, memory, disk, battery, and process information."""

    def snapshot(self) -> dict:
        """Return a full system snapshot."""
        battery = psutil.sensors_battery()
        return {
            "ok": True,
            "platform": platform.platform(),
            "hostname": platform.node(),
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "cpu_count": psutil.cpu_count(),
            "ram": dict(psutil.virtual_memory()._asdict()),
            "disk": [dict(partition._asdict()) for partition in psutil.disk_partitions(all=False)],
            "disk_usage": {partition.mountpoint: dict(psutil.disk_usage(partition.mountpoint)._asdict()) for partition in psutil.disk_partitions(all=False)},
            "battery": dict(battery._asdict()) if battery else None,
            "processes": self.processes(),
        }

    def processes(self) -> list[dict]:
        """Return a concise process list."""
        result = []
        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
            try:
                result.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return result[:500]
