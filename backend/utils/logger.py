"""Logging setup for API, security, and operational events."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(app) -> None:
    """Configure console and rotating file logging."""
    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    level = getattr(logging, app.config["LOG_LEVEL"].upper(), logging.INFO)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "logs.txt"),
        maxBytes=app.config["LOG_MAX_BYTES"],
        backupCount=app.config["LOG_BACKUP_COUNT"],
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    app.logger.setLevel(level)
    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(stream_handler)
