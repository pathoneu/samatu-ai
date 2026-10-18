"""Legend rows (extractor/legend_rows.py) and the generalised symbol counters (vector_symbols
`count_glyph_instances`, cv_match `batch_find_symbol`) — Pathon v3 track W2-A. Synthetic sheets only
(tests/synthetic_plan.py): the legend W1-E draws (a coloured square, a hairline circle, a black cross) and
instances of those glyphs on plan sheets. No client data, no model call."""
from __future__ import annotations

import pytest
from reportlab.lib.pagesizes import A4

from extractor import legend_rows as lr
from extractor import sheet_zones as sz
from extractor import user_text
from extractor.cv_match import _rotate_pct
from synthetic_plan import (
    LEGEND_COLUMN_DX, LEGEND_ROW_STEP, LEGEND_ROWS, LEGEND_TEXT_DX, PT_PER_M, ORIGIN, Sheet, build_plan, two_rooms,
)

W, H = A4
LEGEND_AT = (330.0, 100.0)
BOX_M = (320.0, 95.0, 460.0, 150.0)          # around the legend, mediabox points from the top-left


@pytest.fixture(autouse=True)
def _fresh_cache():
    sz.clear()
    yield
    sz.clear()


def _legend_sheet(**kw) -> Sheet:
    s = two_rooms()
    s.legend_block_at = LEGEND_AT
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _turned(box, rotation, w=W, h=H) -> list[float]:
    """A mediabox box (points, top-left) → display fractions — the viewer's turn (cv_match._rotate_pct)."""
    pts = [_rotate_pct(x / w, y / h, rotation) for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3]))]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def _glyph_drawn_at(i: int, x: float = LEGEND_AT[0]) -> list[float]:
    """Where _zone_blocks draws row i's glyph (6 × 6 pt), mediabox points from the top-left."""
    cy = LEGEND_AT[1] + 12 + i * LEGEND_ROW_STEP + 3
    return [x, cy - 3, x + 6, cy + 3]


def _all_text(res: dict) -> list[str]:
    out = [res.get("detail") or ""]
    for r in res.get("rows") or []:
        out.append(r.get("reason_lt") or "")
    return [t for t in out if t]


# ── A1: rows ────────────────────────────────────────────────────────────────

def test_three_rows_with_their_glyphs_kinds_and_texts():
    res = lr.split_legend_rows(build_plan([_legend_sheet()]), 1, _turned(BOX_M, 0))
    assert res["status"] == "ok" and res["label"] == "SUTARTINIAI ŽYMĖJIMAI" and res["side"] == "left"
    rows = res["rows"]
    assert [r["text"] for r in rows] == list(LEGEND_ROWS)
    assert [r["glyph_kind"] for r in rows] == ["spalvotas", "juodas", "juodas"]
    assert rows[0]["colour"] == "#e6331a" and rows[1]["colour"] is None
    assert all(r["countable"] and r["reason_lt"] is None and r["page"] == 1 for r in rows)
    for i, r in enumerate(rows):
        assert r["glyph_box_pt"] == pytest.approx(_glyph_drawn_at(i), abs=0.8)
        tx0 = r["text_bbox_pct"][0] * W
        assert tx0 == pytest.approx(LEGEND_AT[0] + LEGEND_TEXT_DX, abs=1.0)
    assert len({r["row_id"] for r in rows}) == 3


def test_row_ids_do_not_depend_on_the_box_drawn_around_the_legend():
    pdf = build_plan([_legend_sheet()])
    a = lr.split_legend_rows(pdf, 1, _turned(BOX_M, 0))
    b = lr.split_legend_rows(pdf, 1, _turned((300.0, 80.0, 500.0, 170.0), 0))
    assert [r["row_id"] for r in a["rows"]] == [r["row_id"] for r in b["rows"]]


def test_glyphs_in_a_column_right_of_the_text():
    res = lr.split_legend_rows(build_plan([_legend_sheet(legend_style="column")]), 1, _turned(BOX_M, 0))
    assert res["side"] == "right" and [r["text"] for r in res["rows"]] == list(LEGEND_ROWS)
    for i, r in enumerate(res["rows"]):
        assert r["glyph_box_pt"] == pytest.approx(_glyph_drawn_at(i, LEGEND_AT[0] + LEGEND_COLUMN_DX), abs=0.8)


def test_material_samples_are_rows_but_not_pieces_to_count():
    res = lr.split_legend_rows(build_plan([_legend_sheet(legend_style="swatches")]), 1, _turned(BOX_M, 0))
    assert [r["text"] for r in res["rows"]] == list(LEGEND_ROWS)
    assert all(not r["countable"] and r["reason_lt"] == lr.SAMPLE_LT for r in res["rows"])


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_a_turned_sheets_rows_land_on_the_glyphs_in_both_frames(rotation):
    """A CAD sheet drawn unrotated and turned by /Rotate: the rows are read in the frame the legend reads in,
    and given back in the DISPLAY frame (glyph_bbox_pct — the viewer's turn of where it was drawn) and in
    mediabox points (glyph_box_pt — sheet_zones.zone_to_mediabox_pt, the inverse turn)."""
    res = lr.split_legend_rows(build_plan([_legend_sheet(rotate=rotation)]), 1, _turned(BOX_M, rotation))
    assert res["rotation"] == rotation and [r["text"] for r in res["rows"]] == list(LEGEND_ROWS)
    for i, r in enumerate(res["rows"]):
        drawn = _glyph_drawn_at(i)
        assert r["glyph_box_pt"] == pytest.approx(drawn, abs=0.8)
        assert r["glyph_bbox_pct"] == pytest.approx(_turned(drawn, rotation), abs=0.002)
        Wm, Hm = W, H
        assert sz.zone_to_mediabox_pt({"bbox_pct": r["glyph_bbox_pct"]}, (Wm, Hm), rotation) == pytest.approx(drawn, abs=0.8)
    assert [r["glyph_kind"] for r in res["rows"]] == ["spalvotas", "juodas", "juodas"]


def test_the_suggested_legend_zone_gives_the_same_rows_as_a_drawn_box():
    pdf = build_plan([_legend_sheet()])
    sug = lr.suggest_legend_rows(pdf, 1)
    assert sug["status"] == "ok" and len(sug["legends"]) == 1
    leg = sug["legends"][0]
    assert leg["zone"]["kind"] == "legenda"
    drawn = lr.split_legend_rows(pdf, 1, _turned(BOX_M, 0))
    assert [r["row_id"] for r in leg["rows"]] == [r["row_id"] for r in drawn["rows"]]


def test_a_sheet_without_a_legend_zone_asks_for_a_box():
    sug = lr.suggest_legend_rows(build_plan([two_rooms()]), 1)
    assert sug["legends"] == [] and "nubrėžkite" in sug["detail"]


def test_a_heading_with_plain_text_rows_gives_no_rows_and_says_why():
    res = lr.split_legend_rows(build_plan([_legend_sheet(legend_glyphs=False)]), 1, _turned(BOX_M, 0))
    assert res["status"] == "ok" and res["rows"] == []
    assert "be ženklo" in res["detail"]


def test_a_sheet_without_a_text_layer_is_be_teksto_and_nothing_is_guessed():
    res = lr.split_legend_rows(build_plan([Sheet(title="")]), 1, [0.1, 0.1, 0.9, 0.9])
    assert res["status"] == "be_teksto" and res["rows"] == [] and res["detail"] == lr.NO_TEXT_LT


def test_an_empty_box_a_missing_page_and_bad_bytes_never_raise():
    pdf = build_plan([_legend_sheet()])
    empty = lr.split_legend_rows(pdf, 1, [0.9, 0.9, 0.95, 0.95])
    assert empty["status"] == "ok" and empty["rows"] == [] and empty["detail"]
    assert lr.split_legend_rows(pdf, 5, [0.1, 0.1, 0.9, 0.9])["status"] == "no_page"
    assert lr.split_legend_rows(b"not a pdf", 1, [0.1, 0.1, 0.9, 0.9])["status"] == "no_page"
    assert lr.split_legend_rows(pdf, 1, [0.5, 0.5, 0.4, 0.6])["rows"] == []


def test_a_symbol_character_in_front_of_the_text_is_a_text_glyph():
    s = two_rooms()

    def at(x_pt, y_pt):              # points from the top-left → the sheet's metre frame
        return (x_pt - ORIGIN[0]) / PT_PER_M, (y_pt - ORIGIN[1]) / PT_PER_M
    s.texts = [("⊗ Lubinis šviestuvas", *at(330, 300), (0, 0, 0)), ("⊗ Sieninis šviestuvas", *at(330, 312), (0, 0, 0))]
    res = lr.split_legend_rows(build_plan([s]), 1, _turned((320, 285, 460, 320), 0))
    assert [(r["glyph_kind"], r["glyph_text"], r["text"]) for r in res["rows"]] == [
        ("tekstas", "⊗", "Lubinis šviestuvas"), ("tekstas", "⊗", "Sieninis šviestuvas")]


def test_every_sentence_is_plain_lithuanian():
    pdf = build_plan([_legend_sheet(legend_style="swatches"), Sheet(title="")])
    texts = (_all_text(lr.split_legend_rows(pdf, 1, _turned(BOX_M, 0)))
             + _all_text(lr.split_legend_rows(pdf, 2, [0.1, 0.1, 0.9, 0.9]))
             + _all_text(lr.split_legend_rows(pdf, 1, [0.9, 0.9, 0.95, 0.95]))
             + [lr.PICTURE_LT, lr.NO_TEXT_LT, lr.SAMPLE_LT])
    assert texts and not [t for t in texts if user_text.is_banned(t)]
