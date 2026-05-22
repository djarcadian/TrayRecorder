"""Preferences QDialog — all user-tunable settings on one panel."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .audio import list_microphones
from .settings import Settings

FORMAT_LABELS = {"mp4": "MP4 (H.264 + AAC)", "mkv": "MKV (H.264 + AAC, crash-safe)",
                 "webm": "WebM (VP9 + Opus)", "avi": "AVI (MPEG-4)", "mov": "MOV (H.264 + AAC)"}
QUALITY_LABELS = {"low": "Low (smaller files)", "medium": "Medium", "high": "High", "lossless": "Lossless (huge files)"}
FPS_VALUES = [15, 24, 30, 60]
COUNTDOWN_VALUES = [0, 3, 5]
AUDIO_SOURCE_LABELS = {"system": "System audio only", "mic": "Microphone only",
                       "both": "System + Mic", "off": "Off (no audio)"}


def _combo_from(d: dict[str, str], current: str) -> QComboBox:
    cb = QComboBox()
    for key, label in d.items():
        cb.addItem(label, userData=key)
    idx = max(0, cb.findData(current))
    cb.setCurrentIndex(idx)
    return cb


class HotkeyEdit(QWidget):
    """Records a single key combo when its button is pressed."""

    def __init__(self, current: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit(current)
        self._edit.setReadOnly(True)
        self._btn = QPushButton("Record…")
        self._btn.setCheckable(True)
        self._btn.toggled.connect(self._on_record_toggled)
        layout.addWidget(self._edit, 1)
        layout.addWidget(self._btn)
        self._capture = QKeySequenceEdit()
        self._capture.setVisible(False)
        self._capture.keySequenceChanged.connect(self._on_sequence)
        layout.addWidget(self._capture)

    def _on_record_toggled(self, on: bool) -> None:
        self._capture.setVisible(on)
        if on:
            self._capture.clear()
            self._capture.setFocus()
            self._btn.setText("…press combo")
        else:
            self._btn.setText("Record…")

    def _on_sequence(self, seq: QKeySequence) -> None:
        if seq.isEmpty():
            return
        txt = seq.toString(QKeySequence.PortableText).lower().replace("+", "+")
        # Qt gives e.g. "Ctrl+Shift+R"; keyboard lib wants "ctrl+shift+r"
        self._edit.setText(txt)
        self._btn.setChecked(False)

    def value(self) -> str:
        return self._edit.text().strip()


class PreferencesDialog(QDialog):
    settings_saved = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self._s = settings
        self.setWindowTitle("TrayRecorder — Preferences")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Save folder
        self._folder = QLineEdit(settings.save_folder)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._folder, 1)
        folder_row.addWidget(browse)
        folder_wrap = QWidget()
        folder_wrap.setLayout(folder_row)
        form.addRow("Save folder:", folder_wrap)

        # Format
        self._format = _combo_from(FORMAT_LABELS, settings.file_format)
        form.addRow("File format:", self._format)

        # Quality
        self._quality = _combo_from(QUALITY_LABELS, settings.quality)
        form.addRow("Quality:", self._quality)

        # FPS
        self._fps = QSpinBox()
        self._fps.setRange(1, 120)
        self._fps.setValue(settings.fps)
        form.addRow("Frame rate (fps):", self._fps)

        # Audio defaults
        self._audio_on = QCheckBox("Audio on by default at app launch")
        self._audio_on.setChecked(settings.audio_default_on)
        form.addRow("", self._audio_on)

        self._audio_source = _combo_from(AUDIO_SOURCE_LABELS, settings.audio_source)
        form.addRow("Audio source:", self._audio_source)

        # Mic device
        self._mic = QComboBox()
        self._mic.addItem("Default microphone", userData="")
        for name in list_microphones():
            self._mic.addItem(name, userData=name)
        idx = max(0, self._mic.findData(settings.mic_device))
        self._mic.setCurrentIndex(idx)
        form.addRow("Microphone device:", self._mic)

        # Cursor
        self._cursor = QCheckBox("Capture mouse cursor")
        self._cursor.setChecked(settings.capture_cursor)
        form.addRow("", self._cursor)

        # Countdown
        self._countdown = QComboBox()
        for v in COUNTDOWN_VALUES:
            self._countdown.addItem("Off" if v == 0 else f"{v} seconds", userData=v)
        cidx = max(0, self._countdown.findData(settings.countdown_seconds))
        self._countdown.setCurrentIndex(cidx)
        form.addRow("Countdown before record:", self._countdown)

        # Max recording duration (auto-stop)
        self._max_duration = QSpinBox()
        self._max_duration.setRange(0, 1440)  # up to 24 h
        self._max_duration.setSuffix(" min")
        self._max_duration.setSpecialValueText("No limit")
        self._max_duration.setValue(settings.max_duration_minutes)
        form.addRow("Auto-stop after:", self._max_duration)

        # After-record options
        self._open_folder = QCheckBox("Open save folder when recording ends")
        self._open_folder.setChecked(settings.open_folder_after)
        form.addRow("", self._open_folder)

        self._toast = QCheckBox("Show notification when recording ends")
        self._toast.setChecked(settings.toast_after)
        form.addRow("", self._toast)

        # Stop interactions
        self._dbl_stop = QCheckBox("Double-click tray icon to stop (no confirmation)")
        self._dbl_stop.setChecked(settings.double_click_stop)
        form.addRow("", self._dbl_stop)

        self._confirm_stop = QCheckBox("Single-click on tray asks to confirm stop")
        self._confirm_stop.setChecked(settings.confirm_stop)
        form.addRow("", self._confirm_stop)

        # Hotkey
        self._hotkey = HotkeyEdit(settings.hotkey)
        form.addRow("Global hotkey:", self._hotkey)
        hint = QLabel("Tip: example combo  ctrl+shift+r")
        hint.setStyleSheet("color: #888;")
        form.addRow("", hint)

        # Autostart
        self._autostart = QCheckBox("Start TrayRecorder with Windows")
        self._autostart.setChecked(settings.autostart)
        form.addRow("", self._autostart)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose save folder", self._folder.text())
        if chosen:
            self._folder.setText(chosen)

    def _save(self) -> None:
        s = self._s
        s.save_folder = self._folder.text().strip()
        s.file_format = self._format.currentData()
        s.quality = self._quality.currentData()
        s.fps = int(self._fps.value())
        s.audio_default_on = bool(self._audio_on.isChecked())
        s.audio_source = self._audio_source.currentData()
        s.mic_device = self._mic.currentData() or ""
        s.capture_cursor = bool(self._cursor.isChecked())
        s.countdown_seconds = int(self._countdown.currentData())
        s.max_duration_minutes = int(self._max_duration.value())
        s.open_folder_after = bool(self._open_folder.isChecked())
        s.toast_after = bool(self._toast.isChecked())
        s.double_click_stop = bool(self._dbl_stop.isChecked())
        s.confirm_stop = bool(self._confirm_stop.isChecked())
        new_hotkey = self._hotkey.value() or s.hotkey
        s.hotkey = new_hotkey
        s.autostart = bool(self._autostart.isChecked())
        self.settings_saved.emit()
        self.accept()
