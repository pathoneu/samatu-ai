"""Sprint 2: vision_call applies wall_adjacency only when flag is on
and bails out cleanly when polygons are missing."""
from extractor.vision_call import _apply_polygon_prepass


def test_prepass_applied_when_flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    result = {
        "page_width_m": 10.0,
        "page_height_m": 10.0,
        "patalpos": [
            {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
             "perimetras_m": 20.0},
            {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 0.5), (1.0, 0.5), (1.0, 0.0)],
             "perimetras_m": 20.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    # Shared 0.5 pct → 5m metric; half each = 2.5m off each.
    assert out["patalpos"][0]["perimetras_m"] == 17.5
    assert out["patalpos"][1]["perimetras_saltinis"] == "polygon_adjacency"


def test_prepass_skipped_when_flag_off(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "0")
    result = {
        "page_width_m": 10.0, "page_height_m": 10.0,
        "patalpos": [
            {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
             "perimetras_m": 20.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    assert out["patalpos"][0]["perimetras_m"] == 20.0
    assert "perimetras_saltinis" not in out["patalpos"][0] or \
           out["patalpos"][0].get("perimetras_saltinis") != "polygon_adjacency"


def test_prepass_bails_when_polygon_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    result = {
        "page_width_m": 10.0, "page_height_m": 10.0,
        "patalpos": [
            {"name": "A", "polygon_pct": None, "perimetras_m": 20.0},
            {"name": "B", "polygon_pct": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
             "perimetras_m": 40.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    # No room had its perimetras corrected.
    assert out["patalpos"][0]["perimetras_m"] == 20.0
    assert out["patalpos"][1]["perimetras_m"] == 40.0


def test_prepass_survives_string_polygon_coords(monkeypatch):
    """Regression: Vision occasionally returns polygon_pct entries with string
    coordinates (`"0.25"` vs `0.25`). The old code path crashed inside
    `_segment_axis` with `unsupported operand type(s) for -: 'str' and 'str'`
    and the silent except in vision_call.py swallowed it, leaving rooms with
    no perimetras correction and (more importantly) hiding the failure from
    operators."""
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    result = {
        "page_width_m": 10.0,
        "page_height_m": 10.0,
        "patalpos": [
            {"name": "A",
             "polygon_pct": [["0.0", "0.0"], ["0.0", "0.5"], ["0.5", "0.5"], ["0.5", "0.0"]],
             "perimetras_m": 20.0},
            {"name": "B",
             "polygon_pct": [["0.5", "0.0"], ["0.5", "0.5"], ["1.0", "0.5"], ["1.0", "0.0"]],
             "perimetras_m": 20.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    assert out["patalpos"][0]["perimetras_m"] == 17.5
    assert out["patalpos"][1]["perimetras_saltinis"] == "polygon_adjacency"
