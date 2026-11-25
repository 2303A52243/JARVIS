"""Browser / Web Assistant UI panel for JARVIS."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTextBrowser, QLabel, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal

BTN  = "background:#1E293B;color:#38BDF8;border:1px solid #0284C7;border-radius:5px;padding:6px 12px;"
IN   = "background:#0B0F19;color:#E2E8F0;border:1px solid #1F2937;border-radius:6px;padding:6px;font-size:12px;"
VIEW = "background:#0B0F19;color:#E2E8F0;border:1px solid #1F2937;border-radius:6px;padding:10px;font-size:12px;"


class _SearchWorker(QThread):
    done = Signal(list)
    error = Signal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            from browser.web_search import web_search
            self.done.emit(web_search(self.query, max_results=5))
        except Exception as e:
            self.error.emit(str(e))


class _FetchWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            from browser.web_search import fetch_page_text
            self.done.emit(fetch_page_text(self.url))
        except Exception as e:
            self.error.emit(str(e))


class BrowserPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._results: list = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("🌐 WEB ASSISTANT")
        title.setStyleSheet("color:#F8FAFC;font-size:18px;font-weight:800;letter-spacing:1px;")
        layout.addWidget(title)

        # Search bar
        bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search the web…")
        self.search_input.setStyleSheet(IN)
        self.search_input.returnPressed.connect(self._do_search)
        self.btn_search = QPushButton("🔍 Search")
        self.btn_search.setStyleSheet(BTN)
        self.btn_search.clicked.connect(self._do_search)
        bar.addWidget(self.search_input, 1)
        bar.addWidget(self.btn_search)
        layout.addLayout(bar)

        # URL fetch bar
        url_bar = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a URL to read its content…")
        self.url_input.setStyleSheet(IN)
        self.btn_fetch = QPushButton("📄 Read Page")
        self.btn_fetch.setStyleSheet(BTN)
        self.btn_fetch.clicked.connect(self._do_fetch)
        url_bar.addWidget(self.url_input, 1)
        url_bar.addWidget(self.btn_fetch)
        layout.addLayout(url_bar)

        # Results view
        self.results_view = QTextBrowser()
        self.results_view.setOpenExternalLinks(True)
        self.results_view.setStyleSheet(VIEW)
        layout.addWidget(self.results_view, 1)

        self.status_lbl = QLabel("Ready.")
        self.status_lbl.setStyleSheet("color:#64748B;font-size:11px;")
        layout.addWidget(self.status_lbl)

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.status_lbl.setText(f"Searching for '{query}'…")
        self.btn_search.setEnabled(False)
        self._worker = _SearchWorker(query)
        self._worker.done.connect(self._show_results)
        self._worker.error.connect(lambda e: self._set_status(f"Error: {e}"))
        self._worker.finished.connect(lambda: self.btn_search.setEnabled(True))
        self._worker.start()

    def _show_results(self, results: list):
        self._results = results
        html_parts = ["<h3 style='color:#38BDF8;'>Search Results</h3>"]
        for r in results:
            title = r.get("title", "")
            url   = r.get("url", "")
            snip  = r.get("snippet", "")
            if url:
                html_parts.append(
                    f"<p><a href='{url}' style='color:#38BDF8;font-weight:bold;'>{title}</a><br>"
                    f"<small style='color:#64748B;'>{url}</small><br>"
                    f"<span style='color:#CBD5E1;'>{snip}</span></p><hr style='border-color:#1F2937;'>"
                )
            else:
                html_parts.append(f"<p style='color:#94A3B8;'>{title}: {snip}</p>")
        self.results_view.setHtml("".join(html_parts))
        self._set_status(f"Found {len(results)} results.")

    def _do_fetch(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        self._set_status(f"Fetching {url}…")
        self.btn_fetch.setEnabled(False)
        self._fetch_worker = _FetchWorker(url)
        self._fetch_worker.done.connect(self._show_page)
        self._fetch_worker.error.connect(lambda e: self._set_status(f"Error: {e}"))
        self._fetch_worker.finished.connect(lambda: self.btn_fetch.setEnabled(True))
        self._fetch_worker.start()

    def _show_page(self, text: str):
        self.results_view.setPlainText(text)
        self._set_status("Page loaded. You can copy the text and ask JARVIS to summarize it.")

    def _set_status(self, msg: str):
        self.status_lbl.setText(msg)
