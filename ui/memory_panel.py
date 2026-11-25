"""Memory Manager UI panel for JARVIS.

Lets the user view conversation history, add/search/delete notes,
view preferences and recent tasks – all backed by SQLite.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QPushButton, QLabel, QMessageBox, QSplitter,
)
from PySide6.QtCore import Qt


SECTION_STYLE = "color:#94A3B8; font-size:11px; font-weight:600; letter-spacing:1px; padding:4px 0;"
BTN_STYLE = """
    QPushButton {
        background:#1E293B; color:#94A3B8;
        border:1px solid #334155; border-radius:5px; padding:5px 10px; font-size:11px;
    }
    QPushButton:hover { background:#334155; color:#F8FAFC; }
"""
INPUT_STYLE = """
    QLineEdit, QTextEdit {
        background:#0B0F19; color:#E2E8F0;
        border:1px solid #1F2937; border-radius:6px;
        padding:6px; font-size:12px;
    }
"""


class MemoryPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._init_ui()
        self._load_all()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("🧠 MEMORY MANAGER")
        title.setStyleSheet("color:#F8FAFC; font-size:18px; font-weight:800; letter-spacing:1px;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_history_tab(), "💬 History")
        self.tabs.addTab(self._build_notes_tab(), "📝 Notes")
        self.tabs.addTab(self._build_prefs_tab(), "⚙ Preferences")
        self.tabs.addTab(self._build_tasks_tab(), "📋 Tasks")
        layout.addWidget(self.tabs)

    # ── History tab ──────────────────────────────────────────────────────────
    def _build_history_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("background:#0B0F19; color:#E2E8F0; border:none; font-size:12px;")
        lay.addWidget(self.history_list)
        btn_clear = QPushButton("🗑  Clear All History")
        btn_clear.setStyleSheet(BTN_STYLE)
        btn_clear.clicked.connect(self._clear_history)
        lay.addWidget(btn_clear)
        return w

    # ── Notes tab ────────────────────────────────────────────────────────────
    def _build_notes_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        # Search bar
        search_row = QHBoxLayout()
        self.note_search = QLineEdit(); self.note_search.setPlaceholderText("Search notes…")
        self.note_search.setStyleSheet(INPUT_STYLE)
        btn_search = QPushButton("Search"); btn_search.setStyleSheet(BTN_STYLE)
        btn_search.clicked.connect(self._search_notes)
        search_row.addWidget(self.note_search, 1); search_row.addWidget(btn_search)
        lay.addLayout(search_row)
        # List + preview splitter
        splitter = QSplitter(Qt.Horizontal)
        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet("background:#0B0F19; color:#E2E8F0; border:none; font-size:12px;")
        self.notes_list.currentItemChanged.connect(self._show_note)
        self.note_preview = QTextEdit(); self.note_preview.setReadOnly(True)
        self.note_preview.setStyleSheet(INPUT_STYLE)
        splitter.addWidget(self.notes_list); splitter.addWidget(self.note_preview)
        lay.addWidget(splitter, 1)
        # Add note form
        lay.addWidget(QLabel("New note:", styleSheet=SECTION_STYLE))
        self.note_title = QLineEdit(); self.note_title.setPlaceholderText("Title")
        self.note_title.setStyleSheet(INPUT_STYLE)
        self.note_body = QTextEdit(); self.note_body.setPlaceholderText("Body…")
        self.note_body.setStyleSheet(INPUT_STYLE); self.note_body.setMaximumHeight(80)
        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕ Add Note"); btn_add.setStyleSheet(BTN_STYLE)
        btn_add.clicked.connect(self._add_note)
        btn_del = QPushButton("🗑  Delete Selected"); btn_del.setStyleSheet(BTN_STYLE)
        btn_del.clicked.connect(self._delete_note)
        btn_row.addWidget(btn_add); btn_row.addWidget(btn_del)
        lay.addWidget(self.note_title); lay.addWidget(self.note_body); lay.addLayout(btn_row)
        return w

    # ── Preferences tab ──────────────────────────────────────────────────────
    def _build_prefs_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        self.prefs_view = QTextEdit(); self.prefs_view.setReadOnly(True)
        self.prefs_view.setStyleSheet(INPUT_STYLE)
        lay.addWidget(self.prefs_view)
        btn_refresh = QPushButton("🔄 Refresh"); btn_refresh.setStyleSheet(BTN_STYLE)
        btn_refresh.clicked.connect(self._load_prefs)
        lay.addWidget(btn_refresh)
        return w

    # ── Tasks tab ────────────────────────────────────────────────────────────
    def _build_tasks_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        self.tasks_view = QTextEdit(); self.tasks_view.setReadOnly(True)
        self.tasks_view.setStyleSheet(INPUT_STYLE)
        lay.addWidget(self.tasks_view)
        btn_refresh = QPushButton("🔄 Refresh"); btn_refresh.setStyleSheet(BTN_STYLE)
        btn_refresh.clicked.connect(self._load_tasks)
        lay.addWidget(btn_refresh)
        return w

    # ── Data loaders ─────────────────────────────────────────────────────────
    def _load_all(self):
        self._load_history()
        self._load_notes()
        self._load_prefs()
        self._load_tasks()

    def _load_history(self):
        from memory.database import get_history
        self.history_list.clear()
        for msg in get_history(limit=100):
            role = msg["role"].upper()
            text = msg["content"][:120].replace("\n", " ")
            self.history_list.addItem(f"[{role}] {text}")

    def _load_notes(self, query: str = ""):
        from memory.database import get_all_notes, search_notes
        self.notes_list.clear()
        self._notes_data = search_notes(query) if query else get_all_notes()
        for note in self._notes_data:
            item = QListWidgetItem(note["title"])
            item.setData(Qt.UserRole, note["id"])
            self.notes_list.addItem(item)

    def _search_notes(self):
        self._load_notes(self.note_search.text().strip())

    def _show_note(self, current, _previous):
        if not current:
            return
        note_id = current.data(Qt.UserRole)
        note = next((n for n in self._notes_data if n["id"] == note_id), None)
        if note:
            self.note_preview.setPlainText(
                f"Title: {note['title']}\nTags:  {note['tags']}\n\n{note['body']}"
            )

    def _add_note(self):
        from memory.database import add_note
        title = self.note_title.text().strip()
        body = self.note_body.toPlainText().strip()
        if not title or not body:
            QMessageBox.warning(self, "Missing fields", "Please enter both a title and body.")
            return
        add_note(title=title, body=body)
        self.note_title.clear(); self.note_body.clear()
        self._load_notes()

    def _delete_note(self):
        item = self.notes_list.currentItem()
        if not item:
            return
        note_id = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete note", "Delete this note?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            from memory.database import delete_note
            delete_note(note_id)
            self._load_notes()

    def _clear_history(self):
        if QMessageBox.question(self, "Clear history", "Delete all conversation history?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            from memory.database import clear_history
            clear_history()
            self.history_list.clear()

    def _load_prefs(self):
        from memory.database import get_all_preferences
        prefs = get_all_preferences()
        if prefs:
            self.prefs_view.setPlainText(
                "\n".join(f"{k}: {v}" for k, v in prefs.items())
            )
        else:
            self.prefs_view.setPlainText("No preferences saved yet.")

    def _load_tasks(self):
        from memory.database import get_recent_tasks
        tasks = get_recent_tasks(limit=30)
        if tasks:
            lines = []
            for t in tasks:
                lines.append(f"[{t['status'].upper()}] {t['description']}")
                if t["result"]:
                    lines.append(f"  → {t['result']}")
            self.tasks_view.setPlainText("\n".join(lines))
        else:
            self.tasks_view.setPlainText("No tasks recorded yet.")
