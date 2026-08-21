"""Development narration provider.

Produces real audio without paid APIs:

1. Prefer ``espeak-ng`` / ``espeak`` when present (robotic but spoken).
2. Otherwise generate timed silence with FFmpeg so assembly still works.

Word-level timing is deterministic. If generated audio has a measurable
duration, timings are scaled to that duration so scene lengths match speech.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from biscuit.exceptions import NarrationError
from biscuit.media import media_duration_seconds, run_ffmpeg
from biscuit.providers.base import NarrationProvider, NarrationRequest, NarrationResult
from biscuit.providers.registry import narration_registry
from biscuit.timing import synthetic_timing

logger = logging.getLogger(__name__)


@narration_registry.register("development")
class DevelopmentNarrationProvider(NarrationProvider):
    def synthesize(self, request: NarrationRequest, output_path: Path) -> NarrationResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            self._synthesize_espeak(espeak, request.script_text, output_path, request.words_per_minute)
        else:
            logger.info("espeak-ng not found; generating silent narration of estimated duration.")
            self._synthesize_silence(request, output_path)

        duration = media_duration_seconds(output_path)
        timing = synthetic_timing(
            request.scenes,
            words_per_minute=request.words_per_minute,
            pause_between_scenes=request.pause_between_scenes,
            provider=self.name,
            total_duration_seconds=duration,
        )
        return NarrationResult(audio_path=output_path, timing=timing)

    def _synthesize_espeak(self, binary: str, script_text: str, output_path: Path, wpm: int) -> None:
        with tempfile.TemporaryDirectory(prefix="biscuit-tts-") as tmp:
            wav_path = Path(tmp) / "narration.wav"
            # espeak -s is approximate words-per-minute.
            command = [
                binary,
                "-s",
                str(max(90, min(int(wpm * 1.05), 220))),
                "-p",
                "35",
                "-g",
                "2",
                "-w",
                str(wav_path),
                script_text,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0 or not wav_path.exists():
                raise NarrationError(f"espeak failed: {result.stderr[-1500:]}")
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(wav_path),
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "4",
                    str(output_path),
                ]
            )

    def _synthesize_silence(self, request: NarrationRequest, output_path: Path) -> None:
        from biscuit.timing import estimate_speech_seconds

        duration = sum(
            estimate_speech_seconds(
                scene.narration,
                request.words_per_minute,
                pause_seconds=(
                    scene.break_after_seconds
                    if scene.break_after_seconds
                    else (request.pause_between_scenes if index < len(request.scenes) - 1 else 0.15)
                ),
            )
            for index, scene in enumerate(request.scenes)
        )
        duration = max(duration, 1.0)
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-t",
                f"{duration:.3f}",
                "-q:a",
                "9",
                str(output_path),
            ]
        )
