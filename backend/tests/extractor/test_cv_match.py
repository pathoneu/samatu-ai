"""Template matching: given a page ndarray + template crop, return all
candidate matches with confidence + bbox + scale + rotation. Exercises
synthetic fixtures so we don't depend on Vision."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from extractor.cv_match import find_similar_symbols  # noqa: E402


def _circle_template(size: int = 30) -> np.ndarray:
    t = np.full((size, size), 255, dtype=np.uint8)
    cv2.circle(t, (size // 2, size // 2), size // 3, 0, 2)
    return t


def _synth_page_with_repeats(template: np.ndarray, count: int = 8) -> np.ndarray:
    page = np.full((1200, 1600), 255, dtype=np.uint8)
    h, w = template.shape
    rng = np.random.default_rng(42)
    placed: list[tuple[int, int]] = []
    while len(placed) < count:
        y = int(rng.integers(50, 1200 - h - 50))
        x = int(rng.integers(50, 1600 - w - 50))
        # Avoid overlapping placements so NMS test isn't fooled.
        if any(abs(x - px) < w * 1.5 and abs(y - py) < h * 1.5
               for (px, py) in placed):
            continue
        page[y:y+h, x:x+w] = template
        placed.append((x, y))
    return page


def test_finds_all_repeats_high_confidence():
    template = _circle_template()
    page = _synth_page_with_repeats(template, count=5)
    matches = find_similar_symbols(page, template, threshold=0.85)
    high = [m for m in matches if m["confidence"] >= 0.95]
    assert len(high) == 5


def test_threshold_filters_weak_matches():
    template = _circle_template()
    page = _synth_page_with_repeats(template, count=3)
    strict = find_similar_symbols(page, template, threshold=0.99)
    loose = find_similar_symbols(page, template, threshold=0.5)
    assert len(strict) <= len(loose)


def test_nms_collapses_overlapping_candidates():
    """Without NMS the same symbol gets reported at multiple sub-pixel
    offsets. With NMS each true symbol returns one bbox."""
    template = _circle_template()
    page = _synth_page_with_repeats(template, count=4)
    matches = find_similar_symbols(page, template, threshold=0.85)

    def iou(a: dict, b: dict) -> float:
        ax1, ay1, aw, ah = a["bbox"]
        bx1, by1, bw, bh = b["bbox"]
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh
        ix = max(0, min(ax2, bx2) - max(ax1, bx1))
        iy = max(0, min(ay2, by2) - max(ay1, by1))
        inter = ix * iy
        union = aw * ah + bw * bh - inter
        return inter / union if union else 0

    for i in range(len(matches)):
        for j in range(i + 1, len(matches)):
            assert iou(matches[i], matches[j]) <= 0.3


def test_rotation_invariance_finds_rotated_copy():
    """LT plans rotate symbols 90° on different walls. The matcher
    rotates the TEMPLATE, not the page, and must find them."""
    template = _circle_template()
    page = np.full((400, 400), 255, dtype=np.uint8)
    # 0° copy
    page[100:130, 100:130] = template
    # 90° copy in a different region
    page[200:230, 200:230] = cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE)
    matches = find_similar_symbols(
        page, template, threshold=0.85, rotations=(0, 90)
    )
    assert len(matches) >= 2


def test_returns_empty_when_no_matches():
    template = _circle_template()
    blank = np.full((400, 400), 255, dtype=np.uint8)
    matches = find_similar_symbols(blank, template, threshold=0.95)
    assert matches == []
