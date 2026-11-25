"""Developer Assistant UI panel for JARVIS."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QTextEdit, QFileDialog,
)
from PySide6.QtCore import Qt, QThread, Signal

BTN  = "background:#1E293B;color:#38BDF8;border:1px solid #0284C7;border-radius:5px;padding:6px 12px;"
VIEW = "background:#0B0F19;color:#E2E8F0;border:1px solid #1F2937;border-radius:6px;padding:10px;font-size:12px;font-family:Consolas,'Courier New',monospace;"
LBL  = "color:#94A3B8;font-size:11px;font-weight:600;letter-spacing:1px;padding:4px 0;"


class _ScanWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, root: Path):
        super().__init__()
        self.root = root

    def run(self):
        try:
            import os
            from developer.project_scanner import scan_projects
            projects = scan_projects(self.root)
            self.done.emit({str(k): v for k, v in projects.items()})
        except Exception as e:
            self.error.emit(str(e))


class _LintWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, path: Path, ptype: str):
        super().__init__()
        self.path = path
        self.ptype = ptype

    def run(self):
        try:
            from developer.project_scanner import run_lint
            result = run_lint(self.path, self.ptype)
            self.done.emit(result or "✓ No issues found.")
        except Exception as e:
            self.error.emit(str(e))


class DeveloperPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._projects: dict = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("👨‍💻 DEVELOPER ASSISTANT")
        title.setStyleSheet("color:#F8FAFC;font-size:18px;font-weight:800;letter-spacing:1px;")
        layout.addWidget(title)

        # Scan bar
        scan_row = QHBoxLayout()
        self.btn_pick = QPushButton("📂 Choose Root Folder")
        self.btn_pick.setStyleSheet(BTN)
        self.btn_pick.clicked.connect(self._pick_folder)
        self.btn_scan = QPushButton("🔍 Scan for Projects")
        self.btn_scan.setStyleSheet(BTN)
        self.btn_scan.clicked.connect(self._scan)
        scan_row.addWidget(self.btn_pick)
        scan_row.addWidget(self.btn_scan)
        scan_row.addStretch()
        layout.addLayout(scan_row)

        self.root_lbl = QLabel("No folder selected.")
        self.root_lbl.setStyleSheet(LBL)
        layout.addWidget(self.root_lbl)

        # Project list
        layout.addWidget(QLabel("Detected Projects:", styleSheet=LBL))
        self.project_list = QListWidget()
        self.project_list.setStyleSheet("background:#0B0F19;color:#E2E8F0;border:none;font-size:12px;")
        self.project_list.setMaximumHeight(160)
        layout.addWidget(self.project_list)

        # Actions row
        act_row = QHBoxLayout()
        self.btn_lint = QPushButton("🧹 Run Lint")
        self.btn_lint.setStyleSheet(BTN)
        self.btn_lint.clicked.connect(self._run_lint)
        self.btn_git = QPushButton("🌿 Git Status")
        self.btn_git.setStyleSheet(BTN)
        self.btn_git.clicked.connect(self._git_status)
        act_row.addWidget(self.btn_lint)
        act_row.addWidget(self.btn_git)
        act_row.addStretch()
        layout.addLayout(act_row)

        # Output view
        layout.addWidget(QLabel("Output:", styleSheet=LBL))
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setStyleSheet(VIEW)
        layout.addWidget(self.output_view, 1)

        self._root: Path | None = None

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select project root folder")
        if folder:
            self._root = Path(folder)
            self.root_lbl.setText(f"Root: {self._root}")

    def _scan(self):
        if not self._root:
            self.output_view.setPlainText("Please choose a root folder first.")
            return
        self.output_view.setPlainText("Scanning…")
        self._scan_worker = _ScanWorker(self._root)
        self._scan_worker.done.connect(self._show_projects)
        self._scan_worker.error.connect(lambda e: self.output_view.setPlainText(f"Error: {e}"))
        self._scan_worker.start()

    def _show_projects(self, projects: dict):
        self._projects = projects
        self.project_list.clear()
        if not projects:
            self.output_view.setPlainText("No projects detected.")
            return
        for path, types in projects.items():
            label = f"{Path(path).name}  [{', '.join(types)}]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (path, types))
            self.project_list.addItem(item)
        self.output_view.setPlainText(
            f"Found {len(projects)} project(s).\nSelect one and click 'Run Lint' or 'Git Status'."
        )

    def _selected_project(self):
        item = self.project_list.currentItem()
        if not item:
            self.output_view.setPlainText("Please select a project from the list first.")
            return None, None
        return item.data(Qt.UserRole)

    def _run_lint(self):
        path_str, types = self._selected_project()
        if not path_str:
            return
        ptype = "python" if "python" in types else ("node" if "node" in types else types[0] if types else "python")
        self.output_view.setPlainText(f"Running lint on {path_str} ({ptype})…")
        self._lint_worker = _LintWorker(Path(path_str), ptype)
        self._lint_worker.done.connect(self.output_view.setPlainText)
        self._lint_worker.error.connect(lambda e: self.output_view.setPlainText(f"Lint error: {e}"))
        self._lint_worker.start()

    def _git_status(self):
        path_str, _ = self._selected_project()
        if not path_str:
            return
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status"], cwd=path_str,
                capture_output=True, text=True, timeout=10
            )
            self.output_view.setPlainText(result.stdout or result.stderr or "No git output.")
        except FileNotFoundError:
            self.output_view.setPlainText("git not found. Install Git for Windows.")
        except Exception as e:
            self.output_view.setPlainText(f"Git error: {e}")
