from __future__ import annotations

from pathlib import Path

import pytest

from biscuit.artifacts import ArtifactStore
from biscuit.config import ElevenLabsConfig
from biscuit.exceptions import ProviderNotFoundError
from biscuit.models import Scene
from biscuit.providers.base import ImageRequest, NarrationRequest
from biscuit.providers.image_development import DevelopmentImageProvider
from biscuit.providers.narration_elevenlabs import ElevenLabsNarrationProvider
from biscuit.providers.registry import image_registry, load_builtin_providers, narration_registry, story_registry
from biscuit.providers.story_template import TemplateStoryProvider
from biscuit.story import load_story


def test_builtin_providers_are_registered() -> None:
    load_builtin_providers()
    assert "template" in story_registry.available()
    assert "development" in image_registry.available()
    assert "development" in narration_registry.available()
    assert "elevenlabs" in narration_registry.available()
    with pytest.raises(ProviderNotFoundError):
        image_registry.get("midjourney")


def test_template_provider_one_scene_per_beat(mini_story_path, repo_root) -> None:
    spec = load_story(mini_story_path, characters_dir=repo_root / "characters")
    manifest = TemplateStoryProvider().expand(spec)
    assert len(manifest.scenes) == len(spec.beats)
    assert manifest.script_text
    assert manifest.scenes[0].character_ids == ["biscuit", "veteran"]
    assert "Biscuit found the man" in manifest.scenes[0].narration


def test_development_image_writes_png(tmp_path: Path) -> None:
    scene = Scene(
        id="scene_001",
        index=1,
        beat_id="a",
        title="Snow",
        narration="Snow.",
        visual_description="A courthouse in a blizzard.",
        character_ids=["biscuit", "veteran"],
        emotion="concern",
    )
    from biscuit.models import Character

    request = ImageRequest(
        scene=scene,
        prompt="test prompt",
        characters=[
            Character(id="biscuit", name="Biscuit", species="dog"),
            Character(id="veteran", name="the Veteran"),
        ],
        width=640,
        height=360,
        seed=7,
    )
    output = tmp_path / "001.png"
    path = DevelopmentImageProvider().generate(request, output)
    assert path.exists()
    assert path.stat().st_size > 1000
    # Deterministic for the same seed/request.
    second = tmp_path / "001b.png"
    DevelopmentImageProvider().generate(request, second)
    assert path.read_bytes() == second.read_bytes()


def test_artifact_store_layout(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, "biscuit_in_the_snow")
    store.ensure_dirs()
    assert store.manifest_path.name == "manifest.json"
    assert store.scene_image_path(3).name == "003.png"
    assert store.scene_prompt_path(3).name == "003.txt"
    store.write_text(store.script_path, "Hello")
    assert store.script_path.read_text(encoding="utf-8") == "Hello\n"


class _FakeResponse:
    def __init__(self, audio: bytes, alignment: dict | None) -> None:
        import base64

        self._payload = {
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "alignment": alignment,
        }

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_elevenlabs_provider_writes_audio_and_timing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_ELEVENLABS_KEY", "not-a-real-key")
    scenes = [
        Scene(
            id="scene_001",
            index=1,
            beat_id="a",
            title="A",
            narration="Hello there.",
            visual_description="",
            character_ids=[],
            emotion="",
        )
    ]
    script = "Hello there."
    alignment = {
        "characters": list(script),
        "character_start_times_seconds": [i * 0.1 for i in range(len(script))],
        "character_end_times_seconds": [(i + 1) * 0.1 for i in range(len(script))],
    }
    fake_audio = b"ID3fake-mp3"

    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["headers"] = kwargs.get("headers")
        return _FakeResponse(fake_audio, alignment)

    monkeypatch.setattr("requests.post", fake_post)
    provider = ElevenLabsNarrationProvider(
        elevenlabs=ElevenLabsConfig(api_key_env="TEST_ELEVENLABS_KEY")
    )
    output = tmp_path / "narration.mp3"
    result = provider.synthesize(
        NarrationRequest(script_text=script, scenes=scenes, words_per_minute=150),
        output,
    )
    assert output.read_bytes() == fake_audio
    assert result.timing.provider == "elevenlabs"
    assert result.timing.scenes[0].scene_id == "scene_001"
    assert "with-timestamps" in called["url"]
    assert called["headers"]["xi-api-key"] == "not-a-real-key"
