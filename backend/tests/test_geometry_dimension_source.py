"""The paid reading and the free re-read hand the geometry reading the SAME
dimension strings (audit 2026-09-30, geometry-lanes-2).

The paid reading used to pass the strings of its classified-page text scan,
which never reads a string written along a slanted wall; the free re-read and
the room-outline click read every page, slanted strings included. The same
drawing then got different perimeters depending on which path read it
(objektas_h room 09: 16,02 m as an outline estimate after the paid reading,
16,01 m summed from strings after the free re-read). Now one function —
`geometry_lane.geometry_dimension_strings` — is the only source on every path.
"""
from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import geometry_lane as gl  # noqa: E402
from extractor.plan_area_annotations import scan_text_layer  # noqa: E402
from extractor.plan_dimensions import read_dimension_strings  # noqa: E402
from tests.synthetic_plan import build_plan  # noqa: E402
from tests.test_slanted_dimensions import _cut_corner_room  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


def _apply_geometry_calls(rel: str) -> list[ast.Call]:
    tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "apply_geometry"]


def _parsed():
    return {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}],
            "patalpos": [{"nr": "01", "pavadinimas": "A", "plotas_m2": 11.5,
                          "plotas_saltinis": "eksplikacija", "puslapio_nr": 1, "perimetras_m": 13.6}]}


def test_the_one_source_reads_every_page_and_the_slanted_string():
    pdf = build_plan([_cut_corner_room()])
    dims = gl.geometry_dimension_strings(pdf)
    assert [d["text"] for d in dims if d.get("orientation") == "s"] == ["1414"]
    assert dims == read_dimension_strings(pdf, pages=None)
    # what the paid reading used to hand over: the same strings minus the slanted one
    old_paid = scan_text_layer(pdf, pages=None)["dimensions"]
    assert not [d for d in old_paid if d.get("orientation") == "s"]
    assert len(dims) == len(old_paid) + 1


def test_paid_and_free_paths_call_the_geometry_reading_the_same_way():
    """Neither path hands the reading strings of its own: both leave `dims`
    to the one source (the paid path's text scan is for the other lanes)."""
    for rel in ("extractor/vision_call.py", "api/free_reread.py"):
        calls = _apply_geometry_calls(rel)
        assert calls, rel
        for c in calls:
            assert len(c.args) == 2 and not c.keywords, (
                f"{rel}:{c.lineno} passes its own dimension strings to the geometry reading")
    # the room-outline click reads its strings once and reuses them — from the same source
    src = (BACKEND / "api/room_outline.py").read_text(encoding="utf-8")
    assert "geometry_dimension_strings(pdf_bytes)" in src and "read_dimension_strings" not in src


def test_both_paths_hand_the_geometry_reading_the_same_list(monkeypatch):
    pdf = build_plan([_cut_corner_room()])
    seen: list[list[dict]] = []
    real = gl.geometry_dimension_strings

    def spy(pdf_bytes):
        out = real(pdf_bytes)
        seen.append(copy.deepcopy(out))
        return out

    monkeypatch.setattr(gl, "geometry_dimension_strings", spy)
    gl.apply_geometry(_parsed(), pdf)           # the paid reading's call (vision_call Step 2.44d)
    gl.apply_geometry(_parsed(), pdf)           # the free re-read's call (api/free_reread.py)
    assert len(seen) == 2 and seen[0] == seen[1]
    assert "1414" in [d["text"] for d in seen[0] if d.get("orientation") == "s"]
