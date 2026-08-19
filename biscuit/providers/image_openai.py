"""OpenAI GPT Image provider (opt-in, never the default).

Uses the Images API with ``gpt-image-2`` over HTTPS + ``requests`` — the same
pattern as ElevenLabs, no extra SDK. Credentials come from an environment
variable (default ``OPENAI_API_KEY``), never from YAML.

Text-to-image uses ``/v1/images/generations``. If a scene's characters have
on-disk :class:`~biscuit.models.CharacterReference` files, this provider
switches to ``/v1/images/edits`` so those files can be used as references.
That multipart protocol stays inside this module.
"""

from __future__ import annotations

import base64
import io
import logging
import time
from pathlib import Path
from typing import Any

from PIL import Image

from biscuit.config import OpenAIImageConfig
from biscuit.exceptions import ConfigurationError, ImageGenerationError
from biscuit.image_ops import choose_api_size, fit_cover
from biscuit.providers.base import ImageProvider, ImageRequest
from biscuit.providers.registry import image_registry

logger = logging.getLogger(__name__)

_GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
_EDITS_URL = "https://api.openai.com/v1/images/edits"
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_VALID_QUALITY = frozenset({"low", "medium", "high", "auto"})


@image_registry.register("openai")
class OpenAIImageProvider(ImageProvider):
    def __init__(self, openai: OpenAIImageConfig | None = None, **_ignored: object) -> None:
        self._config = openai or OpenAIImageConfig()
        if self._config.quality not in _VALID_QUALITY:
            raise ConfigurationError(
                f"image.openai.quality must be one of {sorted(_VALID_QUALITY)}, "
                f"got {self._config.quality!r}."
            )

    def generate(self, request: ImageRequest, output_path: Path) -> Path:
        api_key = self._config.resolve_api_key(required=True)
        assert api_key is not None

        api_width, api_height = choose_api_size(self._config.model, request.width, request.height)
        references = [ref for ref in request.references if ref.path.exists() and ref.path.is_file()]
        missing = [ref for ref in request.references if not ref.path.exists()]
        for ref in missing:
            logger.warning(
                "Character reference file missing (%s); skipping. Path: %s",
                ref.kind,
                ref.path,
            )

        scene_label = f"{request.scene.id} (scene {request.scene.index:03d})"
        mode = "edits" if references else "generations"
        logger.info(
            "Generating %s via openai %s %s %dx%d quality=%s (%d reference image(s))",
            scene_label,
            self._config.model,
            mode,
            api_width,
            api_height,
            self._config.quality,
            len(references),
        )
        logger.debug("OpenAI prompt for %s (%d chars):\n%s", scene_label, len(request.prompt), request.prompt)

        started = time.monotonic()
        payload = self._request_image(
            api_key=api_key,
            prompt=request.prompt,
            api_width=api_width,
            api_height=api_height,
            references=[ref.path for ref in references],
            scene_label=scene_label,
        )
        elapsed = time.monotonic() - started
        image_bytes = _decode_image_bytes(payload, scene_label)
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if isinstance(usage, dict):
            logger.info(
                "Generated %s in %.1fs (tokens in=%s out=%s total=%s)",
                scene_label,
                elapsed,
                usage.get("input_tokens"),
                usage.get("output_tokens"),
                usage.get("total_tokens"),
            )
        else:
            logger.info("Generated %s in %.1fs", scene_label, elapsed)

        revised = _revised_prompt(payload)
        if revised:
            _write_revised_prompt(output_path, request.scene.index, revised)

        _save_fitted_png(image_bytes, output_path, request.width, request.height, scene_label)
        return output_path

    def _request_image(
        self,
        *,
        api_key: str,
        prompt: str,
        api_width: int,
        api_height: int,
        references: list[Path],
        scene_label: str,
    ) -> dict[str, Any]:
        import requests

        headers = {"Authorization": f"Bearer {api_key}"}
        size = f"{api_width}x{api_height}"
        last_error: Exception | None = None
        attempts = self._config.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                if references:
                    response = self._post_edits(
                        headers=headers,
                        prompt=prompt,
                        size=size,
                        reference_paths=references,
                    )
                else:
                    response = requests.post(
                        _GENERATIONS_URL,
                        headers={**headers, "Content-Type": "application/json"},
                        json={
                            "model": self._config.model,
                            "prompt": prompt,
                            "n": 1,
                            "size": size,
                            "quality": self._config.quality,
                        },
                        timeout=self._config.timeout_seconds,
                    )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < attempts:
                    logger.warning(
                        "OpenAI request error for %s (attempt %d/%d): %s; retrying.",
                        scene_label,
                        attempt,
                        attempts,
                        exc,
                    )
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                raise ImageGenerationError(
                    f"OpenAI image generation failed for {scene_label}: {exc}"
                ) from exc

            if response.status_code in _RETRY_STATUSES and attempt < attempts:
                logger.warning(
                    "Transient OpenAI error for %s (HTTP %s, attempt %d/%d); retrying.",
                    scene_label,
                    response.status_code,
                    attempt,
                    attempts,
                )
                time.sleep(min(2 ** (attempt - 1), 8))
                continue
            if response.status_code >= 400:
                raise ImageGenerationError(
                    f"OpenAI image generation failed for {scene_label}: "
                    f"HTTP {response.status_code} {_safe_error_text(response)}"
                )
            try:
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                raise ImageGenerationError(
                    f"OpenAI image generation failed for {scene_label}: response was not JSON."
                ) from exc
            if not isinstance(payload, dict):
                raise ImageGenerationError(
                    f"OpenAI image generation failed for {scene_label}: unexpected JSON payload."
                )
            return payload
        raise ImageGenerationError(
            f"OpenAI image generation failed for {scene_label}: {last_error}"
        )

    def _post_edits(
        self,
        *,
        headers: dict[str, str],
        prompt: str,
        size: str,
        reference_paths: list[Path],
    ) -> Any:
        import requests

        files: list[tuple[str, tuple[str, Any, str]]] = []
        opened: list[Any] = []
        try:
            for path in reference_paths:
                handle = path.open("rb")
                opened.append(handle)
                files.append(("image[]", (path.name, handle, "application/octet-stream")))
            data = {
                "model": self._config.model,
                "prompt": prompt,
                "n": "1",
                "size": size,
                "quality": self._config.quality,
            }
            return requests.post(
                _EDITS_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=self._config.timeout_seconds,
            )
        finally:
            for handle in opened:
                handle.close()


def _decode_image_bytes(payload: dict[str, Any], scene_label: str) -> bytes:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise ImageGenerationError(f"OpenAI response for {scene_label} had no image data.")
    first = data[0] if isinstance(data[0], dict) else {}
    b64 = first.get("b64_json")
    if not b64:
        raise ImageGenerationError(
            f"OpenAI response for {scene_label} did not include b64_json image bytes."
        )
    try:
        return base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        raise ImageGenerationError(f"OpenAI image for {scene_label} was not valid base64.") from exc


def _revised_prompt(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    revised = data[0].get("revised_prompt")
    return str(revised) if revised else None


def _write_revised_prompt(output_path: Path, index: int, text: str) -> None:
    prompts_dir = output_path.parent.parent / "image_prompts"
    if not prompts_dir.is_dir():
        return
    path = prompts_dir / f"{index:03d}.revised.txt"
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    logger.info("Wrote API revised prompt to %s", path)


def _save_fitted_png(
    image_bytes: bytes,
    output_path: Path,
    width: int,
    height: int,
    scene_label: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(output_path.name + ".partial")
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw:
            fitted = fit_cover(raw, width, height)
            fitted.save(tmp_path, format="PNG")
        tmp_path.replace(output_path)
    except ImageGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ImageGenerationError(f"Could not decode/fit OpenAI image for {scene_label}: {exc}") from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _safe_error_text(response: Any) -> str:
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or "")
            code = error.get("code")
            if code and message:
                return f"{code}: {message}"[:500]
            return (message or str(error))[:500]
        return str(payload)[:500]
    except Exception:  # noqa: BLE001
        return (getattr(response, "text", "") or "")[:500]
