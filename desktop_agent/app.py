"""Desktop agent application entrypoint."""

from __future__ import annotations

import argparse
import getpass
import threading
import time

from auth import AuthClient
from config import APP_NAME, AgentConfig, ensure_directories
from logger import get_logger
from websocket_client import AgentSocketClient

LOGGER = get_logger(__name__)


def start_tray() -> None:
    """Start a simple visible tray indicator when optional dependencies exist."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception:
        LOGGER.info("System tray dependencies are unavailable; running without tray icon.")
        return

    image = Image.new("RGB", (64, 64), color="#1f6feb")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 46, 46), outline="white", width=4)

    def quit_agent(icon, item):
        icon.stop()
        raise SystemExit(0)

    icon = pystray.Icon(APP_NAME, image, APP_NAME, menu=pystray.Menu(pystray.MenuItem("Quit", quit_agent)))
    icon.run()


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments."""
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--server-url", help="Backend URL, for example https://example.onrender.com")
    parser.add_argument("--login", action="store_true", help="Prompt for login and register this computer")
    parser.add_argument("--no-tray", action="store_true", help="Run without a system tray icon")
    return parser


def main() -> int:
    """Run the desktop agent."""
    args = build_parser().parse_args()
    ensure_directories()
    config = AgentConfig(server_url=args.server_url) if args.server_url else AgentConfig()
    auth_client = AuthClient(config)

    if args.login or not auth_client.load_tokens():
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")
        auth_client.login(email, password)
        device = auth_client.register_device()
        print("Device registered. Pairing code:", device.get("pairing_code"))
        print("Use this code in your controller app to finish pairing.")

    agent = AgentSocketClient(config, auth_client)
    threading.Thread(target=agent.run_forever, daemon=True).start()
    if not args.no_tray:
        start_tray()
    else:
        while True:
            time.sleep(3600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
