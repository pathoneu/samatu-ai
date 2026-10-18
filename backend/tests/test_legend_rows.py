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
def _fresh_cache(tmp_path, monkeypatch):
    from extractor import cv_render_cache
    from extractor.vector_symbols import clear_glyph_cache
    monkeypatch.setattr(cv_render_cache, "CACHE_DIR", tmp_path / "cv_cache")    # rasters stay out of backend/data
    sz.clear()
    clear_glyph_cache()
    yield
    sz.clear()
    clear_glyph_cache()


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


def test_one_long_stroke_is_a_length_sample_a_double_line_is_a_symbol():
    """objektas_d's „LED juosta" (one 1,7 pt stroke) is a length; objektas_b's slot diffuser (two parallel lines)
    is a symbol to count."""
    from test_vector_symbols_2026_09_24 import GREEN, H as DH, W as DW, Draw
    d = Draw()
    d.c.setStrokeColorRGB(*GREEN)
    d.c.setLineWidth(1.7)
    d.c.line(150, DH - 661, 175, DH - 661)
    d.text(182, 664, "LED juosta")
    d.double_line(150, 673, 25, GREEN)
    d.text(182, 676, "Plyšinis difuzorius")
    path = d.c.beginPath()                                   # the same double line as ONE path object (objektas_h)
    d.c.setLineWidth(0.6)
    for off in (-1.0, 1.0):
        path.moveTo(150, DH - 685 + off)
        path.lineTo(175, DH - 685 + off)
    d.c.drawPath(path, stroke=1, fill=0)
    d.text(182, 688, "Plyšinis vienu keliu")
    rows = lr.split_legend_rows(d.pdf(), 1, [140 / DW, 650 / DH, 400 / DW, 700 / DH])["rows"]
    assert [(r["text"], r["countable"]) for r in rows] == [
        ("LED juosta", False), ("Plyšinis difuzorius", True), ("Plyšinis vienu keliu", True)]


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


# ── A2: the coloured glyph counted on every sheet ──────────────────────────

SQUARES_1 = [(0, 90.0, 260.0), (0, 140.0, 300.0), (0, 200.0, 340.0), (0, 250.0, 280.0)]
CIRCLES_1 = [(1, 100.0, 400.0), (1, 160.0, 430.0), (1, 220.0, 460.0)]
CROSSES_1 = [(2, 120.0, 520.0), (2, 230.0, 560.0)]
SQUARES_2 = [(0, 110.0, 270.0), (0, 260.0, 330.0)]
CIRCLES_2 = [(1, 120.0, 410.0)]
CROSSES_2 = [(2, 150.0, 540.0)]


def _counting_plan(*extra: Sheet) -> bytes:
    """Sheet 1: the legend and 4 squares, 3 circles, 2 crosses. Sheet 2: the legend and other instances
    (2 / 1 / 1) — another floor. Sheet 3: sheet 1 printed again (a repeat). Then `extra` sheets."""
    one = _legend_sheet(symbol_marks=SQUARES_1 + CIRCLES_1 + CROSSES_1)
    two = _legend_sheet(symbol_marks=SQUARES_2 + CIRCLES_2 + CROSSES_2)
    three = _legend_sheet(symbol_marks=SQUARES_1 + CIRCLES_1 + CROSSES_1)
    return build_plan([one, two, three, *extra])


def _rows(pdf: bytes, page: int = 1, rotation: int = 0) -> list[dict]:
    return lr.split_legend_rows(pdf, page, _turned(BOX_M, rotation))["rows"]


def _flat(boxes) -> list[float]:
    return [v for b in boxes for v in b]


def _mark_box(x: float, y: float) -> list[float]:
    return [x - 3, y - 3, x + 3, y + 3]


def test_the_coloured_row_is_counted_on_both_floors_and_the_repeat_once():
    from extractor.vector_symbols import clear_glyph_cache, count_glyph_instances
    clear_glyph_cache()
    pdf = _counting_plan()
    square = _rows(pdf)[0]
    out = count_glyph_instances(pdf, square)
    assert out["status"] == "ok" and out["defined"] and out["anchors"] == 1
    assert out["count"] == len(SQUARES_1) + len(SQUARES_2) == 6
    assert [(p["page"], p["count"], p["kartojasi"]) for p in out["per_page"]] == [(1, 4, False), (2, 2, False), (3, 4, True)]
    assert {i["page"] for i in out["instances"]} == {1, 2}              # a repeated sheet adds no marks
    want = sorted(_turned(_mark_box(x, y), 0) for _k, x, y in SQUARES_1)
    got = sorted(i["box_pct"] for i in out["instances"] if i["page"] == 1)
    assert _flat(got) == pytest.approx(_flat(want), abs=0.002)
    # the legend's square on sheets 2 and 3: inside their legend zone — and without the zones, still known as
    # the legend by the row's text beside it
    assert out["legend_copies"] == 0
    bare = count_glyph_instances(pdf, square, zones=False)
    assert bare["count"] == 6 and bare["legend_copies"] == 2


def test_the_black_rows_are_not_vector_counted_they_go_to_the_shape_search():
    from extractor.vector_symbols import count_glyph_instances_many
    pdf = _counting_plan()
    res = count_glyph_instances_many(pdf, _rows(pdf)[1:])
    assert [r["status"] for r in res] == ["nera_zenklo", "nera_zenklo"] and all(r["count"] == 0 for r in res)


def test_a_sheet_without_the_legend_is_listed_not_counted():
    from extractor.vector_symbols import count_glyph_instances
    no_legend = two_rooms()
    no_legend.symbol_marks = [(0, 100.0, 300.0), (0, 200.0, 300.0)]   # the same red square, no legend on the sheet
    pdf = _counting_plan(no_legend)
    square = _rows(pdf)[0]
    plain = count_glyph_instances(pdf, square)
    assert plain["count"] == 6 and plain["kiti"] == []
    wide = count_glyph_instances(pdf, square, other_sheets=True)
    assert wide["count"] == 6 and {i["page"] for i in wide["kiti"]} == {4} and len(wide["kiti"]) == 2
    assert {"page": 4, "count": 2, "kartojasi": False, "legenda_lape": False} in wide["per_page"]
    assert "4" in wide["detail"] and not user_text.is_banned(wide["detail"])


def test_a_legend_on_a_sheet_of_its_own_counts_the_plan_sheets():
    from extractor.vector_symbols import count_glyph_instances
    legend_only = _legend_sheet()
    plan = two_rooms()
    plan.symbol_marks = SQUARES_1
    pdf = build_plan([legend_only, plan])
    out = count_glyph_instances(pdf, _rows(pdf)[0])
    assert out["count"] == 4 and {i["page"] for i in out["instances"]} == {2}
    assert "kitame lape" in out["detail"]


def test_no_instance_inside_a_table_or_the_title_block():
    from extractor.vector_symbols import count_glyph_instances
    s = _legend_sheet(symbol_marks=SQUARES_1 + [(0, 360.0, 330.0), (0, 520.0, 800.0)])   # in the table, in the title block
    s.table_at = (330.0, 300.0)
    s.title_block = "P-01-SA.BR"
    pdf = build_plan([s])
    res = sz.read_zones(pdf, 1)
    assert sz.zone_at(res["zones"], 360.0 / W, 330.0 / H)["kind"] == "lentele"
    assert sz.zone_at(res["zones"], 520.0 / W, 800.0 / H)["kind"] == "antspaudas"
    assert count_glyph_instances(pdf, _rows(pdf)[0])["count"] == len(SQUARES_1)
    assert count_glyph_instances(pdf, _rows(pdf)[0], zones=False)["count"] == len(SQUARES_1) + 2


@pytest.mark.parametrize("rotation", [90, 270])
def test_a_turned_sheets_instances_are_in_the_display_frame(rotation):
    from extractor.vector_symbols import count_glyph_instances
    pdf = build_plan([_legend_sheet(rotate=rotation, symbol_marks=SQUARES_1)])
    out = count_glyph_instances(pdf, _rows(pdf, rotation=rotation)[0])
    assert out["count"] == len(SQUARES_1) and not out["pages_skipped"]
    want = sorted(_turned(_mark_box(x, y), rotation) for _k, x, y in SQUARES_1)
    assert _flat(sorted(i["box_pct"] for i in out["instances"])) == pytest.approx(_flat(want), abs=0.002)


def test_a_time_budget_gives_a_partial_answer_that_says_so():
    from extractor.vector_symbols import clear_glyph_cache, count_glyph_instances
    clear_glyph_cache()
    pdf = _counting_plan()
    out = count_glyph_instances(pdf, _rows(pdf)[0], time_budget_s=0.0)
    assert out["partial"] and out["pages_not_read"] and "dalis" in out["detail"]


def test_a_template_on_a_missing_sheet_or_bad_bytes_never_raises():
    from extractor.vector_symbols import count_glyph_instances
    pdf = _counting_plan()
    assert count_glyph_instances(pdf, {"page": 9, "glyph_bbox_pct": [0.1, 0.1, 0.2, 0.2]})["status"] == "no_page"
    assert count_glyph_instances(b"nope", {"page": 1, "glyph_bbox_pct": [0.1, 0.1, 0.2, 0.2]})["status"] == "failed"


# ── A2 regression: the diffusers' old entry and the generalised one agree ───

def _diffuser_drawings():
    """The corpus-shaped diffuser drawings of test_vector_symbols_2026_09_24 (objektas_h / _d / _g / _b
    shapes): (pdf, legend box in top-left points)."""
    from test_vector_symbols_2026_09_24 import BLUE, GREEN, RED, Draw, _legend, _plan_walls
    out = []
    d = Draw()                                                   # filled circles, two rows (objektas_h)
    _legend(d, [("circle", BLUE, "Ištraukimo difuzorius"), ("circle", RED, "Padavimo difuzorius")])
    _plan_walls(d)
    for x, y in ((400, 200), (700, 250), (800, 400)):
        d.circle(x, y, 3.0, BLUE)
    for x, y in ((350, 150), (450, 350), (650, 150), (750, 450)):
        d.circle(x, y, 3.0, RED)
    d.circle(550, 420, 6.0, BLUE)
    out.append((d.pdf(), (150, 650, 400, 690)))
    d = Draw()                                                   # two rings with petals on one row (objektas_d)
    d.text(965, 403, "Priglaistomi apvalus difuzoriai gipso kartono lubose")
    d.ring_with_petals(904, 400, (0, 0, 1))
    d.ring_with_petals(941, 400, (1, 0, 0))
    _plan_walls(d)
    for x, y in ((350, 200), (700, 300), (850, 450)):
        d.ring_with_petals(x, y, (0, 0, 1))
    for x, y in ((400, 400), (650, 150), (800, 200)):
        d.ring_with_petals(x, y, (1, 0, 0))
    d.circle(500, 250, 4.0, (1, 0, 0), fill=False, stroke=True)
    out.append((d.pdf(), (880, 385, 1190, 420)))
    d = Draw()                                                   # a box with arrows (objektas_g)
    _legend(d, [("box", (0, 0, 1), "Oro padavimo difuzorius"), ("box", (1, 0, 0), "Oro ištraukimo difuzorius")],
            x_symbol=1000, x_text=1040, y0=291, step=66)
    _plan_walls(d)
    for x, y in ((400, 200), (700, 250), (800, 400), (350, 450)):
        d.box_with_arrows(x, y, (0, 0, 1))
    for x, y in ((450, 350), (650, 150), (850, 200)):
        d.box_with_arrows(x, y, (1, 0, 0))
    out.append((d.pdf(), (960, 265, 1190, 380)))
    d = Draw()                                                   # a double-line slot (objektas_b)
    _legend(d, [("circle", BLUE, "Padavimo difuzorius"), ("bar", GREEN, "Priglaistomas plyšinis difuzorius")])
    _plan_walls(d)
    d.circle(400, 200, 3.0, BLUE)
    d.double_line(500, 300, 28, GREEN)
    d.double_line(650, 420, 40, GREEN)
    d.double_line(820, 150, 20, GREEN, vertical=True)
    out.append((d.pdf(), (140, 650, 400, 690)))
    d = Draw()                                                   # the same plan on two sheets (objektas_b)
    for _ in range(2):
        _legend(d, [("circle", BLUE, "Padavimo difuzorius")])
        _plan_walls(d)
        for x, y in ((400, 200), (700, 250), (800, 400)):
            d.circle(x, y, 3.0, BLUE)
        d.page()
    out.append((d.pdf(), (150, 650, 400, 690)))
    return out


@pytest.mark.parametrize("case", range(5), ids=["h_circles", "d_rings", "g_boxes", "b_slots", "b_repeat"])
def test_the_generalised_counter_agrees_with_the_diffuser_entry(case):
    from test_vector_symbols_2026_09_24 import H as DH, W as DW

    from extractor.vector_symbols import count_glyph_instances_many, count_legend_symbols
    pdf, box = _diffuser_drawings()[case]
    old = count_legend_symbols(pdf)
    rows = lr.split_legend_rows(pdf, 1, [box[0] / DW, box[1] / DH, box[2] / DW, box[3] / DH])["rows"]
    assert len(rows) == len(old["per_label"]) and all(r["glyph_kind"] == "spalvotas" for r in rows)
    new = count_glyph_instances_many(pdf, rows)
    got = {r["text"]: n["count"] for r, n in zip(rows, new)}
    want = {label: n for label, n in old["per_label"].items()}
    assert sorted(got.values()) == sorted(want.values()) and sum(got.values()) == old["count"]
    for r, n in zip(rows, new):
        assert any(label.startswith(r["text"][:12]) or r["text"].startswith(label[:12]) for label in want)
        assert n["count"] == next(v for k, v in want.items() if k.startswith(r["text"][:12]) or r["text"].startswith(k[:12]))


# ── A3: the shape search over every sheet for a black glyph ────────────────

def _padded(box_pt, pad=1.0):
    return [box_pt[0] - pad, box_pt[1] - pad, box_pt[2] + pad, box_pt[3] + pad]


def _non_source(entry):
    return [c for c in entry["candidates"] if not c["is_source"]]


def _centres(cands):
    return sorted(((c["box_pct"][0] + c["box_pct"][2]) / 2, (c["box_pct"][1] + c["box_pct"][3]) / 2) for c in cands)


def test_the_black_circle_is_found_on_every_sheet_and_the_drawing_around_it_is_not():
    from extractor.cv_match import batch_find_symbol
    pdf = _counting_plan()
    circle = _rows(pdf)[1]
    res = batch_find_symbol(pdf, 1, _padded(circle["glyph_box_pt"]))
    assert res["status"] == "ok" and not res["partial"]
    assert [e["page"] for e in res["pages"]] == [1, 2, 3]
    assert [len(_non_source(e)) for e in res["pages"]] == [len(CIRCLES_1), len(CIRCLES_2), len(CIRCLES_1)]
    assert sum(c["is_source"] for c in res["pages"][0]["candidates"]) == 1
    # twins of one symbol score alike: the floor is the best twin minus the margin, never under min_score
    assert res["score_floor"] >= res["min_score"]
    assert res["reference_score"] - res["score_floor"] == pytest.approx(res["margin"], abs=1e-4)
    want = sorted((x / W, y / H) for _k, x, y in CIRCLES_1)
    assert _flat(_centres(_non_source(res["pages"][0]))) == pytest.approx(_flat(want), abs=0.004)


def test_a_turned_sheets_shape_matches_are_in_the_display_frame():
    from extractor.cv_match import batch_find_symbol
    pdf = build_plan([_legend_sheet(rotate=90, symbol_marks=CROSSES_1)])
    cross = _rows(pdf, rotation=90)[2]
    res = batch_find_symbol(pdf, 1, _padded(cross["glyph_box_pt"]))
    want = sorted(tuple(_rotate_pct(x / W, y / H, 90)) for _k, x, y in CROSSES_1)
    assert _flat(_centres(_non_source(res["pages"][0]))) == pytest.approx(_flat(want), abs=0.004)


def test_a_raster_sheet_is_skipped_and_said(monkeypatch):
    from extractor import cv_match
    monkeypatch.setattr(cv_match, "RASTER_INK_SHARE", -1.0)          # every sheet looks like a scan
    pdf = build_plan([_legend_sheet(symbol_marks=CIRCLES_1)])
    res = cv_match.batch_find_symbol(pdf, 1, _padded(_rows(pdf)[1]["glyph_box_pt"]))
    assert [e["skipped"] for e in res["pages"]] == ["raster"] and res["pages"][0]["candidates"] == []


def test_the_time_budget_bad_boxes_and_missing_sheets():
    from extractor.cv_match import batch_find_symbol
    pdf = build_plan([_legend_sheet(symbol_marks=CIRCLES_1)])
    box = _padded(_rows(pdf)[1]["glyph_box_pt"])
    late = batch_find_symbol(pdf, 1, box, time_budget_s=0.0)
    assert late["partial"] and late["pages_not_read"] == [1] and "dalis" in late["detail"]
    assert batch_find_symbol(pdf, 4, box)["status"] == "no_page"
    assert batch_find_symbol(pdf, 1, [10, 10, 5, 5])["status"] == "bad_box"
    assert batch_find_symbol(pdf, 1, [10, 10, 400, 600])["status"] == "bad_box"
    assert batch_find_symbol(pdf, 1, [560, 20, 575, 35])["status"] == "no_ink"       # an empty corner
    assert batch_find_symbol(b"nope", 1, box)["status"] in ("no_page", "failed")
    for res in (late, batch_find_symbol(pdf, 1, [10, 10, 5, 5])):
        assert not user_text.is_banned(res["detail"])
