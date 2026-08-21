"""On-disk layout for one pipeline run.

Intermediate artifacts are features: every expensive stage writes something
inspectable so later stages can resume without paying an AI provider again.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from biscuit.models import StoryManifest, TimingDocument


class ArtifactStore:
    """Owns the filesystem layout for a single story run."""

    def __init__(self, output_root: str | Path, story_id: str, *, run_id: str | None = None) -> None:
        self.story_id = story_id
        self.run_id = run_id
        root = Path(output_root) / story_id
        if run_id:
            root = root / run_id
        self.root = root

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def run_state_path(self) -> Path:
        return self.root / "run.json"

    @property
    def script_path(self) -> Path:
        return self.root / "script.txt"

    @property
    def performance_path(self) -> Path:
        return self.root / "performance.txt"

    @property
    def visual_plan_path(self) -> Path:
        return self.root / "visual_plan.json"

    @property
    def narration_path(self) -> Path:
        return self.root / "narration.mp3"

    @property
    def timing_path(self) -> Path:
        return self.root / "narration_timing.json"

    @property
    def image_prompts_dir(self) -> Path:
        return self.root / "image_prompts"

    @property
    def scenes_dir(self) -> Path:
        return self.root / "scenes"

    @property
    def work_dir(self) -> Path:
        return self.root / "work"

    @property
    def video_path(self) -> Path:
        return self.root / "video.mp4"

    @property
    def thumbnail_path(self) -> Path:
        return self.root / "thumbnail.png"

    @property
    def title_path(self) -> Path:
        return self.root / "title.txt"

    @property
    def description_path(self) -> Path:
        return self.root / "description.txt"

    def scene_image_path(self, index: int) -> Path:
        return self.scenes_dir / f"{index:03d}.png"

    def scene_prompt_path(self, index: int) -> Path:
        return self.image_prompts_dir / f"{index:03d}.txt"

    def scene_clip_path(self, index: int) -> Path:
        return self.work_dir / f"{index:03d}.mp4"

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.image_prompts_dir.mkdir(parents=True, exist_ok=True)
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, path: Path, payload: Any) -> Path:
        self.ensure_dirs()
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        tmp_path.replace(path)
        return path

    def write_text(self, path: Path, text: str) -> Path:
        self.ensure_dirs()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text, encoding="utf-8")
        return path

    def write_manifest(self, manifest: StoryManifest) -> Path:
        return self.write_json(self.manifest_path, manifest.to_dict())

    def read_manifest(self) -> StoryManifest:
        if not self.manifest_path.exists():
            raise FileNotFoundError(self.manifest_path)
        with self.manifest_path.open("r", encoding="utf-8") as fh:
            return StoryManifest.from_dict(json.load(fh))

    def write_timing(self, timing: TimingDocument) -> Path:
        return self.write_json(self.timing_path, timing.to_dict())

    def read_timing(self) -> TimingDocument | None:
        if not self.timing_path.exists():
            return None
        try:
            with self.timing_path.open("r", encoding="utf-8") as fh:
                return TimingDocument.from_dict(json.load(fh))
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
            return None

    def write_run_state(self, state: dict[str, Any]) -> Path:
        payload = dict(state)
        payload.setdefault("story_id", self.story_id)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self.write_json(self.run_state_path, payload)

    def read_run_state(self) -> dict[str, Any]:
        if not self.run_state_path.exists():
            return {}
        with self.run_state_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
