from __future__ import annotations

from biscuit.plans.red_mitten import shots, world
from biscuit.providers.story_template import TemplateStoryProvider
from biscuit.story import load_story
from biscuit.visual_plan import apply_story_plan, plan_to_dict
from biscuit.world import shortest_path, validate_spatial_plan, walk_covers


def test_red_mitten_topology_is_a_linear_walk() -> None:
    w = world()
    outbound = w.journeys["outbound"]
    assert outbound == (
        "empty_road",
        "sedan_ditch",
        "road_bank",
        "open_field",
        "treeline",
        "creek_woods",
        "culvert_mouth",
        "culvert_interior",
    )
    assert w.journeys["return"] == tuple(reversed(outbound))
    assert w.journeys["rescue"][0] == "sedan_ditch"
    assert w.journeys["rescue"][-1] == "culvert_interior"
    assert walk_covers(w, outbound)
    assert shortest_path(w, "empty_road", "culvert_interior") == list(outbound)
    assert shortest_path(w, "sedan_ditch", "culvert_mouth") is not None
    assert len(shortest_path(w, "sedan_ditch", "culvert_mouth")) > 2


def test_red_mitten_plan_passes_spatial_validation() -> None:
    errors = validate_spatial_plan(world(), shots())
    assert errors == []


def test_road_to_culvert_teleport_is_rejected() -> None:
    units = shots()
    culvert = next(shot for shot in units if shot["id"] == "arrive_remote_culvert")
    culvert["travel_path"] = []
    # Pretend the previous camera was the road.
    leading = next(shot for shot in units if shot["id"] == "approach_creek_woods")
    leading["location_id"] = "sedan_ditch"
    leading["travel_path"] = []
    errors = validate_spatial_plan(world(), units)
    assert any("jumps" in error or "teleport" in error for error in errors)


def test_direct_road_culvert_travel_path_without_intervening_nodes_is_rejected() -> None:
    units = shots()
    culvert = next(shot for shot in units if shot["id"] == "arrive_remote_culvert")
    culvert["travel_path"] = ["sedan_ditch", "culvert_mouth"]
    previous = next(shot for shot in units if shot["id"] == "approach_creek_woods")
    previous["location_id"] = "sedan_ditch"
    previous["travel_path"] = []
    errors = validate_spatial_plan(world(), units)
    assert any("travel_path" in error or "jumps" in error for error in errors)


def test_snowplow_before_reveal_is_rejected() -> None:
    units = shots()
    field = next(shot for shot in units if shot["id"] == "field_crossing")
    field["visible_entities"] = list(field["visible_entities"]) + ["snowplow"]
    errors = validate_spatial_plan(world(), units)
    assert any("snowplow" in error and "amber_far" in error for error in errors)


def test_victims_cannot_appear_on_the_road_before_discovery() -> None:
    units = shots()
    road = next(shot for shot in units if shot["id"] == "empty_road")
    road["visible_entities"] = list(road["visible_entities"]) + ["woman", "child"]
    errors = validate_spatial_plan(world(), units)
    assert any("woman" in error for error in errors)
    assert any("child" in error for error in errors)


def test_sedan_cannot_move_to_the_culvert() -> None:
    units = shots()
    culvert = next(shot for shot in units if shot["id"] == "culvert_mouth")
    culvert["visible_entities"] = list(culvert["visible_entities"]) + ["sedan"]
    errors = validate_spatial_plan(world(), units)
    assert any("sedan" in error for error in errors)


def test_snowplow_cannot_appear_at_the_creek() -> None:
    units = shots()
    woods = next(shot for shot in units if shot["id"] == "creek_woods")
    woods["visible_entities"] = list(woods["visible_entities"]) + ["snowplow"]
    errors = validate_spatial_plan(world(), units)
    assert any("snowplow" in error for error in errors)


def test_driver_cannot_appear_at_culvert_before_leaving_the_road() -> None:
    units = shots()
    discovery = next(shot for shot in units if shot["id"] == "culvert_discovery")
    discovery["visible_entities"] = list(discovery["visible_entities"]) + ["driver"]
    errors = validate_spatial_plan(world(), units)
    assert any("driver" in error for error in errors)


def test_red_mitten_plan_applies_without_spatial_errors(repo_root) -> None:
    spec = load_story(
        repo_root / "stories" / "biscuit_and_the_red_mitten.yaml",
        characters_dir=repo_root / "characters",
    )
    manifest = TemplateStoryProvider().expand(spec)
    apply_story_plan(manifest, spec)
    assert any(scene.unspoken for scene in manifest.scenes)
    assert {scene.location_id for scene in manifest.scenes} >= {
        "empty_road",
        "sedan_ditch",
        "road_bank",
        "open_field",
        "creek_woods",
        "culvert_mouth",
        "culvert_interior",
    }


def test_plan_records_world_and_unspoken_travel(repo_root) -> None:
    spec = load_story(
        repo_root / "stories" / "biscuit_and_the_red_mitten.yaml",
        characters_dir=repo_root / "characters",
    )
    manifest = TemplateStoryProvider().expand(spec)
    apply_story_plan(manifest, spec)
    plan = plan_to_dict(manifest)
    by_id = {shot["id"]: shot for shot in plan["shots"]}
    assert by_id["return_across_field"]["location_id"] == "open_field"
    assert by_id["return_across_field"]["travel_path"][0] == "culvert_interior"
    assert by_id["lead_across_field"]["unspoken"] is True
    assert by_id["approach_creek_woods"]["location_id"] == "creek_woods"
    assert by_id["arrive_remote_culvert"]["location_id"] == "culvert_mouth"
    assert by_id["rescue_return_field"]["location_id"] == "open_field"
    assert by_id["running_board"]["location_id"] == "sedan_ditch"
    assert "culvert" not in (by_id["leading_at_road"]["local_prompt"] or "").lower()
    sedan = world().entities["sedan"]
    assert sedan.movable is False
    assert "brown-tan" in sedan.canonical
    assert by_id["sedan_in_ditch"]["entity_identity"]
