from __future__ import annotations

from pathlib import Path

from biscuit.artifacts import ArtifactStore
from biscuit.pipeline import StoryPipeline
from biscuit.providers.image_development import DevelopmentImageProvider


def test_pipeline_end_to_end_development(mini_story_path, test_config) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    manifest = pipeline.run(mini_story_path, store=store)

    assert store.manifest_path.exists()
    assert store.script_path.exists()
    assert store.narration_path.exists()
    assert store.timing_path.exists()
    assert store.scene_image_path(1).exists()
    assert store.scene_image_path(2).exists()
    assert store.scene_prompt_path(1).exists()
    assert "Biscuit" in store.scene_prompt_path(1).read_text(encoding="utf-8")
    assert store.video_path.exists()
    assert store.video_path.stat().st_size > 1000
    assert store.thumbnail_path.exists()
    assert store.title_path.exists()
    assert store.description_path.exists()
    assert manifest.scenes[0].duration_seconds
    assert manifest.scenes[0].image_path == "scenes/001.png"


def test_pipeline_skips_existing_images(mini_story_path, test_config, monkeypatch) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")

    calls = {"n": 0}
    original = DevelopmentImageProvider.generate

    def wrapped(self, request, output_path):
        calls["n"] += 1
        return original(self, request, output_path)

    monkeypatch.setattr(DevelopmentImageProvider, "generate", wrapped)
    pipeline.run(mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate")
    assert calls["n"] == 0


def test_pipeline_force_regenerates_images(mini_story_path, test_config, monkeypatch) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")

    calls = {"n": 0}
    original = DevelopmentImageProvider.generate

    def wrapped(self, request, output_path):
        calls["n"] += 1
        return original(self, request, output_path)

    monkeypatch.setattr(DevelopmentImageProvider, "generate", wrapped)
    pipeline.run(
        mini_story_path,
        store=store,
        from_stage="illustrate",
        through_stage="illustrate",
        force=True,
    )
    assert calls["n"] == 2


def test_dry_run_creates_no_video(mini_story_path, test_config) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, dry_run=True)
    assert not store.video_path.exists()
    assert not store.narration_path.exists()


def test_from_stage_assemble_reuses_assets(mini_story_path, test_config) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")
    store.video_path.write_bytes(b"not-a-real-video")
    pipeline.run(mini_story_path, store=store, from_stage="package", through_stage="package")
    # Did not assemble, so the dummy video remains.
    assert store.video_path.read_bytes() == b"not-a-real-video"
    assert store.title_path.exists()
