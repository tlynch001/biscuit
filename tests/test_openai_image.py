from __future__ import annotations

import base64
from pathlib import Path

import pytest
from PIL import Image

from biscuit.config import OpenAIImageConfig
from biscuit.exceptions import ConfigurationError, ImageGenerationError
from biscuit.models import Character, CharacterReference, Scene
from biscuit.providers.base import ImageRequest
from biscuit.providers.image_openai import OpenAIImageProvider
from biscuit.providers.registry import image_registry, load_builtin_providers

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _scene(index: int = 1) -> Scene:
    return Scene(
        id="scene_001",
        index=index,
        beat_id="saw",
        title="Snow",
        narration="Snow fell.",
        visual_description="Biscuit in falling snow.",
        character_ids=["biscuit"],
        emotion="concern",
        image_prompt="cinematic still of Biscuit in snow, 16:9, no text",
    )


def _request(tmp_path: Path, *, with_reference: bool = False) -> tuple[ImageRequest, Path]:
    output = tmp_path / "run" / "scenes" / "001.png"
    characters = [Character(id="biscuit", name="Biscuit", species="dog")]
    references: list[CharacterReference] = []
    if with_reference:
        ref_path = tmp_path / "biscuit_ref.png"
        Image.new("RGB", (64, 64), (196, 150, 82)).save(ref_path)
        references = [CharacterReference(path=ref_path, kind="portrait")]
        characters[0].references = references
    request = ImageRequest(
        scene=_scene(),
        prompt="exact prompt that must be sent",
        characters=characters,
        references=references,
        width=1920,
        height=1080,
    )
    return request, output


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _success_payload(*, revised: str | None = "revised by api") -> dict:
    item: dict = {"b64_json": base64.b64encode(_TINY_PNG).decode("ascii")}
    if revised:
        item["revised_prompt"] = revised
    return {
        "data": [item],
        "usage": {"input_tokens": 11, "output_tokens": 22, "total_tokens": 33},
    }


@pytest.fixture
def openai_provider(monkeypatch: pytest.MonkeyPatch) -> OpenAIImageProvider:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-not-real")
    monkeypatch.setattr("biscuit.providers.image_openai.time.sleep", lambda *_args, **_kwargs: None)
    return OpenAIImageProvider(openai=OpenAIImageConfig(api_key_env="TEST_OPENAI_KEY", max_retries=2))


def test_openai_is_registered() -> None:
    load_builtin_providers()
    assert "openai" in image_registry.available()
    assert "development" in image_registry.available()


def test_missing_api_key_is_configuration_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MISSING_OPENAI_KEY", raising=False)
    provider = OpenAIImageProvider(openai=OpenAIImageConfig(api_key_env="MISSING_OPENAI_KEY"))
    request, output = _request(tmp_path)
    with pytest.raises(ConfigurationError, match="MISSING_OPENAI_KEY"):
        provider.generate(request, output)


def test_generations_payload_and_png(openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request, output = _request(tmp_path)
    (tmp_path / "run" / "image_prompts").mkdir(parents=True)
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["headers"] = kwargs.get("headers")
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    path = openai_provider.generate(request, output)
    assert path.exists()
    with Image.open(path) as img:
        assert img.size == (1920, 1080)
    assert called["url"] == "https://api.openai.com/v1/images/generations"
    assert called["json"]["model"] == "gpt-image-2"
    assert called["json"]["prompt"] == "exact prompt that must be sent"
    assert called["json"]["size"] == "1536x1024"
    assert called["json"]["quality"] == "medium"
    assert called["json"]["n"] == 1
    assert "response_format" not in called["json"]
    assert "api_key" not in called["json"]
    assert called["headers"]["Authorization"] == "Bearer sk-test-not-real"
    revised = tmp_path / "run" / "image_prompts" / "001.revised.txt"
    assert revised.exists()
    assert "revised by api" in revised.read_text(encoding="utf-8")


def test_edits_used_when_reference_file_exists(
    openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path, with_reference=True)
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["files"] = kwargs.get("files")
        called["data"] = kwargs.get("data")
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload(revised=None))

    monkeypatch.setattr("requests.post", fake_post)
    openai_provider.generate(request, output)
    assert called["url"] == "https://api.openai.com/v1/images/edits"
    assert called["json"] is None
    assert called["data"]["model"] == "gpt-image-2"
    assert called["data"]["prompt"] == "exact prompt that must be sent"
    assert called["data"]["size"] == "1536x1024"
    assert called["data"]["quality"] == "medium"
    assert "response_format" not in called["data"]
    assert called["files"]
    assert called["files"][0][0] == "image"


def test_edits_multiple_references_use_image_array_field(
    openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path, with_reference=True)
    extra = tmp_path / "veteran_ref.png"
    Image.new("RGB", (64, 64), (80, 70, 60)).save(extra)
    request.references.append(CharacterReference(path=extra, kind="portrait"))
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["files"] = kwargs.get("files")
        return _FakeResponse(200, _success_payload(revised=None))

    monkeypatch.setattr("requests.post", fake_post)
    openai_provider.generate(request, output)
    assert called["url"] == "https://api.openai.com/v1/images/edits"
    assert [name for name, _meta in called["files"]] == ["image[]", "image[]"]


def test_http_400_does_not_retry_and_names_scene(
    openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path)
    existing = b"original-bytes-must-survive"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(existing)
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return _FakeResponse(
            400,
            {"error": {"message": "bad prompt", "code": "invalid_request_error"}},
        )

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(ImageGenerationError, match="scene_001") as excinfo:
        openai_provider.generate(request, output)
    assert calls["n"] == 1
    assert "sk-test-not-real" not in str(excinfo.value)
    assert output.read_bytes() == existing
    assert not list(output.parent.glob("*.partial"))


def test_http_500_retries_then_succeeds(
    openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path)
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(500, {"error": {"message": "upstream"}})
        return _FakeResponse(200, _success_payload(revised=None))

    monkeypatch.setattr("requests.post", fake_post)
    openai_provider.generate(request, output)
    assert calls["n"] == 3
    assert output.exists()


def test_error_text_does_not_include_api_key(
    openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request, output = _request(tmp_path)

    def fake_post(url, **kwargs):
        return _FakeResponse(401, {"error": {"message": "Incorrect API key provided"}})

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(ImageGenerationError) as excinfo:
        openai_provider.generate(request, output)
    blob = str(excinfo.value) + caplog.text
    assert "sk-test-not-real" not in blob


def test_malformed_response_raises(openai_provider: OpenAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request, output = _request(tmp_path)

    def fake_post(url, **kwargs):
        return _FakeResponse(200, {"data": [{"url": "https://example.invalid/img.png"}]})

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(ImageGenerationError, match="b64_json"):
        openai_provider.generate(request, output)
    assert not output.exists()
