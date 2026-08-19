from __future__ import annotations

import shutil

import pytest

from biscuit.media import media_duration_seconds
from biscuit.video import _motion_filter
from biscuit.config import VideoConfig


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_motion_filter_is_valid_ffmpeg_graph() -> None:
    config = VideoConfig(width=640, height=360, fps=15, fade_seconds=0.1)
    vf = _motion_filter("slow_zoom_in", 1.0, config)
    assert "crop=" in vf
    assert "fade=" in vf
    assert "640:360" in vf or "crop=640:360" in vf


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
