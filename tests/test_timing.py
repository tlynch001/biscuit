from __future__ import annotations

from biscuit.models import Scene
from biscuit.timing import (
    apply_timing_to_scenes,
    estimate_speech_seconds,
    synthetic_timing,
    timing_from_character_alignment,
    tokenize_words,
)


def _scenes() -> list[Scene]:
    return [
        Scene(
            id="scene_001",
            index=1,
            beat_id="a",
            title="A",
            narration="Biscuit walked through the snow.",
            visual_description="",
            character_ids=["biscuit"],
            emotion="quiet",
        ),
        Scene(
            id="scene_002",
            index=2,
            beat_id="b",
            title="B",
            narration="He found the man. He stayed.",
            visual_description="",
            character_ids=["biscuit"],
            emotion="resolve",
        ),
    ]


def test_synthetic_timing_is_deterministic() -> None:
    scenes = _scenes()
    first = synthetic_timing(scenes, words_per_minute=150, pause_between_scenes=0.3)
    second = synthetic_timing(scenes, words_per_minute=150, pause_between_scenes=0.3)
    assert first.to_dict() == second.to_dict()
    assert len(first.scenes) == 2
    assert first.scenes[0].end_seconds == first.scenes[1].start_seconds
    assert first.words
    assert all(word.scene_id in {"scene_001", "scene_002"} for word in first.words)


def test_synthetic_timing_scales_to_audio_duration() -> None:
    scenes = _scenes()
    timing = synthetic_timing(
        scenes, words_per_minute=150, pause_between_scenes=0.2, total_duration_seconds=10.0
    )
    assert timing.total_duration_seconds == 10.0
    assert abs(timing.scenes[-1].end_seconds - 10.0) < 1e-6


def test_apply_timing_writes_scene_durations() -> None:
    scenes = _scenes()
    timing = synthetic_timing(scenes, words_per_minute=120, pause_between_scenes=0.1)
    apply_timing_to_scenes(scenes, timing)
    assert scenes[0].duration_seconds and scenes[0].duration_seconds > 0
    assert scenes[0].start_seconds == 0.0
    assert scenes[1].start_seconds == scenes[0].end_seconds


def test_alignment_maps_paragraphs_to_scenes() -> None:
    scenes = _scenes()
    script = "Biscuit walked through the snow.\n\nHe found the man. He stayed."
    characters = list(script)
    starts = [i * 0.05 for i in range(len(characters))]
    ends = [(i + 1) * 0.05 for i in range(len(characters))]
    timing = timing_from_character_alignment(
        scenes,
        script,
        characters=characters,
        start_times=starts,
        end_times=ends,
        provider="elevenlabs",
    )
    assert timing.provider == "elevenlabs"
    assert [item.scene_id for item in timing.scenes] == ["scene_001", "scene_002"]
    assert timing.scenes[0].start_seconds == 0.0
    assert timing.total_duration_seconds == ends[-1]


def test_estimate_speech_uses_punctuation_pauses() -> None:
    short = estimate_speech_seconds("Snow", 150)
    long = estimate_speech_seconds("Snow. Snow. Snow.", 150)
    assert long > short
    assert tokenize_words("Hello, Biscuit.") == ["Hello,", "Biscuit."]


def test_synthetic_timing_holds_unspoken_shots() -> None:
    scenes = [
        Scene(
            id="scene_001",
            index=1,
            beat_id="a",
            title="A",
            narration="Biscuit walked through the snow.",
            visual_description="",
            character_ids=["biscuit"],
            emotion="quiet",
        ),
        Scene(
            id="scene_002",
            index=2,
            beat_id="a",
            title="Hold",
            narration="",
            visual_description="field",
            character_ids=["biscuit"],
            emotion="quiet",
            unspoken=True,
            hold_seconds=2.6,
            target_duration_seconds=2.6,
        ),
        Scene(
            id="scene_003",
            index=3,
            beat_id="b",
            title="B",
            narration="He found the man.",
            visual_description="",
            character_ids=["biscuit"],
            emotion="resolve",
        ),
    ]
    timing = synthetic_timing(scenes, words_per_minute=150, pause_between_scenes=0.3)
    assert [item.scene_id for item in timing.scenes] == ["scene_001", "scene_002", "scene_003"]
    assert abs(timing.scenes[1].duration_seconds - 2.6) < 1e-6
    assert timing.scenes[1].start_seconds == timing.scenes[0].end_seconds
    assert timing.scenes[2].start_seconds == timing.scenes[1].end_seconds
    assert all(word.scene_id != "scene_002" for word in timing.words)


def test_alignment_places_unspoken_hold_between_spoken_scenes() -> None:
    scenes = [
        Scene(
            id="scene_001",
            index=1,
            beat_id="a",
            title="A",
            narration="Hello there.",
            visual_description="",
            character_ids=[],
            emotion="quiet",
        ),
        Scene(
            id="scene_002",
            index=2,
            beat_id="a",
            title="Hold",
            narration="",
            visual_description="field",
            character_ids=[],
            emotion="quiet",
            unspoken=True,
            hold_seconds=2.5,
        ),
        Scene(
            id="scene_003",
            index=3,
            beat_id="b",
            title="B",
            narration="Goodbye now.",
            visual_description="",
            character_ids=[],
            emotion="quiet",
        ),
    ]
    script = "Hello there.\n\nGoodbye now."
    characters = list(script)
    starts = [i * 0.05 for i in range(len(characters))]
    ends = [(i + 1) * 0.05 for i in range(len(characters))]
    # Leave a 3s gap after the first paragraph so the hold can occupy it.
    second_start = script.index("Goodbye")
    for index in range(second_start, len(starts)):
        starts[index] += 3.0
        ends[index] += 3.0
    timing = timing_from_character_alignment(
        scenes,
        script,
        characters=characters,
        start_times=starts,
        end_times=ends,
        provider="elevenlabs",
    )
    assert [item.scene_id for item in timing.scenes] == ["scene_001", "scene_002", "scene_003"]
    assert timing.scenes[1].duration_seconds >= 2.0
    assert timing.scenes[1].end_seconds <= timing.scenes[2].start_seconds + 1e-6
