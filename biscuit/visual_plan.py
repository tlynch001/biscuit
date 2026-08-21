"""Sidecar cinematic visual plans.

A plan splits authored literary beats into location-aware shots without
changing spoken words. Stories without a registered plan keep one scene per
beat and only receive inferred SSML pacing.

The director may know the entire story. Image prompts are derived from local
shot state, not global world dumps.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from biscuit.exceptions import StoryValidationError
from biscuit.models import Scene, StoryManifest, StorySpec
from biscuit.performance import apply_inferred_pacing, pace_text
from biscuit.ssml import spoken_fingerprint
from biscuit.visual_critic import critic_record

logger = logging.getLogger(__name__)

PLANNER_VERSION = "cinematic-sequences-v2"

PlanLoader = Callable[[], dict[str, Any]]


def _plan_registry() -> dict[str, PlanLoader]:
    from biscuit.plans.red_mitten import PLANNER_ID, SEQUENCES, VISUAL_BIBLE, shots

    return {
        PLANNER_ID: lambda: {
            "visual_bible": dict(VISUAL_BIBLE),
            "sequences": list(SEQUENCES),
            "units": shots(),
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

    shot_index: dict[str, int] = {}
    scenes: list[Scene] = []
    unique = 0
    reused = 0
    for index, unit in enumerate(units, start=1):
        literary = literary_by_beat[unit["beat_id"]]
        shot_id = str(unit["id"])
        reuse = str(unit.get("reuse") or unit.get("reuse_shot_id") or "")
        if reuse and reuse not in shot_index:
            raise StoryValidationError(f"Visual plan reuse {reuse!r} is not a previous shot.")
        spoken = str(unit["spoken"]).strip()
        break_after = float(unit.get("break_after") or 0.0)
        ssml = str(unit.get("ssml") or "").strip()
        if not ssml:
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
        )
        scenes.append(scene)
        shot_index[shot_id] = index
        if reuse:
            reused += 1
        else:
            unique += 1

    manifest.scenes = scenes
    logger.info(
        "Applied cinematic plan for %s: %d literary beats -> %d shots (%d unique, %d reused)",
        spec.id,
        len(spec.beats),
        len(scenes),
        unique,
        reused,
    )
    return manifest


def plan_to_dict(manifest: StoryManifest) -> dict[str, Any]:
    plan = plan_for_story(manifest.story_id) or {}
    return {
        "planner_version": PLANNER_VERSION,
        "story_id": manifest.story_id,
        "visual_bible": plan.get("visual_bible") or {},
        "sequences": plan.get("sequences") or [],
        "shots": [_shot_record(scene) for scene in manifest.scenes],
    }


def _shot_record(scene: Scene) -> dict[str, Any]:
    return {
        "index": scene.index,
        "id": scene.shot_id or scene.id,
        "sequence_id": scene.sequence_id or None,
        "location_id": scene.location_id or None,
        "beat_id": scene.beat_id,
        "narration": scene.narration,
        "ssml": scene.performance_narration or scene.narration,
        "break_after_seconds": scene.break_after_seconds,
        "shot_description": scene.shot_description or scene.visual_description,
        "visible_elements": list(scene.visible_elements),
        "forbidden_elements": list(scene.forbidden_elements),
        "local_prompt": scene.local_prompt,
        "image_prompt": scene.image_prompt,
        "characters": list(scene.character_ids),
        "motion": scene.motion,
        "reuse": scene.reuse_shot_id or None,
        "reference_shot_id": scene.reference_shot_id or None,
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
        if not shot_id or not beat_id or not spoken:
            raise StoryValidationError("Each cinematic shot needs id, beat_id, and spoken text.")
        if shot_id in seen_ids:
            raise StoryValidationError(f"Duplicate shot id {shot_id!r}.")
        seen_ids.add(shot_id)
        if beat_id not in beat_ids:
            raise StoryValidationError(f"Shot {shot_id!r} references unknown beat {beat_id!r}.")
        ssml = str(unit.get("ssml") or spoken)
        if spoken_fingerprint(ssml) != spoken_fingerprint(spoken):
            raise StoryValidationError(f"Shot {shot_id!r} SSML changes spoken words.")
        if not str(unit.get("local_prompt") or unit.get("visual") or "").strip() and not unit.get("reuse"):
            raise StoryValidationError(f"Shot {shot_id!r} needs a local_prompt or reuse.")
        spoken_parts.append(spoken)

    planned = " ".join(spoken_parts)
    literary = " ".join(beat.narration for beat in spec.beats)
    if spoken_fingerprint(planned) != spoken_fingerprint(literary):
        raise StoryValidationError(
            "Cinematic plan does not preserve the literary narration when spoken shots are concatenated."
        )
