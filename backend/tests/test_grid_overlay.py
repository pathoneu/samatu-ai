# backend/tests/test_grid_overlay.py
"""Sprint 3 Section 6: grid_overlay stamps faint gridlines on PDF page rasters."""
from PIL import Image
from extractor.grid_overlay import stamp_grid


def test_returns_image_same_size():
    src = Image.new("RGB", (1000, 700), color="white")
    out = stamp_grid(src, scale_ratio=50, dpi=200)
    assert out.size == src.size
    assert out.mode == "RGB"


def test_no_op_when_scale_invalid():
    src = Image.new("RGB", (500, 500), color="white")
    out_zero = stamp_grid(src, scale_ratio=0, dpi=200)
    out_negative = stamp_grid(src, scale_ratio=-50, dpi=200)
    # Returns the source image unchanged
    assert out_zero.tobytes() == src.tobytes()
    assert out_negative.tobytes() == src.tobytes()


def test_stamps_pixels_at_expected_intervals():
    """At scale=50 + dpi=200, 1m on drawing = 1000mm/50 = 20mm on paper
    = 20mm * 200dpi / 25.4mm/inch = ~157.5 px between grid lines."""
    src = Image.new("RGB", (1000, 700), color="white")
    out = stamp_grid(src, scale_ratio=50, dpi=200)
    # Pixel at (~157, 350) should be slightly grey (gridline) vs white at (10, 350)
    px_grid = out.getpixel((157, 350))
    px_blank = out.getpixel((10, 350))
    # Grid lines are faint — value should be < 255 (slightly grey)
    assert px_grid[0] < px_blank[0] or px_grid != (255, 255, 255), \
        f"Expected gridline at ~x=157, got px {px_grid} vs blank {px_blank}"
