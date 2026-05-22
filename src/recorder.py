"""ffmpeg orchestration: gdigrab video + soundcard audio → mux to chosen format."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QTimer, Signal

from .audio import AudioRecorder
from .settings import Settings


def _ffmpeg_path() -> str:
    """Locate the bundled ffmpeg.exe (works both in dev and PyInstaller frozen)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "resources" / "ffmpeg"  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent / "resources" / "ffmpeg"
    return str(base / "ffmpeg.exe")


def _video_args_for_format(fmt: str, crf: int) -> list[str]:
    fmt = fmt.lower()
    if fmt in ("mp4", "mkv", "mov"):
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if fmt == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", str(max(crf + 6, 18)), "-b:v", "0", "-row-mt", "1"]
    if fmt == "avi":
        return ["-c:v", "mpeg4", "-q:v", "4"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]


def _audio_args_for_format(fmt: str) -> list[str]:
    fmt = fmt.lower()
    if fmt in ("mp4", "mkv", "mov"):
        return ["-c:a", "aac", "-b:a", "192k"]
    if fmt == "webm":
        return ["-c:a", "libopus", "-b:a", "128k"]
    if fmt == "avi":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    return ["-c:a", "aac", "-b:a", "192k"]


class Recorder(QObject):
    started = Signal()
    tick = Signal(int)           # elapsed seconds
    finished = Signal(str)       # final file path
    failed = Signal(str)         # error message
    audio_level = Signal(float)  # 0..1 every ~100 ms while recording with audio

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._ffmpeg_proc: subprocess.Popen | None = None
        self._audio: AudioRecorder | None = None
        self._tmpdir: Path | None = None
        self._video_tmp: Path | None = None
        self._audio_tmp: Path | None = None
        self._final_path: Path | None = None
        self._fmt: str = "mp4"
        self._start_ts: float = 0.0
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    def is_active(self) -> bool:
        return self._ffmpeg_proc is not None and self._ffmpeg_proc.poll() is None

    def start(self, region: QRect, audio_enabled: bool) -> None:
        s = self._settings
        self._fmt = s.file_format.lower()
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        save_dir = Path(s.save_folder)
        save_dir.mkdir(parents=True, exist_ok=True)
        self._final_path = save_dir / f"Recording_{ts}.{self._fmt}"

        self._tmpdir = Path(tempfile.mkdtemp(prefix="screenrec_"))
        self._video_tmp = self._tmpdir / "video.mkv"
        self._audio_tmp = self._tmpdir / "audio.wav"

        # Snap region to even pixel boundaries for H.264
        x = region.x() - (region.x() % 2)
        y = region.y() - (region.y() % 2)
        w = region.width() - (region.width() % 2)
        h = region.height() - (region.height() % 2)
        w = max(w, 2)
        h = max(h, 2)

        ffmpeg = _ffmpeg_path()
        if not Path(ffmpeg).exists():
            self.failed.emit(f"ffmpeg not found at {ffmpeg}")
            return

        cmd = [
            ffmpeg, "-y",
            "-f", "gdigrab",
            "-framerate", str(s.fps),
            "-offset_x", str(x),
            "-offset_y", str(y),
            "-video_size", f"{w}x{h}",
            "-draw_mouse", "1" if s.capture_cursor else "0",
            "-i", "desktop",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(s.crf),
            "-pix_fmt", "yuv420p",
            str(self._video_tmp),
        ]

        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:
            self.failed.emit(f"Failed to start ffmpeg: {e}")
            return

        # Audio
        if audio_enabled and s.audio_source != "off":
            self._audio = AudioRecorder(
                output_path=str(self._audio_tmp),
                source=s.audio_source,
                mic_device_name=s.mic_device,
            )
            self._audio.level_changed.connect(self.audio_level)
            self._audio.start()
        else:
            self._audio = None

        self._start_ts = time.time()
        self._timer.start()
        self.started.emit()

    def _on_tick(self) -> None:
        if self._start_ts:
            self.tick.emit(int(time.time() - self._start_ts))

    def stop(self) -> None:
        self._timer.stop()
        # Graceful ffmpeg shutdown
        if self._ffmpeg_proc is not None and self._ffmpeg_proc.poll() is None:
            try:
                if self._ffmpeg_proc.stdin is not None:
                    self._ffmpeg_proc.stdin.write(b"q")
                    self._ffmpeg_proc.stdin.flush()
            except Exception:
                pass
            try:
                self._ffmpeg_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._ffmpeg_proc.terminate()
                try:
                    self._ffmpeg_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._ffmpeg_proc.kill()
        if self._audio is not None:
            self._audio.stop()

        # Mux/transcode
        try:
            self._finalize()
            self.finished.emit(str(self._final_path))
        except Exception as e:
            self.failed.emit(f"Finalize failed: {e}")
        finally:
            self._cleanup_tmp()
            self._ffmpeg_proc = None
            self._audio = None
            self._start_ts = 0.0

    def _finalize(self) -> None:
        assert self._video_tmp and self._final_path
        ffmpeg = _ffmpeg_path()
        s = self._settings
        has_audio = (
            self._audio is not None
            and self._audio_tmp is not None
            and self._audio_tmp.exists()
            and self._audio_tmp.stat().st_size > 1024
        )

        video_args = _video_args_for_format(self._fmt, s.crf)
        is_x264_compatible_container = self._fmt in ("mp4", "mkv", "mov")
        # If target container accepts the captured h264 stream and we're not changing CRF, copy video.
        video_copy = is_x264_compatible_container

        cmd: list[str] = [ffmpeg, "-y", "-i", str(self._video_tmp)]
        if has_audio:
            cmd += ["-i", str(self._audio_tmp)]
        if video_copy:
            cmd += ["-c:v", "copy"]
        else:
            cmd += video_args
        if has_audio:
            cmd += _audio_args_for_format(self._fmt)
            cmd += ["-shortest"]
        else:
            cmd += ["-an"]
        cmd += [str(self._final_path)]

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            # Fall back to copying the raw mkv if mux fails
            err = result.stderr.decode("utf-8", errors="replace")[-500:]
            fallback = self._final_path.with_suffix(".mkv")
            shutil.copy2(self._video_tmp, fallback)
            self._final_path = fallback
            raise RuntimeError(f"ffmpeg mux failed (saved raw MKV): {err}")

    def _cleanup_tmp(self) -> None:
        if self._tmpdir and self._tmpdir.exists():
            try:
                shutil.rmtree(self._tmpdir, ignore_errors=True)
            except Exception:
                pass
        self._tmpdir = None
        self._video_tmp = None
        self._audio_tmp = None
