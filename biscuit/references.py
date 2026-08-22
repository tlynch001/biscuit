"""Provider-agnostic reference-asset library.

A reference asset is an approved image that establishes something that must
stay visually consistent: a character, a location, a vehicle, a prop, or a
human-promoted composition anchor.

Stories and visual plans name assets by logical id (``biscuit_master``).
This registry is the only place that may store a provider file id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from biscuit.exceptions import ArtDirectionError
from biscuit.hashing import sha256_file
from biscuit.models import CharacterReference, Scene

MAX_REFERENCES_PER_SHOT = 3

ASSET_STATUSES = ("planned", "candidate", "approved", "rejected")
ASSET_CATEGORIES = (
    "character",
    "location",
    "vehicle",
    "prop",
    "environmental",
    "composition",
)

_CATEGORY_RANK = {
    "location": 0,
    "environmental": 1,
    "character": 2,
    "vehicle": 3,
    "prop": 4,
    "composition": 5,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


@dataclass
class ReferenceAsset:
    """One production-design image, not necessarily a finished frame."""

    id: str
    category: str = "prop"
    description: str = ""
    why: str = ""
    needed_by_shots: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    location_ids: list[str] = field(default_factory=list)
    priority: int = 50
    status: str = "planned"
    local_path: str | None = None
    original_path: str | None = None
    provider: str | None = None
    provider_file_id: str | None = None
    content_hash: str | None = None
    source: str = "planner"
    source_shot_id: str | None = None
    continuity_notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.category not in ASSET_CATEGORIES:
            raise ArtDirectionError(
                f"Reference asset {self.id!r} has unknown category {self.category!r}."
            )
        if self.status not in ASSET_STATUSES:
            raise ArtDirectionError(
                f"Reference asset {self.id!r} has unknown status {self.status!r}."
            )
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "why": self.why,
            "needed_by_shots": list(self.needed_by_shots),
            "entity_ids": list(self.entity_ids),
            "location_ids": list(self.location_ids),
            "priority": self.priority,
            "status": self.status,
            "local_path": self.local_path,
            "original_path": self.original_path,
            "provider": self.provider,
            "provider_file_id": self.provider_file_id,
            "content_hash": self.content_hash,
            "source": self.source,
            "source_shot_id": self.source_shot_id,
            "continuity_notes": self.continuity_notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceAsset:
        if not data.get("id"):
            raise ArtDirectionError("Reference asset is missing required field 'id'.")
        return cls(
            id=str(data["id"]),
            category=str(data.get("category") or "prop"),
            description=str(data.get("description") or ""),
            why=str(data.get("why") or ""),
            needed_by_shots=_as_str_list(data.get("needed_by_shots")),
            entity_ids=_as_str_list(data.get("entity_ids")),
            location_ids=_as_str_list(data.get("location_ids")),
            priority=int(data.get("priority") or 50),
            status=str(data.get("status") or "planned"),
            local_path=str(data["local_path"]) if data.get("local_path") else None,
            original_path=str(data["original_path"]) if data.get("original_path") else None,
            provider=str(data["provider"]) if data.get("provider") else None,
            provider_file_id=str(data["provider_file_id"]) if data.get("provider_file_id") else None,
            content_hash=str(data["content_hash"]) if data.get("content_hash") else None,
            source=str(data.get("source") or "planner"),
            source_shot_id=str(data["source_shot_id"]) if data.get("source_shot_id") else None,
            continuity_notes=str(data.get("continuity_notes") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )

    def resolved_path(self, store_root: Path) -> Path | None:
        if not self.local_path:
            return None
        path = Path(self.local_path)
        if not path.is_absolute():
            path = store_root / path
        return path

    def is_approved(self) -> bool:
        return self.status == "approved"

    def has_usable_image(self, store_root: Path) -> bool:
        path = self.resolved_path(store_root)
        return bool(self.is_approved() and path is not None and path.is_file())


@dataclass
class ShotReferenceSelection:
    """Inspectable per-shot choice of at most three logical assets."""

    selected: list[str]
    candidates: list[str]
    ranking: list[dict[str, Any]]
    omitted: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": list(self.selected),
            "candidates": list(self.candidates),
            "ranking": [dict(item) for item in self.ranking],
            "omitted": [dict(item) for item in self.omitted],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ShotReferenceSelection:
        data = data or {}
        return cls(
            selected=_as_str_list(data.get("selected")),
            candidates=_as_str_list(data.get("candidates")),
            ranking=[dict(item) for item in data.get("ranking") or [] if isinstance(item, dict)],
            omitted=[dict(item) for item in data.get("omitted") or [] if isinstance(item, dict)],
        )


class ReferenceRegistry:
    """Persistent story-scoped library of reference assets."""

    version = 1

    def __init__(
        self,
        story_id: str,
        *,
        mode: str = "automatic",
        assets: dict[str, ReferenceAsset] | None = None,
        max_references_per_shot: int = MAX_REFERENCES_PER_SHOT,
    ) -> None:
        self.story_id = story_id
        self.mode = mode
        self.max_references_per_shot = max_references_per_shot
        self.assets: dict[str, ReferenceAsset] = dict(assets or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "story_id": self.story_id,
            "mode": self.mode,
            "max_references_per_shot": self.max_references_per_shot,
            "assets": {asset_id: asset.to_dict() for asset_id, asset in sorted(self.assets.items())},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceRegistry:
        assets = {
            str(key): ReferenceAsset.from_dict(value if isinstance(value, dict) else {"id": key})
            for key, value in (data.get("assets") or {}).items()
        }
        return cls(
            story_id=str(data.get("story_id") or ""),
            mode=str(data.get("mode") or "automatic"),
            assets=assets,
            max_references_per_shot=int(data.get("max_references_per_shot") or MAX_REFERENCES_PER_SHOT),
        )

    @classmethod
    def load(cls, path: Path, *, story_id: str, mode: str | None = None) -> ReferenceRegistry:
        if not path.exists():
            return cls(story_id=story_id, mode=mode)
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if not isinstance(payload, dict):
            raise ArtDirectionError(f"Reference registry {path} must be a JSON object.")
        registry = cls.from_dict(payload)
        registry.story_id = registry.story_id or story_id
        if mode is not None:
            registry.mode = mode
        return registry

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        tmp_path.replace(path)
        return path

    def get(self, asset_id: str) -> ReferenceAsset:
        try:
            return self.assets[asset_id]
        except KeyError as exc:
            raise ArtDirectionError(f"Unknown reference asset {asset_id!r}.") from exc

    def merge_proposal(self, proposed: ReferenceAsset) -> ReferenceAsset:
        """Insert or refresh planner metadata without clobbering human art direction."""

        existing = self.assets.get(proposed.id)
        if existing is None:
            self.assets[proposed.id] = proposed
            return proposed
        existing.category = proposed.category
        existing.description = proposed.description or existing.description
        existing.why = proposed.why or existing.why
        existing.needed_by_shots = list(proposed.needed_by_shots)
        existing.entity_ids = list(proposed.entity_ids)
        existing.location_ids = list(proposed.location_ids)
        existing.priority = proposed.priority
        existing.continuity_notes = proposed.continuity_notes or existing.continuity_notes
        if existing.source == "planner" and proposed.source:
            existing.source = proposed.source
        existing.updated_at = _now()
        return existing

    def register_local(
        self,
        asset_id: str,
        source_path: Path,
        *,
        store_root: Path,
        category: str | None = None,
        description: str = "",
        why: str = "",
        continuity_notes: str = "",
        approve: bool = False,
    ) -> ReferenceAsset:
        if not source_path.exists() or not source_path.is_file():
            raise ArtDirectionError(f"Reference image not found: {source_path}")
        dest_dir = store_root / "references"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}{source_path.suffix.lower() or '.png'}"
        dest.write_bytes(source_path.read_bytes())
        digest = sha256_file(dest)
        asset = self.assets.get(asset_id)
        if asset is None:
            asset = ReferenceAsset(
                id=asset_id,
                category=category or "prop",
                description=description,
                why=why,
                continuity_notes=continuity_notes,
                source="manual",
            )
            self.assets[asset_id] = asset
        elif category:
            asset.category = category
        if description:
            asset.description = description
        if why:
            asset.why = why
        if continuity_notes:
            asset.continuity_notes = continuity_notes
        if asset.content_hash != digest:
            asset.provider_file_id = None
            asset.provider = None
        asset.local_path = str(dest.relative_to(store_root))
        asset.original_path = str(source_path)
        asset.content_hash = digest
        asset.source = "manual" if asset.source == "planner" else asset.source
        asset.status = "approved" if approve or asset.status == "approved" else "candidate"
        asset.updated_at = _now()
        return asset

    def record_generated_candidate(
        self,
        asset_id: str,
        image_path: Path,
        *,
        store_root: Path,
        provider: str,
    ) -> ReferenceAsset:
        asset = self.get(asset_id)
        dest_dir = store_root / "references" / "candidates"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}{image_path.suffix.lower() or '.png'}"
        dest.write_bytes(image_path.read_bytes())
        asset.local_path = str(dest.relative_to(store_root))
        asset.content_hash = sha256_file(dest)
        asset.provider = provider
        asset.provider_file_id = None
        asset.source = "generated"
        asset.status = "candidate"
        asset.updated_at = _now()
        return asset

    def approve(self, asset_id: str, *, store_root: Path | None = None) -> ReferenceAsset:
        asset = self.get(asset_id)
        if store_root is not None:
            path = asset.resolved_path(store_root)
            if path is None or not path.is_file():
                raise ArtDirectionError(
                    f"Cannot approve {asset_id!r}: no local image is registered. "
                    "Use --register-reference or --generate-reference first."
                )
            if asset.local_path and "candidates/" in asset.local_path.replace("\\", "/"):
                dest = store_root / "references" / Path(asset.local_path).name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(path.read_bytes())
                asset.local_path = str(dest.relative_to(store_root))
                asset.content_hash = sha256_file(dest)
        asset.status = "approved"
        asset.updated_at = _now()
        return asset

    def reject(self, asset_id: str) -> ReferenceAsset:
        asset = self.get(asset_id)
        asset.status = "rejected"
        asset.updated_at = _now()
        return asset

    def promote_shot(
        self,
        *,
        asset_id: str,
        shot_id: str,
        image_path: Path,
        store_root: Path,
        description: str = "",
        why: str = "",
        needed_by_shots: Iterable[str] | None = None,
        approve: bool = True,
    ) -> ReferenceAsset:
        if not image_path.exists() or not image_path.is_file():
            raise ArtDirectionError(f"Cannot promote missing shot image: {image_path}")
        dest_dir = store_root / "references"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}{image_path.suffix.lower() or '.png'}"
        dest.write_bytes(image_path.read_bytes())
        asset = self.assets.get(asset_id) or ReferenceAsset(
            id=asset_id,
            category="composition",
            source="promoted_shot",
        )
        asset.category = "composition"
        asset.description = description or asset.description or f"Promoted composition anchor from {shot_id}."
        asset.why = why or asset.why or "Human-approved generated shot used as a later continuity anchor."
        if needed_by_shots is not None:
            asset.needed_by_shots = list(needed_by_shots)
        asset.local_path = str(dest.relative_to(store_root))
        asset.original_path = str(image_path)
        asset.content_hash = sha256_file(dest)
        asset.provider_file_id = None
        asset.provider = None
        asset.source = "promoted_shot"
        asset.source_shot_id = shot_id
        asset.status = "approved" if approve else "candidate"
        asset.updated_at = _now()
        self.assets[asset_id] = asset
        return asset

    def record_upload(
        self,
        asset_id: str,
        *,
        provider: str,
        provider_file_id: str,
        content_hash: str,
    ) -> ReferenceAsset:
        asset = self.get(asset_id)
        asset.provider = provider
        asset.provider_file_id = provider_file_id
        asset.content_hash = content_hash
        asset.updated_at = _now()
        return asset

    def cached_upload_is_valid(self, asset: ReferenceAsset, store_root: Path, *, provider: str) -> bool:
        if not asset.provider_file_id or asset.provider != provider:
            return False
        path = asset.resolved_path(store_root)
        if path is None or not path.is_file():
            return False
        return asset.content_hash == sha256_file(path)

    def approved_unresolved(self, required_ids: Iterable[str], store_root: Path) -> list[str]:
        missing: list[str] = []
        for asset_id in required_ids:
            asset = self.assets.get(asset_id)
            if asset is None or not asset.has_usable_image(store_root):
                missing.append(asset_id)
        return missing


def rank_key(asset: ReferenceAsset) -> tuple[int, int, str]:
    """Higher priority wins; ties prefer location, then character, then id."""

    return (-int(asset.priority), _CATEGORY_RANK.get(asset.category, 9), asset.id)


def select_shot_references(
    assets: Iterable[ReferenceAsset],
    *,
    limit: int = MAX_REFERENCES_PER_SHOT,
) -> ShotReferenceSelection:
    ranked = sorted(assets, key=rank_key)
    selected = ranked[:limit]
    omitted = ranked[limit:]
    ranking = []
    for index, asset in enumerate(ranked, start=1):
        ranking.append(
            {
                "rank": index,
                "id": asset.id,
                "priority": asset.priority,
                "category": asset.category,
                "selected": index <= limit,
                "reason": (
                    f"{asset.category} priority {asset.priority}: {asset.why or asset.description}"
                ).strip(),
            }
        )
    return ShotReferenceSelection(
        selected=[asset.id for asset in selected],
        candidates=[asset.id for asset in ranked],
        ranking=ranking,
        omitted=[
            {
                "id": asset.id,
                "reason": (
                    f"Ranked below the {limit}-reference cap. "
                    f"{asset.category} priority {asset.priority}."
                ),
            }
            for asset in omitted
        ],
    )


def candidates_for_scene(
    scene: Scene,
    registry: ReferenceRegistry,
) -> list[ReferenceAsset]:
    """Assets whose absence would damage this shot's continuity."""

    visible = set(scene.visible_entities) | set(scene.character_ids)
    location = scene.location_id
    found: dict[str, ReferenceAsset] = {}
    for asset in registry.assets.values():
        if asset.status == "rejected":
            continue
        hit = False
        if location and location in asset.location_ids:
            hit = True
        if visible & set(asset.entity_ids):
            hit = True
        if scene.shot_id and scene.shot_id in asset.needed_by_shots and asset.category == "composition":
            # Promoted anchors are never implied. They must be listed for this shot.
            hit = True
        if hit:
            found[asset.id] = asset
    return list(found.values())


def apply_selection_to_scene(scene: Scene, selection: ShotReferenceSelection) -> Scene:
    scene.reference_assets = list(selection.selected)
    scene.reference_candidates = list(selection.candidates)
    scene.reference_selection = selection.to_dict()
    return scene


def to_character_references(
    asset_ids: Iterable[str],
    registry: ReferenceRegistry,
    store_root: Path,
) -> list[CharacterReference]:
    refs: list[CharacterReference] = []
    for asset_id in asset_ids:
        asset = registry.get(asset_id)
        path = asset.resolved_path(store_root)
        if path is None:
            continue
        refs.append(
            CharacterReference(
                path=path,
                kind="art_direction",
                asset_id=asset.id,
                provider_file_id=asset.provider_file_id or "",
            )
        )
    return refs
