"""
Desktop Audio Track for WebRTC audio streaming.

Captures system audio output (what you hear) and streams it
through WebRTC to the remote controller.

Audio capture pipeline:
1. Capture system audio using sounddevice (loopback/Wasapi)
2. Convert to numpy array
3. Resample if needed
4. Create av.AudioFrame with proper timing

Platform-specific notes:
- Windows: Uses WASAPI loopback device
- Linux: Uses PulseAudio monitor device (requires pavucontrol)
- macOS: Uses BlackHole or Soundflower virtual device

Audio specifications:
- Sample rate: 44100 Hz (44.1 kHz)
- Channels: 2 (stereo)
- Format: 16-bit PCM
- Frame size: 960 samples (20ms at 48kHz)

Dependencies:
- sounddevice: Cross-platform audio capture
- numpy: Efficient audio data handling
- av: PyAV for audio frame creation
"""

from __future__ import annotations

import asyncio
import logging
import time
import fractions
from typing import Optional, List

import numpy as np
import av
from aiortc import MediaStreamTrack

# Configure logging
logger = logging.getLogger(__name__)


class DesktopAudioTrack(MediaStreamTrack):
    """
    A MediaStreamTrack that captures and streams system audio output.
    
    Captures the system audio (speaker output) using platform-specific
    loopback devices and streams it through WebRTC.
    
    Features:
    - Low-latency audio capture
    - Automatic device selection
    - Configurable buffer size
    - Resampling support
    - Silence detection (optional)
    """

    # Audio configuration
    SAMPLE_RATE = 44100  # 44.1 kHz standard audio sample rate
    CHANNELS = 2  # Stereo audio
    SAMPLE_WIDTH = 2  # 16-bit samples (2 bytes)
    FRAME_DURATION_MS = 20  # 20ms frames for low latency

    # Calculate samples per frame
    SAMPLES_PER_FRAME = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)

    kind = "audio"

    def __init__(
        self,
        device_name: Optional[str] = None,
        buffer_size_ms: int = 20,
        enable_silence_detection: bool = False,
    ):
        """
        Initialize the desktop audio track.

        Args:
            device_name: Name of audio capture device (auto-detect if None)
            buffer_size_ms: Audio buffer size in milliseconds (20ms for low latency)
            enable_silence_detection: Whether to detect and skip silence
        """
        super().__init__()

        self.device_name = device_name
        self.buffer_size_ms = buffer_size_ms
        self.enable_silence_detection = enable_silence_detection

        # Audio stream and device
        self._stream: Optional[sounddevice.InputStream] = None
        self._device_id: Optional[int] = None
        self._audio_buffer: List[np.ndarray] = []

        # Frame timing
        self._start_time: Optional[float] = None
        self._timestamp = 0
        self._frame_count = 0
        self._sample_rate = self.SAMPLE_RATE

        # Performance tracking
        self._capture_times = []
        self._silence_frames = 0

        # Initialize audio capture
        self._initialize_audio()

        # Calculate time base for audio frames
        self._time_base = fractions.Fraction(1, self._sample_rate)

        logger.info(
            f"DesktopAudioTrack initialized: rate={self._sample_rate}Hz, "
            f"channels={self.CHANNELS}, frames={self.SAMPLES_PER_FRAME}samples"
        )

    def _initialize_audio(self) -> None:
        """
        Initialize the audio capture device.
        
        Platform-specific device selection:
        - Windows: WASAPI loopback (speaker output)
        - Linux: PulseAudio monitor or ALSA loopback
        - macOS: BlackHole or Soundflower virtual device
        """
        try:
            import sounddevice as sd

            if self.device_name:
                # Use specified device
                self._device_id = self._find_device_by_name(self.device_name)
                if self._device_id is None:
                    logger.warning(f"Audio device '{self.device_name}' not found")
                    self._device_id = self._find_default_loopback_device()
            else:
                # Auto-detect loopback device
                self._device_id = self._find_default_loopback_device()

            if self._device_id is None:
                logger.warning(
                    "No loopback audio device found. "
                    "Audio streaming will be disabled."
                )
                return

            # Open audio stream
            self._stream = sd.InputStream(
                device=self._device_id,
                samplerate=self._sample_rate,
                channels=self.CHANNELS,
                dtype=np.int16,
                blocksize=self.SAMPLES_PER_FRAME,
                callback=self._audio_callback,
                latency="low",  # Low latency mode for real-time streaming
            )

            self._stream.start()
            device_info = sd.query_devices(self._device_id)
            logger.info(f"Audio capture started on: {device_info['name']}")

        except ImportError:
            logger.error("sounddevice not installed. Audio streaming disabled.")
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}", exc_info=True)

    def _find_device_by_name(self, name: str) -> Optional[int]:
        """
        Find audio device ID by name.

        Args:
            name: Device name to search for

        Returns:
            Device ID if found, None otherwise
        """
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                if name.lower() in device["name"].lower():
                    logger.info(f"Found device: {device['name']} (ID: {idx})")
                    return idx
            return None
        except Exception as e:
            logger.error(f"Error finding device: {e}")
            return None

    def _find_default_loopback_device(self) -> Optional[int]:
        """
        Find the default system audio loopback device.
        
        Platform-specific detection:
        - Windows: Look for "Stereo Mix" or WASAPI loopback
        - Linux: Look for PulseAudio monitor or "Loopback" device
        - macOS: Look for BlackHole or Soundflower
        
        Returns:
            Device ID if found, None otherwise
        """
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            loopback_keywords = [
                "stereo mix",
                "loopback",
                "monitor",
                "blackhole",
                "soundflower",
                "wave out mix",
                "what u hear",
            ]

            # First, try to find host API-specific loopback device
            for idx, device in enumerate(devices):
                device_name = device["name"].lower()
                max_channels = device.get("max_output_channels", 0)

                # Check if device supports loopback (has input channels despite being output)
                if max_channels > 0 and device.get("max_input_channels", 0) > 0:
                    for keyword in loopback_keywords:
                        if keyword in device_name:
                            logger.info(
                                f"Found loopback device: {device['name']} (ID: {idx})"
                            )
                            return idx

            # Fallback: look for any device with loopback keywords
            for idx, device in enumerate(devices):
                device_name = device["name"].lower()
                for keyword in loopback_keywords:
                    if keyword in device_name:
                        logger.info(
                            f"Found potential loopback: {device['name']} (ID: {idx})"
                        )
                        return idx

            logger.warning("No loopback device found. Available devices:")
            for idx, device in enumerate(devices):
                logger.info(f"  {idx}: {device['name']}")

            return None
        except Exception as e:
            logger.error(f"Error finding loopback device: {e}")
            return None

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: int,
    ) -> None:
        """
        Callback function for audio stream.
        
        Called by sounddevice when new audio data is available.
        Adds the captured audio to the buffer for pickup by recv().
        
        Args:
            indata: Captured audio samples
            frames: Number of frames captured
            time_info: Timing information
            status: Status flags
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        # Add captured audio to buffer
        # Convert to mono if needed (take average of channels for efficiency)
        if indata.shape[1] > 1:
            # Keep stereo for better quality
            self._audio_buffer.append(indata.copy())
        else:
            # Duplicate mono to stereo
            stereo_data = np.column_stack((indata, indata))
            self._audio_buffer.append(stereo_data)

    async def recv(self) -> av.AudioFrame:
        """
        Return the next audio frame for WebRTC encoding.
        
        Called by aiortc at the encoding interval. Reads captured
        audio from the buffer and creates an av.AudioFrame.
        
        Returns:
            av.AudioFrame containing captured audio
            
        Note:
            Returns silence if no audio data is available to keep
            the stream alive.
        """
        try:
            # Calculate frame timing
            if self._start_time is None:
                self._start_time = time.time()

            # Get next timestamp
            pts = self._frame_count * self.SAMPLES_PER_FRAME

            # Get audio data from buffer
            if self._audio_buffer:
                # Get the oldest audio chunk
                audio_data = self._audio_buffer.pop(0)

                # Ensure correct shape (samples, channels)
                if audio_data.shape[0] > self.SAMPLES_PER_FRAME:
                    # Trim to exact frame size
                    audio_data = audio_data[: self.SAMPLES_PER_FRAME]
                elif audio_data.shape[0] < self.SAMPLES_PER_FRAME:
                    # Pad with silence to reach frame size
                    padding = np.zeros(
                        (self.SAMPLES_PER_FRAME - audio_data.shape[0], self.CHANNELS),
                        dtype=audio_data.dtype,
                    )
                    audio_data = np.vstack((audio_data, padding))

                # Silence detection
                if self.enable_silence_detection:
                    rms = np.sqrt(np.mean(audio_data ** 2))
                    if rms < 100:  # Silence threshold (adjust as needed)
                        self._silence_frames += 1
                        # Still send silence to keep stream alive
            else:
                # No audio data available, send silence
                audio_data = np.zeros(
                    (self.SAMPLES_PER_FRAME, self.CHANNELS), dtype=np.int16
                )
                self._silence_frames += 1

            self._frame_count += 1

            # Log statistics periodically
            if self._frame_count % 100 == 0:
                buffer_size = len(self._audio_buffer)
                logger.debug(
                    f"Audio frame {self._frame_count}: buffer={buffer_size}, "
                    f"silence={self._silence_frames}"
                )

            # Create audio frame
            # aiortc expects audio frames in planar format
            # Convert interleaved (samples, channels) to planar (channels, samples)
            planar_data = audio_data.T.astype(np.int16)

            audio_frame = av.AudioFrame.from_ndarray(
                planar_data,
                format="s16",  # 16-bit signed integer
                layout="stereo",
            )

            # Set frame properties
            audio_frame.sample_rate = self._sample_rate
            audio_frame.pts = pts
            audio_frame.time_base = self._time_base

            return audio_frame

        except Exception as e:
            logger.error(f"Failed to create audio frame: {e}", exc_info=True)
            # Return silence on error
            silence = np.zeros((2, self.SAMPLES_PER_FRAME), dtype=np.int16)
            audio_frame = av.AudioFrame.from_ndarray(
                silence, format="s16", layout="stereo"
            )
            audio_frame.sample_rate = self._sample_rate
            audio_frame.pts = self._frame_count * self.SAMPLES_PER_FRAME
            audio_frame.time_base = self._time_base
            self._frame_count += 1
            return audio_frame

    def get_stats(self) -> dict:
        """
        Get current audio track statistics.
        
        Returns:
            Dictionary with frame count, buffer size, and silence ratio
        """
        stats = {
            "frame_count": self._frame_count,
            "sample_rate": self._sample_rate,
            "channels": self.CHANNELS,
            "buffer_size": len(self._audio_buffer),
            "silence_frames": self._silence_frames,
        }

        if self._frame_count > 0:
            stats["silence_ratio"] = self._silence_frames / self._frame_count

        if self._capture_times:
            stats["avg_capture_ms"] = float(np.mean(self._capture_times) * 1000)

        return stats

    def stop(self) -> None:
        """Stop the audio track and release resources."""
        logger.info(
            f"Stopping audio track. Total frames: {self._frame_count}, "
            f"silence: {self._silence_frames}"
        )

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                logger.info("Audio stream closed")
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")

        super().stop()