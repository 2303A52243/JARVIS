"""Minimal debug launcher - shows any errors clearly."""
import sys, os, traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

print("Step 1: Python OK")

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
    from PySide6.QtCore import Qt, QTimer
    print("Step 2: PySide6 OK")
except Exception as e:
    print(f"Step 2 FAILED: {e}")
    sys.exit(1)

try:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    print("Step 3: QApplication OK")
except Exception as e:
    print(f"Step 3 FAILED: {e}")
    sys.exit(1)

try:
    win = QMainWindow()
    win.setWindowTitle("JARVIS Debug Test")
    win.resize(800, 500)

    central = QWidget()
    win.setCentralWidget(central)
    layout = QVBoxLayout(central)

    lbl = QLabel("✅ JARVIS window is working!\n\nIf you can see this, the UI is fine.\nClose this window to continue.")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("font-size: 20px; color: #00FF88; background: #0A0A1A; padding: 40px;")
    layout.addWidget(lbl)

    win.setStyleSheet("background: #0A0A1A;")
    win.show()
    win.raise_()
    win.activateWindow()
    print("Step 4: Window shown - check your screen and taskbar!")
    print("       (press Alt+Tab if you can't see it)")
except Exception as e:
    print(f"Step 4 FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 5: Testing app.config...")
    from app.config import get_settings
    s = get_settings()
    print(f"        Config OK — data dir: {s.jarvis_data_dir}")
except Exception as e:
    print(f"Step 5 FAILED (config): {e}")

try:
    print("Step 6: Testing psutil...")
    import psutil
    print(f"        psutil OK — CPU: {psutil.cpu_percent()}%")
except Exception as e:
    print(f"Step 6 FAILED (psutil): {e}")

try:
    print("Step 7: Testing memory database...")
    from memory.database import init_db
    init_db()
    print("        Memory DB OK")
except Exception as e:
    print(f"Step 7 FAILED (memory): {e}")

print("\nAll checks done. App is running. Close the JARVIS Debug window to exit.")
sys.exit(app.exec())
