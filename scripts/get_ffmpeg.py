#!/usr/bin/env python3
"""Download an FFmpeg build for the current OS into ffmpeg/<os>/.

The binaries are not tracked in git (they are ~100 MB); this script fetches
them for local development and for the CI installer builds.

Usage:
    python scripts/get_ffmpeg.py [--force]
"""
from __future__ import annotations

import io
import os
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WINDOWS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
LINUX_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"


def download(url: str) -> bytes:
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "PitchShifter-build"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def install_windows(dest: str) -> None:
    data = download(WINDOWS_URL)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        member = next(
            name for name in zf.namelist() if name.endswith("/bin/ffmpeg.exe")
        )
        with zf.open(member) as src, open(dest, "wb") as out:
            out.write(src.read())


def install_linux(dest: str) -> None:
    data = download(LINUX_URL)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
        member = next(
            m for m in tf.getmembers() if m.name.endswith("/ffmpeg") and m.isfile()
        )
        src = tf.extractfile(member)
        assert src is not None
        with open(dest, "wb") as out:
            out.write(src.read())
    os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    force = "--force" in sys.argv
    is_windows = platform.system().lower() == "windows"
    subdir = "windows" if is_windows else "linux"
    exe = "ffmpeg.exe" if is_windows else "ffmpeg"
    dest = os.path.join(ROOT, "ffmpeg", subdir, exe)

    if os.path.exists(dest) and not force:
        print(f"FFmpeg already present at {dest} (use --force to re-download)")
        return

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if is_windows:
        install_windows(dest)
    else:
        install_linux(dest)
    print(f"FFmpeg installed at {dest}")


if __name__ == "__main__":
    main()
