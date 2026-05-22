"""Headless-ish smoke test: build the tray, force a menu rebuild, then quit."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from src.monitors import enumerate_monitors
from src.tray import TrayApp


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    app.setApplicationName("ScreenRec")
    app.setOrganizationName("Natran")

    print("Monitors detected:")
    for m in enumerate_monitors():
        print(f"  {m.index}. {m.name}  {m.geometry.width()}x{m.geometry.height()} @ ({m.geometry.x()},{m.geometry.y()})  dpr={m.device_pixel_ratio}")

    tray = TrayApp()
    print(f"Tray visible: {tray.tray.isVisible()}")
    print(f"Tray system available: {tray.tray.isSystemTrayAvailable()}")
    print(f"Hotkey registered: {tray.hotkey.combo}")

    # Force a menu rebuild to catch errors
    tray._rebuild_menu()
    print(f"Menu items: {[a.text() for a in tray.menu.actions()]}")

    QTimer.singleShot(800, app.quit)
    rc = app.exec()
    print(f"Exit code: {rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
