from __future__ import annotations

from biscuit.models import Scene, SceneTiming, TimingDocument
from biscuit.timing import (
    TIMING_LAYOUT,
    apply_timing_to_scenes,
    ensure_unspoken_hold_layout,
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
            target_duration_seconds=2.5,
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
    # Leave a 3s gap after the first paragraph so leftover pause can remain in audio.
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
    assert timing.scenes[1].duration_seconds >= 2.5 - 1e-6
    assert timing.scenes[1].end_seconds <= timing.scenes[2].start_seconds + 1e-6


def _bridge_scenes() -> list[Scene]:
    return [
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
            title="Hold A",
            narration="",
            visual_description="field",
            character_ids=[],
            emotion="quiet",
            unspoken=True,
            hold_seconds=2.2,
            target_duration_seconds=2.2,
        ),
        Scene(
            id="scene_003",
            index=3,
            beat_id="a",
            title="Hold B",
            narration="",
            visual_description="woods",
            character_ids=[],
            emotion="quiet",
            unspoken=True,
            hold_seconds=2.4,
            target_duration_seconds=2.4,
        ),
        Scene(
            id="scene_004",
            index=4,
            beat_id="b",
            title="B",
            narration="Goodbye now.",
            visual_description="",
            character_ids=[],
            emotion="quiet",
        ),
    ]


def test_consecutive_unspoken_holds_do_not_collapse_to_minimum() -> None:
    """Reproduces Red Mitten scenes 18/19: two silent bridges with almost no audio gap."""

    scenes = _bridge_scenes()
    script = "Hello there.\n\nGoodbye now."
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
    assert [item.scene_id for item in timing.scenes] == [
        "scene_001",
        "scene_002",
        "scene_003",
        "scene_004",
    ]
    assert abs(timing.scenes[1].duration_seconds - 2.2) < 1e-6
    assert abs(timing.scenes[2].duration_seconds - 2.4) < 1e-6
    assert timing.scenes[1].duration_seconds > 0.5
    assert timing.scenes[2].duration_seconds > 0.5
    first_end = timing.scenes[0].end_seconds
    assert timing.scenes[1].start_seconds == first_end
    assert timing.scenes[2].start_seconds == timing.scenes[1].end_seconds
    assert timing.scenes[3].start_seconds == timing.scenes[2].end_seconds
    spoken_b = next(item for item in timing.scenes if item.scene_id == "scene_004")
    # Second narrated shot must shift forward by the two holds (tiny/no source gap).
    assert spoken_b.start_seconds >= first_end + 2.2 + 2.4 - 0.05
    original_b = ends[-1] - starts[script.index("Goodbye")]
    assert abs(spoken_b.duration_seconds - original_b) < 0.05
    inserted = sum(dur for _at, dur in timing.audio_silence_insertions)
    assert inserted >= 4.5
    apply_timing_to_scenes(scenes, timing)
    assert abs(scenes[1].duration_seconds - 2.2) < 1e-6
    assert abs(scenes[2].duration_seconds - 2.4) < 1e-6


def test_stale_squeezed_timing_is_rebuilt_to_planned_holds() -> None:
    scenes = _bridge_scenes()
    squeezed = TimingDocument(
        provider="elevenlabs",
        total_duration_seconds=2.0,
        layout="",
        scenes=[
            SceneTiming("scene_001", 0.0, 1.0),
            SceneTiming("scene_002", 1.0, 1.2),
            SceneTiming("scene_003", 1.2, 1.4),
            SceneTiming("scene_004", 1.4, 2.0),
        ],
    )
    rebuilt = ensure_unspoken_hold_layout(scenes, squeezed)
    assert rebuilt.layout == TIMING_LAYOUT
    by_id = {item.scene_id: item for item in rebuilt.scenes}
    assert abs(by_id["scene_002"].duration_seconds - 2.2) < 1e-6
    assert abs(by_id["scene_003"].duration_seconds - 2.4) < 1e-6
    assert by_id["scene_004"].start_seconds == by_id["scene_003"].end_seconds
    assert abs(by_id["scene_004"].duration_seconds - 0.6) < 1e-6
    assert ensure_unspoken_hold_layout(scenes, rebuilt) is rebuilt


def test_synthetic_consecutive_holds_keep_planned_duration() -> None:
    scenes = _bridge_scenes()
    timing = synthetic_timing(scenes, words_per_minute=150, pause_between_scenes=0.3, total_duration_seconds=4.0)
    assert abs(timing.scenes[1].duration_seconds - 2.2) < 1e-6
    assert abs(timing.scenes[2].duration_seconds - 2.4) < 1e-6
    # Spoken-only total_duration must not uniformly crush the holds.
    assert timing.scenes[1].duration_seconds > 1.0
    assert timing.audio_silence_insertions


def test_insert_silence_segments_lengthens_audio(tmp_path) -> None:
    import shutil

    import pytest

    from biscuit.media import insert_silence_segments, media_duration_seconds, run_ffmpeg

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe required")
    path = tmp_path / "tone.mp3"
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "1.0",
            "-q:a",
            "9",
            str(path),
        ]
    )
    insert_silence_segments(path, [(0.4, 0.5)])
    duration = media_duration_seconds(path)
    assert duration is not None
    assert 1.35 < duration < 1.75
