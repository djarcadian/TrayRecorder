"""Windows toast notification with click-to-open-file."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

try:
    from win10toast_click import ToastNotifier
except Exception:  # pragma: no cover
    ToastNotifier = None  # type: ignore[assignment]


def _icon_path() -> str:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "resources"  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent / "resources"
    return str(base / "icon.ico")


def notify_saved(file_path: str) -> None:
    """Show 'Recording saved' toast; clicking the toast opens the file."""
    if ToastNotifier is None:
        return
    size_mb = 0.0
    try:
        size_mb = Path(file_path).stat().st_size / (1024 * 1024)
    except Exception:
        pass

    def _open():
        try:
            os.startfile(file_path)  # noqa: S606
        except Exception:
            pass

    def _show():
        toaster = ToastNotifier()
        toaster.show_toast(
            "Recording saved",
            f"{Path(file_path).name}  ({size_mb:.1f} MB)",
            icon_path=_icon_path(),
            duration=5,
            threaded=True,
            callback_on_click=_open,
        )

    threading.Thread(target=_show, daemon=True).start()
