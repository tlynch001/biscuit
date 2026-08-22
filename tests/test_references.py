from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from biscuit.art_direction import (
    apply_reference_prompts,
    assign_shot_references,
    missing_required_assets,
    propose_assets,
    require_approved_references,
)
from biscuit.artifacts import ArtifactStore
from biscuit.cli import build_arg_parser
from biscuit.exceptions import ArtDirectionError
from biscuit.models import (
    ArtDirectionSpec,
    Character,
    NarrationGuidance,
    Scene,
    SceneConstraints,
    Setting,
    StoryManifest,
    StorySpec,
    VisualStyle,
)
from biscuit.pipeline import StoryPipeline
from biscuit.providers.base import ImageRequest
from biscuit.providers.image_development import DevelopmentImageProvider
from biscuit.references import (
    MAX_REFERENCES_PER_SHOT,
    ReferenceAsset,
    ReferenceRegistry,
    select_shot_references,
    to_character_references,
)
from biscuit.stages import STAGES
from biscuit.story import load_story, parse_story


def _png(path: Path, color: tuple[int, int, int] = (40, 40, 40)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 18), color).save(path)
    return path


def _scene(**kwargs) -> Scene:
    values = {
        "id": "scene_001",
        "index": 1,
        "beat_id": "one",
        "title": "One",
        "narration": "A dog walks.",
        "visual_description": "A winter road.",
        "character_ids": ["biscuit"],
        "emotion": "quiet",
        "shot_id": "road_01",
        "location_id": "empty_road",
        "visible_entities": ["biscuit", "road"],
        "local_prompt": "Biscuit on an empty winter road.",
    }
    values.update(kwargs)
    return Scene(**values)


def _spec(*, mode: str = "automatic") -> StorySpec:
    return StorySpec(
        id="mini_directed",
        title="Mini Directed",
        target_duration_seconds=30,
        tone="winter",
        setting=Setting(location="road"),
        visual_style=VisualStyle(),
        narration=NarrationGuidance(),
        characters=[Character(id="biscuit", name="Biscuit", species="dog")],
        beats=[],
        constraints=SceneConstraints(),
        art_direction=ArtDirectionSpec(mode=mode),
    )


def test_registry_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "reference_assets.json"
    registry = ReferenceRegistry("story", mode="directed")
    registry.assets["biscuit_master"] = ReferenceAsset(
        id="biscuit_master",
        category="character",
        description="the same dog",
        why="identity",
        needed_by_shots=["a", "b"],
        status="planned",
    )
    registry.save(path)
    loaded = ReferenceRegistry.load(path, story_id="story")
    assert loaded.mode == "directed"
    assert loaded.assets["biscuit_master"].description == "the same dog"
    assert loaded.assets["biscuit_master"].needed_by_shots == ["a", "b"]
    again = ReferenceRegistry.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert again.assets["biscuit_master"].id == "biscuit_master"


def test_register_local_and_cached_upload(tmp_path: Path) -> None:
    store_root = tmp_path / "out"
    store_root.mkdir()
    source = _png(tmp_path / "abandoned_car_master.jpg", (90, 60, 30))
    registry = ReferenceRegistry("story", mode="directed")
    asset = registry.register_local(
        "abandoned_car_master",
        source,
        store_root=store_root,
        category="vehicle",
        approve=True,
    )
    assert asset.status == "approved"
    assert asset.local_path == "references/abandoned_car_master.jpg"
    assert (store_root / asset.local_path).is_file()
    assert asset.provider_file_id is None
    registry.record_upload(
        "abandoned_car_master",
        provider="xai",
        provider_file_id="file_abc123",
        content_hash=asset.content_hash or "",
    )
    assert registry.cached_upload_is_valid(registry.get("abandoned_car_master"), store_root, provider="xai")
    # Same bytes: keep the cached file id.
    registry.register_local("abandoned_car_master", source, store_root=store_root, approve=True)
    assert registry.get("abandoned_car_master").provider_file_id == "file_abc123"
    # Changed bytes: invalidate the cached id.
    other = _png(tmp_path / "other.jpg", (10, 10, 10))
    registry.register_local("abandoned_car_master", other, store_root=store_root, approve=True)
    assert registry.get("abandoned_car_master").provider_file_id is None


def test_select_shot_references_caps_at_three_and_is_deterministic() -> None:
    assets = [
        ReferenceAsset(id="mitten", category="prop", priority=58, why="title object"),
        ReferenceAsset(id="biscuit_master", category="character", priority=90, why="hero"),
        ReferenceAsset(id="roadside_ditch_master", category="location", priority=100, why="geography"),
        ReferenceAsset(id="abandoned_car_master", category="vehicle", priority=95, why="orientation"),
        ReferenceAsset(id="child_master", category="character", priority=82, why="identity"),
    ]
    first = select_shot_references(assets)
    second = select_shot_references(list(reversed(assets)))
    assert first.selected == second.selected
    assert first.selected == [
        "roadside_ditch_master",
        "abandoned_car_master",
        "biscuit_master",
    ]
    assert len(first.selected) == MAX_REFERENCES_PER_SHOT
    omitted_ids = {item["id"] for item in first.omitted}
    assert omitted_ids == {"child_master", "mitten"}
    assert all(item["reason"] for item in first.ranking)


def test_location_character_vehicle_win_over_prop() -> None:
    assets = [
        ReferenceAsset(id="red_mitten_master", category="prop", priority=58),
        ReferenceAsset(id="open_field_master", category="location", priority=88),
        ReferenceAsset(id="biscuit_master", category="character", priority=90),
        ReferenceAsset(id="woman_master", category="character", priority=80),
    ]
    selected = select_shot_references(assets).selected
    assert selected[0] in {"biscuit_master", "open_field_master"}
    assert "red_mitten_master" not in selected


def test_legacy_story_has_automatic_art_direction(example_story_path: Path, repo_root: Path) -> None:
    spec = load_story(example_story_path, characters_dir=repo_root / "characters")
    assert spec.art_direction.mode == "automatic"


def test_red_mitten_is_directed(repo_root: Path) -> None:
    spec = load_story(
        repo_root / "stories" / "biscuit_and_the_red_mitten.yaml",
        characters_dir=repo_root / "characters",
    )
    assert spec.art_direction.mode == "directed"
    assert spec.art_direction.max_references_per_shot == 3


def test_red_mitten_reference_plan_assigns_three_or_fewer(repo_root: Path) -> None:
    spec = load_story(
        repo_root / "stories" / "biscuit_and_the_red_mitten.yaml",
        characters_dir=repo_root / "characters",
    )
    from biscuit.providers.story_template import TemplateStoryProvider
    from biscuit.visual_plan import apply_story_plan

    manifest = apply_story_plan(TemplateStoryProvider().expand(spec), spec)
    proposed = propose_assets(manifest, spec)
    assert {asset.id for asset in proposed} >= {
        "biscuit_master",
        "roadside_ditch_master",
        "abandoned_car_master",
        "culvert_master",
    }
    registry = ReferenceRegistry(spec.id, mode="directed")
    for asset in proposed:
        registry.merge_proposal(asset)
    selections = assign_shot_references(manifest, registry)
    sedan = next(scene for scene in manifest.scenes if scene.shot_id == "sedan_in_ditch")
    assert sedan.reference_assets == [
        "roadside_ditch_master",
        "abandoned_car_master",
        "biscuit_master",
    ]
    assert "file_" not in json.dumps(sedan.reference_selection)
    discovery = next(scene for scene in manifest.scenes if scene.shot_id == "culvert_discovery")
    assert discovery.reference_assets == ["culvert_master", "biscuit_master", "child_master"]
    assert {item["id"] for item in selections["culvert_discovery"].omitted} >= {"woman_master", "red_mitten_master"}
    for scene in manifest.scenes:
        assert len(scene.reference_assets) <= 3
        assert scene.reference_selection["selected"] == scene.reference_assets


def test_missing_and_unapproved_references_fail_directed_illustration(tmp_path: Path) -> None:
    spec = _spec(mode="directed")
    scene = _scene(reference_assets=["biscuit_master", "empty_road_master"])
    manifest = StoryManifest(
        version=1,
        story_id="mini_directed",
        title="Mini",
        tone="",
        target_duration_seconds=30,
        setting=Setting(),
        visual_style=VisualStyle(),
        narration=spec.narration,  # type: ignore[arg-type]
        characters=spec.characters,
        scenes=[scene],
    )
    registry = ReferenceRegistry("mini_directed", mode="directed")
    registry.assets["biscuit_master"] = ReferenceAsset(id="biscuit_master", category="character", status="planned")
    problems = missing_required_assets(manifest, registry, tmp_path)
    ids = {item["id"] for item in problems}
    assert ids == {"biscuit_master", "empty_road_master"}
    with pytest.raises(ArtDirectionError, match="biscuit_master"):
        require_approved_references(manifest, registry, tmp_path)


def test_automatic_mode_does_not_require_references(tmp_path: Path) -> None:
    spec = _spec(mode="automatic")
    scene = _scene(reference_assets=["biscuit_master"])
    manifest = StoryManifest(
        version=1,
        story_id="mini_directed",
        title="Mini",
        tone="",
        target_duration_seconds=30,
        setting=Setting(),
        visual_style=VisualStyle(),
        narration=spec.narration,
        characters=spec.characters,
        scenes=[scene],
    )
    registry = ReferenceRegistry("mini_directed", mode="automatic")
    require_approved_references(manifest, registry, tmp_path)


def test_prompts_keep_textual_continuity_with_references() -> None:
    spec = _spec(mode="directed")
    scene = _scene(
        reference_assets=["biscuit_master"],
        continuity={"car_position": "fixed", "road_traffic": "none"},
    )
    manifest = StoryManifest(
        version=1,
        story_id="mini_directed",
        title="Mini",
        tone="winter",
        target_duration_seconds=30,
        setting=Setting(location="road"),
        visual_style=VisualStyle(),
        narration=spec.narration,  # type: ignore[arg-type]
        characters=spec.characters,
        scenes=[scene],
    )
    registry = ReferenceRegistry("mini_directed", mode="directed")
    registry.assets["biscuit_master"] = ReferenceAsset(
        id="biscuit_master",
        category="character",
        description="approved Biscuit",
        status="approved",
    )
    apply_reference_prompts(manifest, spec, registry)
    assert "REFERENCE IMAGES" in scene.image_prompt
    assert "biscuit_master" in scene.image_prompt
    assert "Biscuit on an empty winter road." in scene.image_prompt
    assert "car_position=fixed" in scene.image_prompt


def test_promote_shot_is_human_controlled(tmp_path: Path) -> None:
    store_root = tmp_path / "out"
    image = _png(store_root / "scenes" / "007.png", (12, 24, 36))
    registry = ReferenceRegistry("story", mode="directed")
    registry.assets["biscuit_master"] = ReferenceAsset(
        id="biscuit_master", category="character", priority=90, entity_ids=["biscuit"]
    )
    registry.promote_shot(
        asset_id="roadside_composition_anchor_07",
        shot_id="red_mitten_07",
        image_path=image,
        store_root=store_root,
        needed_by_shots=["later_shot"],
    )
    asset = registry.get("roadside_composition_anchor_07")
    assert asset.status == "approved"
    assert asset.category == "composition"
    assert asset.source == "promoted_shot"
    scene = _scene(shot_id="other_shot", visible_entities=["biscuit"], location_id="")
    from biscuit.references import candidates_for_scene

    ids = {item.id for item in candidates_for_scene(scene, registry)}
    assert "biscuit_master" in ids
    assert "roadside_composition_anchor_07" not in ids


def test_direct_stage_and_force_preserve_approved_assets(
    mini_story_path: Path, test_config, tmp_path: Path
) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="direct")
    assert store.art_direction_path.exists()
    assert store.reference_registry_path.exists()
    text = store.art_direction_path.read_text(encoding="utf-8")
    assert "automatic" in text.lower()

    registry = ReferenceRegistry.load(store.reference_registry_path, story_id="mini_rescue")
    source = _png(tmp_path / "master.png")
    registry.register_local("manual_master", source, store_root=store.root, category="location", approve=True)
    registry.save(store.reference_registry_path)
    digest = registry.get("manual_master").content_hash
    local = registry.get("manual_master").local_path

    pipeline.run(mini_story_path, store=store, from_stage="direct", through_stage="illustrate", force=True)
    again = ReferenceRegistry.load(store.reference_registry_path, story_id="mini_rescue")
    assert again.get("manual_master").status == "approved"
    assert again.get("manual_master").content_hash == digest
    assert again.get("manual_master").local_path == local
    assert (store.root / local).is_file()


def test_directed_pipeline_refuses_unapproved_then_uses_approved(
    mini_story_path: Path, test_config, tmp_path: Path, monkeypatch
) -> None:
    spec = load_story(mini_story_path, characters_dir=test_config.characters_dir)
    store = ArtifactStore(test_config.output_dir, spec.id)
    pipeline = StoryPipeline(test_config)

    def fake_load(path, *, characters_dir=None):
        loaded = load_story(path, characters_dir=characters_dir)
        loaded.art_direction = ArtDirectionSpec(mode="directed")
        return loaded

    monkeypatch.setattr("biscuit.pipeline.load_story", fake_load)
    with pytest.raises(ArtDirectionError, match="approved"):
        pipeline.run(mini_story_path, store=store, through_stage="illustrate")

    registry = ReferenceRegistry.load(store.reference_registry_path, story_id=spec.id, mode="directed")
    source = _png(tmp_path / "biscuit.png", (200, 180, 120))
    for asset_id in list(registry.assets):
        registry.register_local(asset_id, source, store_root=store.root, approve=True)
    registry.save(store.reference_registry_path)

    captured: list[list[str]] = []
    original = DevelopmentImageProvider.generate

    def wrapped(self, request: ImageRequest, output_path: Path):
        captured.append([ref.asset_id for ref in request.references if ref.asset_id])
        return original(self, request, output_path)

    monkeypatch.setattr(DevelopmentImageProvider, "generate", wrapped)
    pipeline.run(mini_story_path, store=store, from_stage="illustrate", through_stage="illustrate")
    assert captured
    assert all(len(item) <= 3 for item in captured)


def test_legacy_pipeline_still_illustrates_without_references(
    mini_story_path: Path, test_config
) -> None:
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    manifest = pipeline.run(mini_story_path, store=store, through_stage="illustrate")
    assert store.scene_image_path(1).exists()
    assert all(not scene.reference_assets for scene in manifest.scenes)


def test_cli_exposes_direct_stage_and_reference_flags() -> None:
    parser = build_arg_parser()
    assert "direct" in STAGES
    assert STAGES[STAGES.index("prompts") + 1] == "direct"
    args = parser.parse_args(
        [
            "--story",
            "stories/x.yaml",
            "--through-stage",
            "direct",
            "--register-reference",
            "abandoned_car_master",
            "--reference-file",
            "references/red_mitten/car.jpg",
            "--approve-reference",
            "abandoned_car_master",
            "--force-references",
        ]
    )
    assert args.through_stage == "direct"
    assert args.register_reference == "abandoned_car_master"
    assert args.approve_references == ["abandoned_car_master"]
    assert args.force_references is True


def test_to_character_references_uses_logical_ids_not_plan_file_ids(tmp_path: Path) -> None:
    registry = ReferenceRegistry("story")
    path = _png(tmp_path / "references" / "biscuit_master.png")
    registry.assets["biscuit_master"] = ReferenceAsset(
        id="biscuit_master",
        category="character",
        status="approved",
        local_path="references/biscuit_master.png",
        provider="xai",
        provider_file_id="file_abc123",
    )
    refs = to_character_references(["biscuit_master"], registry, tmp_path)
    assert refs[0].asset_id == "biscuit_master"
    assert refs[0].provider_file_id == "file_abc123"
    assert refs[0].path == path


def test_invalid_art_direction_mode_rejected() -> None:
    with pytest.raises(Exception, match="art_direction.mode"):
        parse_story(
            {
                "id": "x",
                "title": "X",
                "art_direction": {"mode": "maybe"},
                "characters": [{"id": "a", "name": "A"}],
                "beats": [{"id": "one", "narration": "Hi.", "characters": ["a"]}],
            }
        )
