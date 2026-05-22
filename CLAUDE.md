# CLAUDE.md — TrayRecorder

Windows system-tray screen recorder. Python 3.12 + PySide6 + bundled ffmpeg, packaged as an Inno Setup installer.

> **Naming caveat:** the project directory is `screenrec/` and internal storage keys still say `ScreenRec`. The product was renamed to **TrayRecorder** later — only user-facing strings reflect the new name. See "Naming convention" below before renaming anything else.

## Build & run

Working directory: `C:\Users\Work\dev\screenrec`

```powershell
# Dev run (no install)
.venv\Scripts\python.exe -m src

# Full build → installer
pwsh -File build.ps1
```

`build.ps1` does: regenerate icons → run PyInstaller → run Inno Setup. Outputs:
- `dist\TrayRecorder\TrayRecorder.exe` — portable bundle (~5.7 MB exe + ~258 MB `_internal/`)
- `installer\Output\TrayRecorder_Setup.exe` — single-file installer (~66 MB compressed)

Dependencies installed once via `requirements.txt` + manually-added `pyinstaller==6.10.0`. ffmpeg.exe (essentials build from gyan.dev) lives at `src\resources\ffmpeg\ffmpeg.exe` and is bundled by PyInstaller `--add-data`.

Inno Setup ISCC at `C:\Users\Work\AppData\Local\Programs\Inno Setup 6\ISCC.exe` (installed via winget `JRSoftware.InnoSetup`).

## Module map

```
screenrec.py           Top-level entry point. Adds project root to sys.path and
                       imports src.__main__ — needed because PyInstaller can't
                       run src/__main__.py directly without breaking the
                       package's relative imports.

src/__main__.py        QApplication setup; single-instance guard via QSharedMemory.
src/tray.py            TrayApp — owns QSystemTrayIcon, builds menu dynamically,
                       coordinates recorder/region selector/countdown/preferences.
                       Includes TrayMenu subclass that keeps menu open for the
                       audio toggle action ("sticky").
src/recorder.py        Recorder QObject — spawns ffmpeg via subprocess for video
                       (gdigrab → temp .mkv), runs AudioRecorder thread for audio
                       (→ temp .wav), mux at stop. Always records to MKV
                       internally for crash resilience, then remuxes to chosen
                       format at finalize.
src/audio.py           AudioRecorder QObject — soundcard library, WASAPI loopback
                       for system audio + mic capture. Emits level_changed signal
                       at ~10 Hz with peak-with-decay smoothed RMS.
src/monitors.py        enumerate_monitors(); MonitorOverlay shows big numbered
                       overlays on each screen when the tray menu opens.
src/region_select.py   RegionSelector overlay — drag to pick a rect, with
                       persistent hint banner and Record/Cancel buttons.
src/region_indicator.py BorderOverlay (dotted line outside captured rect,
                       click-through) + StopButton (floating, opaque) shown
                       during active custom-region recording.
src/countdown.py       3-2-1 overlay on the chosen monitor before recording.
src/preferences.py     PreferencesDialog — single form with every setting.
src/settings.py        QSettings wrapper with typed defaults. Persists to
                       HKCU\Software\Natran\ScreenRec (legacy name kept).
src/hotkey.py          GlobalHotkey via `keyboard` library.
src/notify.py          Toast notification on save (win10toast-click).
src/autostart.py       HKCU\...\Run registry toggle.

build_tools/make_icons.py   Generates icon.ico + icon_rec.ico from scratch (PIL).
                            Run automatically by build.ps1. Don't hand-edit the
                            .ico files — they get overwritten on every build.
build_tools/smoke_test.py   Headless tray construction test.
build_tools/record_test.py  End-to-end recording test (records monitor 1 for 4 s).

installer/setup.iss    Inno Setup script. AppId is stable across builds — keeps
                       upgrade flow clean.
```

## Naming convention (important)

The product was renamed from "ScreenRec" → "TrayRecorder" partway through. Rule:

| Surface | Name | Why |
|---|---|---|
| **User-facing strings** (tooltips, dialog titles, menu, errors, installer, Apps & Features, exe filename) | **TrayRecorder** | Current product name |
| **QSettings storage** (`HKCU\Software\Natran\ScreenRec`) | ScreenRec | Renaming would lose users' existing preferences |
| **Autostart registry value name** (`NatranScreenRec`) | ScreenRec | Cleanly overwrites old install's entry on upgrade |
| **Singleton mutex** (`NatranScreenRec-singleton`) | ScreenRec | Internal; no reason to change |
| **Project directory** (`screenrec/`) | screenrec | Internal; no reason to change |
| **`screenrec.py` entry script** | screenrec | Internal; PyInstaller entry |
| **Temp dir prefix** (`%TEMP%\screenrec_*`) | screenrec | Internal |

If asked to add a new user-facing string, use "TrayRecorder". If asked to change a storage path or registry key, don't — it'd break existing installs.

## Gotchas that bit me during this build

1. **PyInstaller + relative imports.** Don't point PyInstaller at `src/__main__.py` directly — relative imports (`from .tray import ...`) fail because Python loses the package context. Use the `screenrec.py` shim at the project root.
2. **Resources path in the frozen bundle.** Build uses `--add-data "src\resources;resources"` so files land at `sys._MEIPASS/resources/`. Code reads via the helper `_resource_dir()` which switches on `getattr(sys, "frozen", False)`.
3. **PowerShell `2>&1` on native executables corrupts exit codes.** Running `ffmpeg ... 2>&1` or `pip ... 2>&1` from PowerShell wraps each stderr line in an ErrorRecord and sets `$LASTEXITCODE` to non-zero even when the command succeeded. Avoid the redirect; stderr is already captured.
4. **Bundle .exe locks itself.** If a previous `TrayRecorder.exe` is running (tray instance from prior install), PyInstaller can't overwrite `dist\TrayRecorder\TrayRecorder.exe`. Always `Stop-Process -Name "TrayRecorder","ScreenRec" -ErrorAction SilentlyContinue` before rebuilding.
5. **Tray single-click vs double-click.** Qt fires `Trigger` immediately, then `DoubleClick` ~250 ms later. We defer the single-click action by `QApplication.doubleClickInterval()` so a real double-click can cancel it before the confirm dialog opens. See `tray._on_activated` + `_single_click_timer`.
6. **Menu position flush with taskbar.** Qt's default tray menu placement leaves a gap above the taskbar — cursor crossing into the taskbar steals focus. We take over: `setContextMenu` is *not* called; `_on_activated` handles `Context` reason and calls `_show_menu_flush` which positions the menu so its bottom edge equals `availableGeometry().bottom()`.
7. **The bouncing VU-bar icon is rebuilt 10×/s.** The base recording pixmap is pre-rendered once at 64×64 (`_rec_base_pixmap`); each level update does a small `QPainter.fillRect` on a copy. Don't move this into a slot that creates a new QPixmap from disk per tick — it'll blow CPU.
8. **AVI has a 4 GB container limit** (~90 min at default quality). No workaround in v1; documented as a limitation.

## Tunable constants worth knowing

| Constant | File | Effect |
|---|---|---|
| `LEVEL_GAIN = 4.0` | `audio.py` | How aggressively RMS maps to 0..1 for the VU bar |
| `LEVEL_DECAY = 0.6` | `audio.py` | Peak-with-decay smoothing (1=hold, 0=no smoothing) |
| `LEVEL_FLOOR = 0.02` | `audio.py` | RMS below this is treated as silence (icon stays unpulsed) |
| `LOW_DISK_THRESHOLD_BYTES` | `tray.py` | Disk-space warning threshold before starting (default 500 MB) |
| `max_duration_minutes` default | `settings.py` (Defaults) | Auto-stop after this many minutes; 0 = no limit (default 120) |
| `CRF_FOR_QUALITY` | `settings.py` | Maps Low/Medium/High/Lossless → ffmpeg CRF |

## Things explicitly left out (don't add without asking)

- numpy removal / Qt slimming to shrink the 259 MB install — user declined.
- Pause/resume during recording — out of scope.
- Webcam overlay / picture-in-picture — out of scope.
- Recording multiple monitors into one file — use Custom to span.
- Code signing — no cert; SmartScreen warning is expected on first run.
- pyinstaller in requirements.txt — kept as a separate manual install (build-time only).

## When making changes

- Editing source modules: rebuild with `build.ps1` to refresh both bundle and installer.
- Editing just the .iss: only need to re-run ISCC (faster).
- Adding a new dependency: update `requirements.txt`, run `pip install -r requirements.txt` into the venv, and add `--hidden-import "<name>"` to the PyInstaller command in `build.ps1` if PyInstaller's auto-detection misses it.
- Adding a new user-facing string: use "TrayRecorder", not "ScreenRec".
