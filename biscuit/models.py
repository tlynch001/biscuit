"""Structured models for stories, characters, scenes, and manifests.

These types are the pipeline's intermediate language. Providers accept and
return them; the orchestrator never needs vendor-specific payloads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


@dataclass
class CharacterReference:
    """Opaque handle to a visual reference file for a character.

    Providers that support reference images (future Flux/SD/API-specific
    character refs) receive these objects. Nothing about a vendor's
    ``--cref`` / image-to-image protocol lives here.
    """

    path: Path
    kind: str = "portrait"

    def to_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterReference:
        return cls(path=Path(data["path"]), kind=str(data.get("kind", "portrait")))


@dataclass
class Character:
    """A first-class reusable character definition."""

    id: str
    name: str
    species: str = "human"
    role: str = ""
    summary: str = ""
    appearance: dict[str, Any] = field(default_factory=dict)
    personality: list[str] = field(default_factory=list)
    visual_anchors: list[str] = field(default_factory=list)
    references: list[CharacterReference] = field(default_factory=list)
    source_path: str | None = None

    def appearance_phrases(self) -> list[str]:
        """Flatten structured appearance fields into prompt phrases."""

        phrases: list[str] = []
        appearance = self.appearance or {}
        for key in ("breed", "build", "coat", "eyes", "age_look", "clothing"):
            value = appearance.get(key)
            if value:
                phrases.append(str(value))
        distinctive = appearance.get("distinctive") or []
        if isinstance(distinctive, str):
            distinctive = [distinctive]
        phrases.extend(str(item) for item in distinctive if item)
        for extra_key, extra_value in appearance.items():
            if extra_key in {"breed", "build", "coat", "eyes", "age_look", "clothing", "distinctive"}:
                continue
            if isinstance(extra_value, str) and extra_value.strip():
                phrases.append(extra_value.strip())
        return phrases

    def consistency_block(self) -> str:
        """Provider-agnostic identity block injected into every relevant prompt."""

        lines = [f"{self.name} ({self.id}): {self.species}"]
        if self.summary:
            lines.append(self.summary.strip().rstrip("."))
        phrases = self.appearance_phrases()
        if phrases:
            lines.append("Appearance: " + "; ".join(phrases))
        if self.visual_anchors:
            lines.append("Must remain consistent: " + "; ".join(self.visual_anchors))
        if self.personality:
            lines.append("Presence/demeanor: " + ", ".join(self.personality))
        return ". ".join(lines) + "."

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["references"] = [ref.to_dict() for ref in self.references]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        if not data.get("id"):
            raise ValueError("Character is missing required field 'id'.")
        if not data.get("name"):
            raise ValueError(f"Character {data.get('id')!r} is missing required field 'name'.")
        references = [
            CharacterReference.from_dict(item) if isinstance(item, dict) else CharacterReference(path=Path(str(item)))
            for item in data.get("references") or []
        ]
        appearance = data.get("appearance") or {}
        if not isinstance(appearance, dict):
            appearance = {"description": str(appearance)}
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            species=str(data.get("species", "human")),
            role=str(data.get("role", "")),
            summary=str(data.get("summary", "")),
            appearance=dict(appearance),
            personality=_as_str_list(data.get("personality")),
            visual_anchors=_as_str_list(data.get("visual_anchors")),
            references=references,
            source_path=str(data["source_path"]) if data.get("source_path") else None,
        )


@dataclass
class Setting:
    location: str = ""
    weather: str = ""
    era: str = ""
    time_of_day: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Setting:
        data = data or {}
        if isinstance(data, str):
            return cls(location=data)
        known = {item.name for item in fields(cls)}
        return cls(**{key: str(value) for key, value in data.items() if key in known and value is not None})

    def prompt_line(self) -> str:
        parts = [part for part in (self.location, self.weather, self.time_of_day, self.era) if part]
        if self.notes:
            parts.append(self.notes)
        return ", ".join(parts)


@dataclass
class VisualStyle:
    medium: str = "cinematic still photograph"
    lighting: str = ""
    color: str = ""
    camera: str = "intimate 16:9 cinematic framing"
    extra: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VisualStyle:
        data = data or {}
        if isinstance(data, str):
            return cls(medium=data)
        known = {item.name for item in fields(cls)}
        return cls(**{key: str(value) for key, value in data.items() if key in known and value is not None})

    def prompt_preamble(self) -> str:
        parts = [self.medium]
        if self.lighting:
            parts.append(self.lighting)
        if self.color:
            parts.append(self.color)
        if self.camera:
            parts.append(self.camera)
        if self.extra:
            parts.append(self.extra)
        return ", ".join(parts)


@dataclass
class NarrationGuidance:
    voice: str = "warm documentary narrator"
    pov: str = "close third person"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> NarrationGuidance:
        data = data or {}
        if isinstance(data, str):
            return cls(notes=data)
        known = {item.name for item in fields(cls)}
        return cls(**{key: str(value) for key, value in data.items() if key in known and value is not None})


@dataclass
class SceneConstraints:
    min_scenes: int = 1
    max_scenes: int = 24
    avoid: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SceneConstraints:
        data = data or {}
        return cls(
            min_scenes=int(data.get("min_scenes", 1)),
            max_scenes=int(data.get("max_scenes", 24)),
            avoid=_as_str_list(data.get("avoid")),
        )


@dataclass
class Beat:
    """An authored story beat that a story provider expands into scenes."""

    id: str
    title: str = ""
    summary: str = ""
    emotion: str = ""
    characters: list[str] = field(default_factory=list)
    narration: str = ""
    visual: str = ""
    motion: str = ""
    transition: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Beat:
        if not data.get("id"):
            raise ValueError("Each beat requires an 'id'.")
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            emotion=str(data.get("emotion", "")),
            characters=_as_str_list(data.get("characters")),
            narration=str(data.get("narration", "")).strip(),
            visual=str(data.get("visual", "")).strip(),
            motion=str(data.get("motion", "")),
            transition=str(data.get("transition", "")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class StorySpec:
    """Validated story YAML after character resolution, before scene expansion."""

    id: str
    title: str
    target_duration_seconds: float
    tone: str
    setting: Setting
    visual_style: VisualStyle
    narration: NarrationGuidance
    characters: list[Character]
    beats: list[Beat]
    constraints: SceneConstraints
    source_path: Path | None = None

    def character_map(self) -> dict[str, Character]:
        return {character.id: character for character in self.characters}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "target_duration_seconds": self.target_duration_seconds,
            "tone": self.tone,
            "setting": self.setting.to_dict(),
            "visual_style": self.visual_style.to_dict(),
            "narration": self.narration.to_dict(),
            "characters": [character.to_dict() for character in self.characters],
            "beats": [beat.to_dict() for beat in self.beats],
            "constraints": self.constraints.to_dict(),
            "source_path": str(self.source_path) if self.source_path else None,
        }


@dataclass
class Scene:
    """One visual + narration unit in the scene manifest."""

    id: str
    index: int
    beat_id: str
    title: str
    narration: str
    visual_description: str
    character_ids: list[str]
    emotion: str
    image_prompt: str = ""
    target_duration_seconds: float | None = None
    duration_seconds: float | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    transition: str = "fade"
    motion: str = "slow_zoom_in"
    image_path: str | None = None
    image_prompt_path: str | None = None
    performance_narration: str = ""
    break_after_seconds: float = 0.0
    shot_id: str = ""
    reuse_shot_id: str = ""
    world_facts: list[str] = field(default_factory=list)
    sequence_id: str = ""
    location_id: str = ""
    local_prompt: str = ""
    visible_elements: list[str] = field(default_factory=list)
    forbidden_elements: list[str] = field(default_factory=list)
    reference_shot_id: str = ""
    shot_description: str = ""
    continuity: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "beat_id": self.beat_id,
            "title": self.title,
            "narration": self.narration,
            "visual_description": self.visual_description,
            "image_prompt": self.image_prompt,
            "characters": list(self.character_ids),
            "emotion": self.emotion,
            "target_duration_seconds": self.target_duration_seconds,
            "duration_seconds": self.duration_seconds,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "transition": self.transition,
            "motion": self.motion,
            "assets": {
                "image": self.image_path,
                "image_prompt": self.image_prompt_path,
            },
            "timing": {
                "start_seconds": self.start_seconds,
                "end_seconds": self.end_seconds,
                "duration_seconds": self.duration_seconds,
            },
            "performance_narration": self.performance_narration,
            "break_after_seconds": self.break_after_seconds,
            "shot_id": self.shot_id,
            "reuse_shot_id": self.reuse_shot_id,
            "world_facts": list(self.world_facts),
            "sequence_id": self.sequence_id,
            "location_id": self.location_id,
            "local_prompt": self.local_prompt,
            "visible_elements": list(self.visible_elements),
            "forbidden_elements": list(self.forbidden_elements),
            "reference_shot_id": self.reference_shot_id,
            "shot_description": self.shot_description,
            "continuity": dict(self.continuity),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scene:
        assets = data.get("assets") or {}
        timing = data.get("timing") or {}
        return cls(
            id=str(data["id"]),
            index=int(data["index"]),
            beat_id=str(data.get("beat_id", "")),
            title=str(data.get("title", "")),
            narration=str(data.get("narration", "")),
            visual_description=str(data.get("visual_description", "")),
            character_ids=_as_str_list(data.get("characters") or data.get("character_ids")),
            emotion=str(data.get("emotion", "")),
            image_prompt=str(data.get("image_prompt", "")),
            target_duration_seconds=_optional_float(data.get("target_duration_seconds")),
            duration_seconds=_optional_float(data.get("duration_seconds") or timing.get("duration_seconds")),
            start_seconds=_optional_float(data.get("start_seconds") or timing.get("start_seconds")),
            end_seconds=_optional_float(data.get("end_seconds") or timing.get("end_seconds")),
            transition=str(data.get("transition", "fade")),
            motion=str(data.get("motion", "slow_zoom_in")),
            image_path=assets.get("image") or data.get("image_path"),
            image_prompt_path=assets.get("image_prompt") or data.get("image_prompt_path"),
            performance_narration=str(data.get("performance_narration", "")),
            break_after_seconds=float(data.get("break_after_seconds") or 0.0),
            shot_id=str(data.get("shot_id", "")),
            reuse_shot_id=str(data.get("reuse_shot_id", "")),
            world_facts=_as_str_list(data.get("world_facts")),
            sequence_id=str(data.get("sequence_id", "")),
            location_id=str(data.get("location_id", "")),
            local_prompt=str(data.get("local_prompt", "")),
            visible_elements=_as_str_list(data.get("visible_elements")),
            forbidden_elements=_as_str_list(data.get("forbidden_elements")),
            reference_shot_id=str(data.get("reference_shot_id", "")),
            shot_description=str(data.get("shot_description", "")),
            continuity=dict(data.get("continuity") or {}) if isinstance(data.get("continuity"), dict) else {},
        )


@dataclass
class WordTiming:
    word: str
    start_seconds: float
    end_seconds: float
    scene_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "scene_id": self.scene_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WordTiming:
        return cls(
            word=str(data["word"]),
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]),
            scene_id=data.get("scene_id"),
        )


@dataclass
class SceneTiming:
    scene_id: str
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "duration_seconds": round(self.duration_seconds, 3),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneTiming:
        return cls(
            scene_id=str(data["scene_id"]),
            start_seconds=float(data["start_seconds"]),
            end_seconds=float(data["end_seconds"]),
        )


@dataclass
class TimingDocument:
    """Persisted narration timing used to drive scene durations."""

    provider: str
    total_duration_seconds: float
    scenes: list[SceneTiming] = field(default_factory=list)
    words: list[WordTiming] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "scenes": [item.to_dict() for item in self.scenes],
            "words": [item.to_dict() for item in self.words],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimingDocument:
        return cls(
            provider=str(data.get("provider", "unknown")),
            total_duration_seconds=float(data.get("total_duration_seconds", 0.0)),
            scenes=[SceneTiming.from_dict(item) for item in data.get("scenes") or []],
            words=[WordTiming.from_dict(item) for item in data.get("words") or []],
        )


@dataclass
class StoryManifest:
    """Inspectable intermediate representation of an expanded story."""

    version: int
    story_id: str
    title: str
    tone: str
    target_duration_seconds: float
    setting: Setting
    visual_style: VisualStyle
    narration: NarrationGuidance
    characters: list[Character]
    scenes: list[Scene]
    constraints: SceneConstraints = field(default_factory=SceneConstraints)
    script_text: str = ""
    literary_script_text: str = ""
    performance_text: str = ""
    story_provider: str = "template"
    image_provider: str = "development"
    narration_provider: str = "development"

    def character_map(self) -> dict[str, Character]:
        return {character.id: character for character in self.characters}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "story_id": self.story_id,
            "title": self.title,
            "tone": self.tone,
            "target_duration_seconds": self.target_duration_seconds,
            "setting": self.setting.to_dict(),
            "visual_style": self.visual_style.to_dict(),
            "narration": self.narration.to_dict(),
            "characters": [character.to_dict() for character in self.characters],
            "constraints": self.constraints.to_dict(),
            "scenes": [scene.to_dict() for scene in self.scenes],
            "script_text": self.script_text,
            "literary_script_text": self.literary_script_text,
            "performance_text": self.performance_text,
            "providers": {
                "story": self.story_provider,
                "image": self.image_provider,
                "narration": self.narration_provider,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryManifest:
        providers = data.get("providers") or {}
        return cls(
            version=int(data.get("version", 1)),
            story_id=str(data["story_id"]),
            title=str(data.get("title", "")),
            tone=str(data.get("tone", "")),
            target_duration_seconds=float(data.get("target_duration_seconds", 0.0)),
            setting=Setting.from_dict(data.get("setting")),
            visual_style=VisualStyle.from_dict(data.get("visual_style")),
            narration=NarrationGuidance.from_dict(data.get("narration")),
            characters=[Character.from_dict(item) for item in data.get("characters") or []],
            constraints=SceneConstraints.from_dict(data.get("constraints")),
            scenes=[Scene.from_dict(item) for item in data.get("scenes") or []],
            script_text=str(data.get("script_text", "")),
            literary_script_text=str(data.get("literary_script_text", "")),
            performance_text=str(data.get("performance_text", "")),
            story_provider=str(providers.get("story", "template")),
            image_provider=str(providers.get("image", "development")),
            narration_provider=str(providers.get("narration", "development")),
        )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def join_script(scenes: list[Scene]) -> str:
    """Join scene narration into the canonical script.txt body.

    Scenes are separated by blank lines so character-offset alignment
    (ElevenLabs) and synthetic timing can map paragraphs back to scenes.
    """

    return "\n\n".join(scene.narration.strip() for scene in scenes if scene.narration.strip())
