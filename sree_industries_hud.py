"""Sree Industries HUD Launcher.

Entry point to launch the Sree Industries Holographic HUD directly:
    python sree_industries_hud.py
"""

from __future__ import annotations

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main() -> None:
    print("=" * 60)
    print("  J.A.R.V.I.S. OS – Sree Industries Neural Holographic HUD")
    print("=" * 60)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("ERROR: PySide6 is not installed.")
        print("Run:  python -m pip install PySide6")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS - Sree Industries HUD")
    app.setOrganizationName("Sree Industries")
    app.setStyle("Fusion")

    from ui.main_window import MainWindow
    window = MainWindow()
    window.setWindowTitle("J.A.R.V.I.S. OS v2.0 – Sree Industries Neural HUD")
    window.show()
    print("  ✓ Sree Industries HUD launched successfully.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
