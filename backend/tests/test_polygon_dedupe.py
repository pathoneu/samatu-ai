"""Duplicate-fill resolution + table-column seed filtering (2026-07-12).

Covers the Beržų failure exactly: corridor-callout labels seeded IDENTICAL
polygons for rooms 103/108/109; the eksplikacija table stacks room numbers in
one vertical column that must never produce seeds.
"""
from extractor.polygon_dedupe import resolve_duplicate_fills
from extractor.room_seeds import _drop_table_columns


def _sq(x0, y0, w, h):
    return [[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]]


def _fill(poly, marker=None):
    e = {"polygon_pct": poly, "polygon_source": "auto_floodfill",
         "confidence": "ok", "area_err": 0.1}
    if marker:
        e["marker_pct"] = marker
    return e


def test_identical_fills_keep_only_area_matching_owner():
    corridor = _sq(0.45, 0.40, 0.03, 0.30)      # 0.009 pct²
    results = {
        "103": _fill(corridor, marker=[0.46, 0.5]),
        "108": _fill(corridor, marker=[0.46, 0.55]),
        "109": _fill(corridor, marker=[0.46, 0.6]),
        "102": _fill(_sq(0.1, 0.1, 0.25, 0.20)),  # unique 0.05 pct²
    }
    plotas = {"103": 9.0, "108": 12.7, "109": 12.7, "102": 50.0}
    scale = 1000.0  # m² per pct² → corridor ≈ 9 m² → belongs to 103
    results, n = resolve_duplicate_fills(results, plotas, scale)
    assert n == 2
    assert results["103"]["polygon_source"] == "auto_floodfill"
    assert results["108"]["polygon_source"] == "manual_needed"
    assert results["109"]["polygon_source"] == "manual_needed"
    # demoted rooms keep their (real, printed-label) marker
    assert results["108"]["marker_pct"] == [0.46, 0.55]
    assert "polygon_pct" not in results["108"]
    # unique fill untouched
    assert results["102"]["polygon_source"] == "auto_floodfill"


def test_no_scale_falls_back_to_engine_area_err():
    dup = _sq(0.2, 0.2, 0.1, 0.1)
    results = {
        "201": {**_fill(dup), "area_err": 0.5},
        "202": {**_fill(dup), "area_err": 0.05},
    }
    results, n = resolve_duplicate_fills(results, {"201": 0, "202": 0}, None)
    assert n == 1
    assert results["202"]["polygon_source"] == "auto_floodfill"
    assert results["201"]["polygon_source"] == "manual_needed"


def test_area_gate_demotes_grossly_wrong_unique_fill():
    results = {
        "301": _fill(_sq(0.1, 0.1, 0.02, 0.02)),   # 0.0004 pct² → 0.4 m² @ k=1000
    }
    results, n = resolve_duplicate_fills(results, {"301": 20.0}, 1000.0)
    assert n == 1
    assert results["301"]["polygon_source"] == "manual_needed"


def test_plausible_unique_fill_survives_gate():
    results = {"401": _fill(_sq(0.1, 0.1, 0.1, 0.1))}   # 0.01 → 10 m²
    results, n = resolve_duplicate_fills(results, {"401": 12.0}, 1000.0)
    assert n == 0
    assert results["401"]["polygon_source"] == "auto_floodfill"


def test_table_column_occurrences_dropped_but_plan_labels_survive():
    # Table = tight x column + text-line row pitch (~0.012), wherever it sits
    # (here x≈0.90, beyond the legacy x<0.10 filter). In-plan spots scattered.
    cands = {
        "101": [(0.90, 0.100), (0.30, 0.25)],
        "102": [(0.901, 0.112), (0.55, 0.30)],
        "103": [(0.899, 0.124), (0.42, 0.60)],
        "104": [(0.90, 0.136)],                 # table-only → no seed
    }
    out = _drop_table_columns(cands)
    assert out["101"] == [(0.30, 0.25)]
    assert out["102"] == [(0.55, 0.30)]
    assert out["103"] == [(0.42, 0.60)]
    assert out["104"] == []


def test_corridor_callout_stack_survives():
    # Real Beržų geometry: labels along one corridor share x within ~0.003 but
    # their y gaps are ≥0.031 (rooms, not table rows) — MUST keep all seeds.
    cands = {
        "106": [(0.5382, 0.334)],
        "107": [(0.5363, 0.3982)],
        "108": [(0.5353, 0.5207)],
        "109": [(0.5349, 0.5523)],
    }
    out = _drop_table_columns(cands)
    for nr in cands:
        assert out[nr], f"in-plan label {nr} wrongly dropped"


def test_two_numbers_sharing_x_is_not_a_column():
    # Only 2 distinct numbers in a tight chain — keep both.
    cands = {"105": [(0.50, 0.20)], "106": [(0.50, 0.21)]}
    out = _drop_table_columns(cands)
    assert out["105"] and out["106"]
