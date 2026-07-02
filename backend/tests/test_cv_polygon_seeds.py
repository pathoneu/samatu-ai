# backend/tests/test_cv_polygon_seeds.py
import numpy as np
from extractor.cv_polygon import point_in_polygon_px


def test_point_in_polygon_inside_and_outside():
    square = np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=np.int32)
    assert point_in_polygon_px(square, 60, 60) is True
    assert point_in_polygon_px(square, 200, 200) is False


def test_point_in_polygon_on_edge_counts_as_inside():
    square = np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=np.int32)
    assert point_in_polygon_px(square, 10, 60) is True   # on the left edge


import cv2
from extractor.cv_polygon import auto_room_polygon, point_in_polygon_px
from tests.conftest_cv import ASSETS_DIR, regenerate_synthetic_assets


def _synthetic_room_raster():
    regenerate_synthetic_assets()
    return cv2.imread(str(ASSETS_DIR / "synthetic_room_with_door.png"), cv2.IMREAD_GRAYSCALE)


def test_auto_room_polygon_accepts_seeds_pct_kwarg_and_guard_holds():
    raster = _synthetic_room_raster()           # 512x512, inner room 156..356
    # seeds_pct is accepted; the returned fill contains the interior seed, so the
    # seed-inside-polygon guard did not reject the correct room.
    res = auto_room_polygon(raster, 0.5, 0.5, seeds_pct=[(0.5, 0.5)])
    assert res is not None
    h, w = raster.shape[:2]
    assert point_in_polygon_px(res.polygon_px, 0.5 * w, 0.5 * h)
