"""Deterministic story provider: authored beats become scenes.

Phase 1 stories carry their own narration. A future LLM provider can take
the same :class:`~biscuit.models.StorySpec` and invent scenes; this
implementation exists so the rest of the pipeline is testable offline.
"""

from __future__ import annotations

from biscuit.models import Scene, StoryManifest, StorySpec, join_script
from biscuit.providers.base import StoryProvider
from biscuit.providers.registry import story_registry

_DEFAULT_MOTIONS = ("slow_zoom_in", "pan_right", "slow_zoom_out", "pan_left")


@story_registry.register("template")
class TemplateStoryProvider(StoryProvider):
    def expand(self, spec: StorySpec) -> StoryManifest:
        scenes: list[Scene] = []
        for index, beat in enumerate(spec.beats, start=1):
            narration = beat.narration or _narration_from_summary(beat.summary, spec)
            visual = beat.visual or beat.summary or beat.title
            motion = beat.motion or _DEFAULT_MOTIONS[(index - 1) % len(_DEFAULT_MOTIONS)]
            transition = beat.transition or ("fade" if index == 1 else "fade")
            character_ids = list(beat.characters) or [spec.characters[0].id]
            scenes.append(
                Scene(
                    id=f"scene_{index:03d}",
                    index=index,
                    beat_id=beat.id,
                    title=beat.title or beat.id.replace("_", " ").title(),
                    narration=narration,
                    visual_description=visual,
                    character_ids=character_ids,
                    emotion=beat.emotion,
                    target_duration_seconds=None,
                    transition=transition,
                    motion=motion,
                )
            )
        return StoryManifest(
            version=1,
            story_id=spec.id,
            title=spec.title,
            tone=spec.tone,
            target_duration_seconds=spec.target_duration_seconds,
            setting=spec.setting,
            visual_style=spec.visual_style,
            narration=spec.narration,
            characters=list(spec.characters),
            constraints=spec.constraints,
            scenes=scenes,
            script_text=join_script(scenes),
            story_provider=self.name,
        )


def _narration_from_summary(summary: str, spec: StorySpec) -> str:
    protagonist = spec.characters[0].name if spec.characters else "the traveler"
    return (
        f"{summary.strip().rstrip('.')} That is what {protagonist} found, "
        f"and it was enough to change the hour."
    )
