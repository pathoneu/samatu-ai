"""The plan-area lane: the designer's room areas, read as text, become the table.

Synthetic PDF drawn with reportlab (ASCII text — Helvetica has no ų/²), and
dict rooms. Nothing here reads a customer drawing.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from extractor.plan_area_annotations import (
    MIN_CANDIDATES, SOURCE_LABEL, apply_height_statements, lane_warnings,
    plan_pages_from_classification, read_area_annotations, read_author_figures,
    read_height_statements, reconcile_rooms_with_annotations, scan_text_layer,
)


def _pdf(draw) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(842, 1191))
    draw(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def _plan_page(c):
    c.setFont("Helvetica", 9)
    # standalone room areas
    c.drawString(120, 900, "37.86 m2")
    c.drawString(420, 900, "14.26 m2")
    c.drawString(120, 700, "3.52 m2")
    # a material total: words one line above the number → a block, not a room
    c.drawString(120, 400, "laminuota grindu danga")
    c.drawString(120, 388, "76.65 m2")
    # a tile-count label
    c.drawString(420, 400, "6vnt.")
    c.drawString(420, 388, "3.70 m2")
    # a dimension string with three decimals is not an area
    c.drawString(600, 600, "2.850")
    # a character-spaced number, the way CAD exports often write it
    x = 600.0
    for ch in "7.25":
        c.drawString(x, 500, ch)
        x += 6.0
    c.drawString(x + 3, 500, "m2")
    # the commonest convention: the room NAME right above its area — a room
    c.drawString(420, 712, "Miegamasis")
    c.drawString(420, 700, "10.55 m2")
    # a legend total with a name-like word AND a material word — not a room
    c.drawString(420, 250, "Sienu dazai")
    c.drawString(420, 238, "320.00 m2")


def test_standalone_labels_are_rooms_and_blocks_are_not():
    ann = read_area_annotations(_pdf(_plan_page))
    by = {a["value_m2"]: a for a in ann}
    assert set(by) == {37.86, 14.26, 3.52, 76.65, 3.7, 7.25, 10.55, 320.0}
    assert by[37.86]["standalone"] and by[14.26]["standalone"] and by[3.52]["standalone"]
    assert by[7.25]["standalone"], "character-spaced digits are re-joined"
    assert by[10.55]["standalone"] and by[10.55]["context"] == "Miegamasis", \
        "a room name beside the area keeps it a room label"
    assert not by[320.0]["standalone"], "a legend total is not a room"
    assert not by[76.65]["standalone"] and "grindu" in by[76.65]["context"]
    assert not by[3.7]["standalone"] and "vnt" in by[3.7]["context"]
    a = by[37.86]
    assert a["page"] == 1 and a["page_width"] == 842 and a["page_height"] == 1191
    x0, top, x1, bottom = a["bbox"]
    assert 115 < x0 < 125 and 0 < top < 400 and x1 > x0 and bottom > top


def test_page_filter_and_no_text_layer():
    pdf = _pdf(_plan_page)
    assert read_area_annotations(pdf, pages=[2]) == []
    assert len(read_area_annotations(pdf, pages=[1])) == 8


def test_plan_pages_from_classification():
    assert plan_pages_from_classification([
        {"page": 1, "tipas": "floor_plan"}, {"page": 2, "tipas": "electrical"},
        {"page": 4, "tipas": "ceiling_plan"}, {"nr": 7, "type": "floor_plan"},
        {"page": 9, "tipas": "wall_elevation"}]) == [1, 4, 7]
    assert plan_pages_from_classification(None) == []


# ── reconcile ────────────────────────────────────────────────────────────────

def _ann(*values, page=4):
    return [{"page": page, "value_m2": v, "standalone": True, "bbox": [1, 2, 3, 4],
             "page_width": 842, "page_height": 1191} for v in values]


def _room(nr, plotas, **kw):
    return {"nr": nr, "pavadinimas": f"Patalpa {nr}", "plotas_m2": plotas, **kw}


def test_confirm_adopt_and_flag():
    rooms = [_room("01", 37.86), _room("02", 14.26), _room("03", 3.11),
             _room("07", 5.64), _room("09", 6.78)]
    res = reconcile_rooms_with_annotations(rooms, _ann(37.86, 14.26, 3.52, 7.25, 6.78))
    assert res["status"] == "applied"
    assert res["confirmed"] == ["01", "02", "09"]
    assert res["adopted"] == ["03"]                     # 3,11 → the label's 3,52
    assert res["unconfirmed"] == ["07"]                 # no label within 20 %
    assert [(u["page"], u["value_m2"]) for u in res["unclaimed"]] == [(4, 7.25)]
    assert res["unclaimed"][0]["bbox"] == [1, 2, 3, 4] and res["unclaimed"][0]["page_width"] == 842
    assert res["sum_m2"] == pytest.approx(37.86 + 14.26 + 3.52 + 7.25 + 6.78)
    r3 = rooms[2]
    assert r3["plotas_m2"] == 3.52 and r3["_plotas_pries_uzrasa_m2"] == 3.11
    assert r3["plotas_saltinis"] == SOURCE_LABEL and r3["_plotas_uzrasas"]["page"] == 4
    assert rooms[0]["plotas_saltinis"] == SOURCE_LABEL and rooms[0]["plotas_m2"] == 37.86
    assert rooms[3].get("_area_unconfirmed") is True and rooms[3]["plotas_m2"] == 5.64, \
        "a room no label supports is flagged, never deleted"


def test_too_few_labels_touch_nothing():
    rooms = [_room("01", 37.86), _room("02", 5.64)]
    res = reconcile_rooms_with_annotations(rooms, _ann(37.86, 14.26))
    assert res["status"] == "insufficient" and res["candidates"] == 2 < MIN_CANDIDATES
    assert "plotas_saltinis" not in rooms[0] and "_area_unconfirmed" not in rooms[1]


def test_table_and_user_rooms_are_never_touched():
    rooms = [_room("01", 30.0, plotas_saltinis="eksplikacija"),
             _room("02", 12.0, manual_override=True),
             _room("03", 9.9)]
    res = reconcile_rooms_with_annotations(rooms, _ann(37.86, 14.26, 10.0))
    assert rooms[0]["plotas_m2"] == 30.0 and rooms[0]["plotas_saltinis"] == "eksplikacija"
    assert rooms[1]["plotas_m2"] == 12.0 and "_area_unconfirmed" not in rooms[1]
    assert res["confirmed"] == ["03"]


def test_each_label_is_claimed_once():
    rooms = [_room("01", 10.0), _room("02", 10.1)]
    res = reconcile_rooms_with_annotations(rooms, _ann(10.0, 20.0, 30.0))
    assert res["confirmed"] == ["01"]
    assert res["unconfirmed"] == ["02"], "the second room cannot claim the same label"


def test_same_rooms_on_a_second_sheet_are_not_summed_twice():
    # lubų planas (p4) and grindų planas (p7) both label the same five rooms;
    # p2 carries the second floor with different values
    ann = (_ann(37.86, 14.26, 3.52, 7.25, 6.78, page=4)
           + _ann(37.86, 14.26, 3.52, 7.25, page=7)
           + _ann(20.0, 12.5, 9.75, page=2))
    rooms = [_room("01", 37.86), _room("02", 14.26), _room("03", 3.52), _room("04", 7.25),
             _room("05", 6.78), _room("06", 20.0), _room("07", 12.5), _room("08", 9.75)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert res["status"] == "applied"
    assert res["pages"] == [2, 4] and res["duplicate_view_pages"] == [7]
    assert res["candidates"] == 8 and res["sum_m2"] == pytest.approx(37.86 + 14.26 + 3.52 + 7.25 + 6.78 + 20 + 12.5 + 9.75)
    assert res["confirmed"] == ["01", "02", "03", "04", "05", "06", "07", "08"]


# ── the author's own figures ─────────────────────────────────────────────────

def _legend_page(c):
    c.setFont("Helvetica", 8)
    c.drawString(80, 1100, "Sienu dazai (spalva S310-G80Y) 320 m2")      # same line
    c.drawString(80, 1060, "laminuota grindu danga")                     # line above …
    c.drawString(80, 1050, "76.65 m2")                                   # … the number
    c.drawString(80, 1010, "Grindjuostes (tokios pacios kaip grindu dangos), h-8cm, 53,69m")
    c.drawString(80, 970, "Sienu plyteles - CORSO IVORY 60X120 cm - 38 vnt.")
    c.drawString(80, 930, "Isvadai TV, internetui h- 1,20m")             # a height, not a quantity
    c.drawString(80, 890, "Rozetes kartu su H 0.3m")                     # a height
    c.drawString(80, 850, "14.26 m2")                                    # a room label: no material word
    c.drawString(80, 810, "LED juostelei po spintele h 1.5m")            # LED, but a height
    c.drawString(80, 770, "Sienu dazai (spalva S310-G80Y) 320 m2")      # repeated → once
    # a legend block interleaved with rotated dimension fragments (the way a
    # grindų planas reads by `top`): the label is two text lines up
    c.drawString(80, 700, "Grindjuostes (derinamos prie duru arba")
    c.drawString(400, 696, "0.610")
    c.drawString(80, 688, "grindu dangos), h-8cm, 53,69m")
    # a note paragraph above a ROOM label on a sheet that labels its rooms —
    # the room lane owns those; the note must not adopt them
    c.drawString(80, 620, "*PASTABA: dregnose patalpose glaistoma ir dazoma dregmei atspariomis medziagomis:")
    c.drawString(80, 608, "5.73 m2")
    c.drawString(300, 608, "3.82 m2")
    c.drawString(500, 608, "6.83 m2")
    # a legend row that also carries a room label before the statement
    c.drawString(80, 560, "101 Tamburas 11.01 m2 Parketlentes (~ 135 m2")
    # two statements on one rebuilt line: the second label starts after the first quantity
    c.drawString(80, 520, "grindu dangos), h-8cm, 53,69m Grindjuostes (is plyteliu), h-8cm, 24,97m")
    # ONE statement with a count and an area: the area keeps the family word before the count
    c.drawString(80, 480, "Plyteliu klojimo 13vnt. 3.95 m2")


def test_author_figures_are_material_statements_not_heights_or_room_labels():
    figs = read_author_figures(_pdf(_legend_page))
    got = {(f["family"], f["value"], f["unit"]) for f in figs}
    assert got == {("sienu_dazymas", 320.0, "m2"), ("grindu_danga", 76.65, "m2"),
                   ("grindjuostes", 53.69, "m"), ("grindjuostes", 24.97, "m"),
                   ("plyteles", 38.0, "vnt"), ("grindu_danga", 135.0, "m2"),
                   ("plyteles", 13.0, "vnt"), ("plyteles", 3.95, "m2")}
    by = {(f["family"], f["value"]): f for f in figs}
    assert by[("grindu_danga", 76.65)]["label"] == "laminuota grindu danga", "the name sits on the line above"
    assert by[("grindjuostes", 53.69)]["label"].startswith("Grindjuostes (derinamos"), \
        "dimension fragments between the legend lines are skipped, not taken as the label"
    assert by[("grindu_danga", 135.0)]["label"] == "Parketlentes", \
        "the label is the phrase after the earlier quantity, not the room label before it"
    assert by[("sienu_dazymas", 320.0)]["page"] == 1
    labels = sorted(f["label"] for f in figs if f["family"] == "grindjuostes")
    assert labels == ["Grindjuostes (derinamos prie duru arba grindu dangos), h-8cm",
                      "Grindjuostes (is plyteliu), h-8cm",
                      "Grindjuostes (tokios pacios kaip grindu dangos), h-8cm"], \
        "two different statements with the same value are both kept; a repeated one is not; " \
        "a second statement on one line starts after the first quantity"
    assert {f["value"] for f in figs if f["family"] == "grindjuostes"} == {53.69, 24.97}
    tile_area = next(f for f in figs if f["family"] == "plyteles" and f["unit"] == "m2")
    assert tile_area["value"] == 3.95 and tile_area["label"].startswith("Plyteliu klojimo")
    assert len(figs) == 9, "room labels under a note paragraph are not statements"


# ── the engine: PDFium boxes in pdfplumber's display frame ───────────────────

def _rotated_page(c):
    c.setFont("Helvetica", 9)
    c.drawString(120, 900, "37.86 m2")
    c.drawString(420, 900, "14.26 m2")
    c.drawString(120, 700, "3.52 m2")
    c.setPageRotation(90)


def test_a_rotated_sheet_is_read_upright_and_cropped_in_the_display_frame():
    """A landscape sheet stored with /Rotate 90: the text is horizontal in the
    page's own frame (that is where it is read) and vertical on the displayed,
    rotated sheet (that is where the crop is cut — pdf2image applies /Rotate).
    The bbox must therefore be in the ROTATED frame: page dims swapped, the
    label taller than wide, everything inside the page."""
    ann = read_area_annotations(_pdf(_rotated_page))
    by = {a["value_m2"]: a for a in ann}
    assert set(by) == {37.86, 14.26, 3.52}, "rotation must not lose a single label"
    a = by[37.86]
    assert (a["page_width"], a["page_height"]) == (1191.0, 842.0), "display dims are the rotated ones"
    x0, top, x1, bottom = a["bbox"]
    assert 0 <= x0 < x1 <= 1191 and 0 <= top < bottom <= 842
    assert (bottom - top) > (x1 - x0), "a horizontal label turns vertical on the rotated sheet"
    # the label was at x=120 from the left, 291 pt from the top of the unrotated
    # sheet; rotated 90° clockwise it sits 291 pt from the RIGHT edge, 120 pt from the top
    assert abs((1191 - x1) - 283) < 12 and abs(top - 120) < 3, a["bbox"]


def _vertical_dimension_page(c):
    c.setFont("Helvetica", 9)
    c.drawString(80, 1060, "laminuota grindu danga")
    c.drawString(80, 1050, "76.65 m2")
    # a vertical string drawn through the legend — text in ANOTHER direction is
    # read in its own frame, never mixed into the horizontal lines around it
    c.saveState(); c.translate(60, 1000); c.rotate(90); c.drawString(0, 0, "3.290 danga 12.50 m2"); c.restoreState()


def test_text_in_another_direction_is_read_in_its_own_frame_never_mixed_in():
    pdf = _pdf(_vertical_dimension_page)
    figs = {(f["value"], f["label"]) for f in read_author_figures(pdf)}
    assert figs == {(76.65, "laminuota grindu danga"), (12.5, "danga")}, \
        "the horizontal statement keeps its own label; the vertical one is its own statement"
    vert = next(f for f in read_author_figures(pdf) if f["value"] == 12.5)
    x0, top, x1, bottom = vert["bbox"]
    assert (bottom - top) > (x1 - x0), "the vertical string is cropped where it stands — vertical"


# ── geometry: where the label stands decides first ───────────────────────────

def _sq(x, y, w, h):
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def _lab(value, cx, cy, page=4):
    # a label whose centre sits at (cx, cy) in page-percent on a 1000×1000 sheet
    return {"page": page, "value_m2": value, "standalone": True,
            "bbox": [cx * 1000 - 10, cy * 1000 - 4, cx * 1000 + 10, cy * 1000 + 4],
            "page_width": 1000, "page_height": 1000}


def test_a_label_inside_the_room_outline_is_that_rooms_area_when_the_value_is_near():
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             _room("02", 12.0, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),    # Vision read 12,0 — label says 14,26 (19 %)
             _room("03", 3.11, polygon_pct=_sq(0.5, 0.4, 0.1, 0.1))]
    ann = [_lab(37.86, 0.25, 0.25), _lab(14.26, 0.6, 0.2), _lab(3.52, 0.55, 0.45)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert res["geometry"] == "shared_frame"
    assert res["confirmed"] == ["01"] and sorted(res["adopted"]) == ["02", "03"]
    assert rooms[1]["plotas_m2"] == 14.26 and rooms[1]["_plotas_pries_uzrasa_m2"] == 12.0, \
        "the label stands inside the outline and is near: the drawing wins, the Vision figure is kept"


def test_a_far_label_inside_the_outline_is_not_taken_by_position_alone():
    """Audit 2026-09-29 (geometry-lanes-7): Vision's box drifted onto the neighbour's label and the room took
    that area at ANY distance. 9,0 against a 14,26 label inside its outline is not adopted: the room keeps its
    figure, is flagged with what the plan says there, and the label is left for the room it belongs to."""
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             _room("02", 9.0, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),
             _room("03", 3.11, polygon_pct=_sq(0.5, 0.4, 0.1, 0.1))]
    ann = [_lab(37.86, 0.25, 0.25), _lab(14.26, 0.6, 0.2), _lab(3.52, 0.55, 0.45)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert res["confirmed"] == ["01"] and res["adopted"] == ["03"] and res["unconfirmed"] == ["02"]
    assert rooms[1]["plotas_m2"] == 9.0 and rooms[1].get("plotas_saltinis") != "plano_uzrasas"
    assert rooms[1]["_area_unconfirmed_reason"] == "label_differs"
    assert rooms[1]["_plotas_uzrasas_kitas"]["value_m2"] == 14.26
    assert [(u["value_m2"], u.get("patalpoje")) for u in res["unclaimed"]] == [(14.26, "02")]
    from extractor.plan_area_annotations import lane_warnings
    from extractor.user_text import is_banned
    warns = lane_warnings(res, rooms)
    said = [w["message"] for w in warns]
    assert len(said) == 1 and "užrašyta 14,26 m²" in said[0] and "9,00 m²" in said[0], said
    assert not [s for s in said if is_banned(s)]


def test_a_far_label_that_names_the_room_is_its_area():
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             {"nr": "02", "pavadinimas": "Miegamasis", "plotas_m2": 9.0, "polygon_pct": _sq(0.5, 0.1, 0.2, 0.2)},
             _room("03", 3.11, polygon_pct=_sq(0.5, 0.4, 0.1, 0.1))]
    ann = [_lab(37.86, 0.25, 0.25), {**_lab(14.26, 0.6, 0.2), "context": "MIEGAMASIS"}, _lab(3.52, 0.55, 0.45)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert sorted(res["adopted"]) == ["02", "03"] and rooms[1]["plotas_m2"] == 14.26
    # …but a name two rooms share cannot tell them apart
    rooms = [{"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 37.86, "polygon_pct": _sq(0.1, 0.1, 0.3, 0.3)},
             {"nr": "02", "pavadinimas": "Miegamasis", "plotas_m2": 9.0, "polygon_pct": _sq(0.5, 0.1, 0.2, 0.2)},
             _room("03", 3.11, polygon_pct=_sq(0.5, 0.4, 0.1, 0.1))]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert "02" in res["unconfirmed"] and rooms[1]["plotas_m2"] == 9.0


def test_a_far_label_another_room_owns_by_value_goes_to_that_room():
    # 02's outline lies over 04's label (16,0); 04 itself has no outline — the value rule gives it the label
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             _room("02", 9.0, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),
             _room("03", 3.11, polygon_pct=_sq(0.5, 0.4, 0.1, 0.1)),
             _room("04", 15.8)]
    ann = [_lab(37.86, 0.25, 0.25), _lab(16.0, 0.6, 0.2), _lab(3.52, 0.55, 0.45)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert rooms[3]["plotas_m2"] == 16.0 and "04" in res["confirmed"]
    assert rooms[1]["plotas_m2"] == 9.0 and rooms[1]["_area_unconfirmed_reason"] == "no_label"
    assert "_plotas_uzrasas_kitas" not in rooms[1] and res["unclaimed"] == []


def test_a_room_whose_outline_holds_two_far_labels_keeps_the_one_nobody_took():
    # Vision's outline of 02 spreads over 04's label (16,0 — 04 takes it by value) and a 20,0 nobody's figure
    # is near: 02's question names the 20,0 still standing in its place
    for far in ([_lab(16.0, 0.6, 0.2), _lab(20.0, 0.8, 0.3)], [_lab(20.0, 0.8, 0.3), _lab(16.0, 0.6, 0.2)]):
        rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
                 _room("02", 9.0, polygon_pct=_sq(0.5, 0.1, 0.4, 0.3)),
                 _room("03", 3.11, polygon_pct=_sq(0.5, 0.6, 0.1, 0.1)),
                 _room("04", 15.8)]
        res = reconcile_rooms_with_annotations(rooms, [_lab(37.86, 0.25, 0.25), *far, _lab(3.52, 0.55, 0.65)])
        assert rooms[3]["plotas_m2"] == 16.0 and "02" in res["unconfirmed"]
        assert rooms[1]["_plotas_uzrasas_kitas"]["value_m2"] == 20.0 and rooms[1]["_area_unconfirmed_reason"] == "label_differs"
        assert [(u["value_m2"], u.get("patalpoje")) for u in res["unclaimed"]] == [(20.0, "02")]


def test_a_confirmed_room_takes_the_labels_value():
    """The label is the fact: within ±3 % the room is confirmed AND carries the label's number, Vision's beside."""
    rooms = [_room("01", 37.5, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)), _room("02", 14.26, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),
             _room("03", 3.5)]
    ann = [_lab(37.86, 0.25, 0.25), _lab(14.26, 0.6, 0.2), _lab(3.52, 0.9, 0.9)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert sorted(res["confirmed"]) == ["01", "02", "03"]
    assert rooms[0]["plotas_m2"] == 37.86 and rooms[0]["_plotas_pries_uzrasa_m2"] == 37.5
    assert rooms[1]["plotas_m2"] == 14.26 and "_plotas_pries_uzrasa_m2" not in rooms[1]
    assert rooms[2]["plotas_m2"] == 3.52 and rooms[2]["_plotas_pries_uzrasa_m2"] == 3.5


def test_a_room_confirmed_after_the_zoom_takes_the_labels_value():
    """The second look (reclaim_after_refinement) confirms within ±3 % — and, like the first, writes the LABEL's
    number, keeping the zoomed figure beside it."""
    from extractor.plan_area_annotations import reclaim_after_refinement
    rooms = [_room("01", 37.86), _room("02", 14.26), _room("03", 3.11), _room("07", 9.0)]
    lane = reconcile_rooms_with_annotations(rooms, _ann(37.86, 14.26, 3.52, 6.90))
    assert "07" in lane["unconfirmed"]
    rooms[3]["plotas_m2"] = 6.85                       # Step 2.5's zoomed re-read
    assert reclaim_after_refinement(rooms, lane) == ["07"]
    assert rooms[3]["plotas_m2"] == 6.9 and rooms[3]["_plotas_pries_uzrasa_m2"] == 6.85
    assert rooms[3]["plotas_saltinis"] == "plano_uzrasas" and "_area_unconfirmed" not in rooms[3]


def test_a_far_label_another_room_takes_after_the_zoom_is_no_longer_the_first_rooms_question():
    # 02's outline lies over 04's 16,0 label; on the first pass 04's Vision figure (12,0) was too far to take it
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             _room("02", 9.0, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),
             _room("03", 3.11, polygon_pct=_sq(0.5, 0.4, 0.1, 0.1)),
             _room("04", 12.0)]
    lane = reconcile_rooms_with_annotations(rooms, [_lab(37.86, 0.25, 0.25), _lab(16.0, 0.6, 0.2), _lab(3.52, 0.55, 0.45)])
    assert rooms[1]["_area_unconfirmed_reason"] == "label_differs" and rooms[1]["_plotas_uzrasas_kitas"]["value_m2"] == 16.0
    rooms[3]["plotas_m2"] = 15.9                       # the zoom reads 04 again: it is 04's label
    from extractor.plan_area_annotations import lane_warnings, reclaim_after_refinement
    assert reclaim_after_refinement(rooms, lane) == ["04"] and rooms[3]["plotas_m2"] == 16.0
    assert "_plotas_uzrasas_kitas" not in rooms[1] and rooms[1]["_area_unconfirmed_reason"] == "no_label"
    said = " ".join(w["message"] for w in lane_warnings(lane, rooms))
    assert "16,00" not in said and "16,0 " not in said


def test_two_outlines_over_one_label_are_the_same_room_drawn_twice():
    """objektas_g: Vision returned the bathroom twice (06 7,01 and 07 5,64);
    the one label „7.25" lies inside both outlines. 06 (closer) takes it, 07
    is kept and flagged as a duplicate of 06 — not merely „no label"."""
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             _room("02", 14.26, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),
             _room("06", 7.01, polygon_pct=_sq(0.2, 0.6, 0.15, 0.15)),
             _room("07", 5.64, polygon_pct=_sq(0.22, 0.62, 0.12, 0.12)),
             _room("09", 6.78, polygon_pct=_sq(0.5, 0.8, 0.1, 0.1))]
    ann = [_lab(37.86, 0.25, 0.25), _lab(14.26, 0.6, 0.2), _lab(7.25, 0.28, 0.69),
           _lab(6.78, 0.55, 0.85), _lab(6.9, 0.3, 0.85), _lab(3.6, 0.16, 0.83)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert res["geometry"] == "shared_frame"
    assert res["adopted"] == ["06"] and rooms[2]["plotas_m2"] == 7.25
    assert res["unconfirmed"] == ["07"] and res["duplicates"] == [{"nr": "07", "of": "06"}]
    assert rooms[3]["_area_unconfirmed_reason"] == "duplicate_of:06" and rooms[3]["plotas_m2"] == 5.64
    assert sorted(u["value_m2"] for u in res["unclaimed"]) == [3.6, 6.9], "two rooms the model never returned"
    assert res["sum_m2"] == pytest.approx(37.86 + 14.26 + 7.25 + 6.78 + 6.9 + 3.6)


def test_without_a_shared_frame_the_value_rule_alone_applies():
    # outlines exist but the labels are printed elsewhere on the sheet (another
    # plan placement) — fewer than 60 % of them fall inside any outline
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.0, 0.0, 0.05, 0.05)),
             _room("02", 14.26, polygon_pct=_sq(0.9, 0.9, 0.05, 0.05)),
             _room("03", 3.11)]
    ann = [_lab(37.86, 0.5, 0.5), _lab(14.26, 0.6, 0.5), _lab(3.52, 0.7, 0.5)]
    res = reconcile_rooms_with_annotations(rooms, ann)
    assert res["geometry"] == "value_only"
    assert res["confirmed"] == ["01", "02"] and res["adopted"] == ["03"]
    assert rooms[2].get("_area_unconfirmed_reason") is None


def test_lane_warnings_say_what_to_check_for_each_finding():
    rooms = [_room("01", 37.86, polygon_pct=_sq(0.1, 0.1, 0.3, 0.3)),
             _room("02", 14.26, polygon_pct=_sq(0.5, 0.1, 0.2, 0.2)),
             _room("06", 7.01, polygon_pct=_sq(0.2, 0.6, 0.15, 0.15)),
             _room("07", 5.64, polygon_pct=_sq(0.22, 0.62, 0.12, 0.12)),
             _room("09", 6.78, polygon_pct=_sq(0.5, 0.8, 0.1, 0.1))]
    ann = [_lab(37.86, 0.25, 0.25), _lab(14.26, 0.6, 0.2), _lab(7.25, 0.28, 0.69),
           _lab(6.78, 0.55, 0.85), _lab(6.9, 0.3, 0.85)]
    lane = reconcile_rooms_with_annotations(rooms, ann)
    ws = lane_warnings(lane, rooms)
    codes = [(w["code"], w["level"], w["severity"]) for w in ws]
    assert codes == [("room_area_unconfirmed", "WARN", "high"), ("plan_area_unclaimed", "WARN", "med")]
    assert "persidengia su patalpa „Patalpa 06\"" in ws[0]["message"] and ws[0]["room"] == "07"
    assert "6,90 m²" in ws[1]["message"] and "trūksta patalpos" in ws[1]["message"]
    assert lane_warnings({"status": "insufficient"}, rooms) == []


def _turned_drawing_page(c):
    """A landscape drawing placed turned 90° on a portrait page, no /Rotate —
    every character at π/2 (objektas_a's grindų planas)."""
    c.saveState()
    c.translate(842, 0)      # turn the whole sheet: text reads bottom-to-top
    c.rotate(90)
    c.setFont("Helvetica", 9)
    c.drawString(120, 300, "37.86 m2")
    c.drawString(420, 300, "14.26 m2")
    c.drawString(120, 500, "3.52 m2")
    c.drawString(120, 700, "Parketlentes (~135 m2)")
    c.drawString(120, 640, "Grindjuostes, h=60 mm (~56 m)")
    c.restoreState()
    # a horizontal note on the page — another direction than the drawing, read on its own
    c.setFont("Helvetica", 9)
    c.drawString(600, 1100, "2.850 danga 12.50 m2")


def test_a_drawing_turned_on_the_page_is_read_in_its_own_direction():
    pdf = _pdf(_turned_drawing_page)
    ann = read_area_annotations(pdf)
    assert {a["value_m2"] for a in ann if a["standalone"]} == {37.86, 14.26, 3.52}
    figs = read_author_figures(pdf)
    assert {(f["family"], f["value"]) for f in figs} == {
        ("grindu_danga", 135.0), ("grindjuostes", 56.0),
        ("grindu_danga", 12.5)}, "the turned legend AND the horizontal note are each read in their own frame"
    a = {x["value_m2"]: x for x in ann}[37.86]
    x0, top, x1, bottom = a["bbox"]
    assert (a["page_width"], a["page_height"]) == (842.0, 1191.0), "no /Rotate: display dims are the page's"
    assert 0 <= x0 < x1 <= 842 and 0 <= top < bottom <= 1191
    assert (bottom - top) > (x1 - x0), "the label stands vertical on the displayed page, like the drawing"
    # drawn at (120, 300) up the turned sheet (translate 842 + rotate 90): the string
    # starts 120 pt above the page bottom and runs upward along x ≈ 842 − 300 = 542
    assert abs(x1 - 542) < 6 and abs((1191 - bottom) - 120) < 6, a["bbox"]


# ── the plan's own storey height ─────────────────────────────────────────────

def _height_page(c):
    c.setFont("Helvetica", 9)
    c.drawString(100, 1100, "H - 2820")                          # the storey height, stated once
    c.drawString(100, 1060, "Kaktos pab. h - 2390")              # a soffit — not the storey
    c.drawString(100, 1020, "spintoje h - 2,20 m")               # a fixture height
    c.drawString(100, 980, "Isvadai TV, internetui h- 1,20m")    # below any storey
    c.drawString(100, 940, "37.86 m2")                           # a room label, untouched
    c.drawString(100, 900, "ap. h - 2260 mm, kai lubos zeminamos")   # a soffit inside a sentence — not the storey
    c.drawString(400, 1100, "H - 2820")                          # the same stamp again on the sheet


def test_the_plan_stated_height_is_read_and_fixture_heights_are_not():
    hs = read_height_statements(_pdf(_height_page))
    assert [(h["value_m"], h["text"]) for h in hs] == [(2.82, "H - 2820"), (2.82, "H - 2820")]
    assert hs[0]["page"] == 1 and hs[0]["bbox"][0] < 110
    assert apply_height_statements([_room("01", 20.0, lubu_aukstis_saltinis="section_average")], hs)["status"] == "applied"
    assert scan_text_layer(_pdf(_height_page))["heights"] == hs


def test_rooms_with_only_our_default_take_the_plan_height_readers_win():
    rooms = [_room("01", 20.0, lubu_aukstis_m=2.82, lubu_aukstis_saltinis="section_average"),
             _room("02", 12.0, lubu_aukstis_m=3.1, lubu_aukstis_saltinis="section_pjuvis"),
             _room("03", 8.0, lubu_aukstis_m=2.82, lubu_aukstis_saltinis="user_override")]
    res = apply_height_statements(rooms, [{"page": 1, "value_m": 2.6, "text": "H - 2600",
                                           "bbox": [1, 2, 3, 4], "page_width": 842, "page_height": 1191}])
    assert res["status"] == "applied" and res["rooms"] == ["01"]
    assert rooms[0]["lubu_aukstis_m"] == 2.6 and rooms[0]["lubu_aukstis_saltinis"] == "plano_uzrasas"
    assert rooms[0]["_lubu_aukstis_uzrasas"]["text"] == "H - 2600"
    assert rooms[1]["lubu_aukstis_m"] == 3.1 and rooms[2]["lubu_aukstis_saltinis"] == "user_override"
    assert apply_height_statements(rooms, [])["status"] == "none"
    two = apply_height_statements([_room("04", 9.0, lubu_aukstis_saltinis="section_average")],
                                  [{"value_m": 2.6}, {"value_m": 3.0}])
    assert two["status"] == "ambiguous", "two stated heights need the per-room readers, not a guess"



def test_zoom_arithmetic_never_overwrites_an_area_the_drawing_states():
    """First fresh objektas_g run (2026-09-10): Step 2.5 zoom turned an adopted
    plan label (14,26 m²) back into wall-dimension arithmetic (11,68 m²)."""
    from extractor.vision_call import _apply_zoom_refinements
    room = {"nr": "02", "plotas_m2": 14.26, "plotas_saltinis": "plano_uzrasas",
            "_plotas_uzrasas": {"page": 4, "value_m2": 14.26}, "perimetras_m": 15.0}
    zoom = {"confidence_zoom": "high", "plotas_saltinis": "from_zoom", "plotas_m2": 11.68,
            "perimetras_saltinis": "from_zoom", "perimetras_m": 13.67}
    changed = _apply_zoom_refinements(room, zoom)
    assert room["plotas_m2"] == 14.26 and room["plotas_saltinis"] == "plano_uzrasas"
    assert room["_plotas_zoom_m2"] == 11.68
    assert changed is True and room["perimetras_m"] == 13.67, "the perimeter still takes the zoom"
    # a room the drawing does not label still takes the zoomed area
    other = {"nr": "07", "plotas_m2": 8.78, "plotas_saltinis": "inline_label"}
    _apply_zoom_refinements(other, {"confidence_zoom": "high", "plotas_saltinis": "from_zoom", "plotas_m2": 8.22})
    assert other["plotas_m2"] == 8.22 and other["plotas_saltinis"] == "wall_dim_calc"



def test_a_zoomed_room_takes_the_label_it_now_matches_but_never_adopts_a_near_miss():
    from extractor.plan_area_annotations import reclaim_after_refinement
    lab = lambda v: {"page": 4, "value_m2": v, "bbox": [0, 0, 1, 1], "page_width": 100, "page_height": 100}
    rooms = [
        {"nr": "07", "pavadinimas": "Miegamasis 3", "plotas_m2": 10.55, "plotas_saltinis": "wall_dim_calc", "_area_unconfirmed": True, "_area_unconfirmed_reason": "no_label"},
        {"nr": "08", "pavadinimas": "Miegamasis 3", "plotas_m2": 8.22, "plotas_saltinis": "wall_dim_calc", "_area_unconfirmed": True, "_area_unconfirmed_reason": "no_label"},
        {"nr": "09", "pavadinimas": "Vonia", "plotas_m2": 5.6, "plotas_saltinis": "wall_dim_calc", "_area_unconfirmed": True, "_area_unconfirmed_reason": "duplicate_of:06"},
    ]
    lane = {"status": "applied", "geometry": "value_only", "confirmed": ["01"], "adopted": [],
            "unconfirmed": ["07", "08", "09"], "duplicates": [{"nr": "09", "of": "06"}],
            "unclaimed": [lab(10.55), lab(3.6), lab(6.9)]}
    assert reclaim_after_refinement(rooms, lane) == ["07"]
    assert rooms[0]["plotas_saltinis"] == "plano_uzrasas" and rooms[0]["_plotas_uzrasas"]["value_m2"] == 10.55
    assert "_area_unconfirmed" not in rooms[0]
    # 8,22 is 19 % from the hall's 6,90 — a different room, left alone
    assert rooms[1]["plotas_m2"] == 8.22 and rooms[1].get("_area_unconfirmed") is True
    # a duplicate stays a duplicate whatever its area
    assert rooms[2].get("_area_unconfirmed") is True
    assert lane["unconfirmed"] == ["08", "09"] and lane["confirmed"] == ["01", "07"]
    assert [u["value_m2"] for u in lane["unclaimed"]] == [3.6, 6.9]
