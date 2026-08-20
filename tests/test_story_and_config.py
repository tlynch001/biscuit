from __future__ import annotations

from pathlib import Path

import pytest

from biscuit.config import load_config
from biscuit.exceptions import ConfigurationError, StoryValidationError
from biscuit.story import load_story, parse_story


def test_example_story_loads_and_resolves_biscuit(example_story_path: Path, repo_root: Path) -> None:
    spec = load_story(example_story_path, characters_dir=repo_root / "characters")
    assert spec.id == "biscuit_in_the_snow"
    assert spec.title == "Biscuit in the Snow"
    assert spec.target_duration_seconds == 270
    ids = [character.id for character in spec.characters]
    assert ids == ["biscuit", "veteran", "clerk"]
    biscuit = spec.character_map()["biscuit"]
    assert biscuit.source_path is not None
    assert "biscuit.yaml" in biscuit.source_path
    assert any("bandana" in phrase.lower() for phrase in biscuit.appearance_phrases())
    assert len(spec.beats) >= 8
    assert spec.beats[0].narration


def test_missing_character_reference_fails(tmp_path: Path) -> None:
    raw = {
        "id": "broken",
        "title": "Broken",
        "characters": [{"id": "only", "name": "Only"}],
        "beats": [
            {
                "id": "one",
                "narration": "Hello.",
                "characters": ["ghost"],
            }
        ],
    }
    with pytest.raises(StoryValidationError, match="unknown character"):
        parse_story(raw, source_path=tmp_path / "story.yaml", characters_dir=tmp_path)


def test_duplicate_character_id_fails(tmp_path: Path) -> None:
    raw = {
        "id": "broken",
        "title": "Broken",
        "characters": [
            {"id": "a", "name": "A"},
            {"id": "a", "name": "Also A"},
        ],
        "beats": [{"id": "one", "narration": "Hello.", "characters": ["a"]}],
    }
    with pytest.raises(StoryValidationError, match="Duplicate character"):
        parse_story(raw, source_path=tmp_path / "story.yaml", characters_dir=tmp_path)


def test_missing_id_fails() -> None:
    with pytest.raises(StoryValidationError, match="id"):
        parse_story({"title": "No ID", "characters": [{"id": "a", "name": "A"}], "beats": [{"id": "b", "narration": "Hi"}]})


def test_library_override_merges_appearance(tmp_path: Path, repo_root: Path) -> None:
    story = tmp_path / "s.yaml"
    story.write_text(
        "\n".join(
            [
                "id: overlay_test",
                "title: Overlay",
                "characters:",
                "  - from: biscuit.yaml",
                "    appearance:",
                "      clothing: a tiny knitted sweater over the bandana",
                "beats:",
                "  - id: one",
                "    characters: [biscuit]",
                "    narration: Biscuit walked.",
            ]
        ),
        encoding="utf-8",
    )
    spec = load_story(story, characters_dir=repo_root / "characters")
    biscuit = spec.character_map()["biscuit"]
    assert biscuit.appearance.get("coat")
    assert "sweater" in str(biscuit.appearance.get("clothing"))


def test_load_config_defaults_and_youtube_disabled(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("output_dir: out\n", encoding="utf-8")
    config = load_config(path)
    assert config.youtube.enabled is False
    assert config.narration.provider == "development"
    assert config.image.provider == "development"
    assert config.image.openai.model == "gpt-image-2"
    assert config.image.openai.api_key_env == "OPENAI_API_KEY"
    assert config.image.width == 1920
    assert config.video.fps == 30


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_config(tmp_path / "nope.yaml")


def test_inline_api_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("narration:\n  api_key: sk-this-should-never-be-here\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="secret"):
        load_config(path)


def test_invalid_youtube_privacy(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("youtube:\n  privacy: worldwide\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="privacy"):
        load_config(path)


def test_openai_image_config_parsed(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "image:",
                "  provider: openai",
                "  openai:",
                "    model: gpt-image-2",
                "    quality: high",
                "    api_key_env: MY_OPENAI_KEY",
                "    timeout_seconds: 90",
                "    max_retries: 1",
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.image.provider == "openai"
    assert config.image.openai.model == "gpt-image-2"
    assert config.image.openai.quality == "high"
    assert config.image.openai.api_key_env == "MY_OPENAI_KEY"
    assert config.image.openai.timeout_seconds == 90
    assert config.image.openai.max_retries == 1
    # Loading config must not require the secret to be present.
    assert config.image.openai.resolve_api_key(required=False) is None


def test_openai_inline_api_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("image:\n  openai:\n    api_key: sk-this-should-never-be-here\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="secret"):
        load_config(path)


def test_openai_invalid_quality_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("image:\n  openai:\n    quality: ultra\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="quality"):
        load_config(path)


def test_example_config_loads(repo_root: Path) -> None:
    config = load_config(repo_root / "config" / "config.example.yaml")
    assert config.youtube.enabled is False
    assert config.image.provider == "development"
    assert config.image.openai.api_key_env == "OPENAI_API_KEY"
    assert config.narration.elevenlabs.api_key_env == "ELEVENLABS_API_KEY"
    assert config.narration.elevenlabs.model_id == "eleven_multilingual_v2"
    assert config.narration.elevenlabs.speed == 0.7
    assert config.narration.words_per_minute == 170


def test_elevenlabs_speed_and_wpm_are_independent(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "narration:",
                "  words_per_minute: 95",
                "  elevenlabs:",
                "    speed: 0.7",
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.narration.words_per_minute == 95
    assert config.narration.elevenlabs.speed == 0.7


def test_elevenlabs_speed_out_of_range_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("narration:\n  elevenlabs:\n    speed: 0.5\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="speed"):
        load_config(path)
    path.write_text("narration:\n  elevenlabs:\n    speed: 1.5\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="speed"):
        load_config(path)
