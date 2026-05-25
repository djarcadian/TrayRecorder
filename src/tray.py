"""System tray controller — owns the icon, menu, and coordinates the recorder."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Signal, Slot, Qt
from PySide6.QtGui import QAction, QColor, QCursor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from . import autostart
from .countdown import CountdownOverlay
from .hotkey import GlobalHotkey
from .monitors import MonitorOverlay, enumerate_monitors
from .notify import notify_saved
from .preferences import PreferencesDialog
from .recorder import Recorder
from .region_indicator import BorderOverlay, StopButton
from .region_select import RegionSelector
from .settings import Settings

LOW_DISK_THRESHOLD_BYTES = 500 * 1024 * 1024


def _resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "resources"


class TrayMenu(QMenu):
    """Menu that stays open when an action marked 'sticky' is clicked.

    Used for the audio on/off toggle so the label can flip in place without
    the whole menu closing and reopening.
    """

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        action = self.activeAction()
        if action is not None and action.data() == "sticky":
            action.trigger()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TrayApp(QObject):
    _hotkey_signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self._icon_idle = QIcon(str(_resource_dir() / "icon.ico"))
        self._icon_rec = QIcon(str(_resource_dir() / "icon_rec.ico"))

        # Pre-render the recording pixmap once so we can composite the
        # VU bar on each audio-level tick without re-decoding the .ico
        # from disk. 64×64 base gives a crisp downscale to any tray DPI.
        self._rec_base_pixmap = self._icon_rec.pixmap(64, 64)
        self._current_audio_level = 0.0

        self.tray = QSystemTrayIcon(self._icon_idle)
        self.tray.setToolTip("TrayRecorder — idle")
        self.menu = TrayMenu()
        # Note: deliberately NOT calling setContextMenu(self.menu) — we want
        # to handle right-clicks ourselves so we can position the menu flush
        # against the taskbar instead of letting Qt's default placement
        # leave a gap.
        self.menu.aboutToHide.connect(self._on_menu_hide)
        self.tray.activated.connect(self._on_activated)

        # Reference to the audio action so we can flip its label in place
        # without rebuilding the entire menu.
        self._audio_action: QAction | None = None

        self.monitor_overlay = MonitorOverlay()

        # Recorder
        self.recorder = Recorder(self.settings)
        self.recorder.started.connect(self._on_recording_started)
        self.recorder.tick.connect(self._on_tick)
        self.recorder.finished.connect(self._on_recording_finished)
        self.recorder.failed.connect(self._on_recording_failed)
        self.recorder.audio_level.connect(self._on_audio_level)

        # Audio current state seeded from preferences default
        if not isinstance(self.settings._s.value("audio_currently_on", None), (bool, str)):
            self.settings.audio_currently_on = self.settings.audio_default_on

        # Hotkey: marshal callback → Qt thread via signal
        self.hotkey = GlobalHotkey()
        self._hotkey_signal.connect(self._on_hotkey)
        self._register_hotkey()

        # Apply autostart preference at launch
        if self.settings.autostart != autostart.get_autostart():
            try:
                autostart.set_autostart(self.settings.autostart)
            except Exception:
                pass

        # Region selector held while open (avoid garbage-collection mid-drag)
        self._region_selector: RegionSelector | None = None
        self._countdown_widget: CountdownOverlay | None = None
        self._pending_region: QRect | None = None
        self._confirm_dialog: QMessageBox | None = None

        # Persistent recording indicators (only for Custom-region recordings).
        self._pending_custom_region: QRect | None = None
        self._border_overlay: BorderOverlay | None = None
        self._stop_button: StopButton | None = None

        # Defer single-click action until past the double-click interval so a
        # genuine double-click doesn't first flash the confirm dialog.
        self._single_click_timer = QTimer()
        self._single_click_timer.setSingleShot(True)
        self._single_click_timer.setInterval(QApplication.doubleClickInterval())
        self._single_click_timer.timeout.connect(self._handle_single_click)

        self.tray.show()

    # ------------------------------------------------------------------
    # Menu building
    # ------------------------------------------------------------------
    def _rebuild_menu(self) -> None:
        self.menu.clear()
        self._audio_action = None
        if self.recorder.is_active():
            self._build_recording_menu()
        else:
            self._build_idle_menu()

    def _show_menu_flush(self) -> None:
        """Show the tray menu anchored against the taskbar (no gap)."""
        self._rebuild_menu()
        if not self.recorder.is_active() and len(QGuiApplication.screens()) > 1:
            self.monitor_overlay.show()

        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()  # excludes the taskbar

        # sizeHint() before show is only an estimate — style padding and
        # DPI rounding aren't applied until the menu materializes, so on
        # Windows the real height tends to be a few px taller than the
        # estimate. Use sizeHint() for initial placement, then re-anchor
        # against the taskbar using the actual height after popup so the
        # menu doesn't overlap the taskbar.
        self.menu.ensurePolished()
        size = self.menu.sizeHint()

        y = avail.bottom() - size.height() + 1
        x = cursor.x() - size.width() // 2
        if x + size.width() > avail.right():
            x = avail.right() - size.width() + 1
        if x < avail.left():
            x = avail.left()
        if y < avail.top():
            y = avail.top()

        self.menu.popup(QPoint(x, y))

        actual_w = self.menu.width()
        actual_h = self.menu.height()
        final_y = avail.bottom() - actual_h + 1
        final_x = x
        if final_x + actual_w > avail.right():
            final_x = avail.right() - actual_w + 1
        if final_x < avail.left():
            final_x = avail.left()
        if final_y < avail.top():
            final_y = avail.top()
        if (final_x, final_y) != (x, y):
            self.menu.move(final_x, final_y)

    def _build_idle_menu(self) -> None:
        monitors = enumerate_monitors()
        for m in monitors:
            label = f"Record {m.index}" if len(monitors) > 1 else "Record"
            act = self.menu.addAction(label)
            act.triggered.connect(lambda _checked=False, mi=m: self._start_monitor_recording(mi))

        custom = self.menu.addAction("Custom")
        custom.triggered.connect(self._start_custom_recording)

        recent = self.menu.addMenu("Recent")
        recents = self.settings.recent_files
        if not recents:
            empty = recent.addAction("(none yet)")
            empty.setEnabled(False)
        else:
            for path in recents:
                a = recent.addAction(Path(path).name)
                a.triggered.connect(lambda _checked=False, p=path: self._open_file(p))

        audio_on = self.settings.audio_currently_on
        audio_label = "Audio On" if audio_on else "Audio Off"
        a_audio = self.menu.addAction(audio_label)
        a_audio.setData("sticky")  # TrayMenu keeps itself open when this is clicked
        a_audio.triggered.connect(self._toggle_audio)
        self._audio_action = a_audio

        a_prefs = self.menu.addAction("Preferences")
        a_prefs.triggered.connect(self._open_preferences)

        a_quit = self.menu.addAction("Quit")
        a_quit.triggered.connect(self._quit)

    def _build_recording_menu(self) -> None:
        elapsed = self._elapsed_str()
        a_status = self.menu.addAction(f"●  Recording {elapsed}")
        a_status.setEnabled(False)
        a_stop = self.menu.addAction("Stop")
        a_stop.triggered.connect(self._request_stop_with_confirm)
        a_quit = self.menu.addAction("Quit")
        a_quit.triggered.connect(self._quit)

    def _on_menu_hide(self) -> None:
        self.monitor_overlay.hide()

    # ------------------------------------------------------------------
    # Tray icon click handling
    # ------------------------------------------------------------------
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Context:
            # Right-click: take over placement so the menu sits flush with
            # the taskbar (Qt's default leaves a gap).
            self._show_menu_flush()
            return
        if not self.recorder.is_active():
            return  # idle: left-click does nothing
        if reason == QSystemTrayIcon.DoubleClick:
            # Cancel the pending single-click and any confirm dialog it opened.
            self._single_click_timer.stop()
            self._close_confirm_dialog()
            if self.settings.double_click_stop:
                self._stop_recording()
            return
        if reason == QSystemTrayIcon.Trigger:
            if self.settings.double_click_stop:
                # Wait one double-click interval to see if a second click follows.
                self._single_click_timer.start()
            else:
                self._handle_single_click()

    @Slot()
    def _handle_single_click(self) -> None:
        if not self.recorder.is_active():
            return
        if self.settings.confirm_stop:
            self._request_stop_with_confirm()
        else:
            self._stop_recording()

    def _close_confirm_dialog(self) -> None:
        if self._confirm_dialog is not None:
            self._confirm_dialog.done(QMessageBox.Cancel)
            self._confirm_dialog = None

    # ------------------------------------------------------------------
    # Recording start flows
    # ------------------------------------------------------------------
    def _start_monitor_recording(self, monitor) -> None:
        if not self._check_disk_space():
            return
        region = QRect(
            monitor.geometry.x(),
            monitor.geometry.y(),
            monitor.geometry.width(),
            monitor.geometry.height(),
        )
        screen = QGuiApplication.screens()[monitor.index - 1]
        self._begin_with_optional_countdown(region, screen)

    def _start_custom_recording(self) -> None:
        if not self._check_disk_space():
            return
        # Hide overlay first to not interfere with selection
        self.monitor_overlay.hide()
        self._region_selector = RegionSelector()
        self._region_selector.selected.connect(self._on_region_selected)
        self._region_selector.cancelled.connect(self._on_region_cancelled)
        self._region_selector.show()
        self._region_selector.raise_()
        self._region_selector.activateWindow()

    def _on_region_selected(self, region: QRect) -> None:
        self._region_selector = None
        # Remember the rect so we can draw the persistent dotted outline +
        # Stop button once recording actually starts.
        self._pending_custom_region = region
        center = region.center()
        target_screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        self._begin_with_optional_countdown(region, target_screen)

    def _on_region_cancelled(self) -> None:
        self._region_selector = None
        self._pending_custom_region = None

    def _begin_with_optional_countdown(self, region: QRect, screen) -> None:
        seconds = self.settings.countdown_seconds
        if seconds <= 0:
            self._begin_recording_now(region)
            return
        self._pending_region = region
        self._countdown_widget = CountdownOverlay(screen, seconds)
        self._countdown_widget.finished.connect(self._on_countdown_finished)
        self._countdown_widget.show()
        self._countdown_widget.raise_()

    def _on_countdown_finished(self) -> None:
        self._countdown_widget = None
        if self._pending_region is not None:
            r = self._pending_region
            self._pending_region = None
            self._begin_recording_now(r)

    def _begin_recording_now(self, region: QRect) -> None:
        audio_enabled = self.settings.audio_currently_on
        self.recorder.start(region, audio_enabled)

    # ------------------------------------------------------------------
    # Stop flows
    # ------------------------------------------------------------------
    def _request_stop_with_confirm(self) -> None:
        if not self.recorder.is_active():
            return
        if not self.settings.confirm_stop:
            self._stop_recording()
            return
        if self._confirm_dialog is not None:
            return  # one at a time
        msg = QMessageBox()
        msg.setWindowTitle("Stop recording?")
        msg.setText("Stop the current recording and save?")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.button(QMessageBox.Ok).setText("Stop")
        msg.setDefaultButton(QMessageBox.Ok)
        msg.setWindowFlag(Qt.WindowStaysOnTopHint)
        self._confirm_dialog = msg
        try:
            result = msg.exec()
        finally:
            self._confirm_dialog = None
        if result == QMessageBox.Ok:
            self._stop_recording()

    def _stop_recording(self) -> None:
        if self.recorder.is_active():
            self.recorder.stop()

    # ------------------------------------------------------------------
    # Recorder signals
    # ------------------------------------------------------------------
    @Slot()
    def _on_recording_started(self) -> None:
        self._current_audio_level = 0.0
        self.tray.setIcon(self._icon_rec)
        self.tray.setToolTip("TrayRecorder — recording 00:00")
        if self._pending_custom_region is not None:
            self._show_region_indicator(self._pending_custom_region)
            self._pending_custom_region = None

    @Slot(int)
    def _on_tick(self, seconds: int) -> None:
        self._elapsed_seconds = seconds
        self.tray.setToolTip(f"TrayRecorder — recording {self._fmt_elapsed(seconds)}")
        # Auto-stop at the configured maximum (0 = no limit)
        limit_min = self.settings.max_duration_minutes
        if limit_min > 0 and seconds >= limit_min * 60:
            self._stop_recording()

    @Slot(str)
    def _on_recording_finished(self, path: str) -> None:
        self._close_confirm_dialog()
        self._hide_region_indicator()
        self.tray.setIcon(self._icon_idle)
        self.tray.setToolTip("TrayRecorder — idle")
        self.settings.add_recent(path)
        if self.settings.toast_after:
            notify_saved(path)
        if self.settings.open_folder_after:
            try:
                os.startfile(str(Path(path).parent))  # noqa: S606
            except Exception:
                pass

    @Slot(str)
    def _on_recording_failed(self, reason: str) -> None:
        self._close_confirm_dialog()
        self._hide_region_indicator()
        self.tray.setIcon(self._icon_idle)
        self.tray.setToolTip("TrayRecorder — idle")
        self.tray.showMessage("TrayRecorder error", reason, QSystemTrayIcon.Critical, 6000)

    @Slot(float)
    def _on_audio_level(self, level: float) -> None:
        """Update tray icon with a VU-style bar that rises from the bottom
        proportional to live audio RMS — actually bounces with the audio.
        """
        if not self.recorder.is_active():
            return
        if not self.settings.audio_currently_on:
            return
        self._current_audio_level = level
        self.tray.setIcon(self._build_pulse_icon(level))

    def _build_pulse_icon(self, level: float) -> QIcon:
        pix = QPixmap(self._rec_base_pixmap)
        if level > 0.0:
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            h = pix.height()
            w = pix.width()
            fill_h = int(round(h * min(1.0, level)))
            if fill_h > 0:
                painter.fillRect(
                    QRect(0, h - fill_h, w, fill_h),
                    QColor(230, 40, 40, 215),
                )
            painter.end()
        return QIcon(pix)

    def _show_region_indicator(self, region: QRect) -> None:
        self._border_overlay = BorderOverlay(region)
        self._border_overlay.show()
        self._stop_button = StopButton(region)
        self._stop_button.clicked.connect(self._stop_recording)
        self._stop_button.show()
        self._stop_button.raise_()

    def _hide_region_indicator(self) -> None:
        if self._border_overlay is not None:
            self._border_overlay.hide()
            self._border_overlay.deleteLater()
            self._border_overlay = None
        if self._stop_button is not None:
            self._stop_button.hide()
            self._stop_button.deleteLater()
            self._stop_button = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    _elapsed_seconds: int = 0

    def _elapsed_str(self) -> str:
        return self._fmt_elapsed(self._elapsed_seconds)

    @staticmethod
    def _fmt_elapsed(seconds: int) -> str:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _toggle_audio(self) -> None:
        self.settings.audio_currently_on = not self.settings.audio_currently_on
        # The TrayMenu subclass keeps itself open when this action is clicked;
        # we just flip the label in place — no popup, no reposition, no flash.
        if self._audio_action is not None:
            self._audio_action.setText(
                "Audio On" if self.settings.audio_currently_on else "Audio Off"
            )

    def _open_file(self, path: str) -> None:
        try:
            os.startfile(path)  # noqa: S606
        except Exception:
            pass

    def _open_preferences(self) -> None:
        dlg = PreferencesDialog(self.settings)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self) -> None:
        # Re-register hotkey if changed
        self._register_hotkey()
        # Sync autostart with prefs
        try:
            autostart.set_autostart(self.settings.autostart)
        except Exception:
            pass

    def _register_hotkey(self) -> None:
        self.hotkey.register(self.settings.hotkey, lambda: self._hotkey_signal.emit())

    @Slot()
    def _on_hotkey(self) -> None:
        # Toggle: if recording, stop (no confirm); else start primary monitor
        if self.recorder.is_active():
            self._stop_recording()
        else:
            monitors = enumerate_monitors()
            if monitors:
                self._start_monitor_recording(monitors[0])

    def _check_disk_space(self) -> bool:
        try:
            free = shutil.disk_usage(self.settings.save_folder).free
        except Exception:
            return True
        if free >= LOW_DISK_THRESHOLD_BYTES:
            return True
        msg = QMessageBox()
        msg.setWindowTitle("Low disk space")
        msg.setText(
            f"Less than {LOW_DISK_THRESHOLD_BYTES // (1024*1024)} MB free in:\n"
            f"{self.settings.save_folder}\n\nRecord anyway?"
        )
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.button(QMessageBox.Ok).setText("Record anyway")
        msg.setDefaultButton(QMessageBox.Cancel)
        return msg.exec() == QMessageBox.Ok

    def _quit(self) -> None:
        if self.recorder.is_active():
            msg = QMessageBox()
            msg.setWindowTitle("Quit TrayRecorder?")
            msg.setText("A recording is in progress. Stop and save before quitting?")
            msg.setIcon(QMessageBox.Question)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            choice = msg.exec()
            if choice == QMessageBox.Cancel:
                return
            if choice == QMessageBox.Save:
                self._stop_recording()
        self.hotkey.unregister()
        QApplication.instance().quit()
