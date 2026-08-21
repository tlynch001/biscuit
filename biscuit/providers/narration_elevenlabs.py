"""ElevenLabs text-to-speech with character-level timing metadata.

Adapted from the tennis_updates pipeline's working with-timestamps flow,
but mapped onto Biscuit scenes rather than tennis player slides.

The API key is never read from YAML. It is resolved from an environment
variable (default ``ELEVENLABS_API_KEY``).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from biscuit.config import ElevenLabsConfig
from biscuit.exceptions import NarrationError
from biscuit.models import TimingDocument, join_script
from biscuit.providers.base import NarrationProvider, NarrationRequest, NarrationResult
from biscuit.providers.registry import narration_registry
from biscuit.timing import synthetic_timing, timing_from_character_alignment

logger = logging.getLogger(__name__)

_API_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"


@narration_registry.register("elevenlabs")
class ElevenLabsNarrationProvider(NarrationProvider):
    def __init__(self, elevenlabs: ElevenLabsConfig | None = None, **_ignored: object) -> None:
        self._config = elevenlabs or ElevenLabsConfig()

    def synthesize(self, request: NarrationRequest, output_path: Path) -> NarrationResult:
        api_key = self._config.resolve_api_key(required=True)
        assert api_key is not None

        import requests

        script_text = request.script_text or join_script(request.scenes)
        url = _API_URL_TEMPLATE.format(voice_id=self._config.voice_id)
        payload = {
            "text": script_text,
            "model_id": self._config.model_id,
            "voice_settings": {
                "stability": self._config.stability,
                "similarity_boost": self._config.similarity_boost,
                # Official with-timestamps field: 1.0 default, <1 slower, >1 faster.
                # Independent of narration.words_per_minute (development/fallback only).
                "speed": self._config.speed,
            },
        }
        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=180)
            response.raise_for_status()
            data = response.json()
            audio_bytes = base64.b64decode(data["audio_base64"])
        except Exception as exc:  # noqa: BLE001
            raise NarrationError(f"ElevenLabs request failed: {exc}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)
        logger.info("Wrote narration audio to %s", output_path)

        alignment_text = script_text
        timing = self._timing_from_response(data.get("alignment"), request, alignment_text)
        return NarrationResult(audio_path=output_path, timing=timing)

    def _timing_from_response(
        self,
        alignment: dict[str, Any] | None,
        request: NarrationRequest,
        script_text: str,
    ) -> TimingDocument:
        if alignment and alignment.get("characters"):
            try:
                return timing_from_character_alignment(
                    request.scenes,
                    script_text,
                    characters=list(alignment["characters"]),
                    start_times=[float(t) for t in alignment["character_start_times_seconds"]],
                    end_times=[float(t) for t in alignment["character_end_times_seconds"]],
                    provider=self.name,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Could not map ElevenLabs alignment; falling back to synthetic timing.")
        else:
            logger.info("ElevenLabs did not return character alignment; using synthetic scene timing.")
        return synthetic_timing(
            request.scenes,
            words_per_minute=request.words_per_minute,
            pause_between_scenes=request.pause_between_scenes,
            provider=self.name,
        )
