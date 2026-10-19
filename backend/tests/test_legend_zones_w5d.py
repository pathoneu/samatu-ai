"""Count matches outside the plan's own drawing — Pathon v3 W5-D, D2 and the follow-ups W2-B found on objektas_h.

D2 (verify): a match inside a legend, table or title-block zone is never a mark; it is LISTED (`uz_zonu`) so the
answer can say what was left out. The raster search also lists a match standing on letters of the text layer
(objektas_h p3: the sheet title „APŠVIETIMO PLANAS" scored above every real switch). Two rows of one count never
claim the same shape-search hit. Synthetic sheets only (tests/synthetic_plan.py); no client data, no model call.
"""
from __future__ import annotations

import pytest

from extractor import sheet_zones as sz
from test_legend_rows import (  # noqa: F401 — the fixture is autouse there; imported here to share it
    CIRCLES_1, CIRCLES_2, SQUARES_1, SQUARES_2, _counting_plan, _fresh_cache, _legend_sheet, _non_source, _padded, _rows,
)
from synthetic_plan import build_plan

W, H = 595.2756, 841.8898


def test_d2_a_vector_match_inside_a_legend_zone_is_listed_never_counted():
    from extractor.vector_symbols import count_glyph_instances
    pdf = _counting_plan()
    out = count_glyph_instances(pdf, _rows(pdf)[0])
    assert out["count"] == len(SQUARES_1) + len(SQUARES_2)
    # the legend's own square printed on sheets 2 and 3 stands in their legend zone: listed, not an instance
    listed = out["uz_zonu"]
    assert {(x["page"], x["zona"]) for x in listed} == {(2, "legenda"), (3, "legenda")}
    for x in listed:
        z = sz.zone_at(sz.read_zones(pdf, x["page"])["zones"], x["x_pct"], x["y_pct"])
        assert z["kind"] == "legenda"
        assert not any(abs(i["x_pct"] - x["x_pct"]) < 1e-3 and abs(i["y_pct"] - x["y_pct"]) < 1e-3
                       for i in out["instances"])
    # zones off: nothing is listed (the legend copy rule takes over)
    assert count_glyph_instances(pdf, _rows(pdf)[0], zones=False)["uz_zonu"] == []


def test_d2_letters_of_the_text_layer_find_the_title():
    from extractor.cv_match import letter_centres
    pdf = build_plan([_legend_sheet()])
    pts = letter_centres(pdf, 1)
    assert pts and all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in pts)
    # the title block's text („PLANAS M 1:100") is written near the bottom left
    assert any(y > 0.9 for _x, y in pts)
    assert letter_centres(pdf, 9) == [] and letter_centres(b"nope", 1) == []


def test_a_shape_match_on_letters_is_listed_and_never_a_mark(monkeypatch):
    from extractor import cv_match
    pdf = _counting_plan()
    circle = _rows(pdf)[1]
    plain = cv_match.batch_find_symbol(pdf, 1, _padded(circle["glyph_box_pt"]))
    first = sorted(_non_source(plain["pages"][0]), key=lambda c: c["box_pct"][0])[0]
    cx, cy = (first["box_pct"][0] + first["box_pct"][2]) / 2, (first["box_pct"][1] + first["box_pct"][3]) / 2
    # pretend the text layer writes a letter right in the middle of that circle (a title's „O")
    monkeypatch.setattr(cv_match, "letter_centres", lambda _pdf, page: [(cx, cy)] if page == 1 else [])
    res = cv_match.batch_find_symbol(pdf, 1, _padded(circle["glyph_box_pt"]))
    marks = _non_source(res["pages"][0])
    assert len(marks) == len(CIRCLES_1) - 1
    assert not any(abs((m["box_pct"][0] + m["box_pct"][2]) / 2 - cx) < 1e-3 for m in marks)
    assert any(x["zona"] == "tekstas" and abs((x["box_pct"][0] + x["box_pct"][2]) / 2 - cx) < 1e-3
               for x in res["pages"][0]["uz_zonu"])
    # the floor is calibrated as before: the hit on letters still counts as a twin of the template
    assert res["reference_score"] == pytest.approx(plain["reference_score"], abs=1e-6)
    # the other sheets are untouched
    assert len(_non_source(res["pages"][1])) == len(CIRCLES_2)


def test_a_template_that_holds_letters_is_matched_on_letters_too(monkeypatch):
    from extractor import cv_match
    pdf = _counting_plan()
    circle = _rows(pdf)[1]
    box = _padded(circle["glyph_box_pt"])
    # every circle — the legend's own one included — „has letters" (a detector glyph with „SD" inside)
    plain = cv_match.batch_find_symbol(pdf, 1, box)
    centres = [((c["box_pct"][0] + c["box_pct"][2]) / 2, (c["box_pct"][1] + c["box_pct"][3]) / 2)
               for e in plain["pages"] for c in e["candidates"]]
    monkeypatch.setattr(cv_match, "letter_centres", lambda _pdf, page: centres)
    res = cv_match.batch_find_symbol(pdf, 1, box)
    assert [len(_non_source(e)) for e in res["pages"]] == [len(_non_source(e)) for e in plain["pages"]]


def test_two_rows_never_claim_the_same_shape_hit():
    from api.legend_count import _one_symbol_one_row
    a = {"saltinis": "rastras", "count": 2, "per_page": [{"page": 3, "count": 2, "kartojasi": False, "legenda_lape": True}],
         "instances": [{"page": 3, "box_pct": [0.1, 0.1, 0.12, 0.12], "score": 0.95},
                       {"page": 3, "box_pct": [0.5, 0.5, 0.52, 0.52], "score": 0.91}]}
    b = {"saltinis": "rastras", "count": 1, "per_page": [{"page": 3, "count": 1, "kartojasi": False, "legenda_lape": True}],
         "instances": [{"page": 3, "box_pct": [0.505, 0.505, 0.525, 0.525], "score": 0.94}]}
    v = {"saltinis": "vektoriai", "count": 1, "instances": [{"page": 3, "box_pct": [0.1, 0.1, 0.12, 0.12], "score": None}]}
    answers = {0: a, 1: b, 2: v}
    _one_symbol_one_row(answers)
    assert a["count"] == 1 and a["instances"][0]["score"] == 0.95 and a["per_page"][0]["count"] == 1
    assert b["count"] == 1                     # the better resemblance keeps it
    assert v["count"] == 1                     # path counts are never touched
    # one raster row alone: nothing to compare
    solo = {0: {"saltinis": "rastras", "count": 1, "per_page": [], "instances": [{"page": 1, "box_pct": [0, 0, 0.1, 0.1], "score": 0.9}]}}
    _one_symbol_one_row(solo)
    assert solo[0]["count"] == 1



def test_d12_a_sheet_whose_only_content_zone_is_a_legend_is_a_legend_sheet():
    """The €0 type from zones (the twin of frontend sheetRail.sheetTypeFromZones). On the corpus the rule found
    two sheets, both plans whose plan zone was not found (objektas_d p4, objektas_h p8) — so the UI applies it
    only to a sheet the reading left without a type."""
    from extractor.sheet_zones import sheet_type_from_zones
    zone = lambda kind: {"kind": kind, "bbox_pct": [0, 0, 0.2, 0.2]}  # noqa: E731
    assert sheet_type_from_zones([zone("legenda"), zone("antspaudas"), zone("pastabos")]) == "legenda"
    assert sheet_type_from_zones([zone("legenda"), zone("planas")]) is None
    assert sheet_type_from_zones([zone("legenda"), zone("lentele")]) is None
    assert sheet_type_from_zones([zone("antspaudas")]) is None and sheet_type_from_zones([]) is None
    # a real synthetic sheet: a legend and the sheet title, no plan drawn
    from synthetic_plan import Sheet
    only = Sheet(walls=[], badges=[], legend_block_at=(330.0, 100.0))
    pdf = build_plan([only])
    kinds = sorted(z["kind"] for z in sz.read_zones(pdf, 1)["zones"])
    assert "legenda" in kinds and "planas" not in kinds
    assert sheet_type_from_zones(sz.read_zones(pdf, 1)["zones"]) == "legenda"
    assert sheet_type_from_zones(sz.read_zones(build_plan([_legend_sheet()]), 1)["zones"]) is None
