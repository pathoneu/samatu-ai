# backend/extractor/grid_overlay.py
"""Sprint 3 Section 6: grid overlay.

Stamps faint 1m × 1m gridlines onto a PDF page raster. Goal: improves
Vision's ability to visually verify scale and read off-grid dimensions.

Math: for scale 1:N at DPI D, 1m drawing = 1000/N mm paper = (1000/N)*D/25.4 px.

Gated by ENABLE_GRID_OVERLAY=1 (caller checks flag; module is pure).
"""
from PIL import Image, ImageDraw

_MM_PER_INCH = 25.4
_GRID_COLOR = (200, 215, 235)  # faint blue-grey
_GRID_OPACITY = 0.35  # blend amount


def stamp_grid(image: Image.Image, scale_ratio: float, dpi: int) -> Image.Image:
    """Return a NEW image with 1m gridlines stamped onto a copy of the source."""
    if scale_ratio <= 0 or dpi <= 0:
        return image
    px_per_meter = (1000.0 / scale_ratio) * dpi / _MM_PER_INCH
    if px_per_meter < 5:  # too tight to be useful
        return image

    out = image.copy().convert("RGB")
    overlay = Image.new("RGB", out.size, _GRID_COLOR)
    mask = Image.new("L", out.size, 0)
    draw = ImageDraw.Draw(mask)

    w, h = out.size
    # Vertical lines
    x = px_per_meter
    while x < w:
        draw.line([(int(x), 0), (int(x), h)], fill=int(255 * _GRID_OPACITY), width=1)
        x += px_per_meter
    # Horizontal lines
    y = px_per_meter
    while y < h:
        draw.line([(0, int(y)), (w, int(y))], fill=int(255 * _GRID_OPACITY), width=1)
        y += px_per_meter

    return Image.composite(overlay, out, mask)
