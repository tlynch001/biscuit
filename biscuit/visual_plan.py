"""Sidecar visual-beat plans.

A plan splits authored literary beats into smaller illustration units without
changing spoken words. Stories without a registered plan keep one scene per
beat and only receive inferred SSML pacing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from biscuit.exceptions import StoryValidationError
from biscuit.models import Scene, StoryManifest, StorySpec
from biscuit.performance import apply_inferred_pacing
from biscuit.ssml import spoken_fingerprint

logger = logging.getLogger(__name__)

PLANNER_VERSION = "visual-beats-v1"

PlanLoader = Callable[[], dict[str, Any]]


def _plan_registry() -> dict[str, PlanLoader]:
    from biscuit.plans.red_mitten import BASE_FACTS, PLANNER_ID, units

    return {
        PLANNER_ID: lambda: {"base_facts": list(BASE_FACTS), "units": units()},
    }


def plan_for_story(story_id: str) -> dict[str, Any] | None:
    loader = _plan_registry().get(story_id)
    if loader is None:
        return None
    return loader()


def apply_story_plan(manifest: StoryManifest, spec: StorySpec) -> StoryManifest:
    """Replace 1:1 literary scenes with visual beats when a plan exists."""

    plan = plan_for_story(spec.id)
    if plan is None:
        apply_inferred_pacing(manifest.scenes)
        logger.info("No visual-beat plan for %s; inferred SSML pacing on %d scenes", spec.id, len(manifest.scenes))
        return manifest

    literary_by_beat = {scene.beat_id: scene for scene in manifest.scenes}
    units = plan["units"]
    _validate_plan(spec, units)

    facts: list[str] = list(plan.get("base_facts") or [])
    shot_index: dict[str, int] = {}
    scenes: list[Scene] = []
    for index, unit in enumerate(units, start=1):
        literary = literary_by_beat[unit["beat_id"]]
        facts = _apply_fact_updates(facts, unit)
        shot_id = str(unit["id"])
        reuse = str(unit.get("reuse") or "")
        if reuse and reuse not in shot_index:
            raise StoryValidationError(f"Visual plan reuse {reuse!r} is not a previous shot.")
        scene = Scene(
            id=f"scene_{index:03d}",
            index=index,
            beat_id=unit["beat_id"],
            title=str(unit.get("title") or literary.title),
            narration=str(unit["spoken"]).strip(),
            visual_description=str(unit["visual"]).strip(),
            character_ids=list(unit.get("characters") or []),
            emotion=str(unit.get("emotion") or literary.emotion),
            transition="fade" if index == 1 else str(unit.get("transition") or literary.transition or "fade"),
            motion=str(unit.get("motion") or literary.motion or "slow_zoom_in"),
            performance_narration=str(unit.get("ssml") or unit["spoken"]).strip(),
            break_after_seconds=float(unit.get("break_after") or 0.0),
            shot_id=shot_id,
            reuse_shot_id=reuse,
            world_facts=list(facts),
        )
        scenes.append(scene)
        shot_index[shot_id] = index

    manifest.scenes = scenes
    logger.info(
        "Applied visual-beat plan for %s: %d literary beats -> %d visual beats",
        spec.id,
        len(spec.beats),
        len(scenes),
    )
    return manifest


def plan_to_dict(manifest: StoryManifest) -> dict[str, Any]:
    return {
        "planner_version": PLANNER_VERSION,
        "story_id": manifest.story_id,
        "visual_beats": [
            {
                "index": scene.index,
                "id": scene.shot_id or scene.id,
                "beat_id": scene.beat_id,
                "spoken": scene.narration,
                "ssml": scene.performance_narration or scene.narration,
                "break_after_seconds": scene.break_after_seconds,
                "visual": scene.visual_description,
                "characters": list(scene.character_ids),
                "motion": scene.motion,
                "reuse": scene.reuse_shot_id or None,
                "world_facts": list(scene.world_facts),
            }
            for scene in manifest.scenes
        ],
    }


def _validate_plan(spec: StorySpec, units: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    by_beat: dict[str, list[str]] = {beat.id: [] for beat in spec.beats}
    for unit in units:
        shot_id = str(unit.get("id") or "")
        beat_id = str(unit.get("beat_id") or "")
        spoken = str(unit.get("spoken") or "").strip()
        if not shot_id or not beat_id or not spoken:
            raise StoryValidationError("Each visual beat needs id, beat_id, and spoken text.")
        if shot_id in seen_ids:
            raise StoryValidationError(f"Duplicate visual beat id {shot_id!r}.")
        seen_ids.add(shot_id)
        if beat_id not in by_beat:
            raise StoryValidationError(f"Visual beat {shot_id!r} references unknown beat {beat_id!r}.")
        ssml = str(unit.get("ssml") or spoken)
        if spoken_fingerprint(ssml) != spoken_fingerprint(spoken):
            raise StoryValidationError(
                f"Visual beat {shot_id!r} SSML changes spoken words."
            )
        by_beat[beat_id].append(spoken)

    for beat in spec.beats:
        planned = " ".join(by_beat[beat.id])
        if spoken_fingerprint(planned) != spoken_fingerprint(beat.narration):
            raise StoryValidationError(
                f"Visual plan for beat {beat.id!r} does not preserve the literary narration."
            )


def _apply_fact_updates(facts: list[str], unit: dict[str, Any]) -> list[str]:
    current = list(facts)
    for item in unit.get("facts_remove") or []:
        if item in current:
            current.remove(item)
    for item in unit.get("facts_add") or []:
        if item not in current:
            current.append(str(item))
    return current
