"""Abstract provider interfaces.

The orchestrator depends only on these types. Adding OpenAI/Grok/Claude
story expansion, a real image API, or a new TTS vendor should not require
rewriting the pipeline — only a new registered implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from biscuit.models import Character, CharacterReference, Scene, StoryManifest, StorySpec, TimingDocument


class StoryProvider(ABC):
    """Expand a structured story concept into scenes.

    Production LLM implementations are not shipped yet. When they are,
    they should follow ``stories/STORYTELLING.md``. Episode One is a
    quality benchmark, not a plot to clone.
    """

    name: str = "base"

    @abstractmethod
    def expand(self, spec: StorySpec) -> StoryManifest:
        """Return a scene manifest with narration and visual descriptions."""


@dataclass
class ImageRequest:
    scene: Scene
    prompt: str
    characters: list[Character]
    references: list[CharacterReference] = field(default_factory=list)
    width: int = 1920
    height: int = 1080
    seed: int | None = None


class ImageProvider(ABC):
    """Generate one still image for a scene."""

    name: str = "base"

    @abstractmethod
    def generate(self, request: ImageRequest, output_path: Path) -> Path:
        """Write an image to ``output_path`` and return that path."""


@dataclass
class NarrationRequest:
    script_text: str
    scenes: list[Scene]
    words_per_minute: int = 145
    pause_between_scenes: float = 0.35


@dataclass
class NarrationResult:
    audio_path: Path
    timing: TimingDocument


class NarrationProvider(ABC):
    """Turn the narration script into audio plus timing metadata."""

    name: str = "base"

    @abstractmethod
    def synthesize(self, request: NarrationRequest, output_path: Path) -> NarrationResult:
        """Write audio to ``output_path`` and return timing for scene durations."""
