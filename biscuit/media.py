"""Thin wrappers around the ffmpeg/ffprobe CLIs."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from biscuit.exceptions import VideoAssemblyError

logger = logging.getLogger(__name__)


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise VideoAssemblyError(
            "ffmpeg was not found on PATH. Install it (e.g. 'apt install ffmpeg' or "
            "'brew install ffmpeg') to assemble video."
        )
    return path


def run_ffmpeg(command: list[str]) -> None:
    require_ffmpeg()
    logger.debug("Running: %s", " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoAssemblyError(f"ffmpeg failed: {result.stderr[-2500:]}")


def media_duration_seconds(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None or not path.exists():
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("ffprobe failed for %s: %s", path, result.stderr[-500:])
        return None
    try:
        payload = json.loads(result.stdout)
        return float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
