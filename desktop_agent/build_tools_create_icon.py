"""Generate a Windows ICO file for packaging."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    """Create resources/icons/app_icon.ico."""
    icon_dir = Path("resources") / "icons"
    icon_dir.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (256, 256), (13, 17, 23, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((42, 54, 214, 166), radius=14, fill=(22, 27, 34, 255), outline=(88, 166, 255, 255), width=10)
    draw.rounded_rectangle((72, 84, 184, 102), radius=9, fill=(46, 160, 67, 255))
    draw.rounded_rectangle((72, 116, 144, 134), radius=9, fill=(31, 111, 235, 255))
    draw.line((128, 166, 128, 202), fill=(201, 209, 217, 255), width=14)
    draw.line((98, 202, 158, 202), fill=(201, 209, 217, 255), width=14)
    image.save(icon_dir / "app_icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
