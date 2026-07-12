"""
Desktop Video Track for WebRTC screen sharing.

Captures the primary monitor's screen content and converts it
to WebRTC-compatible video frames using hardware-accelerated
capture when available.

Capture pipeline:
1. MSS captures screen region (fast, GPU-accelerated on Windows)
2. Convert BGRA → BGR (OpenCV format)
3. Convert BGR → RGB (aiortc/AV format)
4. Create av.VideoFrame with proper timing

Performance optimizations:
- Uses MSS for fast screen capture
- Numpy for efficient frame conversion
- Configurable quality and FPS
- Frame skipping to maintain target FPS
- Low-latency encoding settings

Dependencies:
- mss: Fast screen capture library
- numpy: Efficient array operations
- av: PyAV for video frame creation
"""

from __future__ import annotations

import asyncio
import logging
import time
import fractions
from typing import Optional, Tuple

import numpy as np
import av
from aiortc import VideoStreamTrack
from mss import mss

# Configure logging
logger = logging.getLogger(__name__)


class DesktopVideoTrack(VideoStreamTrack):
    """
    A VideoStreamTrack that captures and streams the desktop screen.
    
    Features:
    - Captures primary monitor at configurable resolution and FPS
    - Supports quality presets: low, medium, high
    - Automatic frame timing for smooth playback
    - Low CPU usage through efficient numpy operations
    - Hardware-accelerated capture via MSS
    """

    # Supported resolutions
    RESOLUTIONS = {
        "hd": (1280, 720),
        "full_hd": (1920, 1080),
        "qhd": (2560, 1440),
    }

    # Quality presets with resolution and compression settings
    QUALITY_PRESETS = {
        "low": {
            "resolution": "hd",  # 720p
            "scale_factor": 1.0,  # Capture at target resolution
        },
        "medium": {
            "resolution": "full_hd",  # 1080p
            "scale_factor": 1.0,  # Capture at target resolution
        },
        "high": {
            "resolution": "qhd",  # 1440p
            "scale_factor": 1.0,  # Capture at full resolution
        },
    }

    def __init__(
        self,
        quality: str = "high",
        fps: int = 30,
        monitor_index: int = 0,
    ):
        """
        Initialize the desktop video track.

        Args:
            quality: Video quality preset ("low", "medium", "high")
            fps: Target frames per second (30 or 60 recommended)
            monitor_index: Index of the monitor to capture (0 = primary)
        """
        super().__init__()

        # Validate quality setting
        if quality not in self.QUALITY_PRESETS:
            logger.warning(f"Invalid quality '{quality}', using 'high'")
            quality = "high"

        self.quality = quality
        self.fps = {"low": 15, "medium": 30, "high": 60}.get(quality, fps)
        self.monitor_index = monitor_index

        # Get quality preset configuration
        preset = self.QUALITY_PRESETS[quality]
        target_resolution = self.RESOLUTIONS[preset["resolution"]]
        self.target_width = target_resolution[0]
        self.target_height = target_resolution[1]
        self.scale_factor = preset["scale_factor"]

        # Initialize screen capture
        self.sct = mss()
        self.monitor = self._get_monitor(monitor_index)

        # Capture resolution (may be scaled)
        self.capture_width = int(self.target_width * self.scale_factor)
        self.capture_height = int(self.target_height * self.scale_factor)

        # Frame timing
        self._start_time: Optional[float] = None
        self._timestamp = 0
        self._frame_count = 0
        self._frame_interval = 1.0 / self.fps

        # Performance tracking
        self._last_capture_time = 0
        self._capture_times = []  # Rolling window of capture times

        # Configure monitor region for capture
        self._update_capture_region()

        logger.info(
            f"DesktopVideoTrack initialized: quality={quality}, "
            f"fps={fps}, resolution={self.target_width}x{self.target_height}, "
            f"capture={self.capture_width}x{self.capture_height}"
        )

    def _get_monitor(self, monitor_index: int) -> dict:
        """
        Get monitor configuration for the specified index.

        Args:
            monitor_index: Index of the monitor (0 = primary)

        Returns:
            Monitor configuration dictionary
        """
        monitors = self.sct.monitors

        # Monitor indices: 0 = all monitors, 1 = primary, 2+ = additional
        if monitor_index == 0:
            # Use primary monitor (index 1 in MSS)
            monitor = monitors[1] if len(monitors) > 1 else monitors[0]
            logger.info(f"Using primary monitor: {monitor}")
        elif monitor_index < len(monitors):
            monitor = monitors[monitor_index]
            logger.info(f"Using monitor {monitor_index}: {monitor}")
        else:
            logger.warning(f"Monitor index {monitor_index} not found, using primary")
            monitor = monitors[1] if len(monitors) > 1 else monitors[0]

        return monitor

    def _update_capture_region(self) -> None:
        """
        Update the capture region based on monitor and target resolution.
        
        Sets the capture region to match the target resolution,
        optionally scaled down for performance.
        """
        monitor_width = self.monitor["width"]
        monitor_height = self.monitor["height"]

        # Calculate capture dimensions while maintaining aspect ratio
        if monitor_width / monitor_height > self.capture_width / self.capture_height:
            # Monitor is wider than target - scale by height
            capture_height = min(self.capture_height, monitor_height)
            capture_width = int(capture_height * (monitor_width / monitor_height))
        else:
            # Monitor is taller than target - scale by width
            capture_width = min(self.capture_width, monitor_width)
            capture_height = int(capture_width * (monitor_height / monitor_width))

        self.capture_width = capture_width
        self.capture_height = capture_height

        logger.debug(
            f"Capture region set: {self.capture_width}x{self.capture_height}"
        )

    async def recv(self) -> av.VideoFrame:
        """
        Capture and return the next video frame.

        This method is called by aiortc at the encoding frame rate.
        It captures the screen, converts the format, and returns
        an av.VideoFrame ready for encoding.

        Frame format conversion pipeline:
        BGRA (MSS) → BGR (OpenCV compatible) → RGB (AV compatible)

        Returns:
            av.VideoFrame containing the captured screen

        Raises:
            RuntimeError: If frame capture fails
        """
        try:
            # Calculate frame timing
            if self._start_time is None:
                self._start_time = time.time()

            pts, time_base = await self.next_timestamp()

            # Frame rate limiting - skip if capturing too fast
            current_time = time.time()
            if current_time - self._last_capture_time < self._frame_interval * 0.9:
                # Too soon for next frame, but still return (aiortc handles timing)
                pass

            # Capture screen frame
            capture_start = time.time()
            frame = await self._capture_screen()
            self._last_capture_time = time.time()

            # Track performance
            capture_time = time.time() - capture_start
            self._capture_times.append(capture_time)
            if len(self._capture_times) > 100:
                self._capture_times.pop(0)

            self._frame_count += 1

            # Log performance every 100 frames
            if self._frame_count % 100 == 0:
                avg_capture_time = np.mean(self._capture_times)
                logger.debug(
                    f"Frame {self._frame_count}: capture={capture_time*1000:.1f}ms, "
                    f"avg={avg_capture_time*1000:.1f}ms"
                )

            # Create video frame
            video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.pts = pts
            video_frame.time_base = time_base

            return video_frame

        except Exception as e:
            logger.error(f"Failed to capture frame: {e}", exc_info=True)
            # Return a blank frame on error to keep the stream alive
            blank = np.zeros((self.target_height, self.target_width, 3), dtype=np.uint8)
            video_frame = av.VideoFrame.from_ndarray(blank, format="rgb24")
            video_frame.pts, video_frame.time_base = await self.next_timestamp()
            return video_frame

    async def _capture_screen(self) -> np.ndarray:
        """
        Capture the screen and return as RGB numpy array.
        
        Capture pipeline:
        1. Capture monitor region using MSS (returns BGRA)
        2. Convert BGRA to BGR (drop alpha channel)
        3. Convert BGR to RGB (correct color space for AV)
        4. Resize to target dimensions if needed
        
        Returns:
            numpy array in RGB format with shape (height, width, 3)
        """
        # Capture screen region using MSS
        # MSS returns BGRA format (Blue, Green, Red, Alpha)
        capture_region = {
            "left": self.monitor["left"],
            "top": self.monitor["top"],
            "width": self.monitor["width"],
            "height": self.monitor["height"],
        }

        # Perform the capture (this is the most expensive operation)
        sct_img = await asyncio.get_event_loop().run_in_executor(
            None, self.sct.grab, capture_region
        )

        # Convert to numpy array
        # MSS returns BGRA, we need RGB for av.VideoFrame
        img_array = np.array(sct_img)

        # Remove alpha channel: BGRA → BGR
        img_bgr = img_array[:, :, :3]

        # Convert BGR → RGB for correct color rendering
        img_rgb = img_bgr[:, :, ::-1]

        # Resize if needed to match target resolution
        if (img_rgb.shape[1] != self.target_width or 
            img_rgb.shape[0] != self.target_height):
            img_rgb = await self._resize_frame(img_rgb)

        return img_rgb

    async def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Resize frame to target dimensions using efficient interpolation.
        
        Uses OpenCV if available for better performance, falls back
        to numpy-based resizing.
        
        Args:
            frame: Input frame as numpy array
            
        Returns:
            Resized frame matching target dimensions
        """
        target_size = (self.target_width, self.target_height)

        try:
            # Try using OpenCV for fast, high-quality resize
            import cv2
            resized = cv2.resize(
                frame,
                target_size,
                interpolation=cv2.INTER_LINEAR,
            )
            return resized
        except ImportError:
            # Fallback to numpy slicing (faster than PIL)
            # This simple resize takes every nth pixel
            h, w = frame.shape[:2]
            scale_h = h // self.target_height
            scale_w = w // self.target_width

            if scale_h > 1 and scale_w > 1:
                # Fast downscaling by taking every nth row/column
                return frame[::scale_h, ::scale_w][:self.target_height, :self.target_width]
            else:
                # For upscaling, just use slice (quality loss but fast)
                return frame[:self.target_height, :self.target_width]

    def get_stats(self) -> dict:
        """
        Get current video track statistics.
        
        Returns:
            Dictionary with frame count, FPS, and capture times
        """
        stats = {
            "frame_count": self._frame_count,
            "target_fps": self.fps,
            "quality": self.quality,
            "resolution": f"{self.target_width}x{self.target_height}",
        }

        if self._capture_times:
            stats["avg_capture_ms"] = float(np.mean(self._capture_times) * 1000)
            stats["max_capture_ms"] = float(np.max(self._capture_times) * 1000)
            stats["min_capture_ms"] = float(np.min(self._capture_times) * 1000)

        return stats

    def stop(self) -> None:
        """Stop the video track and release resources."""
        logger.info(
            f"Stopping video track. Total frames captured: {self._frame_count}"
        )
        if self.sct:
            self.sct.close()
        super().stop()

