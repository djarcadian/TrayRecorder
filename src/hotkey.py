"""Global hotkey via `keyboard` library, with safe re-registration."""

from __future__ import annotations

from typing import Callable, Optional

import keyboard


class GlobalHotkey:
    def __init__(self) -> None:
        self._combo: Optional[str] = None
        self._handle = None
        self._callback: Optional[Callable[[], None]] = None

    def register(self, combo: str, callback: Callable[[], None]) -> bool:
        self.unregister()
        self._combo = combo
        self._callback = callback
        try:
            self._handle = keyboard.add_hotkey(combo, callback, suppress=False, trigger_on_release=False)
            return True
        except Exception:
            self._handle = None
            return False

    def unregister(self) -> None:
        if self._handle is not None and self._combo:
            try:
                keyboard.remove_hotkey(self._handle)
            except Exception:
                pass
        self._handle = None

    @property
    def combo(self) -> Optional[str]:
        return self._combo
