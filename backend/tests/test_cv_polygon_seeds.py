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
