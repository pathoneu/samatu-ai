"""Unit tests for the majority voter (synthetic data, no Vision)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.majority_voter import (
    cluster_dimensions, vote_dimensions, VotedDimension,
)


def _dim(d_id: str, value: float, x: float, y: float,
         ori: str = "horizontal", text: str | None = None) -> dict:
    return {
        "id": d_id, "text": text or str(int(value)),
        "value_mm": value, "x_pct": x, "y_pct": y,
        "orientation": ori, "confidence": "high",
    }


def test_three_runs_unanimous_dimension_collapses_to_one_voted():
    runs = [
        [_dim("d1", 3150, 0.3, 0.5)],
        [_dim("a1", 3150, 0.3, 0.5)],
        [_dim("x9", 3150, 0.3, 0.5)],
    ]
    voted = cluster_dimensions(runs)
    assert len(voted) == 1
    assert voted[0].value_mm == 3150
    assert voted[0].vote_count == 3


def test_median_of_three_close_values():
    """Coordinate jitter + value jitter — voter takes the median."""
    runs = [
        [_dim("d1", 3150, 0.30, 0.50)],
        [_dim("d1", 3160, 0.30, 0.51)],   # close enough to cluster
        [_dim("d1", 3140, 0.31, 0.50)],
    ]
    voted = cluster_dimensions(runs)
    assert len(voted) == 1
    assert voted[0].value_mm == 3150
    assert voted[0].vote_count == 3


def test_singleton_outlier_filtered():
    """A dimension appearing in only ONE of 3 runs is dropped by the
    default min_votes=2 threshold."""
    runs = [
        [_dim("d1", 3150, 0.3, 0.5), _dim("d2", 9999, 0.7, 0.7)],
        [_dim("d1", 3150, 0.3, 0.5)],
        [_dim("d1", 3150, 0.3, 0.5)],
    ]
    voted = cluster_dimensions(runs)
    assert len(voted) == 1
    assert voted[0].value_mm == 3150


def test_different_orientations_dont_merge():
    """Two dimensions at the same point but different orientations are
    different physical features."""
    runs = [
        [_dim("d1", 3000, 0.5, 0.5, ori="horizontal"),
         _dim("d2", 4000, 0.5, 0.5, ori="vertical")],
        [_dim("d1", 3000, 0.5, 0.5, ori="horizontal"),
         _dim("d2", 4000, 0.5, 0.5, ori="vertical")],
    ]
    voted = cluster_dimensions(runs)
    assert len(voted) == 2
    values = sorted(v.value_mm for v in voted)
    assert values == [3000, 4000]


def test_far_apart_dimensions_dont_merge():
    """Dimensions outside the proximity threshold remain separate."""
    runs = [
        [_dim("d1", 3000, 0.1, 0.1)],
        [_dim("d1", 3000, 0.1, 0.1)],
        [_dim("d2", 3000, 0.9, 0.9)],
        [_dim("d2", 3000, 0.9, 0.9)],
    ]
    voted = cluster_dimensions([runs[0] + runs[2], runs[1] + runs[3]])
    # Two separate clusters, each with vote_count=2
    assert len(voted) == 2


def test_zero_or_negative_values_filtered():
    runs = [
        [_dim("d1", 0, 0.3, 0.5)],
        [_dim("d1", -100, 0.3, 0.5)],
        [_dim("d1", 0, 0.3, 0.5)],
    ]
    voted = cluster_dimensions(runs)
    assert voted == []


def test_value_tolerance_blocks_disparate_values_at_same_pixel():
    """A 3150 and 7500 dim at the same point cannot represent the same
    physical feature — they must NOT be merged into one median ~5325."""
    runs = [
        [_dim("d1", 3150, 0.5, 0.5)],
        [_dim("d1", 7500, 0.5, 0.5)],
        [_dim("d1", 3150, 0.5, 0.5)],
    ]
    voted = cluster_dimensions(runs)
    # 3150 has 2 votes (clusters), 7500 has 1 vote (filtered).
    assert len(voted) == 1
    assert voted[0].value_mm == 3150


def test_deterministic_id_assignment():
    """Voted ids should be reassigned in a stable order (d1, d2, … by
    vote_count desc then position) so byte-equality across runs holds."""
    runs = [
        [_dim("d1", 3150, 0.30, 0.50), _dim("d2", 4500, 0.60, 0.20)],
        [_dim("d1", 3150, 0.30, 0.50), _dim("d2", 4500, 0.60, 0.20)],
        [_dim("d1", 3150, 0.30, 0.50), _dim("d2", 4500, 0.60, 0.20)],
    ]
    out1 = vote_dimensions(runs)
    out2 = vote_dimensions(runs)
    assert out1 == out2  # byte-identical (after json.dumps would be too)
    ids = [d["id"] for d in out1["dimensions"]]
    assert ids == ["d1", "d2"]  # stable left-to-right assignment


def test_meta_summary_present():
    runs = [
        [_dim("d1", 3000, 0.3, 0.5)],
        [_dim("d1", 3000, 0.3, 0.5)],
    ]
    out = vote_dimensions(runs)
    assert out["_meta"]["voting_runs"] == 2
    assert out["_meta"]["n_voted"] == 1
    assert out["_meta"]["vote_count_distribution"] == {"2": 1}


def test_empty_runs_yield_empty_output():
    assert cluster_dimensions([]) == []
    assert cluster_dimensions([[], [], []]) == []
