"""LAB/HSV color sampling — replaces hard-coded color rules (Week 4 Task 4.3).

Algorithm (R3 + R6 research):
  1. Crop bbox from rendered page image.
  2. Drop near-white background and near-black line pixels (HSV mask).
  3. K-means in BGR space (k=3); pick dominant chromatic colour.
  4. Match against project legend by ΔE in CIELAB (perceptually uniform).

LLMs are unreliable at naming exact colours ("is this teal or cyan?"). OpenCV
gives us a reproducible RGB → LAB number we can match against the per-project
legend extracted by `legend_injection.extract_legend`.
"""
from __future__ import annotations

import cv2
import numpy as np


def _drop_neutrals(crop_bgr: np.ndarray) -> np.ndarray:
    """Return only chromatic pixels (drop near-white + near-black lines)."""
    if crop_bgr.size == 0:
        return crop_bgr
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1]
    val = hsv[..., 2]
    mask = (sat > 30) & (val > 30) & (val < 240)
    return crop_bgr[mask]


def sample_dominant_color(
    page_bgr: np.ndarray,
    bbox_xyxy: tuple[int, int, int, int],
) -> tuple[int, int, int]:
    """Return dominant RGB color inside `bbox_xyxy` of a BGR-stored image.

    Returns gray (128, 128, 128) when no chromatic pixels are present.
    """
    x0, y0, x1, y1 = bbox_xyxy
    crop = page_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return (128, 128, 128)
    pixels = _drop_neutrals(crop)
    if pixels.size == 0:
        return (128, 128, 128)
    pixels_f = pixels.astype(np.float32)
    k = min(3, len(pixels_f))
    if k < 1:
        return (128, 128, 128)
    _, _, centers = cv2.kmeans(
        pixels_f,
        K=k,
        bestLabels=None,
        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
        attempts=5,
        flags=cv2.KMEANS_RANDOM_CENTERS,
    )
    bgr = centers[0].astype(np.uint8)
    # Return RGB tuple (centers come back BGR because that's how OpenCV reads).
    return (int(bgr[2]), int(bgr[1]), int(bgr[0]))


def _rgb_to_lab(rgb: tuple[int, int, int]) -> np.ndarray:
    arr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
    lab = cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)
    return lab[0, 0].astype(np.float32)


def lab_distance(rgb_a: tuple[int, int, int], rgb_b: tuple[int, int, int]) -> float:
    """ΔE-style Euclidean distance in CIELAB."""
    return float(np.linalg.norm(_rgb_to_lab(rgb_a) - _rgb_to_lab(rgb_b)))


def classify_against_legend(
    sample_rgb: tuple[int, int, int],
    legend: list[dict],
    threshold_delta_e: float = 25.0,
) -> str | None:
    """Return the closest legend entry's `meaning` if within `threshold_delta_e`.

    Each legend entry needs `rgb` (tuple/list of 3 ints) and `meaning` (str).
    Returns None when nothing is close enough — the caller surfaces this as
    `unknown_symbol` in the response.
    """
    sample_lab = _rgb_to_lab(sample_rgb)
    best_meaning: str | None = None
    best_delta = float("inf")
    for entry in legend or []:
        rgb = entry.get("rgb")
        if not rgb or len(rgb) != 3:
            continue
        delta = float(np.linalg.norm(_rgb_to_lab(tuple(rgb)) - sample_lab))
        if delta < best_delta:
            best_delta = delta
            best_meaning = entry.get("meaning")
    if best_delta > threshold_delta_e:
        return None
    return best_meaning
