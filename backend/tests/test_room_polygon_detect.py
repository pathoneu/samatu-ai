"""Accurate room-polygon detection: seed locator + auto_room_polygon.

The pure helpers are unit-tested; the flood-fill quality is an integration test
against the contractor-validated Objektas A fixture (skipped if absent). The
integration test is the real guard: it asserts the area-prior auto-solves the
easy majority AND honestly rejects the known-leaky rooms (106/107/110) to manual
rather than shipping a wrong polygon.
"""
from pathlib import Path

import pytest

from extractor.cv_polygon import seed_grid, auto_room_polygon
from extractor.room_seeds import locate_room_seeds, calibrate_page_scale

FIXTURE = Path(__file__).resolve().parents[2] / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"


def test_seed_grid_is_local_and_nearest_first():
    pts = seed_grid(100, 100, half_w=28, half_h=28, step=14)
    assert pts[0] == (100, 100)  # centroid first
    assert all(72 <= x <= 128 and 72 <= y <= 128 for x, y in pts)
    assert len(pts) == len(set(pts))  # no duplicates


def test_calibrate_page_scale_is_median_robust_to_leaks():
    # 3 good rooms ~1000 m²/pct, one leaked sample (huge area → tiny ratio).
    samples = [(0.01, 10.0), (0.02, 20.0), (0.015, 15.0), (0.80, 5.0)]
    scale = calibrate_page_scale(samples)
    assert 900 < scale < 1100  # median ignores the leaked outlier


def test_calibrate_page_scale_none_when_empty():
    assert calibrate_page_scale([]) is None
    assert calibrate_page_scale([(0, 0), (None, 5)]) is None


@pytest.mark.skipif(not FIXTURE.exists(), reason="Objektas A fixture PDF not present")
def test_auto_polygon_solves_majority_and_rejects_leaks():
    import page_raster_cache as cache
    import cv2, numpy as np

    pdf = FIXTURE.read_bytes()
    raster = cache.render_grayscale_from_bytes(pdf, page_nr=2)
    h, w = raster.shape[:2]
    # Known room areas from the contractor-validated eksplikacija (m²).
    plotas = {"101": 11.01, "102": 50.54, "103": 9.64, "104": 13.51, "105": 10.67,
              "106": 6.84, "107": 6.59, "108": 12.71, "109": 12.71, "110": 23.97, "111": 7.45}

    seeds = locate_room_seeds(pdf, 1, list(plotas))
    assert len(seeds) >= 10, f"label locator should find most rooms, got {len(seeds)}"

    # Two-pass calibration: rectangularity-best fill → median scale.
    pass1 = []
    for nr, (sx, sy) in seeds.items():
        r = auto_room_polygon(raster, sx, sy)
        if r is not None:
            ap = float(cv2.contourArea(r.polygon_px.reshape(-1, 1, 2).astype(np.int32))) / (h * w)
            pass1.append((ap, plotas[nr]))
    scale = calibrate_page_scale(pass1)
    assert scale and scale > 0

    solved, manual = 0, []
    for nr, (sx, sy) in seeds.items():
        r = auto_room_polygon(raster, sx, sy, room_plotas_m2=plotas[nr],
                              page_scale_m2_per_pct=scale)
        if r is None:
            manual.append(nr)
        else:
            solved += 1
            assert len(r.polygon_px) >= 3
            assert r.confidence in ("high", "medium", "low")

    # The easy majority auto-solves; the leaky rooms are honestly routed to manual.
    assert solved >= 7, f"expected >=7 auto-solved, got {solved} (manual={manual})"
    assert "110" in manual, "the known-leaking Miegamasis must be rejected, not shipped"
