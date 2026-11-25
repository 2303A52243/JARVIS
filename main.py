"""JARVIS – Advanced Personal AI Laptop Assistant
Entry point: python main.py
"""

from __future__ import annotations

import sys
import os

# Ensure the project root is always on sys.path regardless of where Python is launched from
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main() -> None:
    print("=" * 60)
    print("  JARVIS – Advanced Personal AI Laptop Assistant")
    print("=" * 60)
    print("  Starting up…")

    # Launch Qt first – window appears fast
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("ERROR: PySide6 is not installed.")
        print("Run:  python -m pip install PySide6")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setOrganizationName("JARVIS AI")
    app.setStyle("Fusion")
    _apply_dark_palette(app)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    print("  ✓ Window launched – loading panels in background…")

    sys.exit(app.exec())


def _apply_dark_palette(app) -> None:
    from PySide6.QtGui import QPalette, QColor

    palette = QPalette()
    dark      = QColor(18, 18, 24)
    mid       = QColor(30, 30, 40)
    text      = QColor(220, 220, 230)
    accent    = QColor(56, 189, 248)
    highlight = QColor(30, 64, 175)

    palette.setColor(QPalette.Window,          dark)
    palette.setColor(QPalette.WindowText,      text)
    palette.setColor(QPalette.Base,            mid)
    palette.setColor(QPalette.AlternateBase,   dark)
    palette.setColor(QPalette.ToolTipBase,     mid)
    palette.setColor(QPalette.ToolTipText,     text)
    palette.setColor(QPalette.Text,            text)
    palette.setColor(QPalette.Button,          mid)
    palette.setColor(QPalette.ButtonText,      text)
    palette.setColor(QPalette.BrightText,      accent)
    palette.setColor(QPalette.Link,            accent)
    palette.setColor(QPalette.Highlight,       highlight)
    palette.setColor(QPalette.HighlightedText, text)

    app.setPalette(palette)


if __name__ == "__main__":
    main()

