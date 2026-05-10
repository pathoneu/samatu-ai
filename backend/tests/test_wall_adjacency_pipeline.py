"""Sprint 2: vision_call applies wall_adjacency only when flag is on
and bails out cleanly when polygons are missing.

2026-05-10 (Week 1 Task 1.4): the half-subtraction mutation is gated OFF
by default. Tests that lock the LEGACY behavior must explicitly set
`ENABLE_LEGACY_HALF_SUBTRACT=1` and reload the module so the runtime flag
re-reads from env. This preserves regression coverage for the rollback
path while letting the default (correct-for-finishes) behavior win."""
import importlib
import sys
from pathlib import Path

# Make the legacy `extractor.*` import path resolvable regardless of pwd.
ROOT = Path(__file__).resolve().parents[1]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extractor.vision_call import _apply_polygon_prepass


def _reload_legacy_on():
    """Re-import wall_adjacency so the env flag re-evaluates.

    Reloads both module aliases that exist in this repo:
    `extractor.wall_adjacency` (legacy, used by vision_call) and
    `backend.extractor.wall_adjacency` (canonical-plan tests).
    """
    for modname in ("extractor.wall_adjacency", "backend.extractor.wall_adjacency"):
        if modname in sys.modules:
            importlib.reload(sys.modules[modname])


def test_prepass_applied_when_flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    monkeypatch.setenv("ENABLE_LEGACY_HALF_SUBTRACT", "1")
    _reload_legacy_on()
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
    assert out["patalpos"][1]["perimetras_saltinis"] == "polygon_adjacency_legacy"


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
    operators.

    Locks the LEGACY half-subtract path; default behaviour now leaves
    `perimetras_m` unchanged (Week 1 Task 1.4)."""
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    monkeypatch.setenv("ENABLE_LEGACY_HALF_SUBTRACT", "1")
    _reload_legacy_on()
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
    assert out["patalpos"][1]["perimetras_saltinis"] == "polygon_adjacency_legacy"
