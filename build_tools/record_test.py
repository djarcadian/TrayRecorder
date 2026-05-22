"""End-to-end recording test: record monitor 1 for ~4 s, verify file."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from src.monitors import enumerate_monitors
from src.recorder import Recorder
from src.settings import Settings


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    app.setApplicationName("ScreenRec")
    app.setOrganizationName("Natran")

    settings = Settings()
    # Force a clean default save path for the test
    test_dir = Path.home() / "Videos" / "ScreenRec_TEST"
    test_dir.mkdir(parents=True, exist_ok=True)
    settings.save_folder = str(test_dir)
    print(f"Save folder: {settings.save_folder}")
    print(f"Format: {settings.file_format}, fps: {settings.fps}, quality: {settings.quality} (crf={settings.crf})")

    rec = Recorder(settings)
    rec.started.connect(lambda: print("STARTED"))
    rec.tick.connect(lambda s: print(f"  tick {s}s"))
    rec.finished.connect(lambda p: (print(f"FINISHED -> {p}"), app.quit()))
    rec.failed.connect(lambda r: (print(f"FAILED: {r}"), app.exit(2)))

    monitors = enumerate_monitors()
    if not monitors:
        print("No monitors found")
        return 3
    m = monitors[0]
    region = m.geometry
    print(f"Recording region: {region.width()}x{region.height()} @ ({region.x()},{region.y()})")

    QTimer.singleShot(500, lambda: rec.start(region, audio_enabled=True))
    QTimer.singleShot(4500, rec.stop)
    QTimer.singleShot(20000, lambda: app.exit(4))  # safety timeout

    rc = app.exec()
    print(f"App exit: {rc}")

    # Find the most recent file
    files = sorted(test_dir.glob("Recording_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if files:
        f = files[0]
        print(f"File: {f.name}  ({f.stat().st_size / 1024:.1f} KB)")
    else:
        print("No file produced")
        return 5
    return rc


if __name__ == "__main__":
    sys.exit(main())
