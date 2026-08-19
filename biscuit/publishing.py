"""YouTube-adjacent packaging: title, description, thumbnail.

The optional uploader lives in :mod:`biscuit.youtube`. This module only
writes local artifacts and never talks to Google.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from biscuit.exceptions import ImageGenerationError
from biscuit.models import StoryManifest

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720
_EM_DASH = "\u2014"


def generate_title(manifest: StoryManifest) -> str:
    return f"{manifest.title} {_EM_DASH} A Biscuit Story"


def generate_description(manifest: StoryManifest) -> str:
    setting = manifest.setting.prompt_line() or "an unnamed place"
    names = ", ".join(character.name for character in manifest.characters)
    chapters = []
    for scene in manifest.scenes:
        start = scene.start_seconds or 0.0
        minutes = int(start // 60)
        seconds = int(start % 60)
        chapters.append(f"{minutes:02d}:{seconds:02d}  {scene.title}")
    lines = [
        f"{manifest.title}",
        "",
        f"A cinematic short story about {names}.",
        f"Set in {setting}.",
        "",
        manifest.tone.capitalize() + "." if manifest.tone else "",
        "",
        "This video was produced by Biscuit, an automated story-video pipeline.",
        "Phase 1 development stills are placeholders for a future image model;",
        "narration may be a local development voice or ElevenLabs.",
        "",
        "Chapters",
        *chapters,
        "",
        "Characters",
        *[f"- {character.name}: {character.summary or character.role}" for character in manifest.characters],
        "",
        "#Biscuit #StoryVideo #ShortFilm",
    ]
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def render_thumbnail(manifest: StoryManifest, hero_image: Path | None, output_path: Path) -> Path:
    try:
        canvas = Image.new("RGB", (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), (10, 16, 28))
        if hero_image and hero_image.exists():
            hero = Image.open(hero_image).convert("RGB")
            hero = _cover(hero, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
            canvas.paste(hero, (0, 0))
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([0, int(THUMBNAIL_HEIGHT * 0.58), THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT], fill=(8, 12, 20, 200))
        draw.rectangle([0, THUMBNAIL_HEIGHT - 14, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT], fill=(196, 48, 48, 255))
        title_font = _font(64, bold=True)
        sub_font = _font(28)
        title = manifest.title.upper()
        draw.text((48, int(THUMBNAIL_HEIGHT * 0.64)), title, font=title_font, fill=(250, 244, 230, 255))
        draw.text((48, int(THUMBNAIL_HEIGHT * 0.64) + 78), "A BISCUIT STORY", font=sub_font, fill=(220, 190, 150, 255))
        combined = canvas.convert("RGBA")
        combined = Image.alpha_composite(combined, overlay)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.convert("RGB").save(output_path, format="PNG")
    except Exception as exc:  # noqa: BLE001
        raise ImageGenerationError(f"Failed to render thumbnail: {exc}") from exc
    return output_path


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    if Path(path).exists():
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()
