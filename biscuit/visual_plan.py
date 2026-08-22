"""Sidecar cinematic visual plans.

A plan splits authored literary beats into location-aware shots without
changing spoken words. Stories without a registered plan keep one scene per
beat and only receive inferred SSML pacing.

The director may know the entire story. Image prompts are derived from local
shot state, not global world dumps. Unspoken shots visualize implied travel.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from biscuit.exceptions import StoryValidationError
from biscuit.models import Scene, StoryManifest, StorySpec
from biscuit.performance import apply_inferred_pacing, pace_text
from biscuit.ssml import spoken_fingerprint
from biscuit.visual_critic import critic_record
from biscuit.world import validate_spatial_plan, world_to_dict

logger = logging.getLogger(__name__)

PLANNER_VERSION = "cinematic-sequences-v4"

PlanLoader = Callable[[], dict[str, Any]]


def _plan_registry() -> dict[str, PlanLoader]:
    from biscuit.plans.red_mitten import (
        PLANNER_ID,
        REFERENCE_ASSETS,
        SEQUENCES,
        VISUAL_BIBLE,
        shots,
        world,
    )

    return {
        PLANNER_ID: lambda: {
            "visual_bible": dict(VISUAL_BIBLE),
            "sequences": list(SEQUENCES),
            "world": world(),
            "units": shots(),
            "reference_assets": list(REFERENCE_ASSETS),
        },
    }


def plan_for_story(story_id: str) -> dict[str, Any] | None:
    loader = _plan_registry().get(story_id)
    if loader is None:
        return None
    return loader()


def apply_story_plan(manifest: StoryManifest, spec: StorySpec) -> StoryManifest:
    """Replace 1:1 literary scenes with cinematic shots when a plan exists."""

    plan = plan_for_story(spec.id)
    if plan is None:
        apply_inferred_pacing(manifest.scenes)
        logger.info("No cinematic plan for %s; inferred SSML pacing on %d scenes", spec.id, len(manifest.scenes))
        return manifest

    literary_by_beat = {scene.beat_id: scene for scene in manifest.scenes}
    units = plan["units"]
    _validate_plan(spec, units)
    world = plan.get("world")
    if world is not None:
        spatial_errors = validate_spatial_plan(world, units)
        if spatial_errors:
            raise StoryValidationError("Spatial continuity errors:\n- " + "\n- ".join(spatial_errors))

    shot_index: dict[str, int] = {}
    scenes: list[Scene] = []
    unique = 0
    reused = 0
    unspoken = 0
    for index, unit in enumerate(units, start=1):
        literary = literary_by_beat[unit["beat_id"]]
        shot_id = str(unit["id"])
        reuse = str(unit.get("reuse") or unit.get("reuse_shot_id") or "")
        if reuse and reuse not in shot_index:
            raise StoryValidationError(f"Visual plan reuse {reuse!r} is not a previous shot.")
        spoken = str(unit.get("spoken") or "").strip()
        is_unspoken = bool(unit.get("unspoken") or not spoken)
        hold = float(unit.get("hold_seconds") or 0.0)
        break_after = float(unit.get("break_after") or hold or 0.0)
        ssml = str(unit.get("ssml") or "").strip()
        if spoken and not ssml:
            ssml = pace_text(spoken, trailing_break=break_after).ssml
        local_prompt = str(unit.get("local_prompt") or "").strip()
        visual = str(unit.get("shot_description") or unit.get("visual") or "").strip()
        scene = Scene(
            id=f"scene_{index:03d}",
            index=index,
            beat_id=unit["beat_id"],
            title=str(unit.get("title") or literary.title),
            narration=spoken,
            visual_description=visual or local_prompt,
            character_ids=list(unit.get("characters") or []),
            emotion=str(unit.get("emotion") or literary.emotion),
            transition="fade" if index == 1 else str(unit.get("transition") or literary.transition or "fade"),
            motion=str(unit.get("motion") or "static"),
            performance_narration=ssml,
            break_after_seconds=break_after,
            shot_id=shot_id,
            reuse_shot_id=reuse,
            sequence_id=str(unit.get("sequence_id") or ""),
            location_id=str(unit.get("location_id") or ""),
            local_prompt=local_prompt,
            visible_elements=list(unit.get("visible_elements") or []),
            forbidden_elements=list(unit.get("forbidden_elements") or []),
            reference_shot_id=str(unit.get("reference_shot_id") or ""),
            shot_description=visual,
            continuity=dict(unit.get("continuity") or {}),
            visible_entities=list(unit.get("visible_entities") or []),
            entity_identity=list(unit.get("entity_identity") or []),
            unspoken=is_unspoken,
            travel_path=list(unit.get("travel_path") or []),
            hold_seconds=hold,
            target_duration_seconds=hold or None,
            reference_assets=list(unit.get("reference_assets") or []),
        )
        scenes.append(scene)
        shot_index[shot_id] = index
        if reuse:
            reused += 1
        else:
            unique += 1
        if is_unspoken:
            unspoken += 1

    manifest.scenes = scenes
    logger.info(
        "Applied cinematic plan for %s: %d literary beats -> %d shots "
        "(%d unique, %d reused, %d unspoken, %d spatial checks)",
        spec.id,
        len(spec.beats),
        len(scenes),
        unique,
        reused,
        unspoken,
        0 if world is None else 1,
    )
    return manifest


def plan_to_dict(manifest: StoryManifest) -> dict[str, Any]:
    plan = plan_for_story(manifest.story_id) or {}
    world = plan.get("world")
    payload: dict[str, Any] = {
        "planner_version": PLANNER_VERSION,
        "story_id": manifest.story_id,
        "visual_bible": plan.get("visual_bible") or {},
        "sequences": plan.get("sequences") or [],
        "shots": [_shot_record(scene) for scene in manifest.scenes],
        "reference_assets": [
            {key: value for key, value in dict(item).items() if key != "provider_file_id"}
            for item in (plan.get("reference_assets") or [])
        ],
    }
    if world is not None:
        payload["world"] = world_to_dict(world)
        payload["journeys"] = dict(world.journeys)
        payload["image_references"] = {
            "abstraction": (
                "Directed stories select up to three logical reference_assets per shot. "
                "The registry resolves those names to local files and optional provider "
                "file ids. Automatic stories may still pass CharacterReference("
                "kind='shot_continuity') from an authored reference_shot_id."
            ),
            "xai": (
                "Approved registry assets are uploaded once via POST /v1/files and then "
                "sent to POST /v1/images/edits as file_id / images[]. Local-path data-URI "
                "edits remain available for grok-imagine-image-2.x. Text-only generation "
                "is unchanged when no references are selected."
            ),
            "openai": "Existing /v1/images/edits multipart path if reference files exist.",
        }
    return payload


def _shot_record(scene: Scene) -> dict[str, Any]:
    return {
        "index": scene.index,
        "id": scene.shot_id or scene.id,
        "sequence_id": scene.sequence_id or None,
        "location_id": scene.location_id or None,
        "beat_id": scene.beat_id,
        "narration": scene.narration,
        "unspoken": scene.unspoken,
        "hold_seconds": scene.hold_seconds or None,
        "ssml": scene.performance_narration or scene.narration,
        "break_after_seconds": scene.break_after_seconds,
        "shot_description": scene.shot_description or scene.visual_description,
        "visible_elements": list(scene.visible_elements),
        "visible_entities": list(scene.visible_entities),
        "entity_identity": list(scene.entity_identity),
        "forbidden_elements": list(scene.forbidden_elements),
        "local_prompt": scene.local_prompt,
        "image_prompt": scene.image_prompt,
        "characters": list(scene.character_ids),
        "motion": scene.motion,
        "reuse": scene.reuse_shot_id or None,
        "reference_shot_id": scene.reference_shot_id or None,
        "reference_assets": list(scene.reference_assets),
        "reference_candidates": list(scene.reference_candidates),
        "reference_selection": dict(scene.reference_selection) or None,
        "travel_path": list(scene.travel_path) or None,
        "continuity": dict(scene.continuity),
        "critic": critic_record(scene),
    }


def _validate_plan(spec: StorySpec, units: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    spoken_parts: list[str] = []
    beat_ids = {beat.id for beat in spec.beats}
    for unit in units:
        shot_id = str(unit.get("id") or "")
        beat_id = str(unit.get("beat_id") or "")
        spoken = str(unit.get("spoken") or "").strip()
        unspoken = bool(unit.get("unspoken") or not spoken)
        if not shot_id or not beat_id:
            raise StoryValidationError("Each cinematic shot needs id and beat_id.")
        if not spoken and not unspoken:
            raise StoryValidationError(f"Shot {shot_id!r} needs spoken text or unspoken=true.")
        if shot_id in seen_ids:
            raise StoryValidationError(f"Duplicate shot id {shot_id!r}.")
        seen_ids.add(shot_id)
        if beat_id not in beat_ids:
            raise StoryValidationError(f"Shot {shot_id!r} references unknown beat {beat_id!r}.")
        if spoken:
            ssml = str(unit.get("ssml") or spoken)
            if spoken_fingerprint(ssml) != spoken_fingerprint(spoken):
                raise StoryValidationError(f"Shot {shot_id!r} SSML changes spoken words.")
            spoken_parts.append(spoken)
        if not str(unit.get("local_prompt") or unit.get("visual") or "").strip() and not unit.get("reuse"):
            raise StoryValidationError(f"Shot {shot_id!r} needs a local_prompt or reuse.")
        if unspoken and not spoken and not (unit.get("hold_seconds") or unit.get("break_after")):
            raise StoryValidationError(f"Unspoken shot {shot_id!r} needs hold_seconds.")

    planned = " ".join(spoken_parts)
    literary = " ".join(beat.narration for beat in spec.beats)
    if spoken_fingerprint(planned) != spoken_fingerprint(literary):
        raise StoryValidationError(
            "Cinematic plan does not preserve the literary narration when spoken shots are concatenated."
        )
