"""Literary narration pacing for ElevenLabs Multilingual v2.

Inserts SSML break tags without changing spoken words. Pauses are inferred
from sentence shape and context — not a fixed gap after every period.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from biscuit.models import Scene
from biscuit.ssml import spoken_fingerprint, ssml_break, strip_ssml

_SENTENCE_RE = re.compile(r".+?(?:[.!?]+|$)", re.DOTALL)
_WORD_RE = re.compile(r"[A-Za-z0-9']+")

_STOP_CUES = re.compile(
    r"\b(stopped|stayed|waited|still|nothing came|that was all|no farther|no record)\b",
    re.IGNORECASE,
)
_NEGATIVE_CUES = re.compile(r"^(no |nothing |neither )", re.IGNORECASE)
_TURN_CUES = re.compile(r"^(then |after a time |first |at last )", re.IGNORECASE)


@dataclass(frozen=True)
class PacedUnit:
    spoken: str
    ssml: str
    break_after_seconds: float


def split_sentences(text: str) -> list[str]:
    """Split on terminal punctuation while keeping fragments such as ``Fence.``"""

    stripped = " ".join(text.split()).strip()
    if not stripped:
        return []
    parts = [match.group(0).strip() for match in _SENTENCE_RE.finditer(stripped)]
    return [part for part in parts if part]


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def infer_break(previous: str | None, current: str, following: str | None) -> float:
    """Seconds of silence after ``current``, before ``following``.

    Short fragments that belong together stay tight. Isolated short actions,
    negations, and turns get more air. Ordinary sentences get a modest breath
    rather than a drumbeat.
    """

    words = word_count(current)
    following_words = word_count(following) if following else 0
    previous_words = word_count(previous) if previous else 0
    fragment = words <= 3
    following_fragment = bool(following) and following_words <= 3
    previous_fragment = bool(previous) and previous_words <= 3
    lowered = current.strip()

    if following is None:
        return 0.0

    if _STOP_CUES.search(lowered) and words <= 6:
        return 1.45
    if _NEGATIVE_CUES.search(lowered) and (fragment or words <= 8):
        return 0.95
    if _TURN_CUES.search(lowered):
        return 0.85

    # "Fence. Field." — keep the pair in one breath-group.
    if fragment and following_fragment:
        return 0.28
    if fragment and previous_fragment and not following_fragment:
        return 0.7
    if fragment:
        return 0.55
    if words <= 6:
        return 0.48
    if words <= 14:
        return 0.4
    return 0.32


def pace_text(text: str, *, trailing_break: float) -> PacedUnit:
    """Return SSML for one spoken passage. Spoken words are unchanged."""

    spoken = " ".join(text.split()).strip()
    sentences = split_sentences(spoken)
    if not sentences:
        return PacedUnit(spoken="", ssml="", break_after_seconds=max(trailing_break, 0.0))

    pieces: list[str] = []
    for index, sentence in enumerate(sentences):
        pieces.append(sentence)
        following = sentences[index + 1] if index + 1 < len(sentences) else None
        previous = sentences[index - 1] if index else None
        if following is None:
            break
        gap = infer_break(previous, sentence, following)
        if gap > 0:
            pieces.append(ssml_break(gap))
    ssml = " ".join(pieces)
    assert spoken_fingerprint(ssml) == spoken_fingerprint(spoken)
    return PacedUnit(spoken=spoken, ssml=ssml, break_after_seconds=max(trailing_break, 0.0))


def apply_inferred_pacing(scenes: list[Scene]) -> list[Scene]:
    """Add performance SSML to existing scenes without splitting them."""

    last = len(scenes) - 1
    for index, scene in enumerate(scenes):
        trailing = 0.35 if index == last else 0.8
        if scene.break_after_seconds:
            trailing = scene.break_after_seconds
        paced = pace_text(scene.narration, trailing_break=trailing)
        scene.performance_narration = paced.ssml
        scene.break_after_seconds = paced.break_after_seconds
    return scenes


def join_performance_script(scenes: list[Scene]) -> str:
    """Exact text sent to ElevenLabs: spoken words plus break tags."""

    parts: list[str] = []
    for scene in scenes:
        body = (scene.performance_narration or scene.narration).strip()
        if not body:
            continue
        tag = ssml_break(scene.break_after_seconds)
        parts.append(f"{body} {tag}".strip() if tag else body)
    return "\n\n".join(parts)


def spoken_script(scenes: list[Scene]) -> str:
    """Spoken-only script (no SSML), still split by visual beat."""

    from biscuit.models import join_script

    return join_script(scenes)


def performance_preserves_speech(original: str, performance: str) -> bool:
    return spoken_fingerprint(original) == spoken_fingerprint(strip_ssml(performance))
