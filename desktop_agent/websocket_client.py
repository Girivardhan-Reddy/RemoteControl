"""Socket.IO client for the desktop agent."""

from __future__ import annotations

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

LOGGER = get_logger(__name__)


class AgentSocketClient:
    """Reconnectable Socket.IO desktop agent client."""

    def __init__(self, config: AgentConfig, auth_client: AuthClient) -> None:
        self.config = config
        self.auth_client = auth_client
        self.sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
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
        self.streaming = False
        self.session_id: str | None = None
        self._register_handlers()

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
        tokens = self.auth_client.load_tokens() or self.auth_client.refresh()
        device = self.auth_client.load_device() or self.auth_client.register_device()
        self.sio.connect(self.config.server_url, transports=["websocket"])
        self.sio.emit("agent_connect", {"token": tokens["access_token"], "device_id": device["id"]})
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def _register_handlers(self) -> None:
        @self.sio.event
        def connect():
            LOGGER.info("Connected to backend Socket.IO")

        @self.sio.event
        def disconnect():
            LOGGER.warning("Disconnected from backend Socket.IO")
            self.streaming = False

        @self.sio.on("controller_ready")
        def controller_ready(data):
            self.session_id = (data or {}).get("session_id")
            LOGGER.info("Controller ready for session %s", self.session_id)

        @self.sio.on("remote_command")
        def remote_command(data):
            self._handle_command(data or {})

    def _heartbeat_loop(self) -> None:
        while self.sio.connected:
            try:
                device = self.auth_client.load_device()
                if device:
                    self.sio.emit("agent_heartbeat", {"device_id": device["id"]})
                    self.auth_client.heartbeat()
            except Exception as exc:
                LOGGER.warning("Heartbeat failed: %s", exc)
            time.sleep(self.config.heartbeat_interval_seconds)

    def _stream_loop(self) -> None:
        while self.streaming and self.sio.connected:
            try:
                frame = self.screen.capture_frame()
                self.sio.emit("agent_frame", {"session_id": self.session_id, **frame.__dict__})
            except Exception as exc:
                LOGGER.exception("Frame capture failed: %s", exc)
            time.sleep(self.screen.frame_interval())

    def _handle_command(self, command: dict) -> None:
        command_type = command.get("type")
        self.session_id = command.get("session_id") or self.session_id
        try:
            if command_type == "screen_start":
                self.streaming = True
                threading.Thread(target=self._stream_loop, daemon=True).start()
                result = {"ok": True}
            elif command_type == "screen_stop":
                self.streaming = False
                result = {"ok": True}
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
                result = self.startup.enable() if command.get("enabled") else self.startup.disable()
            elif command_type == "network":
                result = self.network.status()
            elif command_type == "update":
                result = self.update.download(str(command.get("url", "")), str(command.get("sha256", "")))
            else:
                result = {"ok": False, "error": "Unsupported command type."}
        except Exception as exc:
            LOGGER.exception("Command failed")
            result = {"ok": False, "error": str(exc)}
        self.sio.emit("agent_event", {"session_id": self.session_id, "type": command_type, "result": result})

    def _handle_files(self, command: dict) -> dict:
        action = command.get("action")
        if action == "drives":
            return self.files.drives()
        if action == "browse":
            return self.files.browse(str(command.get("path", "")))
        if action == "download_chunk":
            return self.files.download_chunk(str(command.get("path", "")), int(command.get("offset", 0)))
        if action == "upload_chunk":
            return self.files.upload_chunk(str(command.get("path", "")), str(command.get("data", "")), int(command.get("offset", 0)), bool(command.get("final", False)))
        if action == "delete":
            return self.files.delete(str(command.get("path", "")))
        if action == "rename":
            return self.files.rename(str(command.get("path", "")), str(command.get("new_name", "")))
        if action == "copy":
            return self.files.copy(str(command.get("src", "")), str(command.get("dst", "")))
        if action == "move":
            return self.files.move(str(command.get("src", "")), str(command.get("dst", "")))
        if action == "create_folder":
            return self.files.create_folder(str(command.get("path", "")))
        return {"ok": False, "error": "Unsupported file action."}
