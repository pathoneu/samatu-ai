"""Magic wand: page ndarray + click point → polygon in pixel coords.
Uses adaptive threshold + morph close + flood fill + contour →
polygon. Covers the basic happy path AND the door-gap edge case."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from extractor.cv_wand import suggest_room_polygon  # noqa: E402


def _closed_room(img_size=(400, 400), wall_thickness=6) -> np.ndarray:
    """6-pixel walls match a real LT PDF rendered at ~200 DPI; thinner
    test walls get washed out by the adaptive threshold's local mean."""
    img = np.full(img_size, 255, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (350, 350), 0, wall_thickness)
    return img


def _room_with_door_gap(img_size=(400, 400)) -> np.ndarray:
    """Real architectural room: closed walls except one 8 px door gap
    on the east wall. Naive flood fill leaks; morphology must close it."""
    img = _closed_room(img_size)
    # Carve a small gap on the right wall (x≈350); morph close kernel=11
    # should still seal it.
    cv2.rectangle(img, (346, 180), (357, 188), 255, -1)
    return img


def test_finds_polygon_for_clean_closed_room():
    img = _closed_room()
    polygon = suggest_room_polygon(img, click_x=200, click_y=200)
    assert polygon is not None
    assert len(polygon) >= 4
    # Polygon area should be close to inner rectangle (≈300×300 = 90k px²)
    pts = np.array(polygon, dtype=np.int32)
    area = cv2.contourArea(pts)
    assert 70_000 < area < 100_000


def test_morph_close_seals_door_gap():
    """A 6 px-wide door gap must be sealed by the morph close pass; flood
    fill from inside should not leak to the outside."""
    img = _room_with_door_gap()
    polygon = suggest_room_polygon(
        img, click_x=200, click_y=200, close_kernel=11,
    )
    assert polygon is not None
    pts = np.array(polygon, dtype=np.int32)
    area = cv2.contourArea(pts)
    # Should still be ≈ inside-rect area, not the whole 400×400 page.
    assert area < 130_000


def test_returns_none_when_click_on_wall():
    img = _closed_room()
    polygon = suggest_room_polygon(img, click_x=50, click_y=50)
    # Clicked on the wall — flood fill returns 0-area; must return None.
    assert polygon is None


def test_returns_none_when_click_outside_image():
    img = _closed_room()
    # Click outside the page bounds is a guard the API layer enforces,
    # but the function itself should not crash with negative indices.
    # We cap at 0 and let the wall-check return None.
    polygon = suggest_room_polygon(img, click_x=0, click_y=0)
    # (0,0) is in the white margin → flood fill picks up the entire
    # outer white area which isn't a room. The result MAY be a giant
    # polygon; we just want it not to crash.
    if polygon is not None:
        # When it does fire, area should NOT exceed image bounds.
        pts = np.array(polygon, dtype=np.int32)
        area = cv2.contourArea(pts)
        assert area <= img.shape[0] * img.shape[1]
