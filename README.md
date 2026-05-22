# TrayRecorder

A lightweight Windows 10/11 system-tray screen recorder. Records any monitor or a custom region with optional system + microphone audio.

## Install

1. Run `TrayRecorder_Setup.exe`.
2. (Optional) Tick "Start with Windows" during install.
3. TrayRecorder appears in the system tray.

> SmartScreen may warn on first run because the installer is unsigned. Click **More info → Run anyway**. (V1 ships without a code-signing cert.)

## Use

**Right-click the tray icon** to open the menu — large numbers appear on each connected monitor while the menu is open so you can match "Record 1" / "Record 2" / "Record N" to the right physical screen.

- **Record N** — full-screen capture of that monitor.
- **Custom** — drag a rectangle anywhere across all monitors. Click `● Record` or press Enter; Esc cancels. A thin red dotted outline + floating Stop button remain visible while recording.
- **Recent** — last 5 recordings. Click to open.
- **Audio On / Off** — click to toggle (menu stays open while the label flips).
- **Preferences** — save folder, file format, quality, audio source, hotkey, max-duration auto-stop, etc.
- **Quit** — exits the app.

**While recording**, the tray icon shows a red dot. When audio is on, the icon also overlays a red bar that rises and falls with live audio levels.

**To stop:**
- Single-click the tray icon → confirm prompt.
- Double-click the tray icon → stops immediately (configurable).
- Press the global hotkey (`Ctrl+Shift+R` default).
- Right-click → **Stop** → confirm.
- Click the floating **■ Stop** button (custom region only).

**After recording**, by default the save folder opens automatically and a toast notification appears (click the toast to open the file).

## File formats

| Format | Container | Video | Audio | Notes |
|---|---|---|---|---|
| MP4 *(default)* | mp4 | H.264 | AAC | Universal compatibility |
| MKV | mkv | H.264 | AAC | Crash-resilient — recovers if the app dies mid-record |
| WebM | webm | VP9 | Opus | Browser-friendly, smaller files |
| AVI | avi | MPEG-4 | MP3 | Older players, **4 GB container limit** (~90 min default quality) |
| MOV | mov | H.264 | AAC | Apple-friendly |

Quality slider maps to ffmpeg CRF: Low 28, Medium 23, High 18, Lossless 0.

## Crash recovery

TrayRecorder writes to a temporary MKV during capture and remuxes to your chosen format at stop. If the app crashes mid-recording, the partial file remains in `%TEMP%\screenrec_*\video.mkv` and is playable in VLC.

## Build from source

```powershell
git clone <repo> screenrec
cd screenrec
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pyinstaller==6.10.0

# Drop ffmpeg.exe (essentials build, https://www.gyan.dev/ffmpeg/builds/)
# into  src\resources\ffmpeg\ffmpeg.exe

pwsh -File build.ps1
```

Outputs:
- `dist\TrayRecorder\TrayRecorder.exe` — portable bundle (no install).
- `installer\Output\TrayRecorder_Setup.exe` — single-file installer (requires Inno Setup 6 installed locally).

## Uninstall

Windows **Settings → Apps → TrayRecorder → Uninstall**, or run the uninstaller from the Start Menu. The autostart registry entry is removed automatically; user settings under `HKCU\Software\Natran\ScreenRec` are preserved across uninstall (and across the rename from the legacy "ScreenRec" name) — delete the key manually for a clean wipe.

## Known limitations (v1)

- GDI capture (`gdigrab`) tops out around 22–28 fps at 2K+ resolutions on most hardware. Drop to 24 fps or use a smaller custom region for smoother captures.
- WASAPI loopback can drop audio packets under heavy CPU load.
- Recording multiple monitors into one file isn't supported (use Custom to span them).
- No webcam overlay, no pause/resume, no editing.

## License

TrayRecorder's own source code is released under the [MIT License](LICENSE).

The distributed installer and portable bundle include third-party software
under their own licenses — most notably a GPL-licensed build of FFmpeg. See
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for the full list and
redistribution obligations.
