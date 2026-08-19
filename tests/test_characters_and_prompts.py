from __future__ import annotations

from biscuit.models import (
    Character,
    NarrationGuidance,
    Scene,
    Setting,
    StoryManifest,
    VisualStyle,
    join_script,
)
from biscuit.prompts import build_image_prompt
from biscuit.providers.story_template import TemplateStoryProvider
from biscuit.story import load_story


def test_character_consistency_block_includes_anchors() -> None:
    character = Character(
        id="biscuit",
        name="Biscuit",
        species="dog",
        appearance={"coat": "cream-gold", "distinctive": ["red bandana"]},
        visual_anchors=["never change the bandana"],
    )
    block = character.consistency_block()
    assert "Biscuit" in block
    assert "red bandana" in block
    assert "never change the bandana" in block


def test_prompts_propagate_character_into_every_relevant_scene(
    example_story_path, repo_root
) -> None:
    spec = load_story(example_story_path, characters_dir=repo_root / "characters")
    manifest = TemplateStoryProvider().expand(spec)
    biscuit_scenes = [scene for scene in manifest.scenes if "biscuit" in scene.character_ids]
    assert biscuit_scenes
    for scene in biscuit_scenes:
        prompt = build_image_prompt(scene, characters=manifest.character_map(), spec=spec)
        assert "Biscuit" in prompt
        assert "bandana" in prompt.lower()
        assert "cream-gold" in prompt or "cream" in prompt.lower()
        veteran_scenes_should_differ = "veteran" in scene.character_ids
        if veteran_scenes_should_differ:
            assert "Veteran" in prompt or "olive" in prompt.lower()


def test_prompt_does_not_invent_absent_characters(mini_story_path, repo_root) -> None:
    spec = load_story(mini_story_path, characters_dir=repo_root / "characters")
    manifest = TemplateStoryProvider().expand(spec)
    last = manifest.scenes[-1]
    assert last.character_ids == ["biscuit"]
    prompt = build_image_prompt(last, characters=manifest.character_map(), spec=spec)
    assert "Biscuit" in prompt
    assert "Veteran" not in prompt


def test_join_script_uses_blank_line_separators() -> None:
    scenes = [
        Scene(id="a", index=1, beat_id="a", title="A", narration="One.", visual_description="", character_ids=[], emotion=""),
        Scene(id="b", index=2, beat_id="b", title="B", narration="Two.", visual_description="", character_ids=[], emotion=""),
    ]
    assert join_script(scenes) == "One.\n\nTwo."


def test_manifest_roundtrip() -> None:
    manifest = StoryManifest(
        version=1,
        story_id="x",
        title="X",
        tone="sad",
        target_duration_seconds=12,
        setting=Setting(location="here"),
        visual_style=VisualStyle(),
        narration=NarrationGuidance(),
        characters=[Character(id="b", name="Biscuit", species="dog")],
        scenes=[
            Scene(
                id="scene_001",
                index=1,
                beat_id="one",
                title="One",
                narration="Snow fell.",
                visual_description="snow",
                character_ids=["b"],
                emotion="quiet",
            )
        ],
    )
    restored = StoryManifest.from_dict(manifest.to_dict())
    assert restored.story_id == "x"
    assert restored.scenes[0].narration == "Snow fell."
    assert restored.characters[0].name == "Biscuit"
