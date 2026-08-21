"""FFmpeg video assembly with restrained cinematic movement.

Scene durations come from narration timing. Images get a slow zoom or pan
(Ken Burns-style) plus a short fade. This is intentionally a small,
configurable assembler — not a general effects engine.

Crop x/y in FFmpeg are integer pixels. Animating a 1920×1080 crop on a
small oversize canvas moves well under one output pixel per frame, which
quantizes into a visible staircase (left, then down, then left…). Motion is
therefore evaluated in an oversampled coordinate space and lanczos-downscaled
to the output size so 30 fps pans stay diagonal and smooth.
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

# Bump when the filter graph strategy changes so assemble cache invalidates.
MOTION_FILTER_VERSION = "restrained-travel-v2"
MOTION_OVERSAMPLE = 4
MOTION_HEADROOM = 1.05
# Full Ken Burns travel is paced over this many seconds. Shorter clips use a
# fraction of the headroom so a 3s hold does not race across the frame.
MOTION_FULL_TRAVEL_SECONDS = 24.0

# Bump when outro construction changes independently of the Ken Burns filter.
OUTRO_VERSION = "hold-fade-black-v1"


def last_scene_picture_seconds(narration_seconds: float, config: VideoConfig) -> float:
    """Last-scene length including the post-narration hold and fade to black."""

    base = max(narration_seconds, _MIN_SECONDS)
    return base + max(config.end_hold_seconds, 0.0) + max(config.end_fade_seconds, 0.0)


def outro_tail_seconds(config: VideoConfig) -> float:
    """Seconds added after the final narrated word (hold + fade + black)."""

    return (
        max(config.end_hold_seconds, 0.0)
        + max(config.end_fade_seconds, 0.0)
        + max(config.end_black_seconds, 0.0)
    )


def assemble_video(manifest: StoryManifest, store: ArtifactStore, config: VideoConfig) -> Path:
    require_ffmpeg()
    store.ensure_dirs()

    if not manifest.scenes:
        raise VideoAssemblyError("No scene clips to assemble.")

    last_index = manifest.scenes[-1].index
    clips: list[Path] = []
    for scene in manifest.scenes:
        image = store.root / scene.image_path if scene.image_path else store.scene_image_path(scene.index)
        if not image.exists():
            raise VideoAssemblyError(f"Missing scene image for {scene.id}: {image}")
        narration_duration = max(scene.duration_seconds or scene.target_duration_seconds or 2.0, _MIN_SECONDS)
        fade_out_seconds: float | None = None
        duration = narration_duration
        if scene.index == last_index:
            duration = last_scene_picture_seconds(narration_duration, config)
            if duration > narration_duration:
                fade_out_seconds = max(config.end_fade_seconds, 0.0)
                logger.info(
                    "Final scene outro: %.1fs hold, %.1fs fade to black (clip %.1fs, narration %.1fs)",
                    config.end_hold_seconds,
                    config.end_fade_seconds,
                    duration,
                    narration_duration,
                )
        clip_path = store.scene_clip_path(scene.index)
        _render_clip(image, clip_path, scene, duration, config, fade_out_seconds=fade_out_seconds)
        clips.append(clip_path)

    if config.end_black_seconds > 0:
        black_path = store.work_dir / "outro_black.mp4"
        _render_black(black_path, config.end_black_seconds, config)
        clips.append(black_path)
        logger.info("Appended %.1fs black after fade", config.end_black_seconds)

    silent = store.work_dir / "silent.mp4"
    _concat(clips, silent, config)

    output = store.video_path
    if store.narration_path.exists():
        _mux(silent, store.narration_path, output, config)
    else:
        logger.warning("No narration.mp3 found; video.mp4 will have no audio track.")
        shutil.copy(silent, output)
    return output


def _render_clip(
    image: Path,
    output: Path,
    scene: Scene,
    duration: float,
    config: VideoConfig,
    *,
    fade_out_seconds: float | None = None,
) -> None:
    vf = _motion_filter(scene.motion, duration, config, fade_out_seconds=fade_out_seconds)
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


def oversampled_motion_sizes(width: int, height: int) -> tuple[int, int, int, int]:
    """Return ``(scaled_w, scaled_h, crop_w, crop_h)`` in oversampled pixels.

    The source is scaled to a larger canvas (oversample × headroom), a crop
    window the size of ``oversample × output`` travels across it, then the
    crop is lanczos-downscaled to ``width×height``. Travel is duration-scaled
    so short clips stay nearly still.
    """

    width, height = _even(width), _even(height)
    crop_w = _even(width * MOTION_OVERSAMPLE)
    crop_h = _even(height * MOTION_OVERSAMPLE)
    scaled_w = _even(int(round(crop_w * MOTION_HEADROOM)))
    scaled_h = _even(int(round(crop_h * MOTION_HEADROOM)))
    return scaled_w, scaled_h, crop_w, crop_h


def motion_travel_fraction(duration: float) -> float:
    """How much of the available Ken Burns travel a clip should use."""

    if duration <= 0 or MOTION_FULL_TRAVEL_SECONDS <= 0:
        return 0.0
    return min(duration / MOTION_FULL_TRAVEL_SECONDS, 1.0)


def _lerp_expr(start: float, end: float, last: int) -> str:
    if abs(end - start) < 0.5:
        return f"{start:.2f}"
    return f"{start:.2f}+({end:.2f}-{start:.2f})*n/{last}"


def _motion_filter(
    motion: str,
    duration: float,
    config: VideoConfig,
    *,
    fade_out_seconds: float | None = None,
) -> str:
    """Restrained Ken Burns movement via oversampled crop, then downscale.

    Faster and more predictable than ffmpeg ``zoompan``, which is easy to
    misconfigure and expensive at 1080p. Frame index ``n`` (not timestamp
    ``t``) drives the path so 30 fps output is deterministic.

    ``fade_out_seconds`` overrides the default scene fade-out. The last
    scene uses ``video.end_fade_seconds`` so the picture can hold, then
    fade to black, without changing the 4× oversampled motion math.
    """

    width, height = _even(config.width), _even(config.height)
    scaled_w, scaled_h, crop_w, crop_h = oversampled_motion_sizes(width, height)
    max_x = max(scaled_w - crop_w, 0)
    max_y = max(scaled_h - crop_h, 0)
    fade_in = min(config.fade_seconds, max(duration / 5.0, 0.05))
    if fade_out_seconds is None:
        fade_out = fade_in
    else:
        fade_out = min(max(fade_out_seconds, 0.0), duration)
    fade_out_start = max(duration - fade_out, 0.0)
    frames = max(int(round(duration * config.fps)), 1)
    last = max(frames - 1, 1)
    travel = 0.0 if motion in {"none", "static"} else motion_travel_fraction(duration)
    center_x = max_x / 2.0
    center_y = max_y / 2.0

    if motion in {"none", "static"}:
        x = f"{center_x:.2f}"
        y = f"{center_y:.2f}"
    elif motion == "pan_right":
        x = _lerp_expr(center_x - (max_x * travel) / 2.0, center_x + (max_x * travel) / 2.0, last)
        y = f"{center_y:.2f}"
    elif motion == "pan_left":
        x = _lerp_expr(center_x + (max_x * travel) / 2.0, center_x - (max_x * travel) / 2.0, last)
        y = f"{center_y:.2f}"
    elif motion == "slow_zoom_out":
        start_x = center_x * (1.0 - travel)
        start_y = center_y * (1.0 - travel)
        x = _lerp_expr(start_x, start_x + max_x * travel, last)
        y = _lerp_expr(start_y, start_y + max_y * travel, last)
    else:
        # slow_zoom_in: a short drift from slightly high-right toward center-left.
        start_x = center_x * (1.0 - travel) + max_x * travel
        end_x = center_x * (1.0 - travel)
        start_y = center_y * (1.0 - travel) + max_y * travel * 0.55
        end_y = center_y * (1.0 - travel)
        x = _lerp_expr(start_x, end_x, last)
        y = _lerp_expr(start_y, end_y, last)

    parts = [
        f"scale={scaled_w}:{scaled_h}:flags=lanczos",
        f"crop={crop_w}:{crop_h}:{x}:{y}",
        f"scale={width}:{height}:flags=lanczos",
        "setsar=1",
        f"fade=t=in:st=0:d={fade_in:.3f}",
    ]
    if fade_out > 0:
        parts.append(f"fade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}")
    parts.append(f"fps={config.fps},format=yuv420p")
    return ",".join(parts)


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


def _render_black(output: Path, duration: float, config: VideoConfig) -> None:
    width, height = _even(config.width), _even(config.height)
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:r={config.fps}",
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


def _mux(silent_video: Path, narration: Path, output: Path, config: VideoConfig) -> None:
    """Mux picture with narration, padding silence through the outro.

    Narration is never time-stretched. ``apad`` fills hold / fade / black
    so the audio stream lasts as long as the picture. When a background
    music layer exists later, mix it in this graph so it can continue
    after speech and fade during the visual outro.
    """

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
            "-af",
            "apad",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
    )
