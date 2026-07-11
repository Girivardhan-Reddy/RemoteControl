"""GUI file manager page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from file_manager import FileManager


class FileManagerPage(QWidget):
    """Split-view local and remote file manager controls."""

    def __init__(self, file_manager: FileManager) -> None:
        super().__init__()
        self.file_manager = file_manager
        self.local_model = QFileSystemModel()
        self.local_model.setRootPath(str(Path.home()))
        self.local_tree = QTreeView()
        self.local_tree.setModel(self.local_model)
        self.local_tree.setRootIndex(self.local_model.index(str(Path.home())))
        self.remote_output = QLabel("Remote files appear here after a controller requests browse operations.")
        self.remote_output.setAlignment(Qt.AlignTop)
        self.progress = QProgressBar()
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("File Manager")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        split = QHBoxLayout()
        local_box = QVBoxLayout()
        local_box.addWidget(QLabel("Local Files"))
        local_box.addWidget(self.local_tree)
        remote_box = QVBoxLayout()
        remote_box.addWidget(QLabel("Remote Files"))
        remote_box.addWidget(self.remote_output)
        split.addLayout(local_box)
        split.addLayout(remote_box)
        layout.addLayout(split)
        buttons = QHBoxLayout()
        upload = QPushButton("Upload")
        download = QPushButton("Download")
        rename = QPushButton("Rename")
        delete = QPushButton("Delete")
        new_folder = QPushButton("New Folder")
        for button in (upload, download, rename, delete, new_folder):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        upload.clicked.connect(self.copy_into_selected_folder)
        download.clicked.connect(self.copy_selected_to_destination)
        rename.clicked.connect(self.rename_selected)
        delete.clicked.connect(self.delete_selected)
        new_folder.clicked.connect(self.create_folder)

    def selected_path(self) -> Path:
        """Return the selected local path."""
        index = self.local_tree.currentIndex()
        return Path(self.local_model.filePath(index))

    def copy_into_selected_folder(self) -> None:
        """Copy a chosen file into the selected folder."""
        source, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not source:
            return
        target_dir = self.selected_path()
        if target_dir.is_file():
            target_dir = target_dir.parent
        result = self.file_manager.copy(source, str(target_dir / Path(source).name))
        self.progress.setValue(100 if result.get("ok") else 0)

    def copy_selected_to_destination(self) -> None:
        """Copy the selected file or folder to a chosen destination."""
        source = self.selected_path()
        destination = QFileDialog.getExistingDirectory(self, "Select Download Destination")
        if not destination:
            return
        result = self.file_manager.copy(str(source), str(Path(destination) / source.name))
        self.progress.setValue(100 if result.get("ok") else 0)

    def rename_selected(self) -> None:
        """Rename the selected file or folder."""
        source = self.selected_path()
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=source.name)
        if ok and name:
            self.file_manager.rename(str(source), name)

    def delete_selected(self) -> None:
        """Delete the selected file or empty folder after confirmation."""
        source = self.selected_path()
        if QMessageBox.question(self, "Delete", f"Delete {source}?") == QMessageBox.StandardButton.Yes:
            self.file_manager.delete(str(source))

    def create_folder(self) -> None:
        """Create a new folder under the selected folder."""
        base = self.selected_path()
        if base.is_file():
            base = base.parent
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            self.file_manager.create_folder(str(base / name))
