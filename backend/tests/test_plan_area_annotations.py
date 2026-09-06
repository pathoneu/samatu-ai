"""The plan-area lane: the designer's room areas, read as text, become the table.

Synthetic PDF drawn with reportlab (ASCII text — Helvetica has no ų/²), and
dict rooms. Nothing here reads a customer drawing.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from extractor.plan_area_annotations import (
    MIN_CANDIDATES, SOURCE_LABEL, plan_pages_from_classification,
    read_area_annotations, reconcile_rooms_with_annotations,
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
    assert res["unclaimed"] == [{"page": 4, "value_m2": 7.25}]
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
