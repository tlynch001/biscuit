from __future__ import annotations

import base64
from pathlib import Path

import pytest
from PIL import Image

from biscuit.config import ImageConfig, XAIImageConfig, load_config
from biscuit.exceptions import ConfigurationError, ImageGenerationError
from biscuit.models import Character, CharacterReference, Scene
from biscuit.providers.base import ImageRequest
from biscuit.providers.image_openai import OpenAIImageProvider
from biscuit.providers.image_xai import XAIImageProvider, xai_model_supports_image_edits
from biscuit.providers.registry import image_registry, load_builtin_providers
from biscuit.pipeline import StoryPipeline

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _scene(index: int = 7) -> Scene:
    return Scene(
        id="scene_007",
        index=index,
        beat_id="landing",
        title="Landing",
        narration="A child in a white nightdress.",
        visual_description="Victorian landing, lamp, small girl.",
        character_ids=["biscuit"],
        emotion="dread",
        image_prompt="cinematic still of a Victorian landing, 16:9, no text",
    )


def _request(tmp_path: Path) -> tuple[ImageRequest, Path]:
    output = tmp_path / "run" / "scenes" / "007.png"
    request = ImageRequest(
        scene=_scene(),
        prompt="exact biscuit prompt that must be sent",
        characters=[Character(id="biscuit", name="Biscuit", species="dog")],
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


def _success_payload() -> dict:
    return {"data": [{"b64_json": base64.b64encode(_TINY_PNG).decode("ascii")}]}


@pytest.fixture
def xai_provider(monkeypatch: pytest.MonkeyPatch) -> XAIImageProvider:
    monkeypatch.setenv("TEST_XAI_KEY", "xai-test-not-real")
    monkeypatch.setattr("biscuit.providers.image_xai.time.sleep", lambda *_args, **_kwargs: None)
    return XAIImageProvider(
        xai=XAIImageConfig(
            api_key_env="TEST_XAI_KEY",
            model="grok-imagine-image-quality",
            aspect_ratio="16:9",
            resolution="2k",
            max_retries=2,
        )
    )


def test_xai_and_openai_are_registered() -> None:
    load_builtin_providers()
    assert "xai" in image_registry.available()
    assert "openai" in image_registry.available()
    assert "development" in image_registry.available()
    assert image_registry.get("xai") is XAIImageProvider
    assert image_registry.get("openai") is OpenAIImageProvider


def test_factory_selects_xai(test_config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "xai-test-not-real")
    test_config.image = ImageConfig(provider="xai", width=640, height=360)
    pipeline = StoryPipeline(test_config)
    assert pipeline._image_provider.name == "xai"
    assert isinstance(pipeline._image_provider, XAIImageProvider)


def test_factory_still_selects_openai(test_config, monkeypatch: pytest.MonkeyPatch) -> None:
    from biscuit.config import OpenAIImageConfig

    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-test-not-real")
    test_config.image = ImageConfig(
        provider="openai",
        width=640,
        height=360,
        openai=OpenAIImageConfig(api_key_env="TEST_OPENAI_KEY"),
    )
    pipeline = StoryPipeline(test_config)
    assert pipeline._image_provider.name == "openai"
    assert isinstance(pipeline._image_provider, OpenAIImageProvider)


def test_missing_xai_api_key_fails_clearly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("MISSING_XAI_KEY", raising=False)
    provider = XAIImageProvider(xai=XAIImageConfig(api_key_env="XAI_API_KEY"))
    request, output = _request(tmp_path)
    with pytest.raises(ConfigurationError, match="xAI image provider selected but XAI_API_KEY is not set"):
        provider.generate(request, output)


def test_xai_request_sends_prompt_model_aspect_and_resolution(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request, output = _request(tmp_path)
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["headers"] = kwargs.get("headers")
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    with caplog.at_level("INFO"):
        path = xai_provider.generate(request, output)

    assert path.exists()
    with Image.open(path) as img:
        assert img.size == (1920, 1080)
    assert path.read_bytes()
    assert called["url"] == "https://api.x.ai/v1/images/generations"
    assert called["json"]["prompt"] == "exact biscuit prompt that must be sent"
    assert called["json"]["model"] == "grok-imagine-image-quality"
    assert called["json"]["aspect_ratio"] == "16:9"
    assert called["json"]["resolution"] == "2k"
    assert called["json"]["response_format"] == "b64_json"
    assert called["json"]["n"] == 1
    assert "api_key" not in called["json"]
    assert "xai-test-not-real" not in str(called["json"])
    assert called["headers"]["Authorization"] == "Bearer xai-test-not-real"
    assert "Generating image 007 with xAI / grok-imagine-image-quality" in caplog.text
    assert "xai-test-not-real" not in caplog.text


def test_http_400_preserves_provider_message(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
            {
                "error": {
                    "message": "Your request was rejected by the image moderation system.",
                    "code": "content_policy_violation",
                }
            },
        )

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(ImageGenerationError, match="scene_007") as excinfo:
        xai_provider.generate(request, output)
    assert calls["n"] == 1
    message = str(excinfo.value)
    assert "content_policy_violation" in message
    assert "rejected by the image moderation system" in message
    assert "xai-test-not-real" not in message
    assert output.read_bytes() == existing
    assert not list(output.parent.glob("*.partial"))


def test_http_500_retries_then_succeeds(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path)
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(500, {"error": {"message": "upstream"}})
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    xai_provider.generate(request, output)
    assert calls["n"] == 3
    assert output.exists()


def test_malformed_response_raises(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path)

    def fake_post(url, **kwargs):
        return _FakeResponse(200, {"data": [{"url": "https://example.invalid/img.png"}]})

    monkeypatch.setattr("requests.post", fake_post)
    with pytest.raises(ImageGenerationError, match="b64_json"):
        xai_provider.generate(request, output)
    assert not output.exists()


def test_xai_image_config_nested_and_flat(tmp_path: Path) -> None:
    nested = tmp_path / "nested.yaml"
    nested.write_text(
        "\n".join(
            [
                "image:",
                "  provider: xai",
                "  xai:",
                "    model: grok-imagine-image-quality",
                "    aspect_ratio: '16:9'",
                "    resolution: '2k'",
                "    api_key_env: MY_XAI_KEY",
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(nested)
    assert config.image.provider == "xai"
    assert config.image.xai.model == "grok-imagine-image-quality"
    assert config.image.xai.aspect_ratio == "16:9"
    assert config.image.xai.resolution == "2k"
    assert config.image.xai.api_key_env == "MY_XAI_KEY"
    assert config.image.openai.model == "gpt-image-2"
    assert config.image.xai.resolve_api_key(required=False) is None

    flat = tmp_path / "flat.yaml"
    flat.write_text(
        "\n".join(
            [
                "image:",
                "  enabled: true",
                "  provider: xai",
                "  model: grok-imagine-image",
                "  aspect_ratio: '9:16'",
                "  resolution: '1k'",
            ]
        ),
        encoding="utf-8",
    )
    flat_config = load_config(flat)
    assert flat_config.image.provider == "xai"
    assert flat_config.image.xai.model == "grok-imagine-image"
    assert flat_config.image.xai.aspect_ratio == "9:16"
    assert flat_config.image.xai.resolution == "1k"


def test_nested_xai_settings_win_over_flat_aliases(tmp_path: Path) -> None:
    path = tmp_path / "both.yaml"
    path.write_text(
        "\n".join(
            [
                "image:",
                "  provider: xai",
                "  model: grok-imagine-image",
                "  aspect_ratio: '1:1'",
                "  resolution: '1k'",
                "  xai:",
                "    model: grok-imagine-image-quality",
                "    aspect_ratio: '16:9'",
                "    resolution: '2k'",
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.image.xai.model == "grok-imagine-image-quality"
    assert config.image.xai.aspect_ratio == "16:9"
    assert config.image.xai.resolution == "2k"


def test_invalid_xai_aspect_ratio_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("image:\n  xai:\n    aspect_ratio: widescreen\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="aspect_ratio"):
        load_config(path)


def test_invalid_xai_resolution_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("image:\n  xai:\n    resolution: 4k\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="resolution"):
        load_config(path)


def test_xai_inline_api_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("image:\n  xai:\n    api_key: xai-this-should-never-be-here\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="secret"):
        load_config(path)


def test_xai_model_edit_support_is_prefix_based() -> None:
    assert xai_model_supports_image_edits("grok-imagine-image-2.0")
    assert xai_model_supports_image_edits("grok-imagine-image-2")
    assert not xai_model_supports_image_edits("grok-imagine-image-quality")
    assert not xai_model_supports_image_edits("grok-imagine-image")


def test_quality_model_ignores_shot_continuity_references(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request, output = _request(tmp_path)
    ref = tmp_path / "sedan_in_ditch.png"
    ref.write_bytes(_TINY_PNG)
    request.references = [CharacterReference(path=ref, kind="shot_continuity")]
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    with caplog.at_level("INFO"):
        xai_provider.generate(request, output)

    assert called["url"] == "https://api.x.ai/v1/images/generations"
    assert "image" not in called["json"]
    assert "ignoring 1 reference file" in caplog.text


def test_imagine_2_posts_edits_with_data_uri(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TEST_XAI_KEY", "xai-test-not-real")
    monkeypatch.setattr("biscuit.providers.image_xai.time.sleep", lambda *_args, **_kwargs: None)
    provider = XAIImageProvider(
        xai=XAIImageConfig(
            api_key_env="TEST_XAI_KEY",
            model="grok-imagine-image-2.0",
            aspect_ratio="16:9",
            resolution="2k",
            max_retries=0,
        )
    )
    request, output = _request(tmp_path)
    ref = tmp_path / "culvert_mouth.png"
    Image.new("RGB", (64, 36), (40, 40, 40)).save(ref)
    request.references = [CharacterReference(path=ref, kind="shot_continuity")]
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    provider.generate(request, output)

    assert called["url"] == "https://api.x.ai/v1/images/edits"
    image = called["json"]["image"]
    assert image["type"] == "image_url"
    assert image["url"].startswith("data:image/png;base64,")
    assert called["json"]["model"] == "grok-imagine-image-2.0"
    assert called["json"]["prompt"] == "exact biscuit prompt that must be sent"


def test_quality_model_uses_file_ids_on_edits(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path)
    request.references = [
        CharacterReference(
            path=tmp_path / "missing.png",
            kind="art_direction",
            asset_id="roadside_ditch_master",
            provider_file_id="file_ditch",
        ),
        CharacterReference(
            path=tmp_path / "missing2.png",
            kind="art_direction",
            asset_id="abandoned_car_master",
            provider_file_id="file_car",
        ),
        CharacterReference(
            path=tmp_path / "missing3.png",
            kind="art_direction",
            asset_id="biscuit_master",
            provider_file_id="file_biscuit",
        ),
    ]
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    xai_provider.generate(request, output)
    assert called["url"] == "https://api.x.ai/v1/images/edits"
    assert called["json"]["images"] == [
        {"file_id": "file_ditch"},
        {"file_id": "file_car"},
        {"file_id": "file_biscuit"},
    ]
    assert "image" not in called["json"]


def test_single_file_id_uses_image_object(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, output = _request(tmp_path)
    request.references = [
        CharacterReference(
            path=tmp_path / "missing.png",
            kind="art_direction",
            asset_id="biscuit_master",
            provider_file_id="file_biscuit",
        )
    ]
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["json"] = kwargs.get("json")
        return _FakeResponse(200, _success_payload())

    monkeypatch.setattr("requests.post", fake_post)
    xai_provider.generate(request, output)
    assert called["url"] == "https://api.x.ai/v1/images/edits"
    assert called["json"]["image"] == {"file_id": "file_biscuit"}
    assert "images" not in called["json"]


def test_xai_upload_reference_posts_files_api(
    xai_provider: XAIImageProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "biscuit_master.png"
    Image.new("RGB", (16, 9), (80, 80, 80)).save(source)
    called: dict = {}

    def fake_post(url, **kwargs):
        called["url"] = url
        called["files"] = kwargs.get("files")
        called["data"] = kwargs.get("data")
        called["headers"] = kwargs.get("headers")
        return _FakeResponse(200, {"id": "file_uploaded_1", "filename": source.name})

    monkeypatch.setattr("requests.post", fake_post)
    file_id = xai_provider.upload_reference(source)
    assert file_id == "file_uploaded_1"
    assert called["url"] == "https://api.x.ai/v1/files"
    assert called["data"]["purpose"] == "assistants"
    assert "Authorization" in called["headers"]
    assert called["headers"]["Authorization"].startswith("Bearer ")
