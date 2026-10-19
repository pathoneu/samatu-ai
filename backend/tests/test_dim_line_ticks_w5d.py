"""D8 (Pathon v3 W5-D): a dimension string's evidence line includes the stroke's caps.

Measured on the corpus (scripts/reading_completeness_report.py dimlen): span − drawn length is a CONSTANT per
drawing (objektas_h 1,44 pt median, objektas_g 1,01 pt, a / b / d 0,24 pt) — at the page's own scale objektas_h's
evidence lines read +5,6 % (strings ≤ 1 m +7,3 %), the drawn lengths ±0,0 %. Behind SAMATU_DIM_LINE_TICKS (default
off) the evidence line ends where the drawn line ends; what the perimeter adds up is never touched.
"""
from __future__ import annotations

from extractor import dimension_sum as ds


def _dim(a0, a1, ilgis, horiz=True):
    return {"page": 1, "text": "500", "value_m": 0.5, "span": [a0, a1], "line_pos": 300.0, "span_source": "line",
            "orientation": "h" if horiz else "v", "page_width": 1000.0, "page_height": 800.0, "ilgis_pt": ilgis}


def _one(dims):
    groups = ds._strings_on_base(dims, {"groups": [[1]], "transform": {}})
    return [s for g in groups.values() for s in g]


def test_flag_off_the_evidence_line_is_the_span(monkeypatch):
    monkeypatch.delenv(ds.LINE_TICKS_FLAG, raising=False)
    s = _one([_dim(100.0, 113.24, 12.24)])[0]
    assert s["line_pct"] == [[0.1, 0.375], [0.11324, 0.375]]


def test_flag_on_the_evidence_line_ends_where_the_drawn_line_ends(monkeypatch):
    monkeypatch.setenv(ds.LINE_TICKS_FLAG, "1")
    h, v = _one([_dim(100.0, 113.24, 12.24), _dim(200.0, 250.2, 49.2, horiz=False)])
    assert h["line_pct"] == [[0.1005, 0.375], [0.11274, 0.375]]
    (x0, y0), (x1, y1) = v["line_pct"]
    assert x0 == x1 == 0.3 and round((y1 - y0) * 800.0, 2) == 49.2
    # what matches strings to walls is unchanged
    assert (h["s0"], h["s1"]) == (100.0, 113.24)


def test_flag_on_leaves_a_line_without_a_drawn_length_or_with_a_strange_one(monkeypatch):
    monkeypatch.setenv(ds.LINE_TICKS_FLAG, "1")
    assert ds._drawn_ends(100.0, 113.24, None) == (100.0, 113.24)
    assert ds._drawn_ends(100.0, 113.24, 13.24) == (100.0, 113.24)       # no cap
    assert ds._drawn_ends(100.0, 113.24, 2.0) == (100.0, 113.24)         # a „cap" bigger than half the line
    assert ds._drawn_ends(113.24, 100.0, 12.24) == (112.74, 100.5)       # order kept
