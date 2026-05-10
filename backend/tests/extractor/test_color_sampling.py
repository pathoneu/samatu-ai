"""Week 4 Task 4.3 — OpenCV color sampling tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.extractor.color_sampling import (  # noqa: E402
    sample_dominant_color,
    classify_against_legend,
    lab_distance,
)


def test_dominant_color_picks_red_ignoring_white_background():
    img = np.full((100, 100, 3), 255, dtype=np.uint8)  # all white
    img[40:60, 40:60] = (0, 0, 200)  # red square in BGR
    rgb = sample_dominant_color(img, (30, 30, 70, 70))
    # After kmeans + neutral-drop, the chromatic cluster center should be
    # close to red.
    assert rgb[0] > 150  # R channel
    assert rgb[1] < 50   # G
    assert rgb[2] < 50   # B


def test_classify_against_legend_uses_lab_distance():
    legend = [
        {"meaning": "led_strip", "rgb": (230, 30, 30)},
        {"meaning": "ceiling_light", "rgb": (255, 230, 60)},
    ]
    sample = (220, 40, 40)  # close to led_strip
    match = classify_against_legend(sample, legend)
    assert match == "led_strip"


def test_classify_returns_none_when_too_far():
    legend = [{"meaning": "led_strip", "rgb": (230, 30, 30)}]
    sample = (50, 200, 50)  # green, very different
    match = classify_against_legend(sample, legend, threshold_delta_e=25.0)
    assert match is None


def test_lab_distance_zero_for_same_color():
    assert lab_distance((255, 0, 0), (255, 0, 0)) == 0.0


def test_lab_distance_positive_for_different_colors():
    assert lab_distance((255, 0, 0), (0, 255, 0)) > 0


def test_classify_skips_legend_entries_without_rgb():
    legend = [
        {"meaning": "no_rgb_entry"},  # no rgb — skipped
        {"meaning": "led_strip", "rgb": (230, 30, 30)},
    ]
    match = classify_against_legend((220, 40, 40), legend)
    assert match == "led_strip"


def test_empty_image_returns_neutral_gray():
    img = np.zeros((0, 0, 3), dtype=np.uint8)
    rgb = sample_dominant_color(img, (0, 0, 0, 0))
    assert rgb == (128, 128, 128)
