"""
WebRTC Peer Connection Manager for desktop agent.

Manages the WebRTC peer connection lifecycle including:
- Creating and configuring RTCPeerConnection
- Handling SDP offer/answer exchange via Socket.IO signaling
- ICE candidate gathering and exchange
- Attaching video and audio tracks
- Connection state monitoring

Signaling flow:
1. Agent receives offer from controller -> handle_offer()
2. Agent creates answer -> sends via Socket.IO
3. ICE candidates exchanged bidirectionally
4. Media streams flow directly via P2P WebRTC

Dependencies:
- aiortc: Python WebRTC implementation
- video_track: Desktop screen capture
- audio_track: System audio capture
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    RTCConfiguration,
    RTCIceServer,
    MediaStreamTrack,
)

from aiortc.sdp import candidate_from_sdp, candidate_to_sdp

from .video_track import DesktopVideoTrack
from .audio_track import DesktopAudioTrack

# Configure logging
logger = logging.getLogger(__name__)


class PeerConnectionManager:
    """
    Manages WebRTC peer connection for desktop streaming.
    
    Handles the complete WebRTC lifecycle:
    1. Creates peer connection with STUN/TURN configuration
    2. Attaches desktop video and audio tracks
    3. Manages SDP offer/answer exchange
    4. Processes ICE candidates for NAT traversal
    5. Monitors connection state changes
    
    Attributes:
        pc: The RTCPeerConnection instance
        video_track: Desktop screen capture track
        audio_track: System audio capture track
        signaling_callback: Callback for sending signaling messages via Socket.IO
    """

    def __init__(
        self,
        signaling_callback: Callable[[str, Dict[str, Any]], None],
        video_quality: str = "high",
        video_fps: int = 30,
        enable_audio: bool = True,
    ):
        """
        Initialize the PeerConnectionManager.
        
        Args:
            signaling_callback: Async callback function to send signaling messages
                               via Socket.IO. Takes event name and data dict.
            video_quality: Video quality setting ("low", "medium", "high")
            video_fps: Target frame rate (30 or 60 FPS)
            enable_audio: Whether to capture and stream system audio
        """
        self.signaling_callback = signaling_callback
        self.video_quality = video_quality
        self.video_fps = video_fps
        self.enable_audio = enable_audio

        # Core WebRTC components
        self.pc: Optional[RTCPeerConnection] = None
        self.video_track: Optional[DesktopVideoTrack] = None
        self.audio_track: Optional[DesktopAudioTrack] = None

        # Connection state
        self.is_connected = False
        self.device_id: Optional[str] = None
        self.controller_sid: Optional[str] = None

        # Event for tracking connection state
        self._connection_ready = asyncio.Event()

    def create_peer_connection(self) -> RTCPeerConnection:
        """
        Create and configure an RTCPeerConnection with STUN servers.
        
        STUN servers help discover the public IP address when behind NAT.
        For production, add TURN servers for relay fallback.
        
        Returns:
            Configured RTCPeerConnection instance
        """
        logger.info("Creating peer connection with STUN configuration")

        # Configure ICE servers for NAT traversal
        ice_servers = [
            RTCIceServer(
                urls=["stun:stun.l.google.com:19302"]
            ),
            # Add TURN servers for better connectivity in restrictive networks
            # RTCIceServer(
            #     urls=["turn:your-turn-server.com:3478"],
            #     username="username",
            #     credential="password"
            # ),
        ]

        config = RTCConfiguration(iceServers=ice_servers)

        # Create peer connection
        self.pc = RTCPeerConnection(configuration=config)

        # Register event handlers
        @self.pc.on("track")
        async def on_track(track: MediaStreamTrack):
            """
            Handle incoming media tracks from remote peer.
            Called when the remote controller adds tracks to the connection.
            Note: For desktop agent, we're the sender, so this may not be used,
            but kept for potential bidirectional features.
            """
            logger.info(f"Track received: {track.kind}")

        @self.pc.on("connectionstatechange")
        async def on_connection_state_change():
            """
            Monitor peer connection state changes.
            
            States:
            - new: Initial state
            - connecting: ICE connectivity checks in progress
            - connected: P2P connection established
            - disconnected: Connection lost, may recover
            - failed: Unrecoverable failure
            - closed: Connection terminated
            """
            if self.pc:
                state = self.pc.connectionState
                logger.info(f"Connection state changed to: {state}")

                if state == "connected":
                    logger.info("WebRTC peer connection established successfully")
                    self.is_connected = True
                    self._connection_ready.set()
                elif state == "failed":
                    logger.error("WebRTC peer connection failed")
                    self.is_connected = False
                    self._connection_ready.clear()
                elif state == "closed":
                    logger.info("WebRTC peer connection closed")
                    self.is_connected = False
                    self._connection_ready.clear()
                elif state == "disconnected":
                    logger.warning("WebRTC peer connection lost, attempting recovery")
                    self.is_connected = False

        @self.pc.on("iceconnectionstatechange")
        async def on_ice_connection_state_change():
            """Monitor ICE connection state for debugging NAT traversal."""
            if self.pc:
                ice_state = self.pc.iceConnectionState
                logger.debug(f"ICE connection state: {ice_state}")

        @self.pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate:
                await self.send_ice_candidate(candidate)

        @self.pc.on("icegatheringstatechange")
        async def on_ice_gathering_state_change():
            """Monitor ICE candidate gathering process."""
            if self.pc:
                gathering_state = self.pc.iceGatheringState
                logger.debug(f"ICE gathering state: {gathering_state}")

        logger.info("Peer connection created and configured")
        return self.pc

    async def create_offer(self) -> None:
        """
        Create and send a WebRTC offer to the controller.
        
        Flow:
        1. Create peer connection
        2. Add local media tracks (video + audio)
        3. Create SDP offer
        4. Set local description
        5. Send offer to controller via signaling
        
        This is typically initiated by the agent when the controller
        requests to start streaming.
        """
        logger.info("Creating WebRTC offer")

        try:
            # Create peer connection if not exists
            if not self.pc:
                self.create_peer_connection()

            # Add desktop video track
            logger.info(f"Adding desktop video track (quality: {self.video_quality}, FPS: {self.video_fps})")
            self.video_track = DesktopVideoTrack(
                quality=self.video_quality,
                fps=self.video_fps,
            )
            self.pc.addTrack(self.video_track)

            # Add desktop audio track if enabled
            if self.enable_audio:
                logger.info("Adding desktop audio track")
                self.audio_track = DesktopAudioTrack()
                self.pc.addTrack(self.audio_track)

            # Create SDP offer
            logger.info("Creating SDP offer")
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)

            # Send offer via signaling
            logger.info("Sending offer via signaling callback")
            self.signaling_callback("webrtc_answer", {
                "device_id": self.device_id,
                "answer": {
                    "type": self.pc.localDescription.type,
                    "sdp": self.pc.localDescription.sdp,
                },
                "controller_sid": self.controller_sid,
            })

            logger.info("WebRTC offer created and sent successfully")

        except Exception as e:
            logger.error(f"Failed to create offer: {e}", exc_info=True)
            raise

    async def handle_offer(self, offer_sdp: str, offer_type: str) -> None:
        """
        Handle an incoming WebRTC offer from the controller.
        
        This is the primary flow where:
        1. Controller initiates WebRTC connection
        2. Controller sends SDP offer
        3. Agent processes offer and creates answer
        
        Args:
            offer_sdp: The SDP offer string from controller
            offer_type: The SDP type (usually "offer")
        """
        logger.info("Handling incoming WebRTC offer from controller")

        try:
            # Create peer connection if not exists
            if not self.pc:
                self.create_peer_connection()

            # Set remote description from offer
            logger.debug("Setting remote description from offer")
            remote_offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
            await self.pc.setRemoteDescription(remote_offer)

            # Add desktop video track
            logger.info(f"Adding desktop video track (quality: {self.video_quality}, FPS: {self.video_fps})")
            self.video_track = DesktopVideoTrack(
                quality=self.video_quality,
                fps=self.video_fps,
            )
            self.pc.addTrack(self.video_track)

            # Add desktop audio track if enabled
            if self.enable_audio:
                logger.info("Adding desktop audio track")
                self.audio_track = DesktopAudioTrack()
                self.pc.addTrack(self.audio_track)

            # Create SDP answer
            logger.info("Creating SDP answer")
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)

            # Send answer via signaling
            logger.info("Sending answer via signaling callback")
            self.signaling_callback("webrtc_answer", {
                "device_id": self.device_id,
                "answer": {
                    "type": self.pc.localDescription.type,
                    "sdp": self.pc.localDescription.sdp,
                },
                "controller_sid": self.controller_sid,
            })

            logger.info("WebRTC answer created and sent successfully")

        except Exception as e:
            logger.error(f"Failed to handle offer: {e}", exc_info=True)
            raise

    async def handle_answer(self, answer_sdp: str, answer_type: str) -> None:
        """
        Handle an incoming WebRTC answer from the controller.
        
        Used when the agent initiated the offer and is now
        processing the controller's answer.
        
        Args:
            answer_sdp: The SDP answer string from controller
            answer_type: The SDP type (usually "answer")
        """
        logger.info("Handling incoming WebRTC answer from controller")

        try:
            if not self.pc:
                logger.error("Cannot handle answer - no peer connection exists")
                raise RuntimeError("Peer connection not initialized")

            # Set remote description from answer
            logger.debug("Setting remote description from answer")
            remote_answer = RTCSessionDescription(sdp=answer_sdp, type=answer_type)
            await self.pc.setRemoteDescription(remote_answer)

            logger.info("WebRTC answer processed successfully")

        except Exception as e:
            logger.error(f"Failed to handle answer: {e}", exc_info=True)
            raise

    async def add_ice_candidate(
        self,
        candidate: str,
        sdp_mid: Optional[str],
        sdp_mline_index: Optional[int],
    ) -> None:
        """
        Add an ICE candidate received from the remote peer via signaling.
        
        ICE (Interactive Connectivity Establishment) candidates are
        potential network paths for the P2P connection. Multiple
        candidates are gathered and tested to find the best path.
        
        Args:
            candidate: The ICE candidate string
            sdp_mid: Media stream identification tag
            sdp_mline_index: Media line index in SDP
        """
        try:
            if not self.pc:
                logger.warning("Received ICE candidate but no peer connection exists")
                return

            # Parse and add ICE candidate
            logger.debug(f"Adding ICE candidate: {candidate[:50]}...")
            ice_candidate = candidate_from_sdp(candidate)
            ice_candidate.sdpMid = sdp_mid
            ice_candidate.sdpMLineIndex = sdp_mline_index

            await self.pc.addIceCandidate(ice_candidate)
            logger.debug("ICE candidate added successfully")

        except Exception as e:
            logger.error(f"Failed to add ICE candidate: {e}", exc_info=True)

    async def send_ice_candidate(self, candidate: RTCIceCandidate) -> None:
        """
        Send a locally gathered ICE candidate to the remote peer.
        
        Called automatically by aiortc when local ICE candidates
        are discovered during the gathering process.
        
        Args:
            candidate: The locally gathered ICE candidate
        """
        try:
            if not candidate:
                return

            # Format candidate for signaling
            candidate_data = {
                "device_id": self.device_id,
                "candidate": {
                    "candidate": candidate_to_sdp(candidate),
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                },
                "target": "controller",
                "target_sid": self.controller_sid,
            }

            logger.debug(f"Sending ICE candidate: {candidate.candidate[:50]}...")
            self.signaling_callback("webrtc_ice_candidate", candidate_data)

        except Exception as e:
            logger.error(f"Failed to send ICE candidate: {e}", exc_info=True)

    async def close(self) -> None:
        """
        Close the WebRTC peer connection and cleanup resources.
        
        Stops media tracks, closes the peer connection,
        and resets all state.
        """
        logger.info("Closing WebRTC peer connection")

        try:
            # Stop video track
            if self.video_track:
                logger.debug("Stopping video track")
                self.video_track.stop()
                self.video_track = None

            # Stop audio track
            if self.audio_track:
                logger.debug("Stopping audio track")
                self.audio_track.stop()
                self.audio_track = None

            # Close peer connection
            if self.pc:
                logger.debug("Closing peer connection")
                await self.pc.close()
                self.pc = None

            # Reset connection state
            self.is_connected = False
            self._connection_ready.clear()

            logger.info("WebRTC peer connection closed successfully")

        except Exception as e:
            logger.error(f"Error closing peer connection: {e}", exc_info=True)

    def set_session_info(self, device_id: str, controller_sid: str) -> None:
        """
        Set the session information for signaling.
        
        Args:
            device_id: The device ID for this agent
            controller_sid: The controller's Socket.IO session ID
        """
        self.device_id = device_id
        self.controller_sid = controller_sid
        logger.info(f"Session info set - Device: {device_id}, Controller: {controller_sid}")

    async def wait_for_connection(self, timeout: float = 30.0) -> bool:
        """
        Wait for the WebRTC connection to be established.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if connection established, False on timeout
        """
        try:
            await asyncio.wait_for(self._connection_ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout after {timeout} seconds")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current connection statistics.
        
        Returns:
            Dictionary containing connection state and track information
        """
        return {
            "connected": self.is_connected,
            "connection_state": self.pc.connectionState if self.pc else "none",
            "ice_state": self.pc.iceConnectionState if self.pc else "none",
            "video_track_active": self.video_track is not None,
            "audio_track_active": self.audio_track is not None,
            "device_id": self.device_id,
            "controller_sid": self.controller_sid,
        }


