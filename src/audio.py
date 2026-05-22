"""WASAPI loopback (system) + microphone capture via soundcard, mixed to .wav.

Also emits a `level_changed(float 0..1)` signal so the UI can pulse in time with
the audio (computed as smoothed RMS per block, ~10 Hz).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import soundcard as sc
import soundfile as sf
from PySide6.QtCore import QObject, Signal

SAMPLE_RATE = 48000
BLOCK_FRAMES = 4800  # 0.1 s
LEVEL_DECAY = 0.6    # peak-with-decay smoothing factor (0=no smoothing, 1=hold forever)
LEVEL_GAIN = 4.0     # how aggressively RMS maps to 0..1 (typical voice ≈ 0.05-0.2 RMS)
LEVEL_FLOOR = 0.02   # below this RMS we report 0 (treated as silence)


class AudioRecorder(QObject):
    """Threaded audio capture. Source: 'system', 'mic', 'both', or 'off'."""

    level_changed = Signal(float)  # 0..1, emitted ~10 times per second

    def __init__(self, output_path: str, source: str, mic_device_name: str = "") -> None:
        super().__init__()
        self.output_path = output_path
        self.source = source
        self.mic_device_name = mic_device_name
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: str | None = None

    @property
    def enabled(self) -> bool:
        return self.source != "off"

    def start(self) -> None:
        if not self.enabled:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def error(self) -> str | None:
        return self._error

    def _resolve_mic(self):
        if not self.mic_device_name:
            return sc.default_microphone()
        for m in sc.all_microphones(include_loopback=False):
            if m.name == self.mic_device_name:
                return m
        return sc.default_microphone()

    def _emit_level(self, block: np.ndarray, smoothed_state: list[float]) -> None:
        if block is None or block.size == 0:
            return
        rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))
        if rms < LEVEL_FLOOR:
            rms = 0.0
        # Peak-with-decay: rise instantly, fall slowly.
        smoothed_state[0] = max(rms, smoothed_state[0] * LEVEL_DECAY)
        level = min(1.0, smoothed_state[0] * LEVEL_GAIN)
        self.level_changed.emit(level)

    def _run(self) -> None:
        try:
            speaker = sc.default_speaker()
            loopback_mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            mic = self._resolve_mic() if self.source in ("mic", "both") else None

            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            smoothed = [0.0]

            with sf.SoundFile(
                self.output_path,
                mode="w",
                samplerate=SAMPLE_RATE,
                channels=2,
                subtype="PCM_16",
            ) as wav:
                loop_rec = (
                    loopback_mic.recorder(samplerate=SAMPLE_RATE, channels=2, blocksize=BLOCK_FRAMES)
                    if self.source in ("system", "both")
                    else None
                )
                mic_rec = (
                    mic.recorder(samplerate=SAMPLE_RATE, channels=2, blocksize=BLOCK_FRAMES)
                    if mic is not None
                    else None
                )

                ctx = []
                if loop_rec is not None:
                    ctx.append(loop_rec)
                if mic_rec is not None:
                    ctx.append(mic_rec)

                for r in ctx:
                    r.__enter__()
                try:
                    while not self._stop.is_set():
                        sys_block = (
                            loop_rec.record(numframes=BLOCK_FRAMES)
                            if loop_rec is not None
                            else None
                        )
                        mic_block = (
                            mic_rec.record(numframes=BLOCK_FRAMES)
                            if mic_rec is not None
                            else None
                        )
                        emitted: np.ndarray | None = None
                        if sys_block is not None and mic_block is not None:
                            mixed = np.clip((sys_block + mic_block) * 0.5, -1.0, 1.0)
                            wav.write(mixed.astype(np.float32))
                            emitted = mixed
                        elif sys_block is not None:
                            wav.write(sys_block.astype(np.float32))
                            emitted = sys_block
                        elif mic_block is not None:
                            wav.write(mic_block.astype(np.float32))
                            emitted = mic_block
                        else:
                            time.sleep(0.05)
                        self._emit_level(emitted, smoothed)
                finally:
                    for r in ctx:
                        try:
                            r.__exit__(None, None, None)
                        except Exception:
                            pass
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"


def list_microphones() -> list[str]:
    """Return human-readable names of available input devices (excludes loopback)."""
    try:
        return [m.name for m in sc.all_microphones(include_loopback=False)]
    except Exception:
        return []
