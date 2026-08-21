"""Narration timing: map audio alignment onto scenes.

Narrated shots take their duration from speech alignment. Unspoken visual
holds keep ``hold_seconds`` / ``target_duration_seconds`` instead of being
squeezed into whatever pause happens to exist between spoken paragraphs.
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

# Bump when unspoken-hold layout changes so cached timing is rebuilt.
TIMING_LAYOUT = "unspoken-holds-v1"


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
        if not scene_words:
            hold = scene.target_duration_seconds or scene.hold_seconds or scene.break_after_seconds or 2.5
            cursor = scene_start + max(hold, 0.4)
            scene_timings.append(SceneTiming(scene.id, scene_start, cursor))
            continue
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
    has_holds = any(is_silent_scene(scene) for scene in scenes)
    # Uniform scale would crush planned visual holds to fit spoken-only audio.
    target = natural_total if has_holds else (total_duration_seconds if total_duration_seconds is not None else natural_total)
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
        layout=TIMING_LAYOUT,
        audio_silence_insertions=_source_insertions_for_program_holds(scenes, scene_timings),
    )


def is_silent_scene(scene: Scene) -> bool:
    return not str(scene.narration or "").strip()


def planned_hold_seconds(scene: Scene) -> float:
    """Visual duration for a shot with no spoken words."""

    return float(scene.target_duration_seconds or scene.hold_seconds or scene.break_after_seconds or 2.5)


def layout_program_timeline(
    scenes: list[Scene],
    spoken_audio: list[SceneTiming],
    words: list[WordTiming],
    *,
    provider: str,
) -> TimingDocument:
    """Build the program clock from source-audio spoken times plus planned holds.

    Unspoken shots always receive ``planned_hold_seconds``. If those holds do
    not fit in the source-audio gap before the next speech, later spoken
    shots (and their word timings) shift forward and silence insertions are
    recorded so the audio file can be padded to match.
    """

    remaining = list(spoken_audio)
    scene_timings: list[SceneTiming] = []
    delay = 0.0
    cursor = 0.0
    insertions: list[tuple[float, float]] = []
    delay_by_scene: dict[str, float] = {}

    for scene in scenes:
        if not is_silent_scene(scene):
            orig = remaining.pop(0) if remaining else SceneTiming(scene.id, cursor, cursor + 0.4)
            visual_start = orig.start_seconds + delay
            if visual_start < cursor - 1e-9:
                extra = cursor - visual_start
                insertions.append((orig.start_seconds, extra))
                delay += extra
                visual_start = cursor
            visual_end = orig.end_seconds + delay
            if visual_start > cursor + 1e-9 and scene_timings:
                prev = scene_timings[-1]
                scene_timings[-1] = SceneTiming(prev.scene_id, prev.start_seconds, visual_start)
            elif visual_start > cursor + 1e-9:
                visual_start = cursor
                visual_end = max(visual_end, visual_start + orig.duration_seconds)
            delay_by_scene[scene.id] = delay
            scene_timings.append(SceneTiming(scene.id, visual_start, max(visual_end, visual_start)))
            cursor = scene_timings[-1].end_seconds
            continue

        hold = max(planned_hold_seconds(scene), 0.0)
        scene_timings.append(SceneTiming(scene.id, cursor, cursor + hold))
        cursor += hold

    shifted_words = [
        WordTiming(
            word=item.word,
            start_seconds=item.start_seconds + delay_by_scene.get(item.scene_id or "", 0.0),
            end_seconds=item.end_seconds + delay_by_scene.get(item.scene_id or "", 0.0),
            scene_id=item.scene_id,
        )
        for item in words
    ]
    merged: dict[float, float] = {}
    for at, dur in insertions:
        if dur <= 1e-9:
            continue
        key = round(at, 4)
        merged[key] = merged.get(key, 0.0) + dur
    return TimingDocument(
        provider=provider,
        total_duration_seconds=cursor if cursor > 0 else 0.0,
        scenes=scene_timings,
        words=shifted_words,
        layout=TIMING_LAYOUT,
        audio_silence_insertions=sorted(merged.items()),
    )


def ensure_unspoken_hold_layout(scenes: list[Scene], timing: TimingDocument) -> TimingDocument:
    """Rebuild hold layout from source-audio spoken times when cached timing is stale."""

    if timing.layout == TIMING_LAYOUT:
        return timing
    spoken_ids = {scene.id for scene in scenes if not is_silent_scene(scene)}
    spoken_audio = [item for item in timing.scenes if item.scene_id in spoken_ids]
    spoken_words = [item for item in timing.words if item.scene_id in spoken_ids]
    return layout_program_timeline(scenes, spoken_audio, spoken_words, provider=timing.provider)


def _source_insertions_for_program_holds(
    scenes: list[Scene], scene_timings: list[SceneTiming]
) -> list[tuple[float, float]]:
    """Map program-clock holds back onto spoken-only source audio."""

    by_id = {item.scene_id: item for item in scene_timings}
    insertions: list[tuple[float, float]] = []
    hold_accum = 0.0
    for scene in scenes:
        item = by_id.get(scene.id)
        if item is None or not is_silent_scene(scene):
            continue
        duration = item.duration_seconds
        if duration <= 1e-9:
            continue
        insertions.append((max(0.0, item.start_seconds - hold_accum), duration))
        hold_accum += duration
    return insertions


def timing_from_character_alignment(
    scenes: list[Scene],
    script_text: str,
    *,
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
    provider: str,
) -> TimingDocument:
    """Map ElevenLabs-style character alignment onto scene paragraphs.

    Spoken scenes consume spoken paragraphs in the source-audio clock.
    Unspoken shots then get their planned hold duration on the program clock.
    """

    from biscuit.ssml import spoken_fingerprint

    paragraphs = _split_paragraphs(script_text)
    spoken_paragraphs = [item for item in paragraphs if spoken_fingerprint(item[2])]
    spoken_scenes = [scene for scene in scenes if scene.narration.strip()]

    spoken_timings: list[SceneTiming] = []
    words: list[WordTiming] = []
    usable = min(len(spoken_paragraphs), len(spoken_scenes))

    def char_time(offset: int, *, is_end: bool) -> float:
        times = end_times if is_end else start_times
        if not times:
            return 0.0
        index = min(max(offset, 0), len(times) - 1)
        return times[index]

    for scene, (start, end, text) in zip(spoken_scenes[:usable], spoken_paragraphs[:usable], strict=True):
        start_seconds = char_time(start, is_end=False)
        end_seconds = char_time(end, is_end=True)
        if spoken_timings:
            start_seconds = max(start_seconds, spoken_timings[-1].end_seconds)
        spoken_timings.append(SceneTiming(scene.id, start_seconds, max(end_seconds, start_seconds)))
        words.extend(_words_from_alignment_span(text, scene.id, start, characters, start_times, end_times))

    return layout_program_timeline(scenes, spoken_timings, words, provider=provider)


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
