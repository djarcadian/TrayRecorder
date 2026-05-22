# Third-Party Licenses

TrayRecorder itself is licensed under the MIT License (see [LICENSE](LICENSE)).
The distributed installer (`TrayRecorder_Setup.exe`) and portable bundle
(`dist\TrayRecorder\`) include third-party software listed below, each under
its own license.

## Bundled binary

### FFmpeg

- **Component:** `ffmpeg.exe` — included at `src\resources\ffmpeg\ffmpeg.exe`
  and bundled into the installer.
- **Build:** "essentials" build from <https://www.gyan.dev/ffmpeg/builds/> by
  Gyan Doshi.
- **License:** GPL v3 (because this build includes GPL-licensed components
  such as x264 and x265).
- **Source code:** FFmpeg source is available at
  <https://ffmpeg.org/download.html>. The exact source tarball corresponding
  to the bundled binary, along with the patches and license text, is
  published on Gyan Doshi's builds page above.
- **License text:** the full GPL v3 text ships with the gyan.dev binary
  distribution (`LICENSE.txt`) and is available at
  <https://www.gnu.org/licenses/gpl-3.0.txt>.

Because the bundled `ffmpeg.exe` is GPL-licensed, anyone redistributing the
TrayRecorder installer must comply with GPL v3 redistribution requirements
for that binary (provide source access and preserve the license text).
TrayRecorder's own source code is not derived from FFmpeg — it invokes
`ffmpeg.exe` as a subprocess — and therefore remains under the MIT license.

## Bundled Python packages

PyInstaller bundles the following Python packages (and their runtime
dependencies) into the distributed `.exe`. Each is listed with the license
declared by its upstream project; full license texts are included in the
upstream source distributions linked below.

| Package           | Version  | License            | Upstream                                                  |
|-------------------|----------|--------------------|-----------------------------------------------------------|
| PySide6           | 6.7.3    | LGPL v3            | <https://wiki.qt.io/Qt_for_Python>                        |
| Qt 6 (via PySide6)| (bundled)| LGPL v3 / GPL v3   | <https://www.qt.io/licensing/>                            |
| soundcard         | 0.4.3    | BSD 3-Clause       | <https://github.com/bastibe/SoundCard>                    |
| soundfile         | 0.12.1   | BSD 3-Clause       | <https://github.com/bastibe/python-soundfile>             |
| libsndfile (via soundfile) | (bundled) | LGPL v2.1 | <http://www.mega-nerd.com/libsndfile/>            |
| numpy             | 1.26.4   | BSD 3-Clause       | <https://numpy.org/>                                      |
| keyboard          | 0.13.5   | MIT                | <https://github.com/boppreh/keyboard>                     |
| win10toast-click  | 0.1.2    | MIT                | <https://github.com/vardecab/win10toast-click>            |
| pywin32           | 306      | PSF (Mark Hammond) | <https://github.com/mhammond/pywin32>                     |
| Pillow            | 10.4.0   | HPND (MIT-style)   | <https://github.com/python-pillow/Pillow>                 |

**Note on LGPL components (PySide6/Qt, libsndfile):** these are dynamically
loaded as separate DLLs inside the bundle, so end users retain the ability to
replace them with a modified version of Qt or libsndfile in accordance with
the LGPL.

## Reporting issues

If you believe a third-party component is missing from this list or its
license has been misstated, please open an issue at
<https://github.com/djarcadian/TrayRecorder/issues>.
