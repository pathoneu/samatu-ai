"""Week 1 Task 1.4 — verify shared-wall half-subtraction is OFF by default.

Plan reasoning: each room's polygon describes its own inner contour, so two
adjacent rooms' polygons are physically distinct lines (offset by wall
thickness in real life, often coincident in flattened raster PDFs). Using
A.perim + B.perim is the correct linear footage for finishes (paint,
baseboard, plaster corners) — both sides of the wall are finished.

The legacy half-subtraction was wrong for finishes. It is now gated behind
ENABLE_LEGACY_HALF_SUBTRACT=1 for one-week rollback safety.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import extractor.wall_adjacency as wa  # noqa: E402


def _square(x, y, size):
    return [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]


def test_default_off_does_not_mutate_perimetras_m(monkeypatch):
    monkeypatch.delenv("ENABLE_LEGACY_HALF_SUBTRACT", raising=False)
    importlib.reload(wa)

    rooms = [
        {"id": "A", "perimetras_m": 14.0, "polygon_pct": _square(0.0, 0.0, 0.5)},
        {"id": "B", "perimetras_m": 14.0, "polygon_pct": _square(0.5, 0.0, 0.5)},
    ]
    out = wa.apply_shared_edges(rooms, page_width_m=8.0, page_height_m=4.0)
    assert out[0]["perimetras_m"] == 14.0
    assert out[1]["perimetras_m"] == 14.0
    # Audit info still surfaces the shared length:
    assert out[0]["shared_with_neighbors_m"] > 0
    assert out[0]["shared_edges_provenance"] == "polygon_adjacency_audit"


def test_legacy_flag_restores_old_subtraction(monkeypatch):
    monkeypatch.setenv("ENABLE_LEGACY_HALF_SUBTRACT", "1")
    importlib.reload(wa)

    rooms = [
        {"id": "A", "perimetras_m": 14.0, "polygon_pct": _square(0.0, 0.0, 0.5)},
        {"id": "B", "perimetras_m": 14.0, "polygon_pct": _square(0.5, 0.0, 0.5)},
    ]
    out = wa.apply_shared_edges(rooms, page_width_m=8.0, page_height_m=4.0)
    # Half of the shared edge subtracted from each room's perim
    assert out[0]["perimetras_m"] < 14.0
    assert out[1]["perimetras_m"] < 14.0
    assert out[0]["perimetras_orig_m"] == 14.0
    assert out[0]["perimetras_saltinis"] == "polygon_adjacency_legacy"


def test_no_polygon_no_op(monkeypatch):
    monkeypatch.delenv("ENABLE_LEGACY_HALF_SUBTRACT", raising=False)
    importlib.reload(wa)

    rooms = [
        {"id": "A", "perimetras_m": 14.0},
        {"id": "B", "perimetras_m": 14.0, "polygon_pct": _square(0.5, 0.0, 0.5)},
    ]
    out = wa.apply_shared_edges(rooms, page_width_m=8.0, page_height_m=4.0)
    assert out[0]["perimetras_m"] == 14.0
    assert out[1]["perimetras_m"] == 14.0
    # No mutation, no audit fields
    assert "shared_with_neighbors_m" not in out[0]
    assert "shared_with_neighbors_m" not in out[1]
