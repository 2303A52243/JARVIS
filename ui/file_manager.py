# """File Manager UI for JARVIS.
# Provides a searchable view of authorized files and basic operations (copy, move, rename, delete).
# Uses the existing file management tools defined in the `files` package.
# """

from __future__ import annotations

import os
from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, Signal

# Import tool functions – these are thin wrappers around the backend implementations.
from files.file_search import search_files
from files.file_operations import copy_file, move_file, rename_file, delete_file
from files.folder_permissions import is_path_authorized


class FileManagerPanel(QWidget):
    """Main panel displayed as a tab in the JARVIS MainWindow.

    Features:
    - Search files by name/extension within authorized folders.
    - Display results in a list; selecting an entry shows the full path.
    - Buttons for Copy, Move, Rename, Delete, and Refresh.
    - All operations go through the permission system and request user confirmation.
    """

    # Emitted when a file operation succeeded – UI can listen to show a brief toast.
    operation_completed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("file_manager_panel")
        self._init_ui()
        self._connect_signals()
        # Do NOT auto-scan on startup – user must click Search or Refresh

    # ---------------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------------
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files (name or extension)…")
        self.search_btn = QPushButton("Search")
        self.refresh_btn = QPushButton("Refresh")
        search_layout.addWidget(self.search_input, stretch=1)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.refresh_btn)
        layout.addLayout(search_layout)

        # Result list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.file_list, stretch=1)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy")
        self.move_btn = QPushButton("Move")
        self.rename_btn = QPushButton("Rename")
        self.delete_btn = QPushButton("Delete")
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.move_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

    # ---------------------------------------------------------------------
    # Signal wiring
    # ---------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.search_btn.clicked.connect(self.perform_search)
        self.refresh_btn.clicked.connect(self.refresh_file_list)
        self.copy_btn.clicked.connect(self.copy_selected)
        self.move_btn.clicked.connect(self.move_selected)
        self.rename_btn.clicked.connect(self.rename_selected)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.file_list.itemDoubleClicked.connect(self._show_path_message)

    # ---------------------------------------------------------------------
    # Helper utilities
    # ---------------------------------------------------------------------
    def _current_selected_path(self) -> str | None:
        item = self.file_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _show_path_message(self, item: QListWidgetItem) -> None:
        """Show a small modal with the absolute path of the double‑clicked file."""
        path = item.data(Qt.UserRole)
        QMessageBox.information(self, "File Path", f"{path}")

    # ---------------------------------------------------------------------
    # Core actions
    # ---------------------------------------------------------------------
    def refresh_file_list(self) -> None:
        """Reload the full file list (no filter)."""
        self.file_list.clear()
        # An empty query returns everything inside authorized folders.
        files = search_files(query="", max_depth=5)
        for f in files:
            self._add_file_item(f)
        self.operation_completed.emit("File list refreshed")

    def perform_search(self) -> None:
        query = self.search_input.text().strip()
        self.file_list.clear()
        files = search_files(query=query, max_depth=5)
        for f in files:
            self._add_file_item(f)
        self.operation_completed.emit(f"Search completed ({len(files)} result(s))")

    def _add_file_item(self, file_path: str) -> None:
        # Display only the file name, store the absolute path as user data.
        filename = os.path.basename(file_path)
        item = QListWidgetItem(filename)
        item.setToolTip(file_path)
        item.setData(Qt.UserRole, file_path)
        self.file_list.addItem(item)

    # ---------------------------------------------------------------------
    # File operations – each asks for confirmation and validates the permission.
    # ---------------------------------------------------------------------
    def _confirm_action(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

    def copy_selected(self) -> None:
        src = self._current_selected_path()
        if not src:
            return
        if not is_path_authorized(src):
            QMessageBox.warning(self, "Permission denied", "Selected file is outside authorized folders.")
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if not dest_dir:
            return
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not self._confirm_action("Copy file", f"Copy\n{src}\n→\n{dest}?"):
            return
        try:
            copy_file(src_path=src, dest_path=dest)
            QMessageBox.information(self, "Success", f"Copied to {dest}")
            self.refresh_file_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def move_selected(self) -> None:
        src = self._current_selected_path()
        if not src:
            return
        if not is_path_authorized(src):
            QMessageBox.warning(self, "Permission denied", "Selected file is outside authorized folders.")
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if not dest_dir:
            return
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not self._confirm_action("Move file", f"Move\n{src}\n→\n{dest}?"):
            return
        try:
            move_file(src_path=src, dest_path=dest)
            QMessageBox.information(self, "Success", f"Moved to {dest}")
            self.refresh_file_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def rename_selected(self) -> None:
        src = self._current_selected_path()
        if not src:
            return
        if not is_path_authorized(src):
            QMessageBox.warning(self, "Permission denied", "Selected file is outside authorized folders.")
            return
        new_name, ok = QFileDialog.getSaveFileName(self, "Rename – choose new name", src)
        if not ok or not new_name:
            return
        if not self._confirm_action("Rename file", f"Rename\n{src}\n→\n{new_name}?"):
            return
        try:
            rename_file(src_path=src, new_path=new_name)
            QMessageBox.information(self, "Success", f"Renamed to {new_name}")
            self.refresh_file_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self) -> None:
        src = self._current_selected_path()
        if not src:
            return
        if not is_path_authorized(src):
            QMessageBox.warning(self, "Permission denied", "Selected file is outside authorized folders.")
            return
        if not self._confirm_action("Delete file", f"Delete\n{src}\n? This action cannot be undone."):
            return
        try:
            delete_file(path=src)
            QMessageBox.information(self, "Deleted", f"{src} removed")
            self.refresh_file_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
