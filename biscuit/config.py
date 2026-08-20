"""Configuration loading.

All tunable behavior lives in a YAML file (see ``config/config.example.yaml``).
Secrets are **never** stored in that file. Instead the YAML names an
environment variable (e.g. ``api_key_env: ELEVENLABS_API_KEY``) and this
module resolves the value from the process environment, which may have
been populated from a git-ignored ``.env`` file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from biscuit.exceptions import ConfigurationError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]


def _get_secret(env_var: str | None, *, required: bool = False) -> str | None:
    if not env_var:
        return None
    value = os.environ.get(env_var)
    if required and not value:
        raise ConfigurationError(
            f"Environment variable '{env_var}' is not set. Add it to your shell "
            "environment or to a local .env file (see .env.example); never hardcode "
            "secrets in the config file."
        )
    return value


@dataclass
class ProviderConfig:
    """Generic ``{name, options}`` block used for pluggable components."""

    name: str
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None, *, default_name: str) -> ProviderConfig:
        data = data or {}
        name = str(data.get("provider", default_name))
        options = {k: v for k, v in data.items() if k != "provider"}
        return cls(name=name, options=options)


_VALID_OPENAI_IMAGE_QUALITY = frozenset({"low", "medium", "high", "auto"})


@dataclass
class OpenAIImageConfig:
    """Settings for the opt-in OpenAI GPT Image provider.

    Secrets are resolved from ``api_key_env``, never stored in this object
    as a raw key value.
    """

    model: str = "gpt-image-2"
    quality: str = "medium"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: float = 180.0
    max_retries: int = 2

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> OpenAIImageConfig:
        data = data or {}
        defaults = cls()
        quality = str(data.get("quality", defaults.quality))
        if quality not in _VALID_OPENAI_IMAGE_QUALITY:
            raise ConfigurationError(
                "image.openai.quality must be one of "
                f"{sorted(_VALID_OPENAI_IMAGE_QUALITY)}, got {quality!r}."
            )
        max_retries = int(data.get("max_retries", defaults.max_retries))
        if max_retries < 0:
            raise ConfigurationError("image.openai.max_retries must be >= 0.")
        return cls(
            model=str(data.get("model", defaults.model)),
            quality=quality,
            api_key_env=str(data.get("api_key_env", defaults.api_key_env)),
            timeout_seconds=float(data.get("timeout_seconds", defaults.timeout_seconds)),
            max_retries=max_retries,
        )

    def resolve_api_key(self, *, required: bool) -> str | None:
        return _get_secret(self.api_key_env, required=required)


@dataclass
class ImageConfig:
    provider: str = "development"
    width: int = 1920
    height: int = 1080
    openai: OpenAIImageConfig = field(default_factory=OpenAIImageConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ImageConfig:
        data = data or {}
        defaults = cls()
        return cls(
            provider=str(data.get("provider", defaults.provider)),
            width=int(data.get("width", defaults.width)),
            height=int(data.get("height", defaults.height)),
            openai=OpenAIImageConfig.from_mapping(data.get("openai")),
        )


# Official ElevenLabs TTS docs (eleven_multilingual_v2, with-timestamps):
# voice_settings.speed default 1.0; values < 1.0 slow speech, > 1.0 speed it up.
# Documented product/API range is 0.7–1.2. This is a unitless multiplier, not WPM.
_ELEVENLABS_SPEED_MIN = 0.7
_ELEVENLABS_SPEED_MAX = 1.2


@dataclass
class ElevenLabsConfig:
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    model_id: str = "eleven_multilingual_v2"
    stability: float = 0.5
    similarity_boost: float = 0.75
    speed: float = 1.0
    api_key_env: str = "ELEVENLABS_API_KEY"

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> ElevenLabsConfig:
        data = data or {}
        defaults = cls()
        speed = float(data.get("speed", defaults.speed))
        if speed < _ELEVENLABS_SPEED_MIN or speed > _ELEVENLABS_SPEED_MAX:
            raise ConfigurationError(
                "narration.elevenlabs.speed must be between "
                f"{_ELEVENLABS_SPEED_MIN} and {_ELEVENLABS_SPEED_MAX} "
                f"(ElevenLabs TTS multiplier; default 1.0). Got {speed}."
            )
        return cls(
            voice_id=str(data.get("voice_id", defaults.voice_id)),
            model_id=str(data.get("model_id", defaults.model_id)),
            stability=float(data.get("stability", defaults.stability)),
            similarity_boost=float(data.get("similarity_boost", defaults.similarity_boost)),
            speed=speed,
            api_key_env=str(data.get("api_key_env", defaults.api_key_env)),
        )

    def resolve_api_key(self, *, required: bool) -> str | None:
        return _get_secret(self.api_key_env, required=required)


@dataclass
class NarrationConfig:
    provider: str = "development"
    # Development/espeak and synthetic-timing fallback only. Does NOT control
    # ElevenLabs speaking rate — use narration.elevenlabs.speed for that.
    words_per_minute: int = 170
    pause_between_scenes_seconds: float = 0.35
    elevenlabs: ElevenLabsConfig = field(default_factory=ElevenLabsConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> NarrationConfig:
        data = data or {}
        defaults = cls()
        return cls(
            provider=str(data.get("provider", defaults.provider)),
            words_per_minute=int(data.get("words_per_minute", defaults.words_per_minute)),
            pause_between_scenes_seconds=float(
                data.get("pause_between_scenes_seconds", defaults.pause_between_scenes_seconds)
            ),
            elevenlabs=ElevenLabsConfig.from_mapping(data.get("elevenlabs")),
        )


@dataclass
class VideoConfig:
    assembler: str = "ffmpeg"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    encoder_preset: str = "veryfast"
    fade_seconds: float = 0.45
    default_motion: str = "slow_zoom_in"
    default_transition: str = "fade"
    # After the final narrated word: hold the last still, fade it to black, then black.
    end_hold_seconds: float = 4.0
    end_fade_seconds: float = 2.0
    end_black_seconds: float = 1.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> VideoConfig:
        data = data or {}
        defaults = cls()
        end_hold = float(data.get("end_hold_seconds", defaults.end_hold_seconds))
        end_fade = float(data.get("end_fade_seconds", defaults.end_fade_seconds))
        end_black = float(data.get("end_black_seconds", defaults.end_black_seconds))
        fade_seconds = float(data.get("fade_seconds", defaults.fade_seconds))
        for name, value in (
            ("video.fade_seconds", fade_seconds),
            ("video.end_hold_seconds", end_hold),
            ("video.end_fade_seconds", end_fade),
            ("video.end_black_seconds", end_black),
        ):
            if value < 0:
                raise ConfigurationError(f"{name} must be >= 0, got {value}.")
        return cls(
            assembler=str(data.get("assembler", defaults.assembler)),
            width=int(data.get("width", defaults.width)),
            height=int(data.get("height", defaults.height)),
            fps=int(data.get("fps", defaults.fps)),
            encoder_preset=str(data.get("encoder_preset", defaults.encoder_preset)),
            fade_seconds=fade_seconds,
            default_motion=str(data.get("default_motion", defaults.default_motion)),
            default_transition=str(data.get("default_transition", defaults.default_transition)),
            end_hold_seconds=end_hold,
            end_fade_seconds=end_fade,
            end_black_seconds=end_black,
        )


@dataclass
class PublishingConfig:
    thumbnail_enabled: bool = True
    title_enabled: bool = True
    description_enabled: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> PublishingConfig:
        data = data or {}
        defaults = cls()
        return cls(
            thumbnail_enabled=bool(data.get("thumbnail_enabled", defaults.thumbnail_enabled)),
            title_enabled=bool(data.get("title_enabled", defaults.title_enabled)),
            description_enabled=bool(data.get("description_enabled", defaults.description_enabled)),
        )


_VALID_YOUTUBE_PRIVACY = frozenset({"private", "unlisted", "public"})


@dataclass
class YouTubeConfig:
    """Optional publishing of the finished ``video.mp4`` to YouTube.

    ``enabled`` defaults to ``False`` and must stay that way unless a
    caller deliberately opts in. While disabled, no Google library is
    imported, no OAuth file is read, and no network call is made.
    """

    enabled: bool = False
    privacy: str = "unlisted"
    category_id: str = "1"
    client_secret_path: Path = Path("secrets/youtube_client_secret.json")
    token_path: Path = Path("secrets/youtube_token.json")

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> YouTubeConfig:
        data = data or {}
        defaults = cls()
        privacy = str(data.get("privacy", defaults.privacy))
        if privacy not in _VALID_YOUTUBE_PRIVACY:
            raise ConfigurationError(
                f"youtube.privacy must be one of {sorted(_VALID_YOUTUBE_PRIVACY)}, got {privacy!r}."
            )
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            privacy=privacy,
            category_id=str(data.get("category_id", defaults.category_id)),
            client_secret_path=Path(data.get("client_secret_path", defaults.client_secret_path)),
            token_path=Path(data.get("token_path", defaults.token_path)),
        )


@dataclass
class AppConfig:
    output_dir: Path = Path("output")
    log_dir: Path = Path("logs")
    characters_dir: Path = Path("characters")
    reuse_previous_run: bool = True
    story_provider: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(name="template")
    )
    image: ImageConfig = field(default_factory=ImageConfig)
    narration: NarrationConfig = field(default_factory=NarrationConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    publishing: PublishingConfig = field(default_factory=PublishingConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> AppConfig:
        defaults = cls()
        return cls(
            output_dir=Path(data.get("output_dir", defaults.output_dir)),
            log_dir=Path(data.get("log_dir", defaults.log_dir)),
            characters_dir=Path(data.get("characters_dir", defaults.characters_dir)),
            reuse_previous_run=bool(data.get("reuse_previous_run", defaults.reuse_previous_run)),
            story_provider=ProviderConfig.from_mapping(
                data.get("story_provider"), default_name="template"
            ),
            image=ImageConfig.from_mapping(data.get("image")),
            narration=NarrationConfig.from_mapping(data.get("narration")),
            video=VideoConfig.from_mapping(data.get("video")),
            publishing=PublishingConfig.from_mapping(data.get("publishing")),
            youtube=YouTubeConfig.from_mapping(data.get("youtube")),
        )


def load_config(path: str | Path, *, dotenv_path: str | Path | None = None) -> AppConfig:
    """Load and validate an :class:`AppConfig` from a YAML file."""

    if load_dotenv is not None:
        env_file = Path(dotenv_path) if dotenv_path else Path(".env")
        if env_file.exists():
            load_dotenv(env_file)

    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ConfigurationError(f"Config file {config_path} must contain a YAML mapping.")

    forbidden = _find_inline_secrets(raw)
    if forbidden:
        raise ConfigurationError(
            "Config file appears to contain a secret value. Store API keys in "
            f".env or the environment, not in YAML. Offending key(s): {', '.join(forbidden)}"
        )

    try:
        return AppConfig.from_mapping(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid configuration in {config_path}: {exc}") from exc


_SECRET_KEY_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "client_secret",
        "xi-api-key",
    }
)


def _find_inline_secrets(data: Any, *, prefix: str = "") -> list[str]:
    """Return dotted keys that look like inline secrets rather than env-var names."""

    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            lowered = str(key).lower().replace("_", "")
            if lowered in {k.replace("_", "") for k in _SECRET_KEY_NAMES} and isinstance(value, str):
                if value and not str(key).endswith("_env") and not str(key).endswith("_path"):
                    found.append(path)
            found.extend(_find_inline_secrets(value, prefix=path))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            found.extend(_find_inline_secrets(item, prefix=f"{prefix}[{index}]"))
    return found
