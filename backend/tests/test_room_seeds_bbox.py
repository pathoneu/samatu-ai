# backend/tests/test_room_seeds_bbox.py
from extractor.room_seeds import bbox_centroid_seed


def test_bbox_centroid_seed_basic():
    assert bbox_centroid_seed({"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.2}) == (0.30, 0.30)


def test_bbox_centroid_seed_none_or_bad():
    assert bbox_centroid_seed(None) is None
    assert bbox_centroid_seed({"x": 0.1, "y": 0.2}) is None          # missing w/h
    assert bbox_centroid_seed({"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}) is None  # zero-size
