"""Chunked file manager operations."""

from __future__ import annotations

import base64
import os
import shutil
from pathlib import Path

import psutil

from config import DOWNLOAD_DIR
from logger import get_logger

LOGGER = get_logger(__name__)
CHUNK_SIZE = 512 * 1024


class FileManager:
    """Provide safe local file operations for authorized remote sessions."""

    def drives(self) -> dict:
        """List available drives or mount points."""
        return {"ok": True, "drives": [partition.mountpoint for partition in psutil.disk_partitions(all=False)]}

    def browse(self, path: str) -> dict:
        """List a directory."""
        directory = Path(path).expanduser().resolve()
        if not directory.is_dir():
            return {"ok": False, "error": "Path is not a directory."}
        items = []
        for item in directory.iterdir():
            try:
                stat = item.stat()
                items.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    },
                )
            except OSError as exc:
                LOGGER.warning("Cannot stat %s: %s", item, exc)
        return {"ok": True, "path": str(directory), "items": items}

    def download_chunk(self, path: str, offset: int = 0, size: int = CHUNK_SIZE) -> dict:
        """Read a base64 chunk for download."""
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            return {"ok": False, "error": "Path is not a file."}
        with file_path.open("rb") as handle:
            handle.seek(max(0, int(offset)))
            data = handle.read(min(int(size), CHUNK_SIZE))
        return {
            "ok": True,
            "path": str(file_path),
            "offset": offset,
            "size": len(data),
            "total": file_path.stat().st_size,
            "data": base64.b64encode(data).decode("ascii"),
        }

    def upload_chunk(self, path: str, data_b64: str, offset: int = 0, final: bool = False) -> dict:
        """Write a base64 upload chunk."""
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        data = base64.b64decode(data_b64)
        mode = "r+b" if target.exists() else "wb"
        with target.open(mode) as handle:
            handle.seek(max(0, int(offset)))
            handle.write(data)
        return {"ok": True, "path": str(target), "received": len(data), "final": bool(final)}

    def delete(self, path: str) -> dict:
        """Delete a file or empty directory."""
        target = Path(path).expanduser().resolve()
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        return {"ok": True}

    def rename(self, path: str, new_name: str) -> dict:
        """Rename a file within its current directory."""
        target = Path(path).expanduser().resolve()
        renamed = target.with_name(new_name)
        target.rename(renamed)
        return {"ok": True, "path": str(renamed)}

    def copy(self, src: str, dst: str) -> dict:
        """Copy a file or directory."""
        source = Path(src).expanduser().resolve()
        destination = Path(dst).expanduser().resolve()
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return {"ok": True, "path": str(destination)}

    def move(self, src: str, dst: str) -> dict:
        """Move a file or directory."""
        destination = shutil.move(str(Path(src).expanduser().resolve()), str(Path(dst).expanduser().resolve()))
        return {"ok": True, "path": destination}

    def create_folder(self, path: str) -> dict:
        """Create a folder."""
        Path(path).expanduser().resolve().mkdir(parents=True, exist_ok=True)
        return {"ok": True}

    def default_download_dir(self) -> dict:
        """Return the agent download directory."""
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "path": str(DOWNLOAD_DIR)}
