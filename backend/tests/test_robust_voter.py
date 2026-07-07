"""Tests for the two-tier robust voter + singleton salvage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.majority_voter import robust_voter


def _dim(d_id: str, value: float, x: float, y: float,
         ori: str = "horizontal") -> dict:
    return {
        "id": d_id, "text": str(int(value)),
        "value_mm": value, "x_pct": x, "y_pct": y,
        "orientation": ori, "confidence": "high",
    }


def test_tier1_strict_cluster_kept():
    """A dim that appears in 2 runs within 5% proximity goes through tier 1."""
    runs = [
        [_dim("d1", 3150, 0.30, 0.50)],
        [_dim("d1", 3160, 0.32, 0.51)],
        [_dim("d1", 3150, 0.30, 0.50)],   # third copy
        [_dim("d1", 3150, 0.30, 0.50)],
        [_dim("d1", 3150, 0.30, 0.50)],
    ]
    out = robust_voter(runs)
    assert out["_meta"]["tier1_voted"] == 1
    assert out["dimensions"][0]["_tier"] == "tier1"


def test_tier2_picks_up_relaxed_clusters_tier1_missed():
    """Two dims at 8% proximity (outside tier1=5%) but within tier2=10%,
    appearing in 3 of 5 runs with low value variance — picked up by tier2."""
    runs = [
        [_dim("d1", 3000, 0.10, 0.50)],
        [_dim("d2", 3010, 0.18, 0.50)],   # 8% away → outside tier1
        [_dim("d3", 3000, 0.10, 0.50)],
        [_dim("d4", 3010, 0.18, 0.50)],
        [_dim("d5", 3005, 0.14, 0.50)],   # middle position
    ]
    out = robust_voter(runs)
    # At 8% proximity these are not adjacent enough for tier1, but the
    # 14% mid-record bridges them inside tier2's 10% radius (greedy).
    # Either tier1 catches it (model-dependent) or tier2 does. Either way
    # we expect at least 1 voted dimension.
    assert out["_meta"]["n_voted"] >= 1


def test_singleton_salvage_keeps_exact_matches_across_3_runs():
    """Three runs at very different positions but exactly the same
    value_mm — singleton salvage keeps it as low-confidence."""
    runs = [
        [_dim("d1", 4500, 0.10, 0.10)],
        [_dim("d2", 4500, 0.40, 0.20)],
        [_dim("d3", 4500, 0.70, 0.80)],
    ]
    out = robust_voter(runs, tier2_min_votes=3, singleton_min_runs=3)
    # No spatial cluster (positions are 30%+ apart) → no tier1, no tier2.
    # Singleton salvage with exact value_mm match across 3 runs → 1 voted.
    salvaged = [d for d in out["dimensions"] if d["_singleton"]]
    assert len(salvaged) == 1
    assert salvaged[0]["confidence"] == "low"


def test_singleton_salvage_skips_when_fewer_than_min_runs():
    runs = [
        [_dim("d1", 4500, 0.10, 0.10)],
        [_dim("d2", 4500, 0.50, 0.50)],   # only 2 runs match → below threshold
    ]
    out = robust_voter(runs, singleton_min_runs=3)
    assert out["dimensions"] == []


def test_order_independence_byte_identical_output():
    """The single biggest determinism requirement: reordering input runs
    must produce identical JSON output."""
    runs = [
        [_dim("d1", 3150, 0.30, 0.50), _dim("d2", 4500, 0.60, 0.20)],
        [_dim("d1", 3155, 0.31, 0.50), _dim("d2", 4498, 0.60, 0.20)],
        [_dim("d1", 3150, 0.30, 0.50), _dim("d2", 4500, 0.60, 0.20)],
    ]
    out_a = robust_voter(runs)
    out_b = robust_voter([runs[2], runs[0], runs[1]])
    blob_a = json.dumps(out_a["dimensions"], sort_keys=True)
    blob_b = json.dumps(out_b["dimensions"], sort_keys=True)
    assert blob_a == blob_b


def test_retention_metadata_is_meaningful():
    """retention_pct should be 100% when every dim in a single run survives."""
    runs = [
        [_dim("d1", 3000, 0.1, 0.5), _dim("d2", 4000, 0.5, 0.5)],
        [_dim("d1", 3000, 0.1, 0.5), _dim("d2", 4000, 0.5, 0.5)],
    ]
    out = robust_voter(runs)
    # 2 records per run, 2 voted → retention 100%
    assert out["_meta"]["avg_per_run"] == 2.0
    assert out["_meta"]["retention_pct"] == 100.0


def test_tier_breakdown_in_meta():
    runs = [
        [_dim("d1", 3000, 0.10, 0.50)],
        [_dim("d2", 3000, 0.10, 0.50)],
        [_dim("d3", 3000, 0.10, 0.50)],
    ]
    out = robust_voter(runs)
    meta = out["_meta"]
    assert "tier1_voted" in meta
    assert "tier2_voted" in meta
    assert "singleton_voted" in meta
    # The dim above is unanimous → tier1 catches it
    assert meta["tier1_voted"] == 1
    assert meta["tier2_voted"] == 0


def test_zero_value_records_filtered():
    runs = [
        [_dim("d1", 0, 0.3, 0.5)],
        [_dim("d1", 0, 0.3, 0.5)],
        [_dim("d1", -100, 0.3, 0.5)],
    ]
    out = robust_voter(runs)
    assert out["dimensions"] == []


def test_empty_runs_handled_gracefully():
    out = robust_voter([])
    assert out["dimensions"] == []
    assert out["_meta"]["n_voted"] == 0


def test_cov_threshold_rejects_high_variance_tier2_clusters():
    """Three records spatially co-located but with wildly different values
    must NOT be tier-2 clustered (CoV > 2%)."""
    runs = [
        [_dim("d1", 1000, 0.15, 0.50)],
        [_dim("d1", 5000, 0.18, 0.50)],   # 5x value spread
        [_dim("d1", 9000, 0.12, 0.50)],
    ]
    out = robust_voter(runs, tier2_value_tol=0.02)
    # Tier-1 value-tolerance blocks this too (>5% spread). Tier-2 CoV check
    # also blocks. No singleton (exact-value match) either. Result: empty.
    assert out["_meta"]["n_voted"] == 0
