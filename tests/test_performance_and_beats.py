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
from biscuit.visual_plan import PLANNER_VERSION, apply_story_plan, plan_for_story, plan_to_dict


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


def _red_mitten_manifest(repo_root: Path):
    spec = load_story(
        repo_root / "stories" / "biscuit_and_the_red_mitten.yaml",
        characters_dir=repo_root / "characters",
    )
    manifest = TemplateStoryProvider().expand(spec)
    literary = " ".join(scene.narration for scene in manifest.scenes)
    apply_story_plan(manifest, spec)
    return spec, manifest, literary


def test_red_mitten_visual_plan_preserves_literary_script(repo_root: Path) -> None:
    spec, manifest, literary = _red_mitten_manifest(repo_root)
    assert plan_for_story(spec.id) is not None
    assert PLANNER_VERSION.startswith("cinematic-sequences")
    unique = [scene for scene in manifest.scenes if not scene.reuse_shot_id]
    reused = [scene for scene in manifest.scenes if scene.reuse_shot_id]
    assert 8 <= len({scene.sequence_id for scene in manifest.scenes}) <= 10
    assert 18 <= len(unique) <= 25
    assert len(manifest.scenes) == len(unique) + len(reused)
    spoken = " ".join(scene.narration for scene in manifest.scenes)
    assert spoken_fingerprint(spoken) == spoken_fingerprint(literary)
    performance = join_performance_script(manifest.scenes)
    assert spoken_fingerprint(performance) == spoken_fingerprint(spoken)
    assert "<break time=" in performance
    stopped_at = performance.find("He stopped.")
    assert stopped_at != -1
    nearby = performance[stopped_at : stopped_at + 80]
    assert "<break time=" in nearby
    pause = float(nearby.split('time="')[1].split("s")[0])
    assert pause >= 1.2
    empty = next(scene for scene in manifest.scenes if scene.shot_id == "empty_road")
    assert empty.character_ids == []
    assert empty.location_id == "empty_road"
    assert empty.motion == "static"
    prompt = build_image_prompt(empty, characters=manifest.character_map(), spec=spec)
    assert "World continuity" not in prompt
    assert "no cars" not in empty.local_prompt.lower()
    assert "snowplow" not in empty.local_prompt.lower()
    assert "sedan" not in empty.local_prompt.lower()
    assert "biscuit" not in empty.local_prompt.lower()
    assert {scene.reuse_shot_id for scene in reused} <= {scene.shot_id for scene in manifest.scenes}


def test_red_mitten_prompts_are_local_and_timed(repo_root: Path) -> None:
    spec, manifest, _literary = _red_mitten_manifest(repo_root)
    characters = manifest.character_map()
    by_id = {scene.shot_id: scene for scene in manifest.scenes}

    field = by_id["field_crossing"]
    field_prompt = build_image_prompt(field, characters=characters, spec=spec)
    assert field.location_id == "open_field"
    assert "treeline" in field_prompt.lower() or "tree" in field_prompt.lower()
    for leaked in ("sedan", "snowplow", "culvert", "woman", "road"):
        assert leaked not in field.local_prompt.lower()

    discovery = by_id["culvert_discovery"]
    discovery_prompt = build_image_prompt(discovery, characters=characters, spec=spec)
    assert "woman" in discovery_prompt.lower()
    assert "child" in discovery_prompt.lower()
    assert "snowplow" not in discovery_prompt.lower()

    amber = by_id["amber_far"]
    people_shots = {"culvert_discovery", "culvert_vigil", "rescue_in_culvert", "running_board"}
    plow_index = next(index for index, scene in enumerate(manifest.scenes) if scene.shot_id == "amber_far")
    for scene in manifest.scenes[:plow_index]:
        prompt = build_image_prompt(scene, characters=characters, spec=spec).lower()
        assert "snowplow" not in prompt
        assert " plow" not in prompt
        assert "amber" not in prompt
        if scene.shot_id not in people_shots:
            assert "woman" not in scene.local_prompt.lower()
    amber_prompt = build_image_prompt(amber, characters=characters, spec=spec).lower()
    assert "amber" in amber_prompt
    assert "snowplow" in amber_prompt

    opening = build_image_prompt(by_id["empty_road"], characters=characters, spec=spec)
    field_shot = field.local_prompt
    culvert = discovery.local_prompt
    first_plow = amber.local_prompt
    assert "two-lane" in opening.lower() or "blacktop" in opening.lower()
    assert "field" in field_shot.lower()
    assert "woman" in culvert.lower()
    assert "amber" in first_plow.lower()

    plan = plan_to_dict(manifest)
    assert plan["visual_bible"]
    assert plan["sequences"]
    assert plan["shots"][0]["critic"]["status"] == "not_implemented"
    assert all(shot["location_id"] for shot in plan["shots"])
    assert all(shot["local_prompt"] for shot in plan["shots"])


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
