from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from biscuit.config import VideoConfig
from biscuit.media import media_duration_seconds
from biscuit.video import (
    MOTION_FILTER_VERSION,
    MOTION_FULL_TRAVEL_SECONDS,
    MOTION_HEADROOM,
    MOTION_OVERSAMPLE,
    OUTRO_VERSION,
    _motion_filter,
    last_scene_picture_seconds,
    motion_travel_fraction,
    outro_tail_seconds,
    oversampled_motion_sizes,
)


def test_motion_filter_is_valid_ffmpeg_graph() -> None:
    config = VideoConfig(width=640, height=360, fps=15, fade_seconds=0.1)
    vf = _motion_filter("slow_zoom_in", 1.0, config)
    scaled_w, scaled_h, crop_w, crop_h = oversampled_motion_sizes(640, 360)
    assert f"scale={scaled_w}:{scaled_h}:flags=lanczos" in vf
    assert f"crop={crop_w}:{crop_h}:" in vf
    assert "scale=640:360:flags=lanczos" in vf
    assert "fade=" in vf
    assert "n/" in vf
    assert MOTION_OVERSAMPLE == 4
    assert MOTION_HEADROOM == 1.05
    assert MOTION_FULL_TRAVEL_SECONDS == 24.0
    assert MOTION_FILTER_VERSION.startswith("restrained-travel")


def test_motion_filter_1080p_uses_oversampled_crop_then_downscale() -> None:
    config = VideoConfig(width=1920, height=1080, fps=30, fade_seconds=0.45)
    vf = _motion_filter("slow_zoom_in", 8.0, config)
    scaled_w, scaled_h, crop_w, crop_h = oversampled_motion_sizes(1920, 1080)
    assert crop_w == 1920 * MOTION_OVERSAMPLE
    assert crop_h == 1080 * MOTION_OVERSAMPLE
    assert scaled_w > crop_w
    assert scaled_h > crop_h
    assert f"crop={crop_w}:{crop_h}:" in vf
    assert "scale=1920:1080:flags=lanczos" in vf
    assert "setsar=1" in vf
    # Frame-index animation, not timestamp, so 30 fps steps are uniform.
    assert "n/" in vf
    assert "t/" not in vf


def test_motion_filter_diagonal_path_animates_both_axes() -> None:
    vf = _motion_filter("slow_zoom_in", 24.0, VideoConfig(width=1920, height=1080, fps=30))
    _scaled_w, _scaled_h, crop_w, crop_h = oversampled_motion_sizes(1920, 1080)
    assert f"crop={crop_w}:{crop_h}:" in vf
    assert vf.count("*n/") >= 2
    assert "t/" not in vf


def _crop_axis_spans(vf: str) -> tuple[float, float]:
    import re

    crop = next(part for part in vf.split(",") if part.startswith("crop="))
    _w, _h, x_expr, y_expr = crop[len("crop=") :].split(":", 3)

    def span(expr: str) -> float:
        match = re.search(r"\(([-\d.]+)-([-\d.]+)\)", expr)
        if not match:
            return 0.0
        return abs(float(match.group(1)) - float(match.group(2)))

    return span(x_expr), span(y_expr)


def test_short_clips_use_less_ken_burns_travel() -> None:
    config = VideoConfig(width=1920, height=1080, fps=30, fade_seconds=0.2)
    assert motion_travel_fraction(3.0) == 3.0 / 24.0
    assert motion_travel_fraction(24.0) == 1.0
    assert motion_travel_fraction(40.0) == 1.0
    short = _motion_filter("slow_zoom_in", 3.0, config)
    long = _motion_filter("slow_zoom_in", 24.0, config)
    static = _motion_filter("static", 3.0, config)
    static_crop = next(part for part in static.split(",") if part.startswith("crop="))
    assert "*n/" not in static_crop
    short_x, short_y = _crop_axis_spans(short)
    long_x, long_y = _crop_axis_spans(long)
    assert long_x > short_x * 3
    assert long_y > short_y * 3
    assert short_x > 0
    assert short_y > 0


def test_outro_timing_math_matches_configured_landing() -> None:
    config = VideoConfig(end_hold_seconds=4.0, end_fade_seconds=2.0, end_black_seconds=1.0)
    assert last_scene_picture_seconds(20.0, config) == 26.0
    assert outro_tail_seconds(config) == 7.0
    assert OUTRO_VERSION.startswith("hold-fade-black")


def test_last_scene_fade_to_black_uses_end_fade_not_scene_fade() -> None:
    config = VideoConfig(
        width=640,
        height=360,
        fps=15,
        fade_seconds=0.12,
        end_hold_seconds=4.0,
        end_fade_seconds=2.0,
        end_black_seconds=1.0,
    )
    duration = last_scene_picture_seconds(5.0, config)
    vf = _motion_filter("slow_zoom_in", duration, config, fade_out_seconds=config.end_fade_seconds)
    scaled_w, scaled_h, crop_w, crop_h = oversampled_motion_sizes(640, 360)
    assert f"scale={scaled_w}:{scaled_h}:flags=lanczos" in vf
    assert f"crop={crop_w}:{crop_h}:" in vf
    assert "fade=t=out:st=9.000:d=2.000" in vf
    assert "n/" in vf


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is required")
def test_mini_pipeline_video_is_valid(mini_story_path, test_config) -> None:
    from biscuit.artifacts import ArtifactStore
    from biscuit.pipeline import StoryPipeline

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store)
    duration = media_duration_seconds(store.video_path)
    assert duration is not None
    narration = media_duration_seconds(store.narration_path)
    assert duration > 0.4
    assert narration is not None
    assert duration >= narration + 6.5


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_smooth_motion_clip_renders_1080p(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    from biscuit.artifacts import ArtifactStore
    from biscuit.models import (
        Character,
        NarrationGuidance,
        Scene,
        Setting,
        StoryManifest,
        VisualStyle,
    )
    from biscuit.video import assemble_video

    store = ArtifactStore(tmp_path, "motion_check")
    store.ensure_dirs()
    image = store.scene_image_path(1)
    canvas = Image.new("RGB", (1920, 1080), (20, 40, 80))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((80, 80, 420, 360), fill=(220, 40, 40))
    draw.rectangle((1500, 700, 1840, 1000), fill=(40, 200, 90))
    canvas.save(image)

    manifest = StoryManifest(
        version=1,
        story_id="motion_check",
        title="Motion",
        tone="warm",
        target_duration_seconds=2,
        setting=Setting(location="courthouse"),
        visual_style=VisualStyle(),
        narration=NarrationGuidance(),
        characters=[Character(id="biscuit", name="Biscuit", species="dog")],
        scenes=[
            Scene(
                id="scene_001",
                index=1,
                beat_id="a",
                title="Snow",
                narration="Snow.",
                visual_description="snow",
                character_ids=["biscuit"],
                emotion="calm",
                image_path="scenes/001.png",
                duration_seconds=2.0,
                motion="slow_zoom_in",
            )
        ],
    )
    store = ArtifactStore(tmp_path, "motion_check")
    config = VideoConfig(
        width=1920,
        height=1080,
        fps=30,
        encoder_preset="ultrafast",
        fade_seconds=0.2,
        end_hold_seconds=0.0,
        end_fade_seconds=0.0,
        end_black_seconds=0.0,
    )
    output = assemble_video(manifest, store, config)
    assert output.exists()
    duration = media_duration_seconds(output)
    assert duration is not None
    assert 1.6 < duration < 2.4


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg is required")
def test_outro_hold_fade_black_and_padded_audio(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    from biscuit.artifacts import ArtifactStore
    from biscuit.media import run_ffmpeg
    from biscuit.models import (
        Character,
        NarrationGuidance,
        Scene,
        Setting,
        StoryManifest,
        VisualStyle,
    )
    from biscuit.video import assemble_video

    store = ArtifactStore(tmp_path, "outro_check")
    store.ensure_dirs()
    image = store.scene_image_path(1)
    canvas = Image.new("RGB", (640, 360), (20, 40, 80))
    ImageDraw.Draw(canvas).rectangle((40, 40, 200, 160), fill=(220, 40, 40))
    canvas.save(image)

    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "1.000",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "9",
            str(store.narration_path),
        ]
    )

    manifest = StoryManifest(
        version=1,
        story_id="outro_check",
        title="Outro",
        tone="warm",
        target_duration_seconds=1,
        setting=Setting(location="courthouse"),
        visual_style=VisualStyle(),
        narration=NarrationGuidance(),
        characters=[Character(id="biscuit", name="Biscuit", species="dog")],
        scenes=[
            Scene(
                id="scene_001",
                index=1,
                beat_id="a",
                title="Snow",
                narration="Snow.",
                visual_description="snow",
                character_ids=["biscuit"],
                emotion="calm",
                image_path="scenes/001.png",
                duration_seconds=1.0,
                motion="slow_zoom_in",
            )
        ],
    )
    config = VideoConfig(
        width=640,
        height=360,
        fps=15,
        encoder_preset="ultrafast",
        fade_seconds=0.1,
        end_hold_seconds=4.0,
        end_fade_seconds=2.0,
        end_black_seconds=1.0,
    )
    output = assemble_video(manifest, store, config)
    video_duration = media_duration_seconds(output)
    audio_duration = media_duration_seconds(output)
    narration = media_duration_seconds(store.narration_path)
    last_clip = media_duration_seconds(store.scene_clip_path(1))
    black = media_duration_seconds(store.work_dir / "outro_black.mp4")
    assert video_duration is not None
    assert 7.6 < video_duration < 8.5
    assert audio_duration is not None
    assert abs(audio_duration - video_duration) < 0.35
    assert narration is not None
    assert narration < 1.4
    assert last_clip is not None
    assert 6.6 < last_clip < 7.4
    assert black is not None
    assert 0.8 < black < 1.3
