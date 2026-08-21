"""Build provider-agnostic image prompts from scenes + characters.

Character identity is assembled once from the character library and injected
into every scene that includes that character. Vendor-specific reference
image flags never appear here — reference files travel on
:class:`~biscuit.models.CharacterReference` instead.

Directed cinematic shots use a local frame prompt. The director may know the
whole story; the image generator should only be told what belongs in this
photograph.
"""

from __future__ import annotations

from biscuit.models import Character, Scene, StoryManifest, StorySpec


def build_image_prompt(
    scene: Scene,
    *,
    characters: dict[str, Character],
    spec: StorySpec | StoryManifest,
) -> str:
    if scene.local_prompt.strip():
        return _build_local_shot_prompt(scene, characters=characters, spec=spec)
    return _build_legacy_prompt(scene, characters=characters, spec=spec)


def _in_frame_identity(character: Character) -> str:
    """Appearance only. Summaries can name locations that do not belong in this frame."""

    phrases = character.appearance_phrases()
    anchors = list(character.visual_anchors)
    parts = [f"{character.name} ({character.id}): {character.species}"]
    if phrases:
        parts.append("Appearance: " + "; ".join(phrases))
    if anchors:
        parts.append("Must remain consistent: " + "; ".join(anchors))
    return ". ".join(parts) + "."


def _build_local_shot_prompt(
    scene: Scene,
    *,
    characters: dict[str, Character],
    spec: StorySpec | StoryManifest,
) -> str:
    present = [characters[cid] for cid in scene.character_ids if cid in characters]
    camera = getattr(spec.visual_style, "camera", "") or "16:9 landscape cinematic still"
    medium = getattr(spec.visual_style, "medium", "") or "cinematic still photograph"
    extra = getattr(spec.visual_style, "extra", "") or ""

    sections = [scene.local_prompt.strip()]
    meta = [
        f"Visual style: {medium}" + (f"; {extra}" if extra else ""),
        f"Shot: 16:9 landscape cinematic still, {camera}. Photoreal film still, not illustration.",
    ]
    if spec.tone:
        meta.append(f"Tone: {spec.tone}")
    if scene.emotion:
        meta.append(f"Emotional intent: {scene.emotion}")
    sections.append("\n".join(meta))

    if present:
        char_lines = ["Subjects in this frame — keep identity identical whenever they reappear:"]
        for character in present:
            char_lines.append(f"- {_in_frame_identity(character)}")
        sections.append("\n".join(char_lines))

    if scene.entity_identity:
        sections.append(
            "Persistent identity of visible things in this photograph — the same objects, not new ones:\n"
            + "\n".join(f"- {line}" for line in scene.entity_identity)
        )

    avoid = getattr(spec, "constraints", None)
    avoid_list = avoid.avoid if avoid is not None else []
    if avoid_list:
        sections.append("Avoid: " + "; ".join(avoid_list))

    sections.append(
        "No text, captions, subtitles, watermark, logo, title card, or signage. "
        "Fill a 16:9 frame."
    )
    return "\n\n".join(section for section in sections if section).strip()


def _build_legacy_prompt(
    scene: Scene,
    *,
    characters: dict[str, Character],
    spec: StorySpec | StoryManifest,
) -> str:
    present = [characters[cid] for cid in scene.character_ids if cid in characters]
    style = spec.visual_style.prompt_preamble()
    setting = spec.setting.prompt_line()
    camera = getattr(spec.visual_style, "camera", "") or "intimate 16:9 cinematic framing"

    sections: list[str] = []
    visual = scene.visual_description.strip()
    if visual:
        sections.append(visual)

    meta_lines = []
    if setting:
        meta_lines.append(f"Setting: {setting}")
    if style:
        meta_lines.append(f"Visual style: {style}")
    if spec.tone:
        meta_lines.append(f"Tone: {spec.tone}")
    if scene.emotion:
        meta_lines.append(f"Emotional intent: {scene.emotion}")
    meta_lines.append(f"Shot: 16:9 landscape cinematic still, {camera}. Photoreal film still, not illustration.")
    sections.append("\n".join(meta_lines))

    if present:
        char_lines = [
            "Characters in this frame — keep identity identical in every scene of this film:"
        ]
        for character in present:
            char_lines.append(f"- {character.consistency_block()}")
        sections.append("\n".join(char_lines))
        sections.append(
            "Continuity: same characters, same approximate size and build, same coat or wardrobe, "
            "same markings and face. Do not invent extra animals, people, or props that change identity."
        )

    if scene.world_facts:
        sections.append(
            "World continuity (do not contradict; treat as hard constraints):\n"
            + "\n".join(f"- {fact}" for fact in scene.world_facts)
        )

    avoid = getattr(spec, "constraints", None)
    avoid_list = avoid.avoid if avoid is not None else []
    if avoid_list:
        sections.append("Avoid: " + "; ".join(avoid_list))

    sections.append(
        "No text, captions, subtitles, watermark, logo, title card, or signage. "
        "Fill a 16:9 frame."
    )
    return "\n\n".join(section for section in sections if section).strip()


def apply_prompts(manifest: StoryManifest, spec: StorySpec) -> StoryManifest:
    characters = manifest.character_map()
    for scene in manifest.scenes:
        scene.image_prompt = build_image_prompt(scene, characters=characters, spec=spec)
    return manifest
