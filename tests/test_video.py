from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from biscuit.config import VideoConfig
from biscuit.media import media_duration_seconds
from biscuit.video import (
    MOTION_FILTER_VERSION,
    MOTION_HEADROOM,
    MOTION_OVERSAMPLE,
    _motion_filter,
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
    assert "*n/" in vf
    assert MOTION_OVERSAMPLE == 4
    assert MOTION_HEADROOM == 1.16
    assert MOTION_FILTER_VERSION.startswith("oversample")


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
    assert "*n/" in vf
    assert "*t/" not in vf


def test_motion_filter_diagonal_path_animates_both_axes() -> None:
    vf = _motion_filter("slow_zoom_in", 4.0, VideoConfig(width=1920, height=1080, fps=30))
    _scaled_w, _scaled_h, crop_w, crop_h = oversampled_motion_sizes(1920, 1080)
    assert f"crop={crop_w}:{crop_h}:" in vf
    assert "max(" in vf
    assert "*(1-n/" in vf
    assert "*0.55" in vf


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is required")
def test_mini_pipeline_video_is_valid(mini_story_path, test_config) -> None:
    from biscuit.artifacts import ArtifactStore
    from biscuit.pipeline import StoryPipeline

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store)
    duration = media_duration_seconds(store.video_path)
    assert duration is not None
    assert duration > 0.4


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
    config = VideoConfig(width=1920, height=1080, fps=30, encoder_preset="ultrafast", fade_seconds=0.2)
    output = assemble_video(manifest, store, config)
    assert output.exists()
    duration = media_duration_seconds(output)
    assert duration is not None
    assert 1.6 < duration < 2.4
