"""Rotating logging for the desktop agent."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_DIR, ensure_directories


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    ensure_directories()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    file_handler = RotatingFileHandler(LOG_DIR / "logs.txt", maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
