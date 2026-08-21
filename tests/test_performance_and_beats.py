from __future__ import annotations

from pathlib import Path

from biscuit.models import Scene
from biscuit.performance import (
    apply_inferred_pacing,
    infer_break,
    join_performance_script,
    pace_text,
    split_sentences,
)
from biscuit.prompts import build_image_prompt
from biscuit.providers.story_template import TemplateStoryProvider
from biscuit.ssml import spoken_fingerprint, strip_ssml
from biscuit.story import load_story
from biscuit.visual_plan import apply_story_plan, plan_for_story


def test_pacing_varies_and_preserves_words() -> None:
    opening = (
        "The road ran without a town to finish it. Fence. Field. "
        "A sky the color of wet iron. He stopped. Then he turned into it."
    )
    paced = pace_text(opening, trailing_break=0.8)
    assert spoken_fingerprint(paced.ssml) == spoken_fingerprint(opening)
    assert "<break time=" in paced.ssml
    tags = [float(part.split('time="')[1].split("s")[0]) for part in paced.ssml.split("<break")[1:]]
    assert len(set(round(tag, 2) for tag in tags)) >= 3
    assert infer_break("Ice stood on the wire in little teeth.", "He stopped.", "Then he turned into it.") >= 1.2
    pair = infer_break(None, "Fence.", "Field.")
    after_pair = infer_break("Fence.", "Field.", "A sky the color of wet iron.")
    assert pair < after_pair


def test_inferred_pacing_does_not_rewrite_speech() -> None:
    scenes = [
        Scene(
            id="scene_001",
            index=1,
            beat_id="a",
            title="A",
            narration="Biscuit found the man in the snow. He stayed.",
            visual_description="snow",
            character_ids=["biscuit"],
            emotion="quiet",
        )
    ]
    apply_inferred_pacing(scenes)
    performance = join_performance_script(scenes)
    assert "Biscuit found the man in the snow." in strip_ssml(performance)
    assert "He stayed." in strip_ssml(performance)
    assert spoken_fingerprint(scenes[0].narration) == spoken_fingerprint(performance)


def test_red_mitten_visual_plan_preserves_literary_script(repo_root: Path) -> None:
    spec = load_story(
        repo_root / "stories" / "biscuit_and_the_red_mitten.yaml",
        characters_dir=repo_root / "characters",
    )
    assert plan_for_story(spec.id) is not None
    manifest = TemplateStoryProvider().expand(spec)
    literary = " ".join(scene.narration for scene in manifest.scenes)
    apply_story_plan(manifest, spec)
    assert 40 <= len(manifest.scenes) <= 64
    spoken = " ".join(scene.narration for scene in manifest.scenes)
    assert spoken_fingerprint(spoken) == spoken_fingerprint(literary)
    performance = join_performance_script(manifest.scenes)
    assert spoken_fingerprint(performance) == spoken_fingerprint(spoken)
    assert "<break time=" in performance
    stopped = next(scene for scene in manifest.scenes if scene.narration == "He stopped.")
    assert stopped.break_after_seconds >= 1.4
    empty = next(scene for scene in manifest.scenes if scene.shot_id == "empty_road")
    assert empty.character_ids == []
    prompt = build_image_prompt(empty, characters=manifest.character_map(), spec=spec)
    assert "no cars" in prompt.lower()
    assert "World continuity" in prompt
    assert empty.world_facts
    reused = [scene for scene in manifest.scenes if scene.reuse_shot_id]
    assert {scene.reuse_shot_id for scene in reused} <= {scene.shot_id for scene in manifest.scenes}


def test_pipeline_writes_performance_script(mini_story_path, test_config) -> None:
    from biscuit.artifacts import ArtifactStore
    from biscuit.pipeline import StoryPipeline
    from biscuit.ssml import spoken_fingerprint

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    manifest = pipeline.run(mini_story_path, store=store, through_stage="expand")
    assert store.performance_path.exists()
    assert store.visual_plan_path.exists()
    performance = store.performance_path.read_text(encoding="utf-8")
    literary = store.script_path.read_text(encoding="utf-8")
    assert spoken_fingerprint(performance) == spoken_fingerprint(literary)
    assert manifest.performance_text
    assert len(manifest.scenes) == 2


def test_reuse_source_image_copies_png(test_config) -> None:
    from biscuit.artifacts import ArtifactStore
    from biscuit.models import Character, Scene, Setting, StoryManifest, VisualStyle, NarrationGuidance
    from biscuit.pipeline import StoryPipeline
    from PIL import Image

    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "reuse")
    store.ensure_dirs()
    Image.new("RGB", (64, 36), (9, 8, 7)).save(store.scene_image_path(1))
    first = Scene(
        id="scene_001",
        index=1,
        beat_id="a",
        title="A",
        narration="One.",
        visual_description="road",
        character_ids=["biscuit"],
        emotion="quiet",
        shot_id="empty_road",
    )
    second = Scene(
        id="scene_002",
        index=2,
        beat_id="a",
        title="A",
        narration="Two.",
        visual_description="road again",
        character_ids=[],
        emotion="quiet",
        shot_id="empty_again",
        reuse_shot_id="empty_road",
    )
    manifest = StoryManifest(
        version=1,
        story_id="reuse",
        title="Reuse",
        tone="",
        target_duration_seconds=10,
        setting=Setting(),
        visual_style=VisualStyle(),
        narration=NarrationGuidance(),
        characters=[Character(id="biscuit", name="Biscuit", species="dog")],
        scenes=[first, second],
    )
    source = pipeline._reuse_source_image(second, manifest, store)
    assert source == store.scene_image_path(1)


def test_other_stories_stay_one_scene_per_beat(example_story_path: Path, repo_root: Path) -> None:
    spec = load_story(example_story_path, characters_dir=repo_root / "characters")
    assert plan_for_story(spec.id) is None
    manifest = TemplateStoryProvider().expand(spec)
    before = len(manifest.scenes)
    apply_story_plan(manifest, spec)
    assert len(manifest.scenes) == before == len(spec.beats)
    assert all(scene.performance_narration for scene in manifest.scenes)


def test_split_sentences_keeps_fragments() -> None:
    assert split_sentences("Fence. Field. A sky the color of wet iron.") == [
        "Fence.",
        "Field.",
        "A sky the color of wet iron.",
    ]
