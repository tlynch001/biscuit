"""Deterministic image geometry helpers (no vendor APIs)."""

from __future__ import annotations

from PIL import Image

# Official Images API size enum for GPT Image models (CreateImageRequest /
# CreateImageEditRequest). ``auto`` is omitted so cover-cropping stays deterministic.
_GPT_IMAGE_SIZES = ((1536, 1024), (1024, 1024), (1024, 1536))
_DALLE3_SIZES = ((1792, 1024), (1024, 1024), (1024, 1792))
_DALLE2_SIZES = ((1024, 1024), (512, 512), (256, 256))


def choose_api_size(model: str, width: int, height: int) -> tuple[int, int]:
    """Pick the documented Images API size closest to the canvas aspect ratio.

    GPT Image models, including ``gpt-image-2``, are requested with the
    official size enum: ``1024x1024``, ``1536x1024``, ``1024x1536``. A 16:9
    Biscuit canvas (1920x1080) therefore requests landscape ``1536x1024``.
    The returned still is then cover-cropped locally to the configured canvas.
    """

    model = (model or "").lower()
    if "dall-e-3" in model:
        allowed = _DALLE3_SIZES
    elif "dall-e-2" in model:
        allowed = _DALLE2_SIZES
    else:
        allowed = _GPT_IMAGE_SIZES
    aspect = width / max(height, 1)
    return min(allowed, key=lambda size: abs((size[0] / size[1]) - aspect))


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
