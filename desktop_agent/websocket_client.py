"""Socket.IO client for the desktop agent with WebRTC support."""

from __future__ import annotations

import asyncio
import threading
import time

import socketio

from auth import AuthClient
from clipboard import ClipboardManager
from config import AgentConfig
from file_manager import FileManager
from keyboard import KeyboardController
from logger import get_logger
from mouse import MouseController
from network import NetworkMonitor
from power import PowerManager
from screen import ScreenStreamer
from startup import StartupManager
from system_info import SystemInfo
from update import UpdateManager
from webrtc.peer_connection import PeerConnectionManager

LOGGER = get_logger(__name__)


class AgentSocketClient:
    """Reconnectable Socket.IO desktop agent client with WebRTC support."""

    def __init__(self, config: AgentConfig, auth_client: AuthClient) -> None:
        self.config = config
        self.auth_client = auth_client
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=1, reconnection_delay_max=10, logger=False, engineio_logger=False)
        
        # Feature modules
        self.screen = ScreenStreamer(config)
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.clipboard = ClipboardManager()
        self.files = FileManager()
        self.system = SystemInfo()
        self.power = PowerManager(config)
        self.startup = StartupManager()
        self.network = NetworkMonitor(config)
        self.update = UpdateManager(config)
        
        # Event loop for async WebRTC operations
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._event_loop_thread: threading.Thread | None = None
        
        # Session state
        self.session_id: str | None = None
        self.device_id: str | None = None
        self.controller_sid: str | None = None
        self.streaming = False
        self._heartbeat_thread: threading.Thread | None = None
        
        # Start event loop first (needed before webrtc init)
        self._start_event_loop()
        
        # Initialize WebRTC manager after event loop is running
        self.webrtc = PeerConnectionManager(
            signaling_callback=self._send_signaling_message,
            video_quality="high",
            video_fps=30,
            enable_audio=True,
        )
        
        # Register Socket.IO event handlers
        self._register_handlers()

    def _start_event_loop(self) -> None:
        """Start asyncio event loop in background thread for WebRTC operations."""
        def run_event_loop():
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            self._event_loop.run_forever()
        
        self._event_loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        self._event_loop_thread.start()
        LOGGER.info("Async event loop started for WebRTC operations")
        
    def _run_async(self, coro):
        """Run coroutine in the WebRTC event loop."""
        if self._event_loop and self._event_loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._event_loop)
        else:
            LOGGER.warning("Event loop not running, cannot execute async operation")

    def _send_signaling_message(self, event: str, data: dict) -> None:
        """
        Send WebRTC signaling message via Socket.IO.
        
        This callback is used by PeerConnectionManager to send
        SDP offers, answers, and ICE candidates to the backend.
        
        Args:
            event: Socket.IO event name
            data: Signaling message payload
        """
        try:
            if self.sio and self.sio.connected:
                # Add authentication token to all signaling messages
                data["token"] = self.auth_client.access_token()
                self.sio.emit(event, data)
                LOGGER.debug(f"Signaling message sent: {event}")
            else:
                LOGGER.warning(f"Cannot send signaling message - not connected: {event}")
        except Exception as exc:
            LOGGER.exception(f"Failed to send signaling message: {exc}")

    def run_forever(self) -> None:
        """Connect and reconnect forever."""
        while True:
            try:
                self._connect_once()
                self.sio.wait()
            except Exception as exc:
                LOGGER.error("Socket connection failed: %s", exc)
                time.sleep(self.config.reconnect_delay_seconds)

    def _connect_once(self) -> None:
        """Establish Socket.IO connection and register agent."""
        token = self.auth_client.access_token()
        device = self.auth_client.load_device() or self.auth_client.register_device()
        self.device_id = device.get("id")
        
        LOGGER.info(
            "Connecting Socket.IO to %s for device %s",
            self.config.server_url,
            self.device_id
        )
        
        self.sio.connect(
            self.config.server_url,
            transports=["websocket", "polling"],
            auth={"token": token},
        )
        
        self.sio.emit("agent_connect", {
            "token": token,
            "device_id": self.device_id
        })
        
        # Start heartbeat if not already running
        if not self._heartbeat_thread or not self._heartbeat_thread.is_alive():
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True
            )
            self._heartbeat_thread.start()

    def _register_handlers(self) -> None:
        """Register all Socket.IO event handlers."""
        
        @self.sio.event
        def connect():
            LOGGER.info("Connected to backend Socket.IO")

        @self.sio.event
        def disconnect():
            LOGGER.warning("Disconnected from backend Socket.IO")
            # Stop WebRTC streaming on disconnect
            self._run_async(self.webrtc.close())
            self.streaming = False

        @self.sio.on("controller_ready")
        def controller_ready(data):
            self.session_id = (data or {}).get("session_id")
            LOGGER.info("Controller ready for session %s", self.session_id)

        @self.sio.on("agent_connected")
        def agent_connected(data):
            device = (data or {}).get("device", {})
            LOGGER.info("Agent socket accepted for device %s", device.get("id"))

        @self.sio.on("pairing_required")
        def pairing_required(data):
            LOGGER.warning(
                "%s",
                (data or {}).get("message", "Device pairing is required.")
            )

        @self.sio.on("controller_connected")
        def controller_connected(data):
            """Handle new controller connection notification."""
            controller_sid = data.get("controller_sid")
            device_id = data.get("device_id")
            LOGGER.info(
                "Controller %s connected for device %s",
                controller_sid,
                device_id
            )

        @self.sio.on("remote_command")
        def remote_command(data):
            self._handle_command(data or {})

        # ============================================================
        # WebRTC Signaling Handlers
        # ============================================================
        
        @self.sio.on("webrtc_offer")
        def handle_webrtc_offer(data):
            """
            Handle incoming WebRTC offer from controller.
            
            Flow:
            1. Controller creates offer and sends via signaling
            2. Backend forwards offer to agent
            3. Agent processes offer and creates answer
            4. WebRTC P2P connection established
            """
            try:
                self.controller_sid = data.get("controller_sid")
                self.device_id = data.get("device_id") or self.device_id
                offer = data.get("offer")
                
                if offer and self.controller_sid:
                    LOGGER.info(
                        "Received WebRTC offer from controller %s",
                        self.controller_sid
                    )
                    
                    # Set session info for signaling
                    self.webrtc.set_session_info(self.device_id, self.controller_sid)
                    
                    # Process offer asynchronously
                    self._run_async(
                        self.webrtc.handle_offer(
                            offer.get("sdp"),
                            offer.get("type")
                        )
                    )
                else:
                    LOGGER.error("Invalid WebRTC offer received - missing offer or controller_sid")
                    
            except Exception as exc:
                LOGGER.exception("Error handling WebRTC offer: %s", exc)

        @self.sio.on("webrtc_answer")
        def handle_webrtc_answer(data):
            """
            Handle incoming WebRTC answer from controller.
            
            Used when agent initiated the offer (screen_start command).
            """
            try:
                answer = data.get("answer")
                if answer:
                    LOGGER.info("Received WebRTC answer from controller")
                    self._run_async(
                        self.webrtc.handle_answer(
                            answer.get("sdp"),
                            answer.get("type")
                        )
                    )
            except Exception as exc:
                LOGGER.exception("Error handling WebRTC answer: %s", exc)

        @self.sio.on("webrtc_ice_candidate")
        def handle_webrtc_ice_candidate(data):
            """
            Handle incoming ICE candidate from remote peer.
            
            ICE candidates are exchanged to find the best network path
            for the P2P connection.
            """
            try:
                candidate = data.get("candidate")
                if candidate:
                    LOGGER.debug("Received ICE candidate")
                    self._run_async(
                        self.webrtc.add_ice_candidate(
                            candidate.get("candidate"),
                            candidate.get("sdpMid"),
                            candidate.get("sdpMLineIndex")
                        )
                    )
            except Exception as exc:
                LOGGER.exception("Error handling ICE candidate: %s", exc)

        @self.sio.on("controller_disconnected")
        def handle_controller_disconnected(data):
            """
            Handle controller disconnection.
            
            Cleans up WebRTC connection when controller disconnects.
            """
            try:
                controller_sid = data.get("controller_sid")
                LOGGER.info("Controller disconnected: %s", controller_sid)
                
                if controller_sid == self.controller_sid:
                    LOGGER.info("Active controller disconnected - stopping WebRTC")
                    self._run_async(self.webrtc.close())
                    self.streaming = False
                    self.controller_sid = None
                    
            except Exception as exc:
                LOGGER.exception("Error handling controller disconnect: %s", exc)

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to keep connection alive."""
        while True:
            try:
                if not self.sio.connected:
                    time.sleep(1)
                    continue
                device = self.auth_client.load_device()
                if device:
                    self.sio.emit("agent_heartbeat", {
                        "token": self.auth_client.access_token(),
                        "device_id": device["id"]
                    })
                    self.auth_client.heartbeat()
            except Exception as exc:
                LOGGER.warning("Heartbeat failed: %s", exc)
            time.sleep(self.config.heartbeat_interval_seconds)

    def _handle_command(self, command: dict) -> None:
        """
        Handle remote commands from controller.
        
        Commands include:
        - screen_start/stop: WebRTC streaming control
        - mouse/keyboard: Input control
        - clipboard: Copy/paste operations
        - files: File manager operations
        - system_info, power, network, update: System management
        """
        command_type = command.get("type")
        self.session_id = command.get("session_id") or self.session_id
        self.controller_sid = command.get("controller_sid") or self.controller_sid
        
        LOGGER.debug("Processing command: %s", command_type)
        
        try:
            if command_type == "screen_start":
                # Start WebRTC streaming
                result = self._handle_screen_start()
                    
            elif command_type == "screen_stop":
                # Stop WebRTC streaming
                result = self._handle_screen_stop()
                
            elif command_type == "mouse":
                result = self.mouse.handle(command)
                
            elif command_type == "keyboard":
                result = self.keyboard.handle(command)
                
            elif command_type == "clipboard_get":
                result = self.clipboard.get_text()
                
            elif command_type == "clipboard_set":
                result = self.clipboard.set_text(str(command.get("text", "")))
                
            elif command_type == "files":
                result = self._handle_files(command)
                
            elif command_type == "system_info":
                result = self.system.snapshot()
                
            elif command_type == "power":
                result = self.power.handle(str(command.get("action", "")))
                
            elif command_type == "startup":
                result = (
                    self.startup.enable()
                    if command.get("enabled")
                    else self.startup.disable()
                )
                
            elif command_type == "network":
                result = self.network.status()
                
            elif command_type == "update":
                result = self.update.download(
                    str(command.get("url", "")),
                    str(command.get("sha256", ""))
                )
                
            else:
                result = {"ok": False, "error": f"Unsupported command type: {command_type}"}
                LOGGER.warning("Unsupported command type: %s", command_type)
                
        except Exception as exc:
            LOGGER.exception("Command failed: %s", command_type)
            result = {"ok": False, "error": str(exc)}
            
        # Send result back to controller
        self.sio.emit("agent_event", {
            "token": self.auth_client.access_token(),
            "device_id": self.device_id,
            "controller_sid": self.controller_sid,
            "session_id": self.session_id,
            "type": command_type,
            "result": result
        })

    def _handle_screen_start(self) -> dict:
        """
        Start WebRTC screen streaming.
        
        Creates a WebRTC offer if controller is connected,
        which initiates the P2P streaming session.
        """
        if self.controller_sid and self.device_id:
            LOGGER.info("Starting WebRTC streaming for device %s", self.device_id)
            
            # Set session info for signaling
            self.webrtc.set_session_info(self.device_id, self.controller_sid)
            
            # Create and send offer asynchronously
            self._run_async(self.webrtc.create_offer())
            self.streaming = True
            
            return {
                "ok": True,
                "message": "WebRTC streaming initiated",
                "device_id": self.device_id,
                "controller_sid": self.controller_sid
            }
        else:
            LOGGER.error(
                "Cannot start streaming - no controller connected. "
                "controller_sid=%s, device_id=%s",
                self.controller_sid,
                self.device_id
            )
            return {
                "ok": False,
                "error": "No controller connected"
            }

    def _handle_screen_stop(self) -> dict:
        """Stop WebRTC screen streaming."""
        LOGGER.info("Stopping WebRTC streaming")
        self._run_async(self.webrtc.close())
        self.streaming = False
        
        return {
            "ok": True,
            "message": "Streaming stopped"
        }

    def _handle_files(self, command: dict) -> dict:
        """
        Handle file operations from controller.
        
        Supported actions:
        - drives: List available drives
        - browse: Browse directory contents
        - download_chunk: Download file chunk
        - upload_chunk: Upload file chunk
        - delete: Delete file/directory
        - rename: Rename file/directory
        - copy: Copy file/directory
        - move: Move file/directory
        - create_folder: Create new directory
        """
        action = command.get("action")
        
        if action == "drives":
            return self.files.drives()
        elif action == "browse":
            return self.files.browse(str(command.get("path", "")))
        elif action == "download_chunk":
            return self.files.download_chunk(
                str(command.get("path", "")),
                int(command.get("offset", 0))
            )
        elif action == "upload_chunk":
            return self.files.upload_chunk(
                str(command.get("path", "")),
                str(command.get("data", "")),
                int(command.get("offset", 0)),
                bool(command.get("final", False))
            )
        elif action == "delete":
            return self.files.delete(str(command.get("path", "")))
        elif action == "rename":
            return self.files.rename(
                str(command.get("path", "")),
                str(command.get("new_name", ""))
            )
        elif action == "copy":
            return self.files.copy(
                str(command.get("src", "")),
                str(command.get("dst", ""))
            )
        elif action == "move":
            return self.files.move(
                str(command.get("src", "")),
                str(command.get("dst", ""))
            )
        elif action == "create_folder":
            return self.files.create_folder(str(command.get("path", "")))
        else:
            return {"ok": False, "error": f"Unsupported file action: {action}"}

    def get_stats(self) -> dict:
        """
        Get current agent statistics.
        
        Returns:
            Dictionary with connection state, WebRTC stats, and session info
        """
        stats = {
            "connected": self.sio.connected if self.sio else False,
            "streaming": self.streaming,
            "session_id": self.session_id,
            "device_id": self.device_id,
            "controller_sid": self.controller_sid,
        }
        
        # Add WebRTC stats if available
        if self.webrtc:
            stats["webrtc"] = self.webrtc.get_stats()
            
        return stats

    def __del__(self):
        """Cleanup resources on destruction."""
        LOGGER.info("Cleaning up AgentSocketClient resources")
        
        try:
            # Stop WebRTC streaming
            if self.webrtc:
                asyncio.run_coroutine_threadsafe(
                    self.webrtc.close(),
                    self._event_loop
                ) if self._event_loop else None
            
            # Stop event loop
            if self._event_loop and self._event_loop.is_running():
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                
        except Exception as exc:
            LOGGER.error("Error during cleanup: %s", exc)


# ============================================================
# Legacy classes removed - now using webrtc/ module
# ============================================================
# ScreenVideoTrack -> webrtc/video_track.py: DesktopVideoTrack
# WebRTCManager -> webrtc/peer_connection.py: PeerConnectionManager


