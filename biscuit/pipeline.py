"""Orchestrates one story-video run.

:class:`StoryPipeline` is the only module that knows stage order. Every
expensive step sits behind a provider interface and writes inspectable
artifacts so later stages can resume without rerunning paid work.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from biscuit.artifacts import ArtifactStore, new_run_id
from biscuit.config import AppConfig
from biscuit.exceptions import ArtifactError, ConfigurationError, ImageGenerationError
from biscuit.hashing import sha256_file, sha256_json
from biscuit.models import Character, Scene, StoryManifest, StorySpec, join_script
from biscuit.prompts import apply_prompts
from biscuit.providers.base import ImageRequest, NarrationRequest
from biscuit.providers.registry import image_registry, load_builtin_providers, narration_registry, story_registry
from biscuit.publishing import generate_description, generate_title, render_thumbnail
from biscuit.stages import STAGES, stage_index
from biscuit.story import load_story
from biscuit.timing import apply_timing_to_scenes
from biscuit.video import MOTION_FILTER_VERSION, OUTRO_VERSION, assemble_video
from biscuit.youtube import publish_video

logger = logging.getLogger(__name__)

_FREE_IMAGE_PROVIDERS = frozenset({"development"})


def _image_provider_is_paid(name: str | None) -> bool:
    return bool(name) and name not in _FREE_IMAGE_PROVIDERS


def _parse_image_stamp(path: Path) -> dict[str, str | None]:
    """Read a scene image stamp. Supports JSON provenance and legacy bare hashes."""

    if not path.exists():
        return {"hash": None, "provider": None}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {"hash": None, "provider": None}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("hash"):
                provider = data.get("provider")
                return {
                    "hash": str(data["hash"]).strip(),
                    "provider": str(provider) if provider else None,
                }
        except json.JSONDecodeError:
            pass
    return {"hash": text, "provider": None}


class StoryPipeline:
    def __init__(self, config: AppConfig) -> None:
        load_builtin_providers()
        self._config = config
        self._story_provider = story_registry.create(config.story_provider.name, **config.story_provider.options)
        image_kwargs: dict[str, object] = {}
        if config.image.provider == "openai":
            image_kwargs["openai"] = config.image.openai
        elif config.image.provider == "xai":
            image_kwargs["xai"] = config.image.xai
        self._image_provider = image_registry.create(config.image.provider, **image_kwargs)
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
        regenerate_images: list[int] | None = None,
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
            self._log_dry_run(
                spec, store, from_stage, through_stage, force, regenerate_images=regenerate_images
            )
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
        if regenerate_images and not should("illustrate"):
            logger.warning(
                "--regenerate-image is ignored because illustrate is outside the selected stage range."
            )
        if should("illustrate"):
            manifest = self._run_illustrate(
                manifest, store, force, regenerate_images=regenerate_images or []
            )
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
                "elevenlabs_speed": (
                    self._config.narration.elevenlabs.speed
                    if self._narration_provider.name == "elevenlabs"
                    else None
                ),
                "elevenlabs_model": (
                    self._config.narration.elevenlabs.model_id
                    if self._narration_provider.name == "elevenlabs"
                    else None
                ),
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

    def _run_illustrate(
        self,
        manifest: StoryManifest,
        store: ArtifactStore,
        force: bool,
        regenerate_images: list[int],
    ) -> StoryManifest:
        if self._config.image.provider == "openai":
            self._config.image.openai.resolve_api_key(required=True)
        elif self._config.image.provider == "xai":
            self._config.image.xai.resolve_api_key(required=True)

        known_indexes = {scene.index for scene in manifest.scenes}
        unknown = sorted({index for index in regenerate_images if index not in known_indexes})
        if unknown:
            valid = f"{min(known_indexes)}-{max(known_indexes)}" if known_indexes else "none"
            raise ConfigurationError(
                f"--regenerate-image scene(s) not in this story: {unknown}. Valid indexes are {valid}."
            )

        characters = manifest.character_map()
        regenerate_set = set(regenerate_images)
        width, height = self._config.image.width, self._config.image.height
        current_provider = self._image_provider.name
        model = self._image_model_name(current_provider)
        logger.info(
            "Generating %d scene images via %s provider%s (%sx%s)",
            len(manifest.scenes),
            current_provider,
            f" / {model}" if model else "",
            width,
            height,
        )
        for scene in manifest.scenes:
            prompt_path = store.scene_prompt_path(scene.index)
            if prompt_path.exists():
                disk_prompt = prompt_path.read_text(encoding="utf-8").strip()
                if disk_prompt:
                    scene.image_prompt = disk_prompt
            elif scene.image_prompt:
                store.write_text(prompt_path, scene.image_prompt)

            present = [characters[cid] for cid in scene.character_ids if cid in characters]
            output = store.scene_image_path(scene.index)
            cache_key = self._image_cache_hash(scene, present)
            stamp_path = store.work_dir / f"{scene.index:03d}.image.hash"
            force_this = force or scene.index in regenerate_set
            stamp = _parse_image_stamp(stamp_path)
            recorded_provider = self._resolve_stamp_provider(stamp, scene, present)
            hash_matches = stamp["hash"] == cache_key if stamp["hash"] else False

            if output.exists() and hash_matches and not force_this:
                logger.info(
                    "image cache hit scene=%s id=%s provider=%s size=%sx%s reused=true",
                    scene.index,
                    scene.id,
                    current_provider,
                    width,
                    height,
                )
            elif (
                output.exists()
                and not force_this
                and _image_provider_is_paid(current_provider)
                and recorded_provider not in _FREE_IMAGE_PROVIDERS
            ):
                logger.warning(
                    "image cache stale scene=%s id=%s provider=%s recorded_provider=%s — reusing "
                    "existing paid PNG to avoid accidental API spend. Pass --regenerate-image %s "
                    "(or --force) to regenerate.",
                    scene.index,
                    scene.id,
                    current_provider,
                    recorded_provider or "unknown",
                    scene.index,
                )
            else:
                if (
                    output.exists()
                    and not force_this
                    and _image_provider_is_paid(current_provider)
                    and not _image_provider_is_paid(recorded_provider)
                ):
                    logger.info(
                        "image cache replacing development placeholder scene=%s id=%s "
                        "with provider=%s",
                        scene.index,
                        scene.id,
                        current_provider,
                    )
                references = [ref for character in present for ref in character.references]
                started = time.monotonic()
                try:
                    self._image_provider.generate(
                        ImageRequest(
                            scene=scene,
                            prompt=scene.image_prompt,
                            characters=present,
                            references=references,
                            width=width,
                            height=height,
                        ),
                        output,
                    )
                except ImageGenerationError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    raise ImageGenerationError(
                        f"Image generation failed for {scene.id} (scene {scene.index:03d}): {exc}"
                    ) from exc
                if not output.exists():
                    raise ImageGenerationError(
                        f"Image provider {current_provider} did not create {output} "
                        f"for {scene.id} (scene {scene.index:03d})"
                    )
                stamp_path.write_text(
                    json.dumps({"v": 1, "hash": cache_key, "provider": current_provider}, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                logger.info(
                    "image generated scene=%s id=%s provider=%s size=%sx%s reused=false elapsed=%.1fs",
                    scene.index,
                    scene.id,
                    current_provider,
                    width,
                    height,
                    time.monotonic() - started,
                )
            scene.image_path = store.relative(output)
            scene.image_prompt_path = store.relative(prompt_path)
        manifest.image_provider = current_provider
        store.write_manifest(manifest)
        return manifest

    def _resolve_stamp_provider(
        self,
        stamp: dict[str, str | None],
        scene: Scene,
        present: list[Character],
    ) -> str | None:
        """Return the provider that produced the on-disk PNG, if it can be known.

        New stamps store ``provider`` explicitly. Legacy stamps are a bare hash:
        if that hash matches a development fingerprint, treat the PNG as a
        placeholder; otherwise treat provenance as unknown (paid-safe).
        """

        recorded = stamp.get("provider")
        if recorded:
            return recorded
        if not stamp.get("hash"):
            return None
        development_hash = self._image_cache_hash(scene, present, provider="development")
        if stamp["hash"] == development_hash:
            return "development"
        return None

    def _image_cache_hash(
        self,
        scene: Scene,
        present: list[Character],
        *,
        provider: str | None = None,
    ) -> str:
        """Fingerprint of everything that should invalidate a generated still.

        Paid providers treat a mismatch as *stale* (reuse + warn) unless the
        caller passes ``--force`` or ``--regenerate-image``. Development
        stills regenerate automatically because they are free.
        """

        openai = self._config.image.openai
        xai = self._config.image.xai
        provider_name = provider or self._image_provider.name
        references: list[dict[str, object]] = []
        for character in present:
            for ref in character.references:
                entry: dict[str, object] = {
                    "character_id": character.id,
                    "kind": ref.kind,
                    "path": str(ref.path),
                }
                if ref.path.exists() and ref.path.is_file():
                    entry["sha256"] = sha256_file(ref.path)
                else:
                    entry["sha256"] = None
                references.append(entry)
        payload: dict[str, object] = {
            "prompt": scene.image_prompt.strip(),
            "width": self._config.image.width,
            "height": self._config.image.height,
            "provider": provider_name,
            "model": openai.model if provider_name == "openai" else None,
            "quality": openai.quality if provider_name == "openai" else None,
            "references": references,
        }
        if provider_name == "xai":
            payload["model"] = xai.model
            payload["aspect_ratio"] = xai.aspect_ratio
            payload["resolution"] = xai.resolution
        return sha256_json(payload)

    def _image_model_name(self, provider_name: str) -> str | None:
        if provider_name == "openai":
            return self._config.image.openai.model
        if provider_name == "xai":
            return self._config.image.xai.model
        return None

    def _run_assemble(self, manifest: StoryManifest, store: ArtifactStore, force: bool) -> None:
        fingerprint = self._assemble_fingerprint(manifest, store)
        stamp_path = store.work_dir / "assemble.fingerprint"
        if (
            store.video_path.exists()
            and stamp_path.exists()
            and stamp_path.read_text(encoding="utf-8").strip() == fingerprint
            and not force
        ):
            logger.info("Reusing existing video %s", store.video_path)
            return
        logger.info("Assembling video with FFmpeg")
        assemble_video(manifest, store, self._config.video)
        stamp_path.write_text(fingerprint + "\n", encoding="utf-8")
        logger.info("Wrote %s", store.video_path)

    def _assemble_fingerprint(self, manifest: StoryManifest, store: ArtifactStore) -> str:
        video = self._config.video
        scenes_payload = []
        for scene in manifest.scenes:
            image = store.scene_image_path(scene.index)
            scenes_payload.append(
                {
                    "index": scene.index,
                    "image": sha256_file(image) if image.exists() else None,
                    "duration": scene.duration_seconds,
                    "motion": scene.motion,
                    "transition": scene.transition,
                }
            )
        return sha256_json(
            {
                "width": video.width,
                "height": video.height,
                "fps": video.fps,
                "encoder_preset": video.encoder_preset,
                "fade_seconds": video.fade_seconds,
                "default_motion": video.default_motion,
                "motion_filter_version": MOTION_FILTER_VERSION,
                "outro_version": OUTRO_VERSION,
                "end_hold_seconds": video.end_hold_seconds,
                "end_fade_seconds": video.end_fade_seconds,
                "end_black_seconds": video.end_black_seconds,
                "narration": sha256_file(store.narration_path) if store.narration_path.exists() else None,
                "scenes": scenes_payload,
            }
        )

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
        regenerate_images: list[int] | None = None,
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
        if regenerate_images:
            logger.info("Regenerate image scenes: %s", regenerate_images)
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
