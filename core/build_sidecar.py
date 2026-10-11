"""Build the self-contained core that ships inside Sasu.app.

    uv run --with pyinstaller python build_sidecar.py

Output: apps/desktop/src-tauri/resources/sasu-core/ (a folder, not --onefile, so the
app starts instantly instead of unpacking itself on every launch). Voice models are
not bundled; they download on first use.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "apps" / "desktop" / "src-tauri" / "resources"
WORK = HERE / "build"

if __name__ == "__main__":
    shutil.rmtree(OUT / "sasu-core", ignore_errors=True)
    PyInstaller.__main__.run(
        [
            str(HERE / "sidecar_entry.py"),
            "--name=sasu-core",
            "--onedir",
            "--noconfirm",
            "--clean",
            f"--distpath={OUT}",
            f"--workpath={WORK}",
            f"--specpath={WORK}",
            "--target-architecture=arm64",
            "--collect-all=sherpa_onnx",
            "--collect-all=sounddevice",
            "--collect-submodules=uvicorn",
            "--collect-submodules=sasu_core",
            "--exclude-module=tkinter",
            "--exclude-module=pytest",
            "--exclude-module=mypy",
        ]
    )
    shutil.rmtree(WORK, ignore_errors=True)
    size = sum(f.stat().st_size for f in (OUT / "sasu-core").rglob("*") if f.is_file())
    print(f"built {OUT / 'sasu-core'} ({size / 1e6:.0f} MB)")
