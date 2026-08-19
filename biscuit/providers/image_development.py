"""Development image provider: cinematic placeholder stills.

These images are real PNGs FFmpeg can assemble. They also persist the
*actual* image prompt a future paid API would receive, so prompts can be
reviewed without spending credits.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from biscuit.exceptions import ImageGenerationError
from biscuit.providers.base import ImageProvider, ImageRequest
from biscuit.providers.registry import image_registry

# emotion keyword -> (night, mid, accent)
_PALETTES: list[tuple[tuple[str, ...], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = [
    (("wonder", "quiet", "opening"), (11, 28, 44), (58, 90, 128), (232, 213, 181)),
    (("unease", "wrong", "still"), (10, 14, 20), (40, 52, 64), (140, 150, 160)),
    (("concern", "shock", "figure"), (18, 16, 32), (48, 62, 90), (201, 168, 124)),
    (("tenderness", "approach", "gentle"), (20, 24, 40), (70, 86, 110), (220, 196, 160)),
    (("recognition", "pin", "memory"), (16, 22, 30), (62, 74, 58), (198, 176, 112)),
    (("urgency", "alarm", "bark"), (28, 18, 22), (90, 48, 48), (220, 180, 140)),
    (("determination", "run", "help"), (18, 24, 48), (52, 72, 120), (240, 220, 190)),
    (("hope", "door", "warm"), (24, 20, 28), (120, 78, 48), (255, 214, 160)),
    (("rescue", "discovery"), (22, 26, 40), (80, 70, 70), (236, 210, 170)),
    (("community", "hands"), (16, 20, 32), (64, 72, 88), (210, 190, 160)),
    (("peak", "look", "love"), (12, 16, 28), (48, 56, 80), (250, 230, 190)),
    (("catharsis", "aftermath", "inside"), (20, 22, 36), (90, 86, 78), (232, 208, 168)),
    (("resolve", "closing", "home"), (8, 14, 24), (40, 58, 84), (186, 206, 220)),
]


def _hex_palette(emotion: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    lowered = emotion.lower()
    for keys, night, mid, accent in _PALETTES:
        if any(key in lowered for key in keys):
            return night, mid, accent
    return (11, 21, 32), (46, 74, 98), (212, 196, 168)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


@image_registry.register("development")
class DevelopmentImageProvider(ImageProvider):
    def generate(self, request: ImageRequest, output_path: Path) -> Path:
        try:
            image = render_placeholder(request)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, format="PNG")
        except Exception as exc:  # noqa: BLE001
            raise ImageGenerationError(f"Failed to render development image: {exc}") from exc
        return output_path


def render_placeholder(request: ImageRequest, *, include_copy: bool = True) -> Image.Image:
    width, height = request.width, request.height
    night, mid, accent = _hex_palette(request.scene.emotion)
    rng = random.Random(_seed_for(request))

    img = Image.new("RGB", (width, height), night)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / max(height - 1, 1)
        # Night sky into snow-lit ground, with a warm pool near the lower third.
        if t < 0.62:
            mix = t / 0.62
            color = _lerp(night, mid, mix)
        else:
            mix = (t - 0.62) / 0.38
            color = _lerp(mid, accent, mix * 0.35)
        draw.line([(0, y), (width, y)], fill=color)

    _draw_courthouse(draw, width, height, accent, night, rng)
    _draw_snow(draw, width, height, rng)
    _draw_figures(draw, width, height, request, accent, night)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    img = _vignette(img)
    img = _grain(img, rng)
    if include_copy:
        _draw_copy(img, request)
    return img


def _seed_for(request: ImageRequest) -> int:
    if request.seed is not None:
        return request.seed
    material = f"{request.scene.id}:{request.scene.title}:{request.prompt[:80]}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:8], 16)


def _lerp(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _draw_courthouse(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    accent: tuple[int, int, int],
    night: tuple[int, int, int],
    rng: random.Random,
) -> None:
    base_y = int(height * 0.62)
    building_w = int(width * 0.42)
    building_h = int(height * 0.32)
    x0 = int(width * 0.29)
    y0 = base_y - building_h
    stone = _lerp(night, accent, 0.18)
    draw.rectangle([x0, y0 + int(building_h * 0.22), x0 + building_w, base_y], fill=stone)
    pediment = [
        (x0 - 12, y0 + int(building_h * 0.22)),
        (x0 + building_w // 2, y0),
        (x0 + building_w + 12, y0 + int(building_h * 0.22)),
    ]
    draw.polygon(pediment, fill=_lerp(night, accent, 0.28))
    columns = 6
    col_w = max(8, building_w // 28)
    inner = building_w * 0.12
    for i in range(columns):
        cx = x0 + inner + i * ((building_w - inner * 2) / max(columns - 1, 1))
        draw.rectangle([cx, y0 + int(building_h * 0.24), cx + col_w, base_y - 8], fill=_lerp(accent, night, 0.55))
    # Warm windows
    window = (255, 196, 110)
    for i in range(4):
        wx = x0 + int(building_w * 0.18) + i * int(building_w * 0.18)
        wy = y0 + int(building_h * 0.46)
        draw.rectangle([wx, wy, wx + 22, wy + 36], fill=window)
    # Ground drift
    draw.ellipse([int(width * -0.05), int(height * 0.68), int(width * 1.05), int(height * 1.15)], fill=_lerp(accent, (240, 244, 248), 0.55))


def _draw_snow(draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
    for _ in range(420):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        r = rng.choice((1, 1, 1, 2, 2, 3))
        alpha_white = 180 + rng.randint(0, 75)
        color = (alpha_white, alpha_white, min(255, alpha_white + 8))
        draw.ellipse([x, y, x + r, y + r], fill=color)


def _draw_figures(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    request: ImageRequest,
    accent: tuple[int, int, int],
    night: tuple[int, int, int],
) -> None:
    ids = set(request.scene.character_ids)
    ground = int(height * 0.78)
    if "veteran" in ids:
        # Wheelchair silhouette
        cx, cy = int(width * 0.38), ground
        draw.ellipse([cx - 28, cy - 28, cx + 6, cy + 10], outline=_lerp(night, (20, 20, 20), 0.8), width=6)
        draw.ellipse([cx + 10, cy - 22, cx + 36, cy + 8], outline=_lerp(night, (20, 20, 20), 0.8), width=5)
        draw.rectangle([cx - 8, cy - 70, cx + 18, cy - 20], fill=_lerp(night, (40, 36, 28), 0.3))
        draw.ellipse([cx - 6, cy - 96, cx + 22, cy - 68], fill=_lerp(accent, (80, 70, 60), 0.15))
    if "biscuit" in ids:
        bx = int(width * 0.52) if "veteran" in ids else int(width * 0.48)
        by = ground + 6
        body = (196, 150, 82)
        draw.ellipse([bx, by - 38, bx + 70, by + 8], fill=body)
        draw.polygon([(bx + 58, by - 32), (bx + 86, by - 18), (bx + 62, by - 8)], fill=body)
        draw.ellipse([bx + 52, by - 52, bx + 78, by - 26], fill=body)
        draw.polygon([(bx + 54, by - 50), (bx + 50, by - 68), (bx + 62, by - 48)], fill=(140, 86, 48))
        draw.polygon([(bx + 70, by - 50), (bx + 82, by - 66), (bx + 78, by - 46)], fill=(140, 86, 48))
        # red bandana
        draw.polygon([(bx + 56, by - 30), (bx + 74, by - 28), (bx + 64, by - 12)], fill=(168, 36, 36))
    if "clerk" in ids:
        cx, cy = int(width * 0.62), ground - 10
        draw.rectangle([cx, cy - 90, cx + 28, cy], fill=(72, 70, 78))
        draw.ellipse([cx + 2, cy - 118, cx + 26, cy - 88], fill=(210, 186, 160))


def _vignette(img: Image.Image) -> Image.Image:
    width, height = img.size
    overlay = Image.new("RGB", img.size, (0, 0, 0))
    mask = Image.new("L", img.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([-width * 0.1, -height * 0.2, width * 1.1, height * 1.2], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=min(width, height) * 0.12))
    # invert so edges are dark
    inverted = Image.eval(mask, lambda p: 255 - p)
    return Image.composite(overlay, img, inverted)


def _grain(img: Image.Image, rng: random.Random) -> Image.Image:
    width, height = img.size
    grain = Image.new("L", (width, height), 0)
    pixels = grain.load()
    for _ in range((width * height) // 40):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        pixels[x, y] = rng.randint(0, 40)
    grain = grain.filter(ImageFilter.GaussianBlur(radius=0.4))
    return Image.composite(img, Image.new("RGB", img.size, (20, 20, 20)), grain)


def _draw_copy(img: Image.Image, request: ImageRequest) -> None:
    draw = ImageDraw.Draw(img)
    width, height = img.size
    title_font = _font(max(28, height // 22), bold=True)
    body_font = _font(max(18, height // 38))
    small_font = _font(max(16, height // 48))
    margin = int(width * 0.06)
    title = request.scene.title.upper()
    draw.text((margin, int(height * 0.08)), f"{request.scene.index:02d}  /  {title}", font=title_font, fill=(245, 240, 230))
    names = ", ".join(character.name for character in request.characters) or "empty frame"
    draw.text((margin, int(height * 0.08) + 48), names, font=small_font, fill=(210, 200, 180))
    caption = _wrap(draw, request.scene.visual_description[:280], body_font, int(width * 0.55))
    draw.multiline_text((margin, int(height * 0.82)), caption, font=body_font, fill=(236, 230, 214), spacing=6)
