"""Orchestrates one story-video run.

:class:`StoryPipeline` is the only module that knows stage order. Every
expensive step sits behind a provider interface and writes inspectable
artifacts so later stages can resume without rerunning paid work.
"""

from __future__ import annotations

import logging
from pathlib import Path

from biscuit.artifacts import ArtifactStore, new_run_id
from biscuit.config import AppConfig
from biscuit.exceptions import ArtifactError, ConfigurationError
from biscuit.hashing import sha256_file, sha256_json, sha256_text
from biscuit.models import StoryManifest, StorySpec, join_script
from biscuit.prompts import apply_prompts
from biscuit.providers.base import ImageRequest, NarrationRequest
from biscuit.providers.registry import image_registry, load_builtin_providers, narration_registry, story_registry
from biscuit.publishing import generate_description, generate_title, render_thumbnail
from biscuit.stages import STAGES, stage_index
from biscuit.story import load_story
from biscuit.timing import apply_timing_to_scenes
from biscuit.video import assemble_video
from biscuit.youtube import publish_video

logger = logging.getLogger(__name__)


class StoryPipeline:
    def __init__(self, config: AppConfig) -> None:
        load_builtin_providers()
        self._config = config
        self._story_provider = story_registry.create(config.story_provider.name, **config.story_provider.options)
        self._image_provider = image_registry.create(config.image.provider)
        narration_kwargs: dict[str, object] = {}
        if config.narration.provider == "elevenlabs":
            narration_kwargs["elevenlabs"] = config.narration.elevenlabs
        self._narration_provider = narration_registry.create(config.narration.provider, **narration_kwargs)

    def run(
        self,
        story_path: str | Path,
        *,
        from_stage: str = "parse",
        through_stage: str = "publish",
        force: bool = False,
        dry_run: bool = False,
        new_run: bool = False,
        store: ArtifactStore | None = None,
    ) -> StoryManifest:
        self._validate_stage_range(from_stage, through_stage)
        spec = load_story(story_path, characters_dir=self._config.characters_dir)
        logger.info("Loaded story %s (%d beats, %d characters)", spec.id, len(spec.beats), len(spec.characters))

        if store is None:
            run_id = new_run_id() if new_run or not self._config.reuse_previous_run else None
            store = ArtifactStore(self._config.output_dir, spec.id, run_id=run_id)
        store.ensure_dirs()
        logger.info("Artifacts directory: %s", store.root)

        state = store.read_run_state()
        story_hash = sha256_file(Path(story_path))
        if state.get("story_hash") and state["story_hash"] != story_hash:
            logger.warning("Story file has changed since the last run; downstream caches may be stale.")

        def should(stage: str) -> bool:
            return stage_index(from_stage) <= stage_index(stage) <= stage_index(through_stage)

        if dry_run:
            self._log_dry_run(spec, store, from_stage, through_stage, force)
            if store.manifest_path.exists():
                return store.read_manifest()
            # Expand in memory so callers (and tests) still get a manifest.
            manifest = self._expand(spec)
            apply_prompts(manifest, spec)
            return manifest

        manifest: StoryManifest | None = None
        if should("expand"):
            manifest = self._run_expand(spec, store, state, story_hash, force)
        else:
            manifest = self._require_manifest(store)

        if should("prompts"):
            manifest = self._run_prompts(spec, manifest, store, force)
        if should("narrate"):
            manifest = self._run_narrate(manifest, store, force)
        if should("illustrate"):
            manifest = self._run_illustrate(manifest, store, force)
        if should("assemble"):
            self._run_assemble(manifest, store, force)
        if should("package"):
            self._run_package(manifest, store, force)
        if should("publish"):
            self._run_publish(manifest, store, force)

        state.update(
            {
                "story_id": spec.id,
                "story_hash": story_hash,
                "output": str(store.root),
            }
        )
        store.write_run_state(state)
        return manifest

    def _run_expand(
        self,
        spec: StorySpec,
        store: ArtifactStore,
        state: dict,
        story_hash: str,
        force: bool,
    ) -> StoryManifest:
        cached = store.manifest_path.exists() and state.get("expand_hash") == story_hash
        if cached and not force:
            logger.info("Reusing existing scene expansion (%s)", store.manifest_path)
            return store.read_manifest()
        logger.info("Expanding story beats into scenes via %s provider", self._story_provider.name)
        manifest = self._expand(spec)
        store.write_manifest(manifest)
        store.write_text(store.script_path, manifest.script_text)
        state["expand_hash"] = story_hash
        logger.info("Wrote %s (%d scenes)", store.manifest_path, len(manifest.scenes))
        return manifest

    def _expand(self, spec: StorySpec) -> StoryManifest:
        manifest = self._story_provider.expand(spec)
        manifest.story_provider = self._story_provider.name
        manifest.image_provider = self._image_provider.name
        manifest.narration_provider = self._narration_provider.name
        manifest.script_text = join_script(manifest.scenes)
        return manifest

    def _run_prompts(self, spec: StorySpec, manifest: StoryManifest, store: ArtifactStore, force: bool) -> StoryManifest:
        logger.info("Building character-consistent image prompts")
        apply_prompts(manifest, spec)
        for scene in manifest.scenes:
            prompt_path = store.scene_prompt_path(scene.index)
            if force or not prompt_path.exists() or prompt_path.read_text(encoding="utf-8").strip() != scene.image_prompt.strip():
                store.write_text(prompt_path, scene.image_prompt)
            scene.image_prompt_path = store.relative(prompt_path)
        store.write_manifest(manifest)
        store.write_text(store.script_path, manifest.script_text)
        return manifest

    def _run_narrate(self, manifest: StoryManifest, store: ArtifactStore, force: bool) -> StoryManifest:
        script = manifest.script_text or join_script(manifest.scenes)
        input_hash = sha256_json(
            {
                "script": script,
                "provider": self._narration_provider.name,
                "wpm": self._config.narration.words_per_minute,
            }
        )
        state = store.read_run_state()
        fresh = (
            store.narration_path.exists()
            and store.timing_path.exists()
            and state.get("narrate_hash") == input_hash
        )
        if fresh and not force:
            logger.info("Reusing narration audio and timing")
            timing = store.read_timing()
            if timing:
                apply_timing_to_scenes(manifest.scenes, timing)
                store.write_manifest(manifest)
            return manifest

        if self._config.narration.provider == "elevenlabs":
            self._config.narration.elevenlabs.resolve_api_key(required=True)

        logger.info("Synthesizing narration via %s provider", self._narration_provider.name)
        result = self._narration_provider.synthesize(
            NarrationRequest(
                script_text=script,
                scenes=manifest.scenes,
                words_per_minute=self._config.narration.words_per_minute,
                pause_between_scenes=self._config.narration.pause_between_scenes_seconds,
            ),
            store.narration_path,
        )
        store.write_timing(result.timing)
        apply_timing_to_scenes(manifest.scenes, result.timing)
        for scene in manifest.scenes:
            scene.target_duration_seconds = scene.target_duration_seconds or scene.duration_seconds
        store.write_manifest(manifest)
        state = store.read_run_state()
        state["narrate_hash"] = input_hash
        store.write_run_state(state)
        logger.info(
            "Narration duration %.1fs across %d scenes",
            result.timing.total_duration_seconds,
            len(result.timing.scenes),
        )
        return manifest

    def _run_illustrate(self, manifest: StoryManifest, store: ArtifactStore, force: bool) -> StoryManifest:
        characters = manifest.character_map()
        logger.info("Generating %d scene images via %s provider", len(manifest.scenes), self._image_provider.name)
        for scene in manifest.scenes:
            output = store.scene_image_path(scene.index)
            prompt_hash = sha256_text(scene.image_prompt + f"|{self._config.image.width}x{self._config.image.height}")
            stamp_path = output.with_suffix(".hash")
            reused = (
                output.exists()
                and stamp_path.exists()
                and stamp_path.read_text(encoding="utf-8").strip() == prompt_hash
            )
            if reused and not force:
                logger.info("Reusing %s", output)
            else:
                present = [characters[cid] for cid in scene.character_ids if cid in characters]
                references = [ref for character in present for ref in character.references]
                self._image_provider.generate(
                    ImageRequest(
                        scene=scene,
                        prompt=scene.image_prompt,
                        characters=present,
                        references=references,
                        width=self._config.image.width,
                        height=self._config.image.height,
                    ),
                    output,
                )
                stamp_path.write_text(prompt_hash + "\n", encoding="utf-8")
                logger.info("Wrote %s", output)
            scene.image_path = store.relative(output)
        store.write_manifest(manifest)
        return manifest

    def _run_assemble(self, manifest: StoryManifest, store: ArtifactStore, force: bool) -> None:
        if store.video_path.exists() and not force:
            logger.info("Reusing existing video %s", store.video_path)
            return
        logger.info("Assembling video with FFmpeg")
        assemble_video(manifest, store, self._config.video)
        logger.info("Wrote %s", store.video_path)

    def _run_package(self, manifest: StoryManifest, store: ArtifactStore, force: bool) -> None:
        if self._config.publishing.title_enabled and (force or not store.title_path.exists()):
            store.write_text(store.title_path, generate_title(manifest))
            logger.info("Wrote %s", store.title_path)
        if self._config.publishing.description_enabled and (force or not store.description_path.exists()):
            store.write_text(store.description_path, generate_description(manifest))
            logger.info("Wrote %s", store.description_path)
        if self._config.publishing.thumbnail_enabled and (force or not store.thumbnail_path.exists()):
            hero = None
            if manifest.scenes:
                peak = max(manifest.scenes, key=lambda s: _emotion_weight(s.emotion))
                if peak.image_path:
                    hero = store.root / peak.image_path
            render_thumbnail(manifest, hero, store.thumbnail_path)
            logger.info("Wrote %s", store.thumbnail_path)

    def _run_publish(self, manifest: StoryManifest, store: ArtifactStore, force: bool) -> None:
        state = store.read_run_state()
        title = store.title_path.read_text(encoding="utf-8").strip() if store.title_path.exists() else generate_title(manifest)
        description = store.description_path.read_text(encoding="utf-8") if store.description_path.exists() else generate_description(manifest)
        result = publish_video(
            video_path=store.video_path,
            title=title,
            description=description,
            thumbnail_path=store.thumbnail_path if store.thumbnail_path.exists() else None,
            config=self._config.youtube,
            force=force,
            already_uploaded_id=state.get("youtube_video_id"),
        )
        if result.status == "success" and result.video_id:
            state["youtube_video_id"] = result.video_id
            store.write_run_state(state)
        elif result.status == "failed":
            logger.error("YouTube publish failed: %s", result.video_error)

    def _require_manifest(self, store: ArtifactStore) -> StoryManifest:
        try:
            return store.read_manifest()
        except FileNotFoundError as exc:
            raise ArtifactError(
                f"No manifest at {store.manifest_path}. Run the expand stage first "
                "(omit --from-stage, or use --from-stage expand)."
            ) from exc

    def _log_dry_run(
        self,
        spec: StorySpec,
        store: ArtifactStore,
        from_stage: str,
        through_stage: str,
        force: bool,
    ) -> None:
        logger.info("Dry run for story %s", spec.id)
        logger.info("Output: %s", store.root)
        logger.info("Stages: %s -> %s (force=%s)", from_stage, through_stage, force)
        logger.info(
            "Providers: story=%s image=%s narration=%s youtube.enabled=%s",
            self._story_provider.name,
            self._image_provider.name,
            self._narration_provider.name,
            self._config.youtube.enabled,
        )
        for beat in spec.beats:
            logger.info("  beat %s (%s) characters=%s", beat.id, beat.emotion, ",".join(beat.characters))

    @staticmethod
    def _validate_stage_range(from_stage: str, through_stage: str) -> None:
        try:
            start = stage_index(from_stage)
            end = stage_index(through_stage)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        if start > end:
            raise ConfigurationError(f"--from-stage {from_stage} is after --through-stage {through_stage}.")


def _emotion_weight(emotion: str) -> int:
    lowered = emotion.lower()
    for keyword, score in (
        ("peak", 10),
        ("look", 9),
        ("rescue", 8),
        ("hope", 7),
        ("urgency", 6),
        ("concern", 5),
    ):
        if keyword in lowered:
            return score
    return 1
