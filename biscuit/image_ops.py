"""Deterministic image geometry helpers (no vendor APIs)."""

from __future__ import annotations

from PIL import Image

# Older GPT Image models (gpt-image-1 / 1.5 / 1-mini) use the fixed size enum.
_GPT_IMAGE_ENUM_SIZES = ((1536, 1024), (1024, 1024), (1024, 1536))
_DALLE3_SIZES = ((1792, 1024), (1024, 1024), (1024, 1792))
_DALLE2_SIZES = ((1024, 1024), (512, 512), (256, 256))

# Official Image Generation guide constraints for gpt-image-2.
_GPT_IMAGE_2_MAX_EDGE = 3840
_GPT_IMAGE_2_MIN_PIXELS = 655_360
_GPT_IMAGE_2_MAX_PIXELS = 8_294_400
_GPT_IMAGE_2_MAX_ASPECT = 3.0


def choose_api_size(model: str, width: int, height: int) -> tuple[int, int]:
    """Pick an API ``size`` appropriate for ``model`` and the output canvas.

    ``gpt-image-2`` accepts arbitrary ``WIDTHxHEIGHT`` values that satisfy the
    official constraints (multiples of 16, max edge 3840, aspect ≤ 3:1,
    655,360–8,294,400 pixels). A 1920x1080 canvas therefore requests
    1920x1088 (1080 is not a multiple of 16; ties round up so we can
    cover-crop 4px instead of padding).

    Older GPT Image models and DALL·E stay on their documented size enums.
    """

    model = (model or "").lower()
    if model.startswith("gpt-image-2"):
        return _gpt_image_2_size(width, height)
    if "dall-e-3" in model:
        return _closest_enum(width, height, _DALLE3_SIZES)
    if "dall-e-2" in model:
        return _closest_enum(width, height, _DALLE2_SIZES)
    return _closest_enum(width, height, _GPT_IMAGE_ENUM_SIZES)


def _closest_enum(width: int, height: int, allowed: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    aspect = width / max(height, 1)
    return min(allowed, key=lambda size: abs((size[0] / size[1]) - aspect))


def _multiple_of_16(value: int) -> int:
    """Round to a multiple of 16 (nearest; ties round up). Minimum 16."""

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


def _gpt_image_2_size(width: int, height: int) -> tuple[int, int]:
    width, height = _multiple_of_16(width), _multiple_of_16(height)
    return _enforce_gpt_image_2_constraints(width, height)


def _enforce_gpt_image_2_constraints(width: int, height: int) -> tuple[int, int]:
    def snap(w: float, h: float) -> tuple[int, int]:
        return max(_multiple_of_16(int(round(w))), 16), max(_multiple_of_16(int(round(h))), 16)

    longest = max(width, height)
    if longest > _GPT_IMAGE_2_MAX_EDGE:
        scale = _GPT_IMAGE_2_MAX_EDGE / longest
        width, height = snap(width * scale, height * scale)

    pixels = width * height
    if pixels > _GPT_IMAGE_2_MAX_PIXELS:
        scale = (_GPT_IMAGE_2_MAX_PIXELS / pixels) ** 0.5
        width, height = snap(width * scale, height * scale)

    pixels = width * height
    if pixels < _GPT_IMAGE_2_MIN_PIXELS:
        scale = (_GPT_IMAGE_2_MIN_PIXELS / max(pixels, 1)) ** 0.5
        width, height = snap(width * scale, height * scale)
        while width * height < _GPT_IMAGE_2_MIN_PIXELS:
            if width <= height:
                width += 16
            else:
                height += 16

    long_edge, short_edge = max(width, height), min(width, height)
    if short_edge and long_edge / short_edge > _GPT_IMAGE_2_MAX_ASPECT:
        new_long = max(_multiple_of_16(int(short_edge * _GPT_IMAGE_2_MAX_ASPECT)), 16)
        if width >= height:
            width = new_long
        else:
            height = new_long
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
