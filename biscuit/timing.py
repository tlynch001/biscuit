"""Narration timing: map audio alignment onto scenes.

Scene duration is driven by spoken timing, never by a guessed slide length.
When a real TTS provider (ElevenLabs) returns character-level alignment,
this module converts it into per-scene and per-word timings. When a
development provider has no alignment, it synthesizes deterministic
timings from word counts so the rest of the pipeline still runs.
"""

from __future__ import annotations

import re

from biscuit.models import Scene, SceneTiming, TimingDocument, WordTiming

_WORD_RE = re.compile(r"\S+")
_PUNCT_PAUSE = {
    ".": 0.45,
    "!": 0.45,
    "?": 0.5,
    ";": 0.28,
    ":": 0.22,
    ",": 0.18,
    "—": 0.25,
    "–": 0.2,
}


def tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def estimate_speech_seconds(text: str, words_per_minute: int, *, pause_seconds: float = 0.0) -> float:
    words = tokenize_words(text)
    if not words:
        return max(pause_seconds, 0.4)
    base = (len(words) / max(words_per_minute, 1)) * 60.0
    extra = 0.0
    for word in words:
        extra += _PUNCT_PAUSE.get(word[-1], 0.0)
    return max(0.4, base + extra + pause_seconds)


def synthetic_timing(
    scenes: list[Scene],
    *,
    words_per_minute: int,
    pause_between_scenes: float,
    provider: str = "development",
    total_duration_seconds: float | None = None,
) -> TimingDocument:
    """Build deterministic word/scene timings from narration text.

    If ``total_duration_seconds`` is supplied (e.g. from probing generated
    audio), word timings are scaled to match the real file length.
    """

    words: list[WordTiming] = []
    scene_timings: list[SceneTiming] = []
    cursor = 0.0
    for index, scene in enumerate(scenes):
        scene_start = cursor
        scene_words = tokenize_words(scene.narration)
        if scene.break_after_seconds:
            pause_after = scene.break_after_seconds
        else:
            pause_after = pause_between_scenes if index < len(scenes) - 1 else 0.15
        speech = estimate_speech_seconds(scene.narration, words_per_minute, pause_seconds=0.0)
        if not scene_words:
            cursor = scene_start + speech
        else:
            weights = [1.0 + _PUNCT_PAUSE.get(word[-1], 0.0) * 2.0 for word in scene_words]
            weight_sum = sum(weights) or 1.0
            for word, weight in zip(scene_words, weights, strict=True):
                duration = speech * (weight / weight_sum)
                words.append(
                    WordTiming(
                        word=word,
                        start_seconds=cursor,
                        end_seconds=cursor + duration,
                        scene_id=scene.id,
                    )
                )
                cursor += duration
        cursor += pause_after
        scene_timings.append(SceneTiming(scene.id, scene_start, cursor))

    natural_total = cursor if cursor > 0 else 1.0
    target = total_duration_seconds if total_duration_seconds is not None else natural_total
    factor = target / natural_total
    if factor != 1.0:
        words = [
            WordTiming(
                word=item.word,
                start_seconds=item.start_seconds * factor,
                end_seconds=item.end_seconds * factor,
                scene_id=item.scene_id,
            )
            for item in words
        ]
        scene_timings = [
            SceneTiming(item.scene_id, item.start_seconds * factor, item.end_seconds * factor)
            for item in scene_timings
        ]
    return TimingDocument(
        provider=provider,
        total_duration_seconds=target,
        scenes=scene_timings,
        words=words,
    )


def timing_from_character_alignment(
    scenes: list[Scene],
    script_text: str,
    *,
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
    provider: str,
) -> TimingDocument:
    """Map ElevenLabs-style character alignment onto scene paragraphs."""

    paragraphs = _split_paragraphs(script_text)
    scene_timings: list[SceneTiming] = []
    words: list[WordTiming] = []

    def char_time(offset: int, *, is_end: bool) -> float:
        times = end_times if is_end else start_times
        if not times:
            return 0.0
        index = min(max(offset, 0), len(times) - 1)
        return times[index]

    usable = min(len(paragraphs), len(scenes))
    for scene, (start, end, text) in zip(scenes[:usable], paragraphs[:usable], strict=True):
        start_seconds = char_time(start, is_end=False)
        end_seconds = char_time(end, is_end=True)
        if scene_timings:
            start_seconds = scene_timings[-1].end_seconds
        scene_timings.append(SceneTiming(scene.id, start_seconds, max(end_seconds, start_seconds)))
        words.extend(_words_from_alignment_span(text, scene.id, start, characters, start_times, end_times))

    total = end_times[-1] if end_times else (scene_timings[-1].end_seconds if scene_timings else 0.0)
    if scene_timings:
        last = scene_timings[-1]
        scene_timings[-1] = SceneTiming(last.scene_id, last.start_seconds, max(last.end_seconds, total))
    return TimingDocument(provider=provider, total_duration_seconds=total, scenes=scene_timings, words=words)


def apply_timing_to_scenes(scenes: list[Scene], timing: TimingDocument) -> None:
    by_id = {item.scene_id: item for item in timing.scenes}
    for scene in scenes:
        item = by_id.get(scene.id)
        if item is None:
            continue
        scene.start_seconds = item.start_seconds
        scene.end_seconds = item.end_seconds
        scene.duration_seconds = item.duration_seconds


def _split_paragraphs(script_text: str) -> list[tuple[int, int, str]]:
    paragraphs: list[tuple[int, int, str]] = []
    cursor = 0
    pieces = script_text.split("\n\n")
    for index, raw in enumerate(pieces):
        start = cursor
        stripped = raw.strip()
        if stripped:
            inner_start = start + (len(raw) - len(raw.lstrip()))
            paragraphs.append((inner_start, inner_start + len(stripped), stripped))
        cursor = start + len(raw) + (2 if index < len(pieces) - 1 else 0)
    return paragraphs


def _words_from_alignment_span(
    text: str,
    scene_id: str,
    paragraph_start: int,
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
) -> list[WordTiming]:
    words: list[WordTiming] = []
    for match in _WORD_RE.finditer(text):
        abs_start = paragraph_start + match.start()
        abs_end = paragraph_start + match.end()
        start_index = min(max(abs_start, 0), max(len(start_times) - 1, 0)) if start_times else 0
        end_index = min(max(abs_end - 1, 0), max(len(end_times) - 1, 0)) if end_times else 0
        start = start_times[start_index] if start_times else 0.0
        end = end_times[end_index] if end_times else start
        token = match.group()
        if token.startswith("<") or token.startswith("time=") or token == "/>":
            continue
        words.append(
            WordTiming(word=token, start_seconds=start, end_seconds=max(end, start), scene_id=scene_id)
        )
    return words
