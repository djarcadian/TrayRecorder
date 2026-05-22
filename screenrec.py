"""Top-level entry point for PyInstaller.

This sits outside the `src` package so PyInstaller can run it as a plain
script without breaking the package's relative imports inside src/.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` is importable as a package
# (works both in dev and in the PyInstaller-frozen bundle).
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys._MEIPASS)))  # type: ignore[attr-defined]
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
