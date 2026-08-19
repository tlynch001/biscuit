"""FFmpeg video assembly with restrained cinematic movement.

Scene durations come from narration timing. Images get a slow zoom or pan
(Ken Burns-style) plus a short fade. This is intentionally a small,
configurable assembler — not a general effects engine.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from biscuit.artifacts import ArtifactStore
from biscuit.config import VideoConfig
from biscuit.exceptions import VideoAssemblyError
from biscuit.media import require_ffmpeg, run_ffmpeg
from biscuit.models import Scene, StoryManifest

logger = logging.getLogger(__name__)

_MIN_SECONDS = 0.2


def assemble_video(manifest: StoryManifest, store: ArtifactStore, config: VideoConfig) -> Path:
    require_ffmpeg()
    store.ensure_dirs()

    clips: list[Path] = []
    for scene in manifest.scenes:
        image = store.root / scene.image_path if scene.image_path else store.scene_image_path(scene.index)
        if not image.exists():
            raise VideoAssemblyError(f"Missing scene image for {scene.id}: {image}")
        duration = max(scene.duration_seconds or scene.target_duration_seconds or 2.0, _MIN_SECONDS)
        clip_path = store.scene_clip_path(scene.index)
        _render_clip(image, clip_path, scene, duration, config)
        clips.append(clip_path)

    if not clips:
        raise VideoAssemblyError("No scene clips to assemble.")

    silent = store.work_dir / "silent.mp4"
    _concat(clips, silent, config)

    output = store.video_path
    if store.narration_path.exists():
        _mux(silent, store.narration_path, output, config)
    else:
        logger.warning("No narration.mp3 found; video.mp4 will have no audio track.")
        shutil.copy(silent, output)
    return output


def _render_clip(image: Path, output: Path, scene: Scene, duration: float, config: VideoConfig) -> None:
    vf = _motion_filter(scene.motion, duration, config)
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(config.fps),
            "-i",
            str(image),
            "-vf",
            vf,
            "-t",
            f"{duration:.3f}",
            "-r",
            str(config.fps),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            config.encoder_preset,
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    )


def _even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def _motion_filter(motion: str, duration: float, config: VideoConfig) -> str:
    """Restrained Ken Burns movement via crop-on-oversized-scale.

    Faster and more predictable than ffmpeg ``zoompan``, which is easy to
    misconfigure and expensive at 1080p.
    """

    width, height = _even(config.width), _even(config.height)
    scaled_w, scaled_h = _even(int(width * 1.16)), _even(int(height * 1.16))
    max_x = max(scaled_w - width, 0)
    max_y = max(scaled_h - height, 0)
    fade = min(config.fade_seconds, max(duration / 5.0, 0.05))
    fade_out_start = max(duration - fade, 0.0)
    t = max(duration, 0.001)

    if motion == "pan_right":
        x = f"min({max_x}*t/{t:.3f}\\,{max_x})"
        y = str(max_y // 2)
    elif motion == "pan_left":
        x = f"max({max_x}*(1-t/{t:.3f})\\,0)"
        y = str(max_y // 2)
    elif motion == "slow_zoom_out":
        x = f"min({max_x}*t/{t:.3f}\\,{max_x})"
        y = f"min({max_y}*t/{t:.3f}\\,{max_y})"
    elif motion in {"none", "static"}:
        x = str(max_x // 2)
        y = str(max_y // 2)
    else:
        # slow_zoom_in: drift toward the upper-right of the oversized frame
        x = f"max({max_x}*(1-t/{t:.3f})\\,0)"
        y = f"max({max_y}*(1-t/{t:.3f}*0.55)\\,0)"

    return (
        f"scale={scaled_w}:{scaled_h},"
        f"crop={width}:{height}:{x}:{y},"
        f"fade=t=in:st=0:d={fade:.3f},"
        f"fade=t=out:st={fade_out_start:.3f}:d={fade:.3f},"
        f"fps={config.fps},format=yuv420p"
    )


def _concat(clips: list[Path], output: Path, config: VideoConfig) -> None:
    list_file = output.parent / "concat_list.txt"
    with list_file.open("w", encoding="utf-8") as fh:
        for clip in clips:
            fh.write(f"file '{clip.resolve()}'\n")
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:v",
            "libx264",
            "-preset",
            config.encoder_preset,
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(config.fps),
            str(output),
        ]
    )


def _mux(silent_video: Path, narration: Path, output: Path, config: VideoConfig) -> None:
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(narration),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
    )
