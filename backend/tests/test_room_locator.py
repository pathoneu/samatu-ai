"""Rooms are located by their number badge in the text layer, then by an area
label, then by Vision's box — and the source is written down. Synthetic only."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import room_locator as rl  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402


def _rooms():
    return [{"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "bbox_pct": {"x": 0.10, "y": 0.10, "w": 0.30, "h": 0.15}},
            {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0}]


def test_badges_locate_both_rooms_on_the_plan_page():
    pdf = build_plan([two_rooms()])
    where = rl.locate_rooms(pdf, _rooms(), plan_pages=[1])
    assert where["01"]["saltinis"] == "zenkliukas" and where["01"]["page"] == 1
    assert where["02"]["saltinis"] == "zenkliukas"
    # badge 1 sits at (2,2 m, 1,5 m) from the sheet origin (60 pt, 80 pt)
    assert abs(where["01"]["cx"] * 595 - (60 + 2.2 * PT_PER_M)) < 4
    assert abs(where["01"]["cy"] * 842 - (80 + 1.5 * PT_PER_M)) < 4
    assert round(where["01"]["W"]) == 595 and round(where["01"]["H"]) == 842


def test_table_rows_are_not_badges():
    """A room list repeats the numbers: '01  Kambarys  12,00'. A number with a
    name to its right on the same line is a table row, not a badge."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 5)
    for i, (nr, name) in enumerate((("01", "Kambarys"), ("02", "Vonia"))):
        y = 300 - i * 9
        c.drawString(40, y, nr)
        c.drawString(60, y, name)
        c.drawString(140, y, "12,00")
    c.showPage()
    c.save()
    where = rl.locate_rooms(buf.getvalue(), _rooms(), plan_pages=[1])
    assert where["01"]["saltinis"] == "bbox"                # fell back to Vision's box
    assert "02" not in where                                # nothing to fall back on


def test_no_badge_no_label_no_bbox_means_unlocated():
    pdf = build_plan([Sheet(walls=[(0, 0, 3, 0.2)])])
    where = rl.locate_rooms(pdf, [{"nr": "05", "plotas_m2": 4.0}], plan_pages=[1])
    assert "05" not in where


def test_an_existing_area_label_wins_over_a_badge():
    pdf = build_plan([two_rooms()])
    rooms = _rooms()
    rooms[0]["_plotas_uzrasas"] = {"page": 1, "bbox": [300, 400, 320, 410], "page_width": 595, "page_height": 842}
    where = rl.locate_rooms(pdf, rooms, plan_pages=[1])
    assert where["01"]["saltinis"] == "plotas_uzrasas" and abs(where["01"]["cx"] * 595 - 310) < 1


def test_the_badge_nearest_to_visions_box_wins_when_a_number_repeats():
    sheet = two_rooms()
    sheet.badges = [("1", 2.2, 1.5), ("1", 5.7, 1.5)]      # the same digit twice on the plan
    pdf = build_plan([sheet])
    room = {"nr": "01", "plotas_m2": 12.0, "bbox_pct": {"x": 0.30, "y": 0.10, "w": 0.15, "h": 0.12}}   # box around the second badge
    where = rl.locate_rooms(pdf, [room], plan_pages=[1])
    assert abs(where["01"]["cx"] * 595 - (60 + 5.7 * PT_PER_M)) < 4
