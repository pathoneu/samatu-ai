"""Magic wand polygon suggestion. Returns a list of (x, y) pixel
points or None when the click is on a wall / produces a degenerate
contour. Caller (cv_tools API) maps pixel → PDF coords; the wand
itself stays in image space.

Tunables: `close_kernel` controls morphological closing strength.
Larger values seal wider door gaps but risk eating into wall corners.
The frontend exposes this as a "sensitivity" slider.
"""
from __future__ import annotations

import cv2
import numpy as np


def suggest_room_polygon(
    page: np.ndarray,
    click_x: int,
    click_y: int,
    close_kernel: int = 7,
    simplify_eps: float = 0.005,
) -> list[tuple[int, int]] | None:
    if page.ndim != 2:
        raise ValueError("page must be grayscale")
    h, w = page.shape

    # Binarize: walls/lines = 0 (black), open space = 255 (white).
    binary = cv2.adaptiveThreshold(
        page, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 35, 11,
    )
    # Seal small gaps in the BLACK wall network (door openings, hatch
    # noise). MORPH_CLOSE on the original closes dark holes in white
    # regions — wrong direction for us. Invert so walls become the white
    # foreground, MORPH_CLOSE bridges gaps between wall segments, then
    # invert back so flood fill sees walls as 0 again.
    kernel = np.ones((close_kernel, close_kernel), np.uint8)
    inverted = cv2.bitwise_not(binary)
    inv_closed = cv2.morphologyEx(
        inverted, cv2.MORPH_CLOSE, kernel, iterations=1,
    )
    closed = cv2.bitwise_not(inv_closed)

    # Bounds check — guard against caller passing out-of-range coords.
    if not (0 <= click_x < w and 0 <= click_y < h):
        return None

    # If the click landed on a wall pixel (==0), bail — flood fill won't
    # produce a meaningful region.
    if closed[click_y, click_x] != 255:
        return None

    # Flood fill the white region around the click with a sentinel value.
    flood = closed.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, mask, (click_x, click_y), 128)

    room_mask = (flood == 128).astype(np.uint8) * 255
    contours, _ = cv2.findContours(
        room_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 100:
        return None

    eps = simplify_eps * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, eps, True)
    return [(int(p[0][0]), int(p[0][1])) for p in approx]
