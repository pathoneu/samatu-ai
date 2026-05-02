"""Detector / DetectionResult / BBox shape contracts."""

import pytest
from detector_bench.core.types import (
    BBox, DetectionResult, Detector,
)


def test_bbox_normalized_constructible():
    b = BBox(x_pct=0.1, y_pct=0.2, w_pct=0.3, h_pct=0.4)
    assert b.x_pct == 0.1
    assert b.y_pct == 0.2
    assert b.w_pct == 0.3
    assert b.h_pct == 0.4


def test_bbox_rejects_out_of_range():
    with pytest.raises(ValueError):
        BBox(x_pct=-0.1, y_pct=0.2, w_pct=0.3, h_pct=0.4)
    with pytest.raises(ValueError):
        BBox(x_pct=0.1, y_pct=0.2, w_pct=1.5, h_pct=0.4)  # w > 1.0


def test_detection_result_count_matches_bbox_len():
    bboxes = [BBox(0.1, 0.1, 0.05, 0.05), BBox(0.5, 0.5, 0.05, 0.05)]
    r = DetectionResult(
        count=2, bboxes=bboxes, runtime_s=1.5, cost_usd=0.0,
        errors=[], notes="ok",
    )
    assert r.count == len(r.bboxes) == 2


def test_detection_result_count_can_exceed_bboxes_when_pipeline_only_counts():
    # Some pipelines (text-driven) return a count without precise bboxes.
    r = DetectionResult(
        count=5, bboxes=[], runtime_s=0.1, cost_usd=0.0,
        errors=[], notes="text-only count",
    )
    assert r.count == 5
    assert r.bboxes == []


def test_detector_abc_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Detector()  # ABC; subclasses must implement setup + detect
