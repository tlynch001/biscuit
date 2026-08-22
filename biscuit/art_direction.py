"""Human-directed art-direction planning.

The visual plan describes the movie. This module proposes the small set of
reference assets that should be approved before shooting, assigns at most
three logical references to each shot, and writes a readable checklist.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from biscuit.exceptions import ArtDirectionError
from biscuit.models import Scene, StoryManifest, StorySpec
from biscuit.prompts import apply_prompts
from biscuit.references import (
    MAX_REFERENCES_PER_SHOT,
    ReferenceAsset,
    ReferenceRegistry,
    ShotReferenceSelection,
    apply_selection_to_scene,
    candidates_for_scene,
    select_shot_references,
)
from biscuit.visual_plan import plan_for_story

ART_DIRECTION_VERSION = "reference-assets-v1"

_GENERIC_SKIP_ENTITIES = frozenset(
    {
        "snow",
        "snowflake",
        "tree",
        "trees",
        "sky",
        "wind",
        "light",
        "shadow",
        "tracks",
        "fence",
    }
)


def propose_assets(manifest: StoryManifest, spec: StorySpec) -> list[ReferenceAsset]:
    """Propose continuity-critical masters. Not every noun becomes an asset."""

    plan = plan_for_story(spec.id) or {}
    sidecar = plan.get("reference_assets")
    if sidecar:
        return [_asset_from_sidecar(item, manifest) for item in sidecar]
    if spec.art_direction.mode != "directed":
        return []
    return _heuristic_assets(manifest, spec)


def _asset_from_sidecar(item: dict[str, Any], manifest: StoryManifest) -> ReferenceAsset:
    asset_id = str(item.get("id") or "").strip()
    if not asset_id:
        raise ArtDirectionError("Sidecar reference asset is missing 'id'.")
    needed = _as_str_list(item.get("needed_by_shots"))
    entity_ids = _as_str_list(item.get("entity_ids"))
    location_ids = _as_str_list(item.get("location_ids"))
    if not needed:
        needed = _shots_for_asset(manifest, entity_ids=entity_ids, location_ids=location_ids)
    return ReferenceAsset(
        id=asset_id,
        category=str(item.get("category") or "prop"),
        description=str(item.get("description") or ""),
        why=str(item.get("why") or ""),
        needed_by_shots=needed,
        entity_ids=entity_ids,
        location_ids=location_ids,
        priority=int(item.get("priority") or 50),
        continuity_notes=str(item.get("continuity_notes") or ""),
        source="planner",
        status="planned",
    )


def _shots_for_asset(
    manifest: StoryManifest,
    *,
    entity_ids: list[str],
    location_ids: list[str],
) -> list[str]:
    shots: list[str] = []
    entities = set(entity_ids)
    locations = set(location_ids)
    for scene in manifest.scenes:
        visible = set(scene.visible_entities) | set(scene.character_ids)
        if (locations and scene.location_id in locations) or (entities and visible & entities):
            shots.append(scene.shot_id or scene.id)
    return shots


def _heuristic_assets(manifest: StoryManifest, spec: StorySpec) -> list[ReferenceAsset]:
    """Directed stories without a sidecar still get a conservative library."""

    proposed: dict[str, ReferenceAsset] = {}
    location_shots: dict[str, list[str]] = defaultdict(list)
    entity_shots: dict[str, list[str]] = defaultdict(list)
    for scene in manifest.scenes:
        shot_id = scene.shot_id or scene.id
        if scene.location_id:
            location_shots[scene.location_id].append(shot_id)
        for entity_id in set(scene.visible_entities) | set(scene.character_ids):
            if entity_id and entity_id.lower() not in _GENERIC_SKIP_ENTITIES:
                entity_shots[entity_id].append(shot_id)

    for location_id, shots in location_shots.items():
        if len(shots) < 2:
            continue
        asset_id = f"{location_id}_master"
        proposed[asset_id] = ReferenceAsset(
            id=asset_id,
            category="location",
            description=f"Canonical view of {location_id.replace('_', ' ')}.",
            why="This location is photographed from more than one camera position.",
            needed_by_shots=list(shots),
            location_ids=[location_id],
            priority=90,
            source="planner",
        )

    character_ids = {character.id for character in spec.characters}
    for entity_id, shots in entity_shots.items():
        unique_shots = list(dict.fromkeys(shots))
        if entity_id not in character_ids and len(unique_shots) < 2:
            continue
        if entity_id in character_ids:
            category = "character"
            priority = 85
            why = "Recurring character whose identity must not drift."
        else:
            category = "prop"
            priority = 70
            why = "Recurring object whose inconsistency would damage continuity."
        asset_id = f"{entity_id}_master"
        proposed[asset_id] = ReferenceAsset(
            id=asset_id,
            category=category,
            description=f"Canonical appearance of {entity_id.replace('_', ' ')}.",
            why=why,
            needed_by_shots=unique_shots,
            entity_ids=[entity_id],
            priority=priority,
            source="planner",
        )
    return list(proposed.values())


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def assign_shot_references(
    manifest: StoryManifest,
    registry: ReferenceRegistry,
) -> dict[str, ShotReferenceSelection]:
    selections: dict[str, ShotReferenceSelection] = {}
    for scene in manifest.scenes:
        candidates = candidates_for_scene(scene, registry)
        # Composition anchors must never win just because they exist.
        usable = [
            asset
            for asset in candidates
            if asset.category != "composition"
            or (scene.shot_id and scene.shot_id in asset.needed_by_shots)
        ]
        selection = select_shot_references(
            usable, limit=registry.max_references_per_shot or MAX_REFERENCES_PER_SHOT
        )
        apply_selection_to_scene(scene, selection)
        selections[scene.shot_id or scene.id] = selection
    return selections


def apply_reference_prompts(manifest: StoryManifest, spec: StorySpec, registry: ReferenceRegistry) -> None:
    """Rebuild prompts, then attach inspectable reference instructions."""

    apply_prompts(manifest, spec)
    for scene in manifest.scenes:
        block = reference_prompt_block(scene, registry)
        if block:
            scene.image_prompt = f"{block}\n\n{scene.image_prompt.strip()}".strip()


def reference_prompt_block(scene: Scene, registry: ReferenceRegistry) -> str:
    if not scene.reference_assets:
        return ""
    lines = [
        "REFERENCE IMAGES (ingredients for THIS photograph, not other times or places):",
    ]
    for asset_id in scene.reference_assets:
        asset = registry.assets.get(asset_id)
        if asset is None:
            lines.append(f"- {asset_id}: planned reference (not yet in the library).")
            continue
        label = asset.status.upper()
        detail = asset.description or asset.why or asset.category
        lines.append(f"- {asset.id} [{label}] ({asset.category}): {detail}")
    lines.append(
        "Use the approved references to lock identity, scale, orientation, and geography. "
        "This prompt describes only what happens in this shot. "
        "Do not blend the references into a sequence of different scenes."
    )
    if scene.continuity:
        facts = "; ".join(f"{key}={value}" for key, value in scene.continuity.items())
        lines.append(f"Textual continuity still applies: {facts}.")
    return "\n".join(lines)


def missing_required_assets(
    manifest: StoryManifest,
    registry: ReferenceRegistry,
    store_root: Path,
) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    seen: set[str] = set()
    for scene in manifest.scenes:
        for asset_id in scene.reference_assets:
            if asset_id in seen:
                continue
            seen.add(asset_id)
            asset = registry.assets.get(asset_id)
            if asset is None:
                problems.append(
                    {
                        "id": asset_id,
                        "status": "missing",
                        "detail": "Required by the shot plan but absent from the registry.",
                    }
                )
                continue
            if asset.status != "approved":
                problems.append(
                    {
                        "id": asset_id,
                        "status": asset.status,
                        "detail": "Directed illustration will not use an unapproved reference.",
                    }
                )
                continue
            if not asset.has_usable_image(store_root):
                problems.append(
                    {
                        "id": asset_id,
                        "status": asset.status,
                        "detail": "Approved, but no local image is registered.",
                    }
                )
    return problems


def require_approved_references(
    manifest: StoryManifest,
    registry: ReferenceRegistry,
    store_root: Path,
) -> None:
    if registry.mode != "directed":
        return
    problems = missing_required_assets(manifest, registry, store_root)
    if not problems:
        return
    lines = [
        "Directed illustration cannot start until these reference assets are approved "
        "and have a local image:"
    ]
    for item in problems:
        lines.append(f"- {item['id']} ({item['status']}): {item['detail']}")
    lines.append(
        "Register or generate a candidate, then --approve-reference ID. "
        "Stories without art_direction.mode: directed do not require this."
    )
    raise ArtDirectionError("\n".join(lines))


def render_art_direction_markdown(
    *,
    spec: StorySpec,
    manifest: StoryManifest,
    registry: ReferenceRegistry,
    selections: dict[str, ShotReferenceSelection] | None = None,
) -> str:
    mode = spec.art_direction.mode
    title = spec.title
    lines = [
        f"# {title} — Art Direction",
        "",
        f"Mode: **{mode}**",
        f"Planner: `{ART_DIRECTION_VERSION}`",
        f"Max references per shot: {registry.max_references_per_shot}",
        "",
    ]
    if mode != "directed":
        lines.extend(
            [
                "This story uses **automatic** illustration.",
                "No human-approved reference library is required.",
                "Shot prompts remain text-only unless a character library image exists.",
                "",
            ]
        )
        if not registry.assets:
            return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "## Visual identity",
            "",
            spec.visual_style.prompt_preamble() or spec.tone or "See the story visual_style block.",
            "",
            spec.setting.prompt_line() or spec.setting.notes or "",
            "",
            "## Required reference assets",
            "",
            "These are production-design plates, not necessarily frames in the finished video.",
            "Approve them before `--from-stage illustrate` on a directed story.",
            "",
        ]
    )
    if not registry.assets:
        lines.append("No reference assets were proposed.")
        lines.append("")
    for asset in sorted(registry.assets.values(), key=lambda item: (-item.priority, item.id)):
        mark = "x" if asset.status == "approved" else " "
        lines.append(f"- [{mark}] `{asset.id}` — **{asset.status}** ({asset.category})")
        if asset.description:
            lines.append(f"    {asset.description}")
        if asset.why:
            lines.append(f"    Why: {asset.why}")
        if asset.needed_by_shots:
            preview = ", ".join(asset.needed_by_shots[:12])
            extra = "" if len(asset.needed_by_shots) <= 12 else f" (+{len(asset.needed_by_shots) - 12} more)"
            lines.append(f"    Needed by shots: {preview}{extra}")
        if asset.local_path:
            lines.append(f"    Local image: `{asset.local_path}`")
        if asset.provider_file_id:
            lines.append(f"    Provider file cached for `{asset.provider}` (id stored only in the registry).")
        if asset.continuity_notes:
            lines.append(f"    Continuity: {asset.continuity_notes}")
        lines.append("")

    lines.extend(["## Shot assignments", "", "At most three references per shot. Masters outrank promoted anchors.", ""])
    for scene in manifest.scenes:
        shot_id = scene.shot_id or scene.id
        selection = (selections or {}).get(shot_id)
        chosen = scene.reference_assets or (selection.selected if selection else [])
        lines.append(f"### {scene.index:02d}. `{shot_id}`")
        if scene.location_id:
            lines.append(f"Location: `{scene.location_id}`")
        if scene.shot_description:
            lines.append(scene.shot_description)
        if chosen:
            lines.append("Selected: " + ", ".join(f"`{item}`" for item in chosen))
        else:
            lines.append("Selected: _(none)_")
        if selection and selection.omitted:
            omitted = ", ".join(item["id"] for item in selection.omitted)
            lines.append(f"Omitted over the 3-reference cap: {omitted}")
        if scene.continuity:
            bits = [f"{key}={value}" for key, value in scene.continuity.items()]
            lines.append("Continuity: " + "; ".join(bits))
        lines.append("")

    problems = [
        asset
        for asset in registry.assets.values()
        if asset.status != "approved" and asset.needed_by_shots
    ]
    lines.extend(["## Unresolved requirements", ""])
    if mode != "directed":
        lines.append("None — automatic mode.")
    elif not problems:
        lines.append("All proposed references that shots need are approved.")
    else:
        for asset in problems:
            lines.append(f"- `{asset.id}` is **{asset.status}** and is still required before illustration.")
    lines.append("")
    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


def art_direction_payload(
    *,
    spec: StorySpec,
    manifest: StoryManifest,
    registry: ReferenceRegistry,
    selections: dict[str, ShotReferenceSelection],
) -> dict[str, Any]:
    return {
        "version": ART_DIRECTION_VERSION,
        "story_id": spec.id,
        "title": spec.title,
        "mode": spec.art_direction.mode,
        "max_references_per_shot": registry.max_references_per_shot,
        "assets": [asset.to_dict() for asset in registry.assets.values()],
        "shots": [
            {
                "index": scene.index,
                "shot_id": scene.shot_id or scene.id,
                "location_id": scene.location_id or None,
                "subjects": list(scene.character_ids),
                "visible_entities": list(scene.visible_entities),
                "reference_assets": list(scene.reference_assets),
                "reference_candidates": list(scene.reference_candidates),
                "reference_selection": dict(scene.reference_selection),
                "continuity": dict(scene.continuity),
            }
            for scene in manifest.scenes
        ],
        "selections": {key: value.to_dict() for key, value in selections.items()},
    }


def reference_generation_prompt(asset: ReferenceAsset, spec: StorySpec) -> str:
    style = spec.visual_style.prompt_preamble()
    setting = spec.setting.prompt_line()
    return "\n\n".join(
        part
        for part in (
            f"Production-design reference plate for `{asset.id}` ({asset.category}).",
            asset.description,
            asset.why,
            asset.continuity_notes,
            f"Visual style: {style}" if style else "",
            f"Setting: {setting}" if setting else "",
            "This is a master reference, not a story beat. No text, captions, or watermark. 16:9.",
        )
        if part
    )
