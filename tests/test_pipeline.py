from __future__ import annotations

from pathlib import Path

import pytest

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


def test_pipeline_development_regenerates_stale_images(mini_story_path, test_config, monkeypatch) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")
    (store.work_dir / "001.image.hash").write_text("stale\n", encoding="utf-8")

    calls = {"indexes": []}
    original = DevelopmentImageProvider.generate

    def wrapped(self, request, output_path):
        calls["indexes"].append(request.scene.index)
        return original(self, request, output_path)

    monkeypatch.setattr(DevelopmentImageProvider, "generate", wrapped)
    pipeline.run(mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate")
    assert calls["indexes"] == [1]


def test_pipeline_regenerate_image_only_one_scene(mini_story_path, test_config, monkeypatch) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")

    calls = {"indexes": []}
    original = DevelopmentImageProvider.generate

    def wrapped(self, request, output_path):
        calls["indexes"].append(request.scene.index)
        return original(self, request, output_path)

    monkeypatch.setattr(DevelopmentImageProvider, "generate", wrapped)
    pipeline.run(
        mini_story_path,
        store=store,
        from_stage="illustrate",
        through_stage="illustrate",
        regenerate_images=[2],
    )
    assert calls["indexes"] == [2]


def test_pipeline_openai_stale_cache_does_not_spend(mini_story_path, test_config, monkeypatch) -> None:
    from biscuit.config import ImageConfig, OpenAIImageConfig
    from biscuit.providers.image_openai import OpenAIImageProvider

    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-not-real")
    test_config.image = ImageConfig(
        provider="openai",
        width=test_config.image.width,
        height=test_config.image.height,
        openai=OpenAIImageConfig(api_key_env="TEST_OPENAI_KEY"),
    )
    calls = {"n": 0}

    def fake_generate(self, request, output_path):
        calls["n"] += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        Image.new("RGB", (request.width, request.height), (20, 30, 40)).save(output_path)
        return output_path

    monkeypatch.setattr(OpenAIImageProvider, "generate", fake_generate)
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")
    assert calls["n"] == 2

    pipeline.run(mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate")
    assert calls["n"] == 2

    (store.work_dir / "001.image.hash").write_text("stale\n", encoding="utf-8")
    pipeline.run(mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate")
    assert calls["n"] == 2, "stale paid cache must reuse, not regenerate"

    pipeline.run(
        mini_story_path,
        store=store,
        from_stage="illustrate",
        through_stage="illustrate",
        regenerate_images=[1],
    )
    assert calls["n"] == 3


def test_pipeline_image_failure_preserves_completed_scene(mini_story_path, test_config, monkeypatch) -> None:
    from biscuit.exceptions import ImageGenerationError

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="prompts")

    original = DevelopmentImageProvider.generate

    def wrapped(self, request, output_path):
        if request.scene.index == 2:
            raise ImageGenerationError("boom for scene_002")
        return original(self, request, output_path)

    monkeypatch.setattr(DevelopmentImageProvider, "generate", wrapped)
    with pytest.raises(ImageGenerationError, match="scene_002"):
        pipeline.run(mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate")
    assert store.scene_image_path(1).exists()
    assert not store.scene_image_path(2).exists()


def test_pipeline_unknown_regenerate_index(mini_story_path, test_config) -> None:
    from biscuit.exceptions import ConfigurationError

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    with pytest.raises(ConfigurationError, match="not in this story"):
        pipeline.run(
            mini_story_path,
            store=store,
            through_stage="illustrate",
            regenerate_images=[99],
        )


def test_assemble_rebuilds_when_image_changes(mini_story_path, test_config, monkeypatch) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="assemble")

    calls = {"n": 0}

    def fake_assemble(*_args, **_kwargs):
        calls["n"] += 1

    monkeypatch.setattr("biscuit.pipeline.assemble_video", fake_assemble)
    pipeline.run(mini_story_path, store=store, from_stage="assemble", through_stage="assemble")
    assert calls["n"] == 0

    from PIL import Image

    Image.new("RGB", (640, 360), (255, 0, 0)).save(store.scene_image_path(1))
    pipeline.run(mini_story_path, store=store, from_stage="assemble", through_stage="assemble")
    assert calls["n"] == 1


def test_assemble_rebuilds_when_outro_config_changes(mini_story_path, test_config, monkeypatch) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="assemble")

    calls = {"n": 0}

    def fake_assemble(*_args, **_kwargs):
        calls["n"] += 1

    monkeypatch.setattr("biscuit.pipeline.assemble_video", fake_assemble)
    pipeline.run(mini_story_path, store=store, from_stage="assemble", through_stage="assemble")
    assert calls["n"] == 0

    test_config.video.end_hold_seconds = 9.0
    pipeline.run(mini_story_path, store=store, from_stage="assemble", through_stage="assemble")
    assert calls["n"] == 1


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


def _install_fake_openai(monkeypatch, calls: dict):
    from biscuit.providers.image_openai import OpenAIImageProvider
    from PIL import Image

    def fake_generate(self, request, output_path):
        calls.setdefault("indexes", []).append(request.scene.index)
        calls["n"] = calls.get("n", 0) + 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (request.width, request.height), (20, 30, 40)).save(output_path)
        return output_path

    monkeypatch.setattr(OpenAIImageProvider, "generate", fake_generate)


def _openai_config(test_config, monkeypatch):
    from biscuit.config import ImageConfig, OpenAIImageConfig

    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-not-real")
    test_config.image = ImageConfig(
        provider="openai",
        width=test_config.image.width,
        height=test_config.image.height,
        openai=OpenAIImageConfig(api_key_env="TEST_OPENAI_KEY"),
    )
    return test_config


def _write_image_stamp(store, index: int, *, digest: str, provider: str | None) -> None:
    import json

    path = store.work_dir / f"{index:03d}.image.hash"
    if provider is None:
        path.write_text(digest + "\n", encoding="utf-8")
    else:
        path.write_text(
            json.dumps({"v": 1, "hash": digest, "provider": provider}, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def test_pipeline_development_placeholders_are_replaced_by_openai(
    mini_story_path, test_config, monkeypatch
) -> None:
    """development → openai must generate; placeholders are not treated as paid."""

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")
    stamp = (store.work_dir / "001.image.hash").read_text(encoding="utf-8")
    assert '"provider": "development"' in stamp or '"provider":"development"' in stamp

    _openai_config(test_config, monkeypatch)
    calls: dict = {}
    _install_fake_openai(monkeypatch, calls)
    StoryPipeline(test_config).run(
        mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate"
    )
    assert calls["indexes"] == [1, 2]


def test_pipeline_legacy_development_hash_is_replaced_by_openai(
    mini_story_path, test_config, monkeypatch
) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")
    manifest = store.read_manifest()
    characters = manifest.character_map()
    for scene in manifest.scenes:
        present = [characters[cid] for cid in scene.character_ids if cid in characters]
        digest = pipeline._image_cache_hash(scene, present, provider="development")
        _write_image_stamp(store, scene.index, digest=digest, provider=None)

    _openai_config(test_config, monkeypatch)
    calls: dict = {}
    _install_fake_openai(monkeypatch, calls)
    StoryPipeline(test_config).run(
        mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate"
    )
    assert calls["indexes"] == [1, 2]


def test_pipeline_stale_openai_image_remains_protected(mini_story_path, test_config, monkeypatch) -> None:
    _openai_config(test_config, monkeypatch)
    calls: dict = {}
    _install_fake_openai(monkeypatch, calls)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    StoryPipeline(test_config).run(mini_story_path, store=store, through_stage="illustrate")
    assert calls["n"] == 2

    _write_image_stamp(store, 1, digest="stale-openai-fingerprint", provider="openai")
    StoryPipeline(test_config).run(
        mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate"
    )
    assert calls["n"] == 2, "stale OpenAI PNG must be reused, not regenerated"


def test_pipeline_missing_openai_image_generates(mini_story_path, test_config, monkeypatch) -> None:
    _openai_config(test_config, monkeypatch)
    calls: dict = {}
    _install_fake_openai(monkeypatch, calls)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    StoryPipeline(test_config).run(mini_story_path, store=store, through_stage="illustrate")
    assert calls["indexes"] == [1, 2]

    store.scene_image_path(2).unlink()
    calls["indexes"] = []
    StoryPipeline(test_config).run(
        mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate"
    )
    assert calls["indexes"] == [2]


def test_pipeline_partial_paid_run_resumes_development_and_missing(
    mini_story_path, test_config, monkeypatch
) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="illustrate")

    _openai_config(test_config, monkeypatch)
    calls: dict = {}
    _install_fake_openai(monkeypatch, calls)
    openai_pipeline = StoryPipeline(test_config)
    manifest = store.read_manifest()
    scene1 = manifest.scenes[0]
    present = [
        manifest.character_map()[cid] for cid in scene1.character_ids if cid in manifest.character_map()
    ]
    openai_hash = openai_pipeline._image_cache_hash(scene1, present)
    _write_image_stamp(store, 1, digest=openai_hash, provider="openai")

    openai_pipeline.run(
        mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate"
    )
    assert calls["indexes"] == [2], "paid scene 1 stays; leftover development scene 2 generates"


def test_pipeline_paid_to_paid_provider_switch_is_conservative(
    mini_story_path, test_config, monkeypatch
) -> None:
    _openai_config(test_config, monkeypatch)
    calls: dict = {}
    _install_fake_openai(monkeypatch, calls)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    StoryPipeline(test_config).run(mini_story_path, store=store, through_stage="illustrate")
    assert calls["n"] == 2

    _write_image_stamp(store, 1, digest="other-paid-fingerprint", provider="another_paid")
    StoryPipeline(test_config).run(
        mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate"
    )
    assert calls["n"] == 2, "valid paid assets from another provider must not be replaced"


def test_openai_illustrate_requires_env_var(mini_story_path, test_config, monkeypatch) -> None:
    from biscuit.config import ImageConfig, OpenAIImageConfig
    from biscuit.exceptions import ConfigurationError

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TEST_OPENAI_KEY", raising=False)
    test_config.image = ImageConfig(
        provider="openai",
        width=test_config.image.width,
        height=test_config.image.height,
        openai=OpenAIImageConfig(api_key_env="TEST_OPENAI_KEY"),
    )
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    with pytest.raises(ConfigurationError, match="TEST_OPENAI_KEY"):
        pipeline.run(mini_story_path, store=store, through_stage="illustrate")
