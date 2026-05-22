"""Persistent settings via QSettings (Windows registry HKCU\\Software\\Natran\\ScreenRec)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings

ORG = "Natran"
APP = "ScreenRec"


@dataclass(frozen=True)
class Defaults:
    save_folder: str = str(Path(os.environ.get("USERPROFILE", "")) / "Videos" / "TrayRecorder")
    file_format: str = "mp4"             # mp4, mkv, webm, avi, mov
    quality: str = "high"                # low, medium, high, lossless
    fps: int = 30                        # 15, 24, 30, 60
    audio_default_on: bool = True
    audio_source: str = "both"           # system, mic, both, off
    mic_device: str = ""                 # empty = default
    capture_cursor: bool = True
    countdown_seconds: int = 3           # 0, 3, 5
    open_folder_after: bool = True
    toast_after: bool = True
    double_click_stop: bool = True
    confirm_stop: bool = True
    hotkey: str = "ctrl+shift+r"
    autostart: bool = False
    audio_currently_on: bool = True      # tray-toggle state, persisted
    max_duration_minutes: int = 120      # 0 = no limit


CRF_FOR_QUALITY = {"low": 28, "medium": 23, "high": 18, "lossless": 0}


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)
        self._d = Defaults()

    def _get(self, key: str, default, cast):
        v = self._s.value(key, default)
        if cast is bool:
            if isinstance(v, str):
                return v.lower() in ("true", "1", "yes")
            return bool(v)
        if cast is int:
            return int(v)
        return str(v) if v is not None else default

    @property
    def save_folder(self) -> str:
        p = self._get("save_folder", self._d.save_folder, str)
        Path(p).mkdir(parents=True, exist_ok=True)
        return p

    @save_folder.setter
    def save_folder(self, v: str) -> None: self._s.setValue("save_folder", v)

    @property
    def file_format(self) -> str: return self._get("file_format", self._d.file_format, str)
    @file_format.setter
    def file_format(self, v: str) -> None: self._s.setValue("file_format", v)

    @property
    def quality(self) -> str: return self._get("quality", self._d.quality, str)
    @quality.setter
    def quality(self, v: str) -> None: self._s.setValue("quality", v)

    @property
    def crf(self) -> int: return CRF_FOR_QUALITY.get(self.quality, 18)

    @property
    def fps(self) -> int: return self._get("fps", self._d.fps, int)
    @fps.setter
    def fps(self, v: int) -> None: self._s.setValue("fps", v)

    @property
    def audio_default_on(self) -> bool: return self._get("audio_default_on", self._d.audio_default_on, bool)
    @audio_default_on.setter
    def audio_default_on(self, v: bool) -> None: self._s.setValue("audio_default_on", v)

    @property
    def audio_source(self) -> str: return self._get("audio_source", self._d.audio_source, str)
    @audio_source.setter
    def audio_source(self, v: str) -> None: self._s.setValue("audio_source", v)

    @property
    def mic_device(self) -> str: return self._get("mic_device", self._d.mic_device, str)
    @mic_device.setter
    def mic_device(self, v: str) -> None: self._s.setValue("mic_device", v)

    @property
    def capture_cursor(self) -> bool: return self._get("capture_cursor", self._d.capture_cursor, bool)
    @capture_cursor.setter
    def capture_cursor(self, v: bool) -> None: self._s.setValue("capture_cursor", v)

    @property
    def countdown_seconds(self) -> int: return self._get("countdown_seconds", self._d.countdown_seconds, int)
    @countdown_seconds.setter
    def countdown_seconds(self, v: int) -> None: self._s.setValue("countdown_seconds", v)

    @property
    def open_folder_after(self) -> bool: return self._get("open_folder_after", self._d.open_folder_after, bool)
    @open_folder_after.setter
    def open_folder_after(self, v: bool) -> None: self._s.setValue("open_folder_after", v)

    @property
    def toast_after(self) -> bool: return self._get("toast_after", self._d.toast_after, bool)
    @toast_after.setter
    def toast_after(self, v: bool) -> None: self._s.setValue("toast_after", v)

    @property
    def double_click_stop(self) -> bool: return self._get("double_click_stop", self._d.double_click_stop, bool)
    @double_click_stop.setter
    def double_click_stop(self, v: bool) -> None: self._s.setValue("double_click_stop", v)

    @property
    def confirm_stop(self) -> bool: return self._get("confirm_stop", self._d.confirm_stop, bool)
    @confirm_stop.setter
    def confirm_stop(self, v: bool) -> None: self._s.setValue("confirm_stop", v)

    @property
    def hotkey(self) -> str: return self._get("hotkey", self._d.hotkey, str)
    @hotkey.setter
    def hotkey(self, v: str) -> None: self._s.setValue("hotkey", v)

    @property
    def autostart(self) -> bool: return self._get("autostart", self._d.autostart, bool)
    @autostart.setter
    def autostart(self, v: bool) -> None: self._s.setValue("autostart", v)

    @property
    def audio_currently_on(self) -> bool: return self._get("audio_currently_on", self._d.audio_default_on, bool)
    @audio_currently_on.setter
    def audio_currently_on(self, v: bool) -> None: self._s.setValue("audio_currently_on", v)

    @property
    def max_duration_minutes(self) -> int: return self._get("max_duration_minutes", self._d.max_duration_minutes, int)
    @max_duration_minutes.setter
    def max_duration_minutes(self, v: int) -> None: self._s.setValue("max_duration_minutes", v)

    @property
    def recent_files(self) -> list[str]:
        raw = self._s.value("recent_files", "")
        if not raw:
            return []
        return [p for p in str(raw).split("|") if p and Path(p).exists()]

    def add_recent(self, path: str, limit: int = 5) -> None:
        existing = [p for p in self.recent_files if p != path]
        new_list = ([path] + existing)[:limit]
        self._s.setValue("recent_files", "|".join(new_list))
