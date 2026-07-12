"""Screen streaming configuration shared by the desktop agent.

Live pixels are sent by ``desktop_agent.webrtc.video_track.DesktopVideoTrack`` over
WebRTC. This module intentionally no longer captures JPEG screenshots for
Socket.IO transport.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import AgentConfig


@dataclass(frozen=True)
class QualityProfile:
    """Video quality target for the WebRTC desktop track."""

    name: str
    width: int
    height: int
    fps: int
    start_bitrate_kbps: int
    max_bitrate_kbps: int


QUALITY_PROFILES = {
    "low": QualityProfile("low", 1280, 720, 15, 900, 1_500),
    "medium": QualityProfile("medium", 1920, 1080, 30, 2_500, 4_500),
    "high": QualityProfile("high", 2560, 1440, 60, 5_000, 9_000),
}


class ScreenStreamer:
    """Compatibility facade for code that queries screen streaming settings."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.quality = "medium"

    def set_quality(self, quality: str) -> QualityProfile:
        """Select a WebRTC quality profile."""
        self.quality = quality if quality in QUALITY_PROFILES else "medium"
        return self.profile

    @property
    def profile(self) -> QualityProfile:
        """Return the active quality profile."""
        return QUALITY_PROFILES[self.quality]

    def frame_interval(self) -> float:
        """Return target frame interval for the selected WebRTC profile."""
        return 1.0 / self.profile.fps

    def capture_frame(self):
        """Reject legacy screenshot-over-Socket.IO streaming."""
        raise RuntimeError("Raw screenshot streaming has been removed; use WebRTC media tracks.")
