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


@dataclass
class AutoFillResult:
    polygon_px: np.ndarray   # shape (N, 2), int32, image-space pixel coords
    confidence: str          # 'high' | 'medium' | 'low'
    area_err: float | None   # |est_m2 - plotas_m2| / plotas_m2 if area-prior used
    fill_method: str         # 'auto_floodfill_v1'


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


def point_in_polygon_px(polygon_px, x: float, y: float) -> bool:
    """True if pixel (x, y) is inside or on the polygon. Used to reject
    'wrong room' fills — the seed that produced a polygon must lie within it,
    else the flood escaped into a different space (the 'marked random places'
    bug)."""
    contour = np.asarray(polygon_px, dtype=np.int32).reshape(-1, 1, 2)
    # measureDist=False → +1 inside, 0 on edge, -1 outside
    return cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0


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


def seed_grid(cx_px: int, cy_px: int, half_w: int = 70, half_h: int = 50,
              step: int = 14) -> list[tuple[int, int]]:
    """Dense local grid of candidate seed points around a label centroid.

    Seeding the EXACT room-number centroid lands on the glyph ink every time
    ('click landed on a wall pixel') and small grids land in glyph-hole pockets.
    A dense local grid escapes both — caller keeps only white-basin pixels.
    Points are ordered nearest-first so the closest valid seed wins ties.
    """
    pts = []
    for dy in range(0, half_h + 1, step):
        for dx in range(0, half_w + 1, step):
            for sx, sy in {(cx_px + dx, cy_px + dy), (cx_px - dx, cy_px + dy),
                           (cx_px + dx, cy_px - dy), (cx_px - dx, cy_px - dy)}:
                if (sx, sy) not in pts:
                    pts.append((sx, sy))
    return pts


def auto_room_polygon(
    raster: np.ndarray,
    label_x_pct: float,
    label_y_pct: float,
    *,
    seeds_pct: list[tuple[float, float]] | None = None,
    room_plotas_m2: float | None = None,
    page_scale_m2_per_pct: float | None = None,
    sensitivities: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8),
    max_area_pct: float = 0.42,
    area_err_max: float = 0.40,
) -> AutoFillResult | None:
    """Best-effort accurate room polygon from a room-label seed.

    Multi-seed grid around (label_x_pct, label_y_pct) × a sensitivity sweep;
    each candidate is validated (with a TIGHT max_area_pct to reject leaks) and,
    when ``room_plotas_m2`` + ``page_scale_m2_per_pct`` are given, gated on an
    AREA PRIOR (|estimated m² − known m²| / known m²). The area prior both picks
    the right fill among several valid ones AND detects its own failures —
    returns None (→ caller routes the room to manual) instead of shipping a
    leaked/fragmented polygon. Returns None when no candidate survives.
    """
    if raster.ndim == 3:
        raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
    h, w = raster.shape
    centers_px: list[tuple[int, int]] = []
    for (px, py) in [(label_x_pct, label_y_pct), *(seeds_pct or [])]:
        c = (int(round(px * w)), int(round(py * h)))
        if c not in centers_px:
            centers_px.append(c)
    page_area = float(h * w)
    binary = binarize_page(raster)

    candidates: list[tuple[np.ndarray, float, float | None]] = []
    for sens in sensitivities:
        kernel, epsilon = _sensitivity_to_params(sens)
        closed = gap_fill_doors(binary, kernel_size=kernel)
        covered = np.zeros((h, w), dtype=np.uint8)  # dedup seeds already inside a found basin
        for (gcx, gcy) in centers_px:                       # NEW: iterate all centers
            for sx, sy in seed_grid(gcx, gcy):
                if not (0 <= sx < w and 0 <= sy < h):
                    continue
                if closed[sy, sx] == 0 or covered[sy, sx]:
                    continue
                mask = flood_fill_from_click(closed, sx, sy)
                if mask.sum() == 0:
                    continue
                covered |= mask
                poly = extract_polygon(mask, simplify_epsilon_pct=epsilon)
                if len(poly) < 3:
                    continue
                try:
                    validate_polygon(poly, page_dims=(h, w), max_area_pct=max_area_pct)
                except PolygonValidationError:
                    continue
                # GUARD: the fill must contain the seed that produced it, else the
                # simplified contour escaped into a different space (wrong-room fill).
                # NB: we test the producing grid seed (sx, sy) — NOT the raw label
                # centre — because on many LT plans the printed room-number label
                # lands on ink / a callout geometrically OUTSIDE the room polygon
                # (verified on Beržų 103-110), which would wrongly reject correct
                # fills. The producing seed is always in the room's white basin, so
                # this rejects only genuinely leaked/degenerate contours.
                if not point_in_polygon_px(poly, sx, sy):
                    continue
                area_px = float(cv2.contourArea(poly.reshape(-1, 1, 2).astype(np.int32)))
                area_pct = area_px / page_area
                area_err = None
                if page_scale_m2_per_pct and room_plotas_m2:
                    est_m2 = area_pct * page_scale_m2_per_pct
                    area_err = abs(est_m2 - room_plotas_m2) / room_plotas_m2
                candidates.append((poly, area_pct, area_err))

    if not candidates:
        return None

    have_prior = any(c[2] is not None for c in candidates)
    if have_prior:
        gated = [c for c in candidates if c[2] is not None and c[2] <= area_err_max]
        if not gated:
            return None  # every fill disagrees with the known area → manual
        poly, _area_pct, ae = min(gated, key=lambda c: c[2])
        conf = "high" if ae < 0.10 else ("medium" if ae < 0.25 else "low")
        return AutoFillResult(poly, conf, ae, "auto_floodfill_v1")
    # No area prior: pick the largest valid fill (already gated < max_area_pct,
    # so it cannot be a leak; largest avoids glyph-hole micro-pockets).
    poly, _area_pct, _ = max(candidates, key=lambda c: c[1])
    return AutoFillResult(poly, "medium", None, "auto_floodfill_v1")


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
