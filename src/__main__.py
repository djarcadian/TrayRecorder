"""Entry point: enforces single instance, creates QApplication, runs tray."""

from __future__ import annotations

import sys

from PySide6.QtCore import QSharedMemory, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .tray import TrayApp


def _enforce_single_instance() -> QSharedMemory | None:
    shm = QSharedMemory("NatranScreenRec-singleton")
    if not shm.create(1):
        return None
    return shm


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    app.setApplicationName("TrayRecorder")
    app.setOrganizationName("Natran")

    shm = _enforce_single_instance()
    if shm is None:
        QMessageBox.information(None, "TrayRecorder", "TrayRecorder is already running.")
        return 0

    _tray = TrayApp()  # noqa: F841 (kept alive by reference)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
