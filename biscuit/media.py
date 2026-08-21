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


def insert_silence_segments(path: Path, insertions: list[tuple[float, float]]) -> None:
    """Insert silence into ``path`` at source-audio timestamps.

    ``insertions`` are ``(at_seconds, silence_seconds)`` on the *original*
    file clock. They are applied last-to-first so earlier times stay valid.
    """

    cleaned = [(max(0.0, float(at)), float(dur)) for at, dur in insertions if float(dur) > 0.001]
    if not cleaned:
        return
    require_ffmpeg()
    rate, layout = _audio_stream_params(path)
    current = path
    temps: list[Path] = []
    try:
        for at, dur in sorted(cleaned, key=lambda item: item[0], reverse=True):
            nxt = current.with_name(current.name + f".pad{len(temps)}.mp3")
            temps.append(nxt)
            _insert_one_silence(current, nxt, at, dur, rate, layout)
            current = nxt
        if current != path:
            current.replace(path)
            if current in temps:
                temps.remove(current)
    finally:
        for tmp in temps:
            tmp.unlink(missing_ok=True)


def _audio_stream_params(path: Path) -> tuple[int, str]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 44100, "stereo"
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels,channel_layout",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    rate = 44100
    layout = "stereo"
    try:
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [{}])[0]
        rate = int(stream.get("sample_rate") or rate)
        channels = int(stream.get("channels") or 2)
        layout = str(stream.get("channel_layout") or ("mono" if channels == 1 else "stereo"))
    except (TypeError, ValueError, json.JSONDecodeError, IndexError):
        pass
    if layout in {"", "unknown", "None"}:
        layout = "stereo"
    return rate, layout


def _insert_one_silence(
    source: Path,
    dest: Path,
    at: float,
    duration: float,
    rate: int,
    layout: str,
) -> None:
    src_dur = media_duration_seconds(source) or 0.0
    silence = f"anullsrc=r={rate}:cl={layout},atrim=0:{duration:.4f},asetpts=PTS-STARTPTS"
    if at <= 0.001:
        filt = f"{silence}[sil];[sil][0:a]concat=n=2:v=0:a=1[out]"
    elif at >= src_dur - 0.001:
        filt = f"{silence}[sil];[0:a][sil]concat=n=2:v=0:a=1[out]"
    else:
        filt = (
            f"[0:a]atrim=0:{at:.4f},asetpts=PTS-STARTPTS[left];"
            f"[0:a]atrim=start={at:.4f},asetpts=PTS-STARTPTS[right];"
            f"{silence}[sil];"
            f"[left][sil][right]concat=n=3:v=0:a=1[out]"
        )
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            filt,
            "-map",
            "[out]",
            "-codec:a",
            "libmp3lame",
            "-qscale:a",
            "4",
            str(dest),
        ]
    )
