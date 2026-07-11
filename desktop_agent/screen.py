"""Screen capture and JPEG compression."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from mss import mss
from PIL import Image

from config import AgentConfig
from logger import get_logger

LOGGER = get_logger(__name__)


@dataclass
class FramePacket:
    """Encoded screen frame."""

    image: str
    width: int
    height: int
    image_width: int
    image_height: int
    quality: int
    captured_at: float


class ScreenStreamer:
    """Capture the primary display at a configurable frame rate."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.quality = config.jpeg_quality
        self.last_capture_seconds = 0.0

    def capture_frame(self) -> FramePacket:
        """Capture, resize, compress, and base64-encode a frame."""
        started = time.perf_counter()
        with mss() as capture:
            monitor = capture.monitors[1]
            raw = np.array(capture.grab(monitor))
        desktop_width = int(monitor["width"])
        desktop_height = int(monitor["height"])
        rgb = cv2.cvtColor(raw, cv2.COLOR_BGRA2RGB)
        image = Image.fromarray(rgb)
        if image.width > self.config.frame_width:
            ratio = self.config.frame_width / image.width
            image = image.resize((self.config.frame_width, int(image.height * ratio)), Image.Resampling.BILINEAR)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=self.quality, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        self.last_capture_seconds = time.perf_counter() - started
        self._adjust_quality()
        return FramePacket(
            image=encoded,
            width=desktop_width,
            height=desktop_height,
            image_width=image.width,
            image_height=image.height,
            quality=self.quality,
            captured_at=time.time(),
        )

    def frame_interval(self) -> float:
        """Return the target delay between frames."""
        return 1.0 / max(1, self.config.screen_fps)

    def _adjust_quality(self) -> None:
        """Lower quality under load and recover when capture is fast."""
        interval = self.frame_interval()
        if self.last_capture_seconds > interval and self.quality > self.config.min_jpeg_quality:
            self.quality -= 5
        elif self.last_capture_seconds < interval * 0.5 and self.quality < self.config.max_jpeg_quality:
            self.quality += 2
