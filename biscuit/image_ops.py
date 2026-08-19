"""Deterministic image geometry helpers (no vendor APIs)."""

from __future__ import annotations

from PIL import Image


def even16(value: int) -> int:
    """Round ``value`` to a multiple of 16 (nearest; ties round up). Minimum 16.

    Ties round up so a 1920x1080 canvas maps to 1920x1088, which can be
    cover-cropped by 4px instead of padded.
    """

    if value <= 16:
        return 16
    remainder = value % 16
    if remainder == 0:
        return value
    down = value - remainder
    up = down + 16
    if remainder >= 8:
        return up
    return down


def choose_api_size(model: str, width: int, height: int) -> tuple[int, int]:
    """Pick a provider size that is as close as possible to the canvas.

    ``gpt-image-2`` accepts arbitrary sizes within documented constraints,
    including 1920x1080. Older GPT Image models only accept a short list.
    """

    model = (model or "").lower()
    if model.startswith("gpt-image-2"):
        width16, height16 = even16(width), even16(height)
        width16, height16 = _clamp_gpt_image_2(width16, height16)
        return width16, height16

    allowed = ((1536, 1024), (1024, 1024), (1024, 1536))
    if "dall-e-3" in model or model == "dall-e-3":
        allowed = ((1792, 1024), (1024, 1024), (1024, 1792))
    aspect = width / max(height, 1)
    return min(allowed, key=lambda size: abs((size[0] / size[1]) - aspect))


def _clamp_gpt_image_2(width: int, height: int) -> tuple[int, int]:
    """Enforce gpt-image-2 size constraints without changing aspect much."""

    width, height = even16(width), even16(height)
    max_edge = 3840
    min_pixels = 655_360
    max_pixels = 8_294_400
    if max(width, height) > max_edge:
        scale = max_edge / max(width, height)
        width, height = even16(int(width * scale)), even16(int(height * scale))
    pixels = width * height
    if pixels > max_pixels:
        scale = (max_pixels / pixels) ** 0.5
        width, height = even16(int(width * scale)), even16(int(height * scale))
    if pixels < min_pixels:
        scale = (min_pixels / max(pixels, 1)) ** 0.5
        width, height = even16(int(width * scale) + 16), even16(int(height * scale) + 16)
    if max(width, height) / max(min(width, height), 1) > 3:
        if width > height:
            width = even16(height * 3)
        else:
            height = even16(width * 3)
    return width, height


def fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale uniformly and center-crop to ``width`` x ``height``. Never stretch."""

    rgb = image.convert("RGB")
    if rgb.size == (width, height):
        return rgb
    src_w, src_h = rgb.size
    scale = max(width / src_w, height / src_h)
    new_w = max(int(round(src_w * scale)), width)
    new_h = max(int(round(src_h * scale)), height)
    resized = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max((resized.width - width) // 2, 0)
    top = max((resized.height - height) // 2, 0)
    return resized.crop((left, top, left + width, top + height))
