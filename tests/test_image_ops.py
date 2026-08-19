from __future__ import annotations

from PIL import Image

from biscuit.image_ops import choose_api_size, fit_cover


def test_gpt_image_picks_documented_landscape_for_16_9() -> None:
    assert choose_api_size("gpt-image-2", 1920, 1080) == (1536, 1024)
    assert choose_api_size("gpt-image-1", 1920, 1080) == (1536, 1024)
    assert choose_api_size("gpt-image-1.5", 1280, 720) == (1536, 1024)


def test_gpt_image_picks_square_and_portrait() -> None:
    assert choose_api_size("gpt-image-2", 1080, 1080) == (1024, 1024)
    assert choose_api_size("gpt-image-2", 1080, 1920) == (1024, 1536)


def test_dalle_models_keep_their_size_enums() -> None:
    assert choose_api_size("dall-e-3", 1920, 1080) == (1792, 1024)
    assert choose_api_size("dall-e-2", 1920, 1080) == (1024, 1024)


def test_fit_cover_identity() -> None:
    src = Image.new("RGB", (1920, 1080), (12, 34, 56))
    out = fit_cover(src, 1920, 1080)
    assert out.size == (1920, 1080)
    assert out.getpixel((0, 0)) == (12, 34, 56)


def test_fit_cover_does_not_stretch() -> None:
    """A landscape API still (1536x1024) is scaled uniformly and center-cropped to 16:9."""

    src = Image.new("RGB", (1536, 1024), (200, 10, 10))
    # Wide centered stripe so LANCZOS resampling cannot wash out the midpoint.
    for x in range(700, 836):
        for y in range(1024):
            src.putpixel((x, y), (0, 255, 0))
    out = fit_cover(src, 1920, 1080)
    assert out.size == (1920, 1080)
    # Cover scale is max(1920/1536, 1080/1024) = 1.25 → 1920x1280, then crop 100px top/bottom.
    assert out.getpixel((960, 540)) == (0, 255, 0)
    assert out.getpixel((0, 540)) == (200, 10, 10)
