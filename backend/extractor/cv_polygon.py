"""cv_polygon — Phase C-3 click-to-fill OpenCV pipeline.

Bluebeam Dynamic Fill recipe:
  raster → binarize (adaptive threshold) → gap_fill_doors (morph close)
        → flood_fill_from_click → extract_polygon (contour + simplify)
        → validate_polygon (area + shape sanity) → polygon_pdf coords

All functions are pure; LRU caching of inputs lives in page_raster_cache.py.

Coordinate convention:
  - Internal: numpy arrays in (row, col) = (y, x) image-space pixels
  - External (API): {x_pct, y_pct} normalized 0-1 fractions of page
  - Output polygon: PDF point space (caller multiplies by page_pt / page_px)
"""

from __future__ import annotations
from dataclasses import dataclass
import cv2
import numpy as np


class PolygonValidationError(ValueError):
    """Raised when the extracted polygon fails sanity checks."""


@dataclass
class FillResult:
    polygon_px: np.ndarray  # shape (N, 2), int32, image-space pixel coords
    confidence: str          # 'high' | 'medium' | 'low'
    fill_method: str         # 'flood_fill_v1'


def binarize_page(raster: np.ndarray) -> np.ndarray:
    """Adaptive threshold to separate walls (black) from interior (white).

    Adaptive (per-region) threshold tolerates uneven lighting in scanned PDFs.
    Block size 41 is a sweet spot for 300 DPI floor plans — small enough to
    capture local wall density, large enough to avoid noise inside rooms.
    """
    if raster.ndim == 3:
        raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        raster,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=41,
        C=10,
    )
    return binary


def gap_fill_doors(binary: np.ndarray, kernel_size: int = 15) -> np.ndarray:
    """Morphological close: dilate then erode.

    Bridges small gaps in walls (door openings drawn as wall breaks) so a
    flood-fill from the room interior doesn't leak into corridors.

    binary: uint8, 255 = empty, 0 = wall.
    kernel_size: pixels. Should be ≥ widest door opening at the current DPI.
                 At 300 DPI a typical 800mm door spans ~95 px — but doors are
                 usually drawn schematically as 20-40 px gaps. Default 15 px
                 bridges most door symbols without consuming wall material.

    Note: morph operations work on white foreground; we INVERT first so walls
    (currently black) become foreground for closing, then invert back.
    """
    inverted = cv2.bitwise_not(binary)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    closed_inv = cv2.morphologyEx(inverted, cv2.MORPH_CLOSE, kernel)
    return cv2.bitwise_not(closed_inv)


def flood_fill_from_click(binary: np.ndarray, click_x: int, click_y: int) -> np.ndarray:
    """Flood-fill the connected white region containing the click point.

    Returns a binary mask: 1 inside the filled region, 0 elsewhere. If the
    click lands on a wall pixel, returns an all-zeros mask (nothing to fill).

    cv2.floodFill needs a mask 2 pixels larger than the source on each axis
    (per OpenCV docs); we strip the border before returning.
    """
    if binary[click_y, click_x] == 0:
        return np.zeros_like(binary, dtype=np.uint8)
    h, w = binary.shape
    src = binary.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(
        src, flood_mask, seedPoint=(click_x, click_y),
        newVal=128, loDiff=0, upDiff=0,
        flags=4,
    )
    return (src == 128).astype(np.uint8)


def extract_polygon(mask: np.ndarray, simplify_epsilon_pct: float = 1.0) -> np.ndarray:
    """Find external contour of the mask + Douglas-Peucker simplify.

    mask: uint8, 1 inside the region, 0 elsewhere.
    simplify_epsilon_pct: tolerance as % of the contour's bounding diagonal.
                          1.0% = good for rectangular rooms (4-6 vertices).
                          0.0 = no simplification (raw contour pixel count).
    Returns: int32 array shape (N, 2). Empty (0, 2) if no contour found.
    """
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE,
    )
    if not contours:
        return np.zeros((0, 2), dtype=np.int32)
    contour = max(contours, key=cv2.contourArea)
    if simplify_epsilon_pct > 0:
        x, y, w, h = cv2.boundingRect(contour)
        diag = float(np.hypot(w, h))
        epsilon = diag * simplify_epsilon_pct / 100.0
        contour = cv2.approxPolyDP(contour, epsilon, closed=True)
    return contour.reshape(-1, 2).astype(np.int32)


def validate_polygon(
    polygon: np.ndarray,
    page_dims: tuple[int, int],
    min_area_pct: float = 0.0005,
    max_area_pct: float = 0.80,
    max_jagged_ratio: float = 8.0,
) -> None:
    """Sanity-check the extracted polygon. Raises PolygonValidationError on failure.

    page_dims: (height, width) in pixels.
    min_area_pct: reject if area < this fraction of page area (noise).
    max_area_pct: reject if area > this fraction (flood leaked outside room).
    max_jagged_ratio: reject if perimeter / sqrt(area) > this (too crinkly).
    """
    if len(polygon) < 3:
        raise PolygonValidationError("polygon has fewer than 3 vertices (degenerate)")
    contour = polygon.reshape(-1, 1, 2).astype(np.int32)
    area = cv2.contourArea(contour)
    if area <= 0:
        raise PolygonValidationError("polygon has zero area (degenerate)")
    h, w = page_dims
    page_area = float(h * w)
    if area / page_area < min_area_pct:
        raise PolygonValidationError(
            f"polygon too small ({area:.0f} px², "
            f"{area/page_area*100:.3f}% of page; min {min_area_pct*100:.2f}%)"
        )
    if area / page_area > max_area_pct:
        raise PolygonValidationError(
            f"polygon too large ({area/page_area*100:.0f}% of page; "
            "fill likely leaked outside the room)"
        )
    perimeter = cv2.arcLength(contour, closed=True)
    jagged = perimeter / np.sqrt(area)
    if jagged > max_jagged_ratio:
        raise PolygonValidationError(
            f"polygon too jagged (perimeter/√area={jagged:.1f}, "
            f"max {max_jagged_ratio}; likely noise or partial fill)"
        )


def _sensitivity_to_params(sensitivity: float) -> tuple[int, float]:
    """Sensitivity → (kernel_size, simplify_epsilon_pct).

    0.0 = aggressive bridging (large kernel), high simplification
    1.0 = strict (small kernel, finer polygon)
    """
    sensitivity = max(0.0, min(1.0, sensitivity))
    kernel = max(3, int(round(25 - 22 * sensitivity)))
    epsilon = 0.5 + 1.5 * (1.0 - sensitivity)
    return kernel, epsilon


def click_to_fill_pipeline(
    raster: np.ndarray,
    click_x_pct: float,
    click_y_pct: float,
    sensitivity: float = 0.7,
) -> FillResult:
    """End-to-end click-to-fill. Raises PolygonValidationError on failure.

    raster: grayscale or BGR image of the page.
    click_x_pct, click_y_pct: normalized 0-1 fractions of page width/height.
    sensitivity: 0.0 (loose, more bridging) ↔ 1.0 (strict, fine polygon).

    Returns FillResult with polygon in image-space pixels (int32).
    Caller maps to PDF point space via `pdf_x = pixel_x * pdf_w / image_w`.
    """
    if raster.ndim == 3:
        raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
    h, w = raster.shape
    click_x = int(round(click_x_pct * w))
    click_y = int(round(click_y_pct * h))
    if not (0 <= click_x < w and 0 <= click_y < h):
        raise PolygonValidationError(
            f"click ({click_x_pct:.3f}, {click_y_pct:.3f}) outside page bounds"
        )

    kernel_size, epsilon_pct = _sensitivity_to_params(sensitivity)

    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=kernel_size)
    mask = flood_fill_from_click(closed, click_x=click_x, click_y=click_y)
    if mask.sum() == 0:
        raise PolygonValidationError(
            "click landed on a wall pixel — try clicking deeper inside the room"
        )
    polygon = extract_polygon(mask, simplify_epsilon_pct=epsilon_pct)
    if len(polygon) == 0:
        raise PolygonValidationError("no contour found in flood-filled mask")
    validate_polygon(polygon, page_dims=(h, w))

    bbox_area = float(
        (polygon[:, 0].max() - polygon[:, 0].min()) *
        (polygon[:, 1].max() - polygon[:, 1].min())
    )
    poly_area = float(cv2.contourArea(polygon.reshape(-1, 1, 2).astype(np.int32)))
    rectangularity = poly_area / bbox_area if bbox_area > 0 else 0
    if 4 <= len(polygon) <= 6 and rectangularity > 0.85:
        confidence = "high"
    elif rectangularity > 0.65:
        confidence = "medium"
    else:
        confidence = "low"

    return FillResult(
        polygon_px=polygon, confidence=confidence, fill_method="flood_fill_v1",
    )
