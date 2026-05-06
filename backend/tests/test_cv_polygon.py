"""Phase C-3 (2026-05-02): click-to-fill OpenCV pipeline tests.

Synthetic images first (deterministic), real-PDF smoke at the end.
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

from extractor.cv_polygon import (
    binarize_page,
    gap_fill_doors,
    flood_fill_from_click,
    extract_polygon,
    validate_polygon,
    click_to_fill_pipeline,
    FillResult,
    PolygonValidationError,
)
from tests.conftest_cv import ASSETS_DIR, regenerate_synthetic_assets

regenerate_synthetic_assets()  # ensure assets exist before tests


def _load(name: str) -> np.ndarray:
    img = cv2.imread(str(ASSETS_DIR / name), cv2.IMREAD_GRAYSCALE)
    assert img is not None, f"asset missing: {name}"
    return img


# ── binarize_page ────────────────────────────────────────────────────────────

def test_binarize_page_walls_become_black():
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    assert binary.shape == raster.shape
    assert binary.dtype == np.uint8
    assert binary[156, 256] == 0, "wall pixel should be black after binarize"
    assert binary[256, 256] == 255, "interior pixel should be white after binarize"


def test_binarize_page_handles_uneven_lighting():
    raster = _load("synthetic_room_simple.png").copy()
    h, _ = raster.shape
    gradient = np.linspace(-40, 40, h, dtype=np.int16).reshape(-1, 1)
    raster = np.clip(raster.astype(np.int16) + gradient, 0, 255).astype(np.uint8)
    binary = binarize_page(raster)
    assert binary[256, 256] == 255
    assert binary[156, 256] == 0


# ── gap_fill_doors ───────────────────────────────────────────────────────────

def test_gap_fill_doors_bridges_door_opening():
    raster = _load("synthetic_room_with_door.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=15)
    # 8-px gap closes cleanly with 15-px kernel. Sample the gap mid-point
    # (south wall y=356, x=252 = center of the 248-256 gap).
    assert closed[356, 252] == 0, "door gap should be bridged after morph-close"


def test_gap_fill_doors_preserves_interior():
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    assert closed[256, 256] == 255, "deep interior should stay white"


def test_gap_fill_doors_kernel_too_large_consumes_room():
    # Room is 200x200; needs kernel ≥ 200 to fully consume the interior.
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=250)
    assert closed[256, 256] == 0


# ── flood_fill_from_click ────────────────────────────────────────────────────

def test_flood_fill_from_click_fills_clicked_room():
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    mask = flood_fill_from_click(closed, click_x=256, click_y=256)
    assert mask[256, 256] == 1
    assert mask[100, 100] == 0
    n_filled = int(mask.sum())
    assert 30000 < n_filled < 50000, f"expected ~38k pixels, got {n_filled}"


def test_flood_fill_from_click_outside_room_returns_empty():
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    mask = flood_fill_from_click(binary, click_x=256, click_y=156)
    assert mask.sum() == 0, "click on wall returns empty mask"


# ── extract_polygon ──────────────────────────────────────────────────────────

def test_extract_polygon_simple_square_returns_4_corners():
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    mask = flood_fill_from_click(closed, click_x=256, click_y=256)
    polygon = extract_polygon(mask, simplify_epsilon_pct=1.0)
    assert 4 <= len(polygon) <= 5, f"expected 4-5 vertices, got {len(polygon)}"
    assert polygon.shape[1] == 2
    assert polygon.dtype == np.int32


def test_extract_polygon_empty_mask_returns_empty():
    raster = _load("synthetic_room_simple.png")
    empty_mask = np.zeros(raster.shape, dtype=np.uint8)
    polygon = extract_polygon(empty_mask)
    assert polygon.shape == (0, 2)


def test_extract_polygon_simplification_removes_jagged_edges():
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    mask = flood_fill_from_click(closed, click_x=256, click_y=256)
    raw = extract_polygon(mask, simplify_epsilon_pct=0.0)
    simple = extract_polygon(mask, simplify_epsilon_pct=2.0)
    assert len(raw) > 100
    assert len(simple) <= 8


# ── validate_polygon ─────────────────────────────────────────────────────────

def test_validate_polygon_accepts_normal_room():
    polygon = np.array([[156, 156], [356, 156], [356, 356], [156, 356]], dtype=np.int32)
    validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_zero_area():
    polygon = np.array([[100, 100], [100, 100], [100, 100]], dtype=np.int32)
    with pytest.raises(PolygonValidationError, match="area"):
        validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_too_small():
    polygon = np.array([[10, 10], [20, 10], [20, 20], [10, 20]], dtype=np.int32)
    with pytest.raises(PolygonValidationError, match="too small"):
        validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_too_large():
    polygon = np.array([[5, 5], [507, 5], [507, 507], [5, 507]], dtype=np.int32)
    with pytest.raises(PolygonValidationError, match="too large"):
        validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_jagged():
    n = 60
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    radii = np.where(np.arange(n) % 2 == 0, 100, 30)
    polygon = np.column_stack([
        256 + radii * np.cos(angles),
        256 + radii * np.sin(angles),
    ]).astype(np.int32)
    with pytest.raises(PolygonValidationError, match="jagged"):
        validate_polygon(polygon, page_dims=(512, 512))


# ── click_to_fill_pipeline ───────────────────────────────────────────────────

def test_click_to_fill_pipeline_synthetic_room_simple():
    raster = _load("synthetic_room_simple.png")
    h, w = raster.shape
    result = click_to_fill_pipeline(
        raster=raster, click_x_pct=256/w, click_y_pct=256/h,
        sensitivity=0.7,
    )
    assert isinstance(result, FillResult)
    assert 4 <= len(result.polygon_px) <= 6
    xs, ys = result.polygon_px[:, 0], result.polygon_px[:, 1]
    assert 140 <= xs.min() <= 170
    assert 340 <= xs.max() <= 370
    assert 140 <= ys.min() <= 170
    assert 340 <= ys.max() <= 370
    assert result.confidence in ("high", "medium")
    assert result.fill_method == "flood_fill_v1"


def test_click_to_fill_pipeline_with_door_succeeds():
    raster = _load("synthetic_room_with_door.png")
    h, w = raster.shape
    result = click_to_fill_pipeline(
        raster=raster, click_x_pct=256/w, click_y_pct=256/h,
        sensitivity=0.7,
    )
    xs = result.polygon_px[:, 0]
    ys = result.polygon_px[:, 1]
    assert xs.max() < 380, "fill should NOT leak past the south wall via door gap"
    assert ys.max() < 380


def test_click_to_fill_pipeline_click_on_wall_raises():
    raster = _load("synthetic_room_simple.png")
    h, w = raster.shape
    with pytest.raises(PolygonValidationError):
        click_to_fill_pipeline(
            raster=raster, click_x_pct=256/w, click_y_pct=156/h,
            sensitivity=0.7,
        )
