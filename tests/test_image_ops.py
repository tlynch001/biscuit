from __future__ import annotations

from PIL import Image

from biscuit.image_ops import choose_api_size, fit_cover


def test_gpt_image_2_requests_1920x1088_for_1080p() -> None:
    # 1080 is not a multiple of 16; ties round up so we cover-crop 4px.
    assert choose_api_size("gpt-image-2", 1920, 1080) == (1920, 1088)
    assert choose_api_size("gpt-image-2-2026-04-21", 1920, 1080) == (1920, 1088)


def test_gpt_image_2_size_satisfies_official_constraints() -> None:
    width, height = choose_api_size("gpt-image-2", 1920, 1080)
    assert width % 16 == 0 and height % 16 == 0
    assert max(width, height) <= 3840
    assert max(width, height) / min(width, height) <= 3
    assert 655_360 <= width * height <= 8_294_400


def test_older_gpt_image_models_keep_fixed_enum() -> None:
    assert choose_api_size("gpt-image-1", 1920, 1080) == (1536, 1024)
    assert choose_api_size("gpt-image-1.5", 1280, 720) == (1536, 1024)
    assert choose_api_size("gpt-image-1-mini", 1080, 1080) == (1024, 1024)
    assert choose_api_size("gpt-image-1", 1080, 1920) == (1024, 1536)


def test_dalle_models_keep_their_size_enums() -> None:
    assert choose_api_size("dall-e-3", 1920, 1080) == (1792, 1024)
    assert choose_api_size("dall-e-2", 1920, 1080) == (1024, 1024)


def test_gpt_image_2_clamps_oversize_and_undersize() -> None:
    wide, tall = choose_api_size("gpt-image-2", 8000, 4000)
    assert max(wide, tall) <= 3840
    assert wide % 16 == 0 and tall % 16 == 0
    small_w, small_h = choose_api_size("gpt-image-2", 64, 64)
    assert small_w * small_h >= 655_360
    assert small_w % 16 == 0 and small_h % 16 == 0


def test_fit_cover_identity() -> None:
    src = Image.new("RGB", (1920, 1080), (12, 34, 56))
    out = fit_cover(src, 1920, 1080)
    assert out.size == (1920, 1080)
    assert out.getpixel((0, 0)) == (12, 34, 56)


def test_fit_cover_api_1088_to_canvas_1080() -> None:
    src = Image.new("RGB", (1920, 1088), (40, 40, 200))
    out = fit_cover(src, 1920, 1080)
    assert out.size == (1920, 1080)
    assert out.getpixel((0, 0)) == (40, 40, 200)


def test_fit_cover_does_not_stretch() -> None:
    """A landscape API still is scaled uniformly and center-cropped to 16:9."""

    src = Image.new("RGB", (1536, 1024), (200, 10, 10))
    for x in range(700, 836):
        for y in range(1024):
            src.putpixel((x, y), (0, 255, 0))
    out = fit_cover(src, 1920, 1080)
    assert out.size == (1920, 1080)
    assert out.getpixel((960, 540)) == (0, 255, 0)
    assert out.getpixel((0, 540)) == (200, 10, 10)
