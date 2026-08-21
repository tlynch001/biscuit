"""Build provider-agnostic image prompts from scenes + characters.

Character identity is assembled once from the character library and injected
into every scene that includes that character. Vendor-specific reference
image flags never appear here — reference files travel on
:class:`~biscuit.models.CharacterReference` instead.
"""

from __future__ import annotations

from biscuit.models import Character, Scene, StoryManifest, StorySpec


def build_image_prompt(
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
