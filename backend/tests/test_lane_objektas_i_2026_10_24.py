"""The four rules that made the geometry lane read objektas_i (2026-10-24), each on a synthetic drawing.

The contractor's drawing read 0 of 17 rooms cold (docs/superpowers/research/2026-10-24-cold-run-contractor-uploads.md):
its room badges are 6,6 pt tall (the cap was 6,5 pt; another project's are 11 pt), its outer walls are a second
fill colour, its two units repeat their room numbers on one sheet and in two stacked tables, and its door swings
are dashed arcs whose ends touch a dashed threshold. Every drawing here is invented.
"""
from __future__ import annotations

import io
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from extractor import drawn_openings as do  # noqa: E402
from extractor import room_locator as rl  # noqa: E402
from extractor import vector_rooms as vr  # noqa: E402
from tests.synthetic_plan import LT_FONT, PT_PER_M, Sheet, _pt, two_rooms  # noqa: E402

W, H = A4


def _dims(c, font: float, n: int = 8, x0: float = 80, y0: float = 700) -> None:
    """n dimension strings in one font — the sheet's yardstick."""
    c.setFont("Helvetica", font)
    for i in range(n):
        c.drawString(x0 + (i % 4) * 110, y0 - (i // 4) * 60, "4200")


def _measured(pdf: bytes, text: str) -> float:
    """The height the shared character reader gives a word (the frame the rule measures in)."""
    from extractor.plan_area_annotations import _iter_pages, _words
    for _pn, _W, _H, chars, _td in _iter_pages(pdf, {1}):
        for w in _words(chars):
            if w["text"] == text:
                return w["bottom"] - w["top"]
    raise AssertionError(text)


# ── 1. badge height relative to the sheet's dimension strings ────────────────

def test_the_cap_follows_the_dimension_strings_with_a_ceiling_and_a_fallback():
    assert rl.badge_height_cap([6.55] * 20) >= 6.6 * 1.5          # objektas_i: badges 6,6 pt over 6,55 pt strings
    assert rl.badge_height_cap([6.62] * 20) >= 11.0               # objektas_j2: badges 11 pt over 6,62 pt strings
    assert rl.badge_height_cap([2.91] * 20) < 6.5                 # objektas_h: tighter than the old fixed cap
    assert rl.badge_height_cap([9.0] * 20) == rl.BADGE_CEILING_PT  # never a sheet title
    assert rl.badge_height_cap([6.0] * 3) == rl.BADGE_MAX_H_PT     # too few strings to measure against


def _badge_sheet(dim_font: float, badges: list[tuple[str, float, float, float]], dims: bool = True) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 7)
    c.drawString(60, 30, "PERTVARU PLANAS M 1:75")
    if dims:
        _dims(c, dim_font)
    for text, x, y, font in badges:
        c.setFont("Helvetica", font)
        c.drawString(x, y, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_badges_as_tall_as_the_strings_and_much_taller_are_found_and_a_title_is_not():
    """objektas_i writes its badges as tall as its dimension strings (6,6 pt, one over the old 6,5 pt cap);
    objektas_j2 writes them 1,7 times taller (11 pt). Both are badges. A number three times the strings'
    height is a sheet title, not a room."""
    pdf = _badge_sheet(6.0, [("3", 150, 400, 6.0), ("4", 300, 400, 10.0), ("5", 450, 400, 20.0)])
    assert 6.5 < _measured(pdf, "3") < 7.0                         # objektas_i's 6,6 pt — over the old fixed cap
    assert 10.5 < _measured(pdf, "4") < 11.5                       # objektas_j2's 11 pt
    rooms = [{"nr": "3", "plotas_m2": 10.0}, {"nr": "4", "plotas_m2": 10.0}, {"nr": "5", "plotas_m2": 10.0}]
    where = rl.locate_rooms(pdf, rooms, plan_pages=[1])
    assert where["3"]["saltinis"] == "zenkliukas" and where["4"]["saltinis"] == "zenkliukas"
    assert "5" not in where


def test_a_sheet_without_dimension_strings_keeps_the_old_fixed_cap():
    pdf = _badge_sheet(0, [("3", 150, 400, 6.0), ("4", 300, 400, 4.0)], dims=False)
    where = rl.locate_rooms(pdf, [{"nr": "3", "plotas_m2": 9.0}, {"nr": "4", "plotas_m2": 9.0}], plan_pages=[1])
    assert "3" not in where and where["4"]["saltinis"] == "zenkliukas"


# ── 2. the wall solid from every colour that closes rings with the walls ─────

def _two_colour_plan(extra=()) -> bytes:
    """two_rooms() with its bottom wall drawn in a darker grey (objektas_i: outer walls 0,39, partitions 0,58),
    plus whatever `extra` fills are asked for: (x0, y0, x1, y1 metres, grey)."""
    sheet = two_rooms()
    t = 0.2
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for x0, y0, x1, y1 in sheet.walls:
        grey = 0.39 if y0 >= 3 + t - 1e-9 else 0.58
        c.setFillGray(grey)
        ax, ay = _pt(x0, y0, sheet)
        bx, by = _pt(x1, y1, sheet)
        c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=0, fill=1)
    for x0, y0, x1, y1, grey in extra:
        c.setFillGray(grey)
        ax, ay = _pt(x0, y0, sheet)
        bx, by = _pt(x1, y1, sheet)
        c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=0, fill=1)
    c.setFillGray(0)
    c.setFont(LT_FONT, 7)
    c.drawString(60, 30, "PLANAS M 1:100")
    c.showPage()
    c.save()
    return buf.getvalue()


def _at(x_m: float, y_m: float) -> dict:
    return {"page": 1, "cx": (60 + x_m * PT_PER_M) / W, "cy": (80 + y_m * PT_PER_M) / H, "saltinis": "zenkliukas"}


def test_a_second_wall_colour_that_closes_the_rooms_joins_the_solid():
    out = vr.trace_vector_rooms(_two_colour_plan(), 1, {"01": _at(2.2, 1.5), "02": _at(5.7, 1.5)},
                                {"01": 12.0, "02": 9.0}, 1 / PT_PER_M)
    assert set(out["rooms"]) == {"01", "02"}, out["reasons"]
    assert abs(out["rooms"]["01"]["plotas_m2"] - 12.0) / 12.0 <= 0.02
    assert abs(out["rooms"]["02"]["plotas_m2"] - 9.0) / 9.0 <= 0.02


def test_a_floor_zone_fill_and_a_legend_swatch_stay_out_of_the_walls():
    """A floor-zone fill touching two walls (1 m deep: thicker than any wall) and a legend swatch that touches
    nothing are not walls: room 2 is not cut, its area stays the table's."""
    extra = [(4.4, 1.0, 7.4, 2.0, 0.85),            # a zone fill across room 2, wall to wall
             (9.0, 6.0, 11.0, 6.15, 0.74)]           # a swatch beside the drawing
    out = vr.trace_vector_rooms(_two_colour_plan(extra), 1, {"01": _at(2.2, 1.5), "02": _at(5.7, 2.6)},
                                {"01": 12.0, "02": 9.0}, 1 / PT_PER_M)
    assert set(out["rooms"]) == {"01", "02"}, out["reasons"]
    assert abs(out["rooms"]["02"]["plotas_m2"] - 9.0) / 9.0 <= 0.02


def test_one_colour_sheets_get_the_solid_they_always_got():
    from extractor.pdf_vectors import filled_shapes
    from tests.synthetic_plan import build_plan
    pdf = build_plan([two_rooms()])
    solid, n = vr._wall_solid(pdf, 1, W * H, 1 / PT_PER_M)
    fills = [p for _c, p in filled_shapes(pdf, 1)]
    assert n == 7 and abs(solid.area - vr._fused(fills).area) < 1e-6


# ── 3. two units with the same room numbers ──────────────────────────────────

def _two_unit_sheet() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 7)
    c.drawString(60, 30, "PERTVARU PLANAS M 1:75")
    c.setFont("Helvetica", 5)
    for i, n in enumerate(("1", "2", "3")):                       # the left unit: rooms 1–3
        c.drawString(80 + (i % 2) * 90, 600 - (i // 2) * 120, n)
    for i, n in enumerate(("1", "2", "3", "4")):                  # the right unit: rooms 1–4
        c.drawString(360 + (i % 2) * 90, 600 - (i // 2) * 120, n)
    c.showPage()
    c.save()
    return buf.getvalue()


def _unit_rooms():
    rooms = []
    for u, count in ((1, 3), (2, 4)):
        for n in range(1, count + 1):
            rooms.append({"nr": f"{u}-{n}", "plotas_m2": 10.0, "_vienetas": u, "_nr_brezinyje": str(n)})
    return rooms


def test_each_unit_room_is_seated_in_its_own_units_part_of_the_sheet():
    where = rl.locate_rooms(_two_unit_sheet(), _unit_rooms(), plan_pages=[1])
    assert len(where) == 7 and all(v["saltinis"] == "zenkliukas" for v in where.values())
    assert all(where[f"1-{n}"]["cx"] * W < 300 for n in (1, 2, 3))
    assert all(where[f"2-{n}"]["cx"] * W > 300 for n in (1, 2, 3, 4))


def test_a_sheet_showing_numbers_both_units_have_equally_is_not_guessed():
    seen = [(1, n, {"cx": 0.1 * n, "cy": 0.5}) for n in (1, 2, 3)]
    rooms = [{"nr": f"{u}-{n}", "_vienetas": u, "_nr_brezinyje": str(n)} for u in (1, 2) for n in (1, 2, 3)]
    assert rl.units_of_badges(seen, rooms) == {}
    # …but the unit numbered exactly 1–3 is told from one numbered 1–4
    rooms += [{"nr": "2-4", "_vienetas": 2, "_nr_brezinyje": "4"}]
    assert set(rl.units_of_badges(seen, rooms).values()) == {1}


def test_rooms_without_units_are_located_exactly_as_before():
    """No `_vienetas` on any room: the unit path never runs (the badge order and the first-found rule stand)."""
    sheet = two_rooms()
    sheet.badges = [("1", 2.2, 1.5), ("1", 5.7, 1.5)]
    from tests.synthetic_plan import build_plan
    where = rl.locate_rooms(build_plan([sheet]), [{"nr": "01", "plotas_m2": 12.0}], plan_pages=[1])
    assert abs(where["01"]["cx"] * W - (60 + 2.2 * PT_PER_M)) < 4      # the first badge read, as before


def _stacked_tables(totals=("17,00", "26,50"), second_numbers=("1", "2", "3", "4")) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 6)
    c.drawString(40, 60, "PLANAS M 1:75")
    y = 500

    def table(rows, total_label, total):
        nonlocal y
        c.drawString(400, y, "PATALPŲ EKSPLIKACIJA")
        y -= 10
        for nr, name, area in rows:
            c.drawString(392, y, nr)
            c.drawString(402, y, name)
            c.drawRightString(540, y, area)
            c.drawString(543, y, "m2")
            c.drawString(40, y + 1, "Visus matmenis tikslinti vietoje")       # sheet notes on the same height
            y -= 10
        if total:
            c.drawString(392, y, f"{total_label}: {total} m2")
        y -= 30

    table([("1", "Koridorius", "8,00"), ("2", "Miegamasis", "6,00"), ("3", "Vonios kambarys", "3,00")],
          "Bendras kairiojo bloko plotas", totals[0])
    names = ("Koridorius", "Miegamasis", "Vonios kambarys", "Svetainė")
    areas = ("7,50", "6,00", "3,00", "10,00")
    table(list(zip(second_numbers, names, areas)), "Bendras dešiniojo bloko plotas", totals[1])
    c.showPage()
    c.save()
    return buf.getvalue()


def test_two_stacked_tables_repeating_their_numbers_become_two_units():
    import pdfplumber

    from extractor.pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber, stacked_unit_rooms
    pdf = _stacked_tables()
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        rooms, info = stacked_unit_rooms(doc)
    assert [r["nr"] for r in rooms] == ["1-1", "1-2", "1-3", "2-1", "2-2", "2-3", "2-4"]
    assert [(r["_vienetas"], r["_nr_brezinyje"]) for r in rooms][3] == (2, "1")
    assert [r["plotas_m2"] for r in rooms] == [8.0, 6.0, 3.0, 7.5, 6.0, 3.0, 10.0]
    assert [u["suma_m2"] for u in info["units"]] == [17.0, 26.5]
    out = extract_eksplikacija_pdfplumber(pdf)
    assert len(out["patalpos"]) == 7 and out["_meta"]["total_area_m2"] == 43.5


def test_tables_that_do_not_repeat_numbers_or_do_not_add_up_are_left_to_the_old_reader():
    import pdfplumber

    from extractor.pdfplumber_eksplikacija import stacked_unit_rooms
    with pdfplumber.open(io.BytesIO(_stacked_tables(second_numbers=("4", "5", "6", "7")))) as doc:
        assert stacked_unit_rooms(doc) is None                      # one building's table, continued
    with pdfplumber.open(io.BytesIO(_stacked_tables(totals=("17,00", "30,00")))) as doc:
        assert stacked_unit_rooms(doc) is None                      # a unit whose rows miss its own sum: misread


# ── 4. dashed swing arcs ──────────────────────────────────────────────────────

def _dashed_door(threshold: bool = True) -> bytes:
    """A 0,8 m door at 1:75 drawn the way objektas_i draws it: the swing as 2,8 pt dashes with 1,4 pt gaps (no
    dash pattern — every dash its own line), its end touching a dashed threshold rectangle in the same grey."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setStrokeColorRGB(0.58, 0.58, 0.6)
    c.setLineWidth(0.12)
    cx, cy, r = 300.0, 400.0, 30.24                       # hinge; 0,8 m at 1:75
    dash, gap = 2.8, 1.4
    a = 0.0
    while a < math.pi / 2:
        b = min(a + dash / r, math.pi / 2)
        c.line(cx + r * math.cos(a), cy + r * math.sin(a), cx + r * math.cos(b), cy + r * math.sin(b))
        a = b + gap / r
    if threshold:                                         # the threshold: a dashed box from the arc's end
        x = cx + 0.4
        while x < cx + r:
            c.line(x, cy - 0.7, min(x + dash, cx + r), cy - 0.7)
            c.line(x, cy - 4.4, min(x + dash, cx + r), cy - 4.4)
            x += dash + gap
        c.line(cx + r, cy - 0.7, cx + r + 1.4, cy - 2.1)  # a corner piece at 45°
        c.line(cx + r + 1.4, cy - 2.6, cx + r, cy - 4.4)
    c.setFillGray(0)
    c.setFont(LT_FONT, 7)
    c.drawString(60, 30, "PERTVARU PLANAS M 1:75")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_a_dashed_swing_arc_touching_a_dashed_threshold_is_read_as_a_door():
    m = 0.75 * 0.0254 / 72 * 100                          # metres per point at 1:75
    marks = do.page_marks(_dashed_door(), 1, m)
    dashed = [a for a in marks.arcs if a.source == "dash"]
    assert len(dashed) == 1, marks.arcs
    arc = dashed[0]
    # page frame: y down, so the hinge is at (300, H - 400)
    assert abs(arc.cx - 300) < 1.0 and abs(arc.cy - (H - 400)) < 1.0 and abs(arc.r * m - 0.8) < 0.03
    # the opening the leaf closes — from the hinge to the arc's far end on the wall — is a door
    kind, _ = do.opening_kind([(300.0, H - 400.0), (330.24, H - 400.0)], 0.8, 0.12, marks, m)
    assert kind == "durys"


def test_the_turn_limit_lets_an_arc_through_and_stops_at_a_corner():
    r_lo = do.LEAF_M[0] / (0.75 * 0.0254 / 72 * 100)
    lim = do._turn_max_deg(r_lo)
    assert math.degrees((do.DASH_MAX_PT + do.DASH_GAP_PT) / r_lo) <= lim < 45.0


# ── 5. an open space whose rooms differ in ceiling height (objektas_b, 2026-10-24) ──

def _open_space_parsed(h1: float, h2: float) -> dict:
    return {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}],
            "patalpos": [{"nr": "01", "pavadinimas": "A", "plotas_m2": 12.6, "plotas_saltinis": "eksplikacija",
                          "puslapio_nr": 1, "perimetras_m": 13.9, "lubu_aukstis_m": h1},
                         {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija",
                          "puslapio_nr": 1, "perimetras_m": 12.3, "lubu_aukstis_m": h2}]}


def _one_space_plan() -> bytes:
    from tests.synthetic_plan import build_plan
    a = two_rooms()
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]       # no partition: one space, two rooms in the table
    return build_plan([a])


def test_mixed_heights_and_no_boundary_leave_the_rooms_unshared_with_a_reason(monkeypatch):
    """objektas_b: tambūras, living room (5,7 m, double height) and corridor (2,82 m) are one face. A share by
    floor area gave the living room 47,8 m of the 65,1 m (+36 m² of wall). No share is written: each room keeps
    what it had and says why."""
    from extractor import geometry_lane as gl
    monkeypatch.setattr(gl, "propose_split", lambda *a, **k: {"status": "no_proposal"})
    parsed = _open_space_parsed(5.7, 2.82)
    out = gl.apply_geometry(parsed, _one_space_plan())
    r1, r2 = parsed["patalpos"]
    assert out["erdves_skirtingu_auksciu"] == [["01", "02"]]
    assert r1["perimetras_m"] == 13.9 and r2["perimetras_m"] == 12.3          # what each had — not a share
    assert "perimetras_saltinis" not in r1 and "_perimetras_ivertis_m" not in r1
    assert "lubų aukščiai skirtingi" in r1["_perimetras_priezastis"] and r1["_atvira_erdve"]["nariai"] == ["01", "02"]
    # the same space at one height is still shared by floor area, exactly as before
    same = _open_space_parsed(2.7, 2.7)
    gl.apply_geometry(same, _one_space_plan())
    assert same["patalpos"][0]["perimetras_saltinis"] == "atviros_erdves_ivertis"


def test_heights_settled_after_the_lane_take_the_share_back_and_agreeing_heights_restore_it(monkeypatch):
    """In the paid reading the double height arrives AFTER the lane (objektas_b: height salvage). The project-level
    pass every calc path runs (universal_rules.prepare_rooms_for_calc) checks the shares against the final heights."""
    from extractor import geometry_lane as gl
    from extractor.universal_rules import prepare_rooms_for_calc
    monkeypatch.setattr(gl, "propose_split", lambda *a, **k: {"status": "no_proposal"})
    parsed = _open_space_parsed(2.82, 2.82)
    gl.apply_geometry(parsed, _one_space_plan())
    r1, r2 = parsed["patalpos"]
    assert r1["perimetras_saltinis"] == "atviros_erdves_ivertis"
    share = r1["perimetras_m"]
    r1["lubu_aukstis_m"] = 5.7                                    # the height salvage, later in the reading
    out = prepare_rooms_for_calc(parsed["patalpos"])
    assert out["atviros_erdves"]["unshared"] == 2
    assert r1["perimetras_m"] == 13.9 and r2["perimetras_m"] == 12.3 and "perimetras_saltinis" not in r1
    assert "lubų aukščiai skirtingi" in r1["_perimetras_priezastis"]
    r1["lubu_aukstis_m"] = 2.82                                   # he corrects it in Prielaidos
    out = prepare_rooms_for_calc(parsed["patalpos"])
    assert out["atviros_erdves"]["reshared"] == 2 and r1["perimetras_m"] == share
    assert r1["perimetras_saltinis"] == "atviros_erdves_ivertis" and r1["_perimetras_pries_geometrija"] == 13.9


def test_mixed_heights_in_a_two_room_space_read_each_sides_own_walls():
    """With a boundary the lane can propose, each side's own faces are read (the boundary is a wall of neither):
    no share by floor area, no „heights differ" reason left behind."""
    from extractor import geometry_lane as gl
    parsed = _open_space_parsed(5.7, 2.82)
    gl.apply_geometry(parsed, _one_space_plan())
    r1, r2 = parsed["patalpos"]
    for r in (r1, r2):
        assert r["_konturas"]["saltinis"] == "padalinta_programos"
        assert r["perimetras_saltinis"] != "atviros_erdves_ivertis" and r["perimetras_m"] > 0
        assert gl.UNSHARED not in r and "aukščiai" not in str(r.get("_perimetras_priezastis") or "")
    assert abs(r1["perimetras_m"] + r2["perimetras_m"] - r1["_atvira_erdve"]["perimetras_m"]) < 0.3
