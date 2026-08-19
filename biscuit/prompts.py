"""Build provider-agnostic image prompts from scenes + characters.

Character identity is assembled once from the character library and injected
into every scene that includes that character. Vendor-specific reference
image flags never appear here.
"""

from __future__ import annotations

from biscuit.models import Character, Scene, StoryManifest, StorySpec


_NEGATIVE = (
    "no text, no captions, no subtitles, no watermark, no logo, "
    "no extra limbs, no deformed faces"
)


def build_image_prompt(
    scene: Scene,
    *,
    characters: dict[str, Character],
    spec: StorySpec | StoryManifest,
) -> str:
    present = [characters[cid] for cid in scene.character_ids if cid in characters]
    style = spec.visual_style.prompt_preamble()
    setting = spec.setting.prompt_line()
    lines = [
        style,
        f"Setting: {setting}" if setting else "",
        f"Tone: {spec.tone}" if spec.tone else "",
        f"Emotional intent: {scene.emotion}" if scene.emotion else "",
        scene.visual_description.strip(),
    ]
    if present:
        lines.append("Characters in frame (keep identity consistent across scenes):")
        for character in present:
            lines.append(f"- {character.consistency_block()}")
            if character.references:
                kinds = ", ".join(ref.kind for ref in character.references)
                lines.append(
                    f"  Reference images available for {character.name} ({kinds}); "
                    "use them if the image provider supports character references."
                )
    avoid = getattr(spec, "constraints", None)
    avoid_list = avoid.avoid if avoid is not None else []
    if avoid_list:
        lines.append("Avoid: " + "; ".join(avoid_list))
    lines.append(_NEGATIVE)
    return "\n".join(line for line in lines if line).strip()


def apply_prompts(manifest: StoryManifest, spec: StorySpec) -> StoryManifest:
    characters = manifest.character_map()
    for scene in manifest.scenes:
        scene.image_prompt = build_image_prompt(scene, characters=characters, spec=spec)
    return manifest
