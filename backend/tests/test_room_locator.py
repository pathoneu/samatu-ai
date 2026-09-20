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
    """A room list repeats the numbers: '01  Kambarys  12,00' — stacked a few
    millimetres apart in one column. Rooms are metres apart; a column is a table."""
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


def test_a_label_on_the_badges_line_does_not_disqualify_it():
    """objektas_h, 2026-09-19: badge „4" has the furniture label „LENTYNOS" 30 pt
    to its right on the same line — still a badge."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 4)
    c.drawString(300, 400, "4")
    c.drawString(332, 400, "LENTYNOS")
    c.showPage()
    c.save()
    where = rl.locate_rooms(buf.getvalue(), [{"nr": "04", "plotas_m2": 26.0}], plan_pages=[1])
    assert where["04"]["saltinis"] == "zenkliukas" and abs(where["04"]["cx"] * 595 - 301) < 3


def test_a_piece_of_a_longer_number_is_not_a_badge():
    """objektas_h, 2026-09-19: the character reader splits a spaced „885" into
    „8" + „85" — the stray „8" must not locate room 08. A badge stands alone:
    no other number touches it on its line."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 4)
    c.drawString(60, 700, "PERTVARU PLANAS")  # the reader skips a direction with under 8 characters
    c.drawString(200, 500, "8")
    c.drawString(204.3, 500, "85")            # 2 pt after the „8": the same number, letter-spaced
    c.drawString(300, 400, "8")               # the real badge, alone
    c.showPage()
    c.save()
    where = rl.locate_rooms(buf.getvalue(), [{"nr": "08", "plotas_m2": 4.0}], plan_pages=[1])
    assert where["08"]["saltinis"] == "zenkliukas"
    assert abs(where["08"]["cx"] * 595 - 301) < 3 and abs(where["08"]["cy"] * 842 - (842 - 401.5)) < 4


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


# ── three-digit room numbers (objektas_a, 2026-09-21) ────────────────────────
# Architects number the rooms of a house 101, 102 … (first storey), 201 … — written inside the room in a
# font twice the size of a designer's „01" badge. The locator took only 1–2 digits in a small font: on
# objektas_a ten of eleven rooms had no place at all, so none of them could be outlined; with their
# numbers found, all eleven are. Loosening the SMALL-badge rule instead was measured and rejected: on
# objektas_h two rooms lost their outlines to other small numbers, and on objektas_b furniture item
# numbers („08", „17") became rooms.

def _page(draw) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    draw(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def _house():
    return [{"nr": "101", "plotas_m2": 11.0}, {"nr": "102", "plotas_m2": 50.5}, {"nr": "103", "plotas_m2": 9.6}]


def test_a_three_digit_room_number_written_in_the_room_is_its_place():
    def draw(c):
        c.setFont("Helvetica", 11)
        c.drawString(200, 600, "101")
        c.drawString(330, 520, "102")
        c.drawString(260, 430, "103")
        c.setFont("Helvetica", 7)                          # …and the room table repeats them, stacked in a column
        for i, nr in enumerate(("101", "102", "103")):
            c.drawString(40, 200 - i * 10, nr)
            c.drawString(70, 200 - i * 10, "Kambarys")
    where = rl.locate_rooms(_page(draw), _house(), plan_pages=[1])
    assert {nr: v["saltinis"] for nr, v in where.items()} == {"101": "zenkliukas", "102": "zenkliukas", "103": "zenkliukas"}
    assert abs(where["101"]["cx"] * 595 - 209) < 4 and abs(where["101"]["cy"] * 842 - (842 - 604)) < 5
    assert abs(where["103"]["cx"] * 595 - 269) < 4


def test_a_three_digit_number_that_is_part_of_something_else_is_not_a_room():
    def draw(c):
        c.setFont("Helvetica", 11)
        c.drawString(200, 600, "101")
        c.drawString(222, 600, "5")                        # „101 5": a letter-spaced dimension, not room 101
        c.drawString(330, 40, "102")                       # in the title block
    where = rl.locate_rooms(_page(draw), _house(), plan_pages=[1])
    assert where == {}


def test_a_huge_number_is_a_title_not_a_room():
    def draw(c):
        c.setFont("Helvetica", 22)
        c.drawString(200, 600, "101")
    assert rl.locate_rooms(_page(draw), _house(), plan_pages=[1]) == {}


def test_short_room_numbers_keep_the_small_badge_rule():
    """„08" in a 7 pt font is a furniture item number on objektas_b, not room 08."""
    def draw(c):
        c.setFont("Helvetica", 9.5)
        c.drawString(200, 600, "08")
    assert rl.locate_rooms(_page(draw), [{"nr": "08", "plotas_m2": 6.8}], plan_pages=[1]) == {}
