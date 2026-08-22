"""Story YAML loading, character library resolution, and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from biscuit.exceptions import StoryValidationError
from biscuit.models import (
    ArtDirectionSpec,
    Beat,
    Character,
    CharacterReference,
    NarrationGuidance,
    SceneConstraints,
    Setting,
    StorySpec,
    VisualStyle,
)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StoryValidationError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise StoryValidationError(f"{path} must contain a YAML mapping.")
    return raw


def load_character_file(path: Path) -> Character:
    data = load_yaml_mapping(path)
    data.setdefault("id", path.stem)
    character = Character.from_dict(data)
    character.source_path = str(path)
    character.references = [
        CharacterReference(path=_resolve_reference_path(path.parent, ref.path), kind=ref.kind)
        for ref in character.references
    ]
    return character


def _resolve_reference_path(base: Path, relative: Path) -> Path:
    candidate = relative if relative.is_absolute() else (base / relative)
    return candidate


def resolve_characters(
    entries: list[Any],
    *,
    characters_dir: Path,
    story_dir: Path,
) -> list[Character]:
    if not entries:
        raise StoryValidationError("Story must define at least one character.")

    characters: list[Character] = []
    seen: set[str] = set()
    for entry in entries:
        if isinstance(entry, str):
            entry = {"from": entry}
        if not isinstance(entry, dict):
            raise StoryValidationError(f"Invalid character entry: {entry!r}")
        character = _resolve_one_character(entry, characters_dir=characters_dir, story_dir=story_dir)
        if character.id in seen:
            raise StoryValidationError(f"Duplicate character id {character.id!r}.")
        seen.add(character.id)
        characters.append(character)
    return characters


def _resolve_one_character(
    entry: dict[str, Any],
    *,
    characters_dir: Path,
    story_dir: Path,
) -> Character:
    source = entry.get("from")
    if source:
        source_path = Path(str(source))
        search_paths = []
        if source_path.is_absolute():
            search_paths.append(source_path)
        else:
            search_paths.append(characters_dir / source_path)
            search_paths.append(story_dir / source_path)
            if source_path.suffix == "":
                search_paths.append(characters_dir / f"{source_path}.yaml")
                search_paths.append(characters_dir / f"{source_path}.yml")
        matched = next((path for path in search_paths if path.exists()), None)
        if matched is None:
            raise StoryValidationError(
                f"Character library file not found for {source!r}. Looked in: "
                + ", ".join(str(path) for path in search_paths)
            )
        base = load_character_file(matched)
        overlay = {key: value for key, value in entry.items() if key != "from"}
        merged = {**base.to_dict(), **overlay}
        if "appearance" in overlay and isinstance(base.appearance, dict) and isinstance(overlay["appearance"], dict):
            merged["appearance"] = {**base.appearance, **overlay["appearance"]}
        if "visual_anchors" in overlay or "personality" in overlay:
            # overlay list fields replace rather than extend — explicit is clearer
            pass
        merged["source_path"] = str(matched)
        character = Character.from_dict(merged)
        return character
    return Character.from_dict(entry)


def load_story(path: str | Path, *, characters_dir: Path | None = None) -> StorySpec:
    story_path = Path(path)
    raw = load_yaml_mapping(story_path)
    return parse_story(raw, source_path=story_path, characters_dir=characters_dir)


def parse_story(
    raw: dict[str, Any],
    *,
    source_path: Path | None = None,
    characters_dir: Path | None = None,
) -> StorySpec:
    errors: list[str] = []
    story_id = str(raw.get("id") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not story_id:
        errors.append("Missing required field 'id'.")
    if not title:
        errors.append("Missing required field 'title'.")

    duration = raw.get("target_duration_seconds")
    if duration is None and raw.get("target_duration"):
        duration = raw["target_duration"]
    try:
        target_duration = float(duration) if duration is not None else 240.0
    except (TypeError, ValueError):
        errors.append("target_duration_seconds must be a number.")
        target_duration = 240.0
    if target_duration <= 0:
        errors.append("target_duration_seconds must be positive.")

    story_dir = source_path.parent if source_path else Path(".")
    resolved_characters_dir = characters_dir or story_dir.parent / "characters"
    try:
        characters = resolve_characters(
            list(raw.get("characters") or []),
            characters_dir=resolved_characters_dir,
            story_dir=story_dir,
        )
    except (StoryValidationError, ValueError) as exc:
        errors.append(str(exc))
        characters = []

    beats_raw = raw.get("beats") or []
    if not beats_raw:
        errors.append("Story must include a non-empty 'beats' list.")
    beats: list[Beat] = []
    beat_ids: set[str] = set()
    character_ids = {character.id for character in characters}
    for item in beats_raw:
        if not isinstance(item, dict):
            errors.append(f"Beat must be a mapping, got {type(item).__name__}.")
            continue
        try:
            beat = Beat.from_dict(item)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if beat.id in beat_ids:
            errors.append(f"Duplicate beat id {beat.id!r}.")
        beat_ids.add(beat.id)
        if not beat.narration and not beat.summary:
            errors.append(f"Beat {beat.id!r} needs narration or summary.")
        for character_id in beat.characters:
            if character_id not in character_ids:
                errors.append(f"Beat {beat.id!r} references unknown character {character_id!r}.")
        beats.append(beat)

    constraints = SceneConstraints.from_dict(raw.get("scene_constraints") or raw.get("constraints"))
    if beats and not (constraints.min_scenes <= len(beats) <= constraints.max_scenes):
        errors.append(
            f"Beat count {len(beats)} is outside scene_constraints "
            f"({constraints.min_scenes}-{constraints.max_scenes})."
        )

    try:
        art_direction = ArtDirectionSpec.from_dict(raw.get("art_direction"))
    except ValueError as exc:
        errors.append(str(exc))
        art_direction = ArtDirectionSpec()

    if errors:
        raise StoryValidationError("Story validation failed:\n- " + "\n- ".join(errors))

    return StorySpec(
        id=story_id,
        title=title,
        target_duration_seconds=target_duration,
        tone=str(raw.get("tone") or ""),
        setting=Setting.from_dict(raw.get("setting")),
        visual_style=VisualStyle.from_dict(raw.get("visual_style")),
        narration=NarrationGuidance.from_dict(raw.get("narration")),
        characters=characters,
        beats=beats,
        constraints=constraints,
        art_direction=art_direction,
        source_path=source_path,
    )
