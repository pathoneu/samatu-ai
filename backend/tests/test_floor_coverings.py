"""`extractor/floor_coverings` — which covering the FLOOR PLAN draws in a room.

Read, not guessed from the room's purpose. Two kinds of evidence, both measured
on real designers' sheets (2026-09-20) and imitated here on invented ones:
  · `uzrasas` — the covering is written inside the room;
  · `rastas`  — the room is hatched in the colour a legend line is written in.
Anything less than that is NOT a reading: a black legend, the skirting legend,
the heating plan, two coverings in one room — the room keeps its question.
"""
from __future__ import annotations

import pytest

from extractor.floor_coverings import classify_line, find_floor_sheets, read_floor_coverings
from synthetic_floor_plan import (
    BLACK, BLUE, BROWN, GREEN, M_PER_PT, ORANGE, RED, FloorSheet, Hatch, build_floor_pdf, point_pt, room_pt,
)

LIVING = (0.0, 0.0, 5.0, 4.0)
BATH = (5.2, 0.0, 7.2, 2.4)
HALL = (5.2, 2.6, 7.2, 4.0)


def _rooms(*specs):
    return [{"nr": nr, "polygon": room_pt(rect) if rect else None, "point": point} for nr, rect, point in specs]


def _read(sheet: FloorSheet, rooms, page: int = 1):
    return read_floor_coverings(build_floor_pdf([sheet]), page, rooms, m_per_pt=M_PER_PT)


@pytest.mark.parametrize("text,want", [
    ("plytelės", "plyteles"),
    ("120cm x 60cm plytelė, matinė", "plyteles"),
    ("Akmens masės plytelės", "plyteles"),
    ("laminuota grindų danga", "minksta"),
    ("Laminatas, ąžuolo sp.", "minksta"),
    ("SPC vinilinės grindys", "minksta"),
    ("Parketas, eglutės raštas", "minksta"),
    ("Grindys - ąžuolas, eglutės raštas 98,37 m2", "minksta"),
    ("Kiliminė danga", "minksta"),
    ("Grindjuostės (iš plytelių), h-8cm, 24,97m", None),
    ("Grindjuostės (derinamos prie durų arba grindų dangos)", None),
    ("Plytelių klojimo pradžios taškas", None),
    ("Šildomos grindys", None),
    ("Grindų šildymo kolektorius", None),
    ("Tarpai tarp plytelių 0.5 mm", None),
    ("GRINDŲ DANGŲ PLANAS", None),
    ("Miegamasis", None),
    ("", None),
])
def test_which_lines_name_a_covering(text, want):
    assert classify_line(text) == want


def test_the_floor_sheet_is_found_by_its_title():
    pdf = build_floor_pdf([
        FloorSheet(title="IŠDĖSTYMO PLANAS M 1:100"),
        FloorSheet(title="GRINDŲ DANGŲ PLANAS M 1:100"),
        FloorSheet(title="ŠILDOMŲ GRINDŲ PLANAS M 1:100"),
        FloorSheet(title="1A. GRINDŲ PLANAS M 1:50"),
        # a note on a wall-tile sheet is not a title (real project: two elevation sheets)
        FloorSheet(title="SIENŲ IŠKLOTINĖS", legend=[("4. Sienų plytelių siūles suvesti su grindų plytelių siūlėmis (vadovautis grindų planu).", BLACK)]),
    ])
    assert find_floor_sheets(pdf, [1, 2, 3, 4, 5]) == [2, 4]
    assert find_floor_sheets(pdf, [1, 3]) == []
    assert find_floor_sheets(b"not a pdf", [1]) == []


def test_a_covering_written_inside_the_room():
    sheet = FloorSheet(
        rooms=[LIVING, BATH],
        labels=[(["plytelės", "60X60cm", "13vnt.", "3.95 m²"], 5.6, 1.0, BLUE),
                (["laminuota", "grindų danga", "76,65 m²"], 1.8, 1.8, BLUE)])
    out = _read(sheet, _rooms(("01", LIVING, None), ("03", BATH, None)))
    bath, living = out["rooms"]["03"], out["rooms"]["01"]
    assert (bath["danga"], bath["irodymas"], bath["page"]) == ("plyteles", "uzrasas", 1)
    assert bath["plotas_m2"] == pytest.approx(3.95)
    assert bath["tekstas"].startswith("plytelės 60X60cm")
    x0, y0, x1, y1 = bath["rect_pct"]
    assert 0 < x0 < x1 < 1 and 0 < y0 < y1 < 1 and (x1 - x0) < 0.2       # the label, not the sheet
    assert (living["danga"], living["irodymas"]) == ("minksta", "uzrasas")
    assert living["plotas_m2"] == pytest.approx(76.65)


def test_a_label_does_not_leak_into_the_room_next_door():
    sheet = FloorSheet(rooms=[LIVING, BATH], labels=[(["plytelės", "3.95 m²"], 5.6, 1.0, BLUE)])
    out = _read(sheet, _rooms(("01", LIVING, None), ("03", BATH, None)))
    assert "01" not in out["rooms"] and out["rooms"]["03"]["danga"] == "plyteles"


def test_a_hatch_in_the_colour_of_its_legend_line():
    sheet = FloorSheet(
        rooms=[LIVING, BATH, HALL],
        hatches=[Hatch(LIVING, BROWN, "herringbone"), Hatch(BATH, ORANGE, "grid", (1.2, 0.6)),
                 Hatch(HALL, GREEN, "grid", (0.6, 0.6))],
        legend=[("Grindys - ąžuolas, eglutės raštas 98,37 m2", BROWN),
                ("120cm x 60cm plytelė, šviesi", ORANGE),
                ("60 x 60cm plytelė, matinė", GREEN)])
    out = _read(sheet, _rooms(("05", LIVING, None), ("07", BATH, None), ("01", HALL, None)))
    assert {nr: (r["danga"], r["irodymas"]) for nr, r in out["rooms"].items()} == {
        "05": ("minksta", "rastas"), "07": ("plyteles", "rastas"), "01": ("plyteles", "rastas")}
    assert out["rooms"]["05"]["tekstas"].startswith("Grindys - ąžuolas")
    assert [l["klase"] for l in out["legenda"]] == ["minksta", "plyteles", "plyteles"]
    # each key line carries its sheet and a box that reaches left over the swatch (W5-D D1)
    for line in out["legenda"]:
        assert line["page"] == out["page"] and len(line["rect_pct"]) == 4
        x0, y0, x1, y1 = line["rect_pct"]
        assert 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0
    # where to look: the room on the floor sheet
    x0, y0, x1, y1 = out["rooms"]["07"]["rect_pct"]
    assert x0 < (room_pt(BATH)[0][0] + 10) / 1190.55 < x1


def test_a_room_known_only_by_the_place_of_its_number():
    """An open plan's member (or a room whose outline was refused) has no
    polygon of its own — the hatch around its number answers."""
    sheet = FloorSheet(
        rooms=[(0.0, 0.0, 9.0, 4.0)],
        hatches=[Hatch((0.0, 0.0, 4.0, 4.0), GREEN, "grid"), Hatch((4.0, 0.0, 9.0, 4.0), BROWN, "herringbone")],
        legend=[("60 x 60cm plytelė", GREEN), ("Grindys - ąžuolas, eglutės raštas", BROWN)])
    out = _read(sheet, _rooms(("04", None, point_pt(2.0, 2.0)), ("05", None, point_pt(6.5, 2.0))))
    assert out["rooms"]["04"]["danga"] == "plyteles" and out["rooms"]["05"]["danga"] == "minksta"


def test_two_tile_colours_in_one_bathroom_are_still_tiles():
    sheet = FloorSheet(
        rooms=[BATH],
        hatches=[Hatch((5.2, 0.0, 7.2, 1.4), ORANGE, "grid", (1.2, 0.6)), Hatch((5.2, 1.4, 7.2, 2.4), BLUE, "grid", (1.2, 0.6))],
        legend=[("120cm x 60cm plytelė, šviesi", ORANGE), ("120cm x 60cm plytelė, rožinė", BLUE)])
    out = _read(sheet, _rooms(("08", BATH, None)))
    assert out["rooms"]["08"]["danga"] == "plyteles"


def test_two_kinds_of_covering_in_one_room_is_not_a_reading():
    sheet = FloorSheet(
        rooms=[LIVING],
        hatches=[Hatch((0.0, 0.0, 2.4, 4.0), GREEN, "grid"), Hatch((2.4, 0.0, 5.0, 4.0), BROWN, "herringbone")],
        legend=[("60 x 60cm plytelė", GREEN), ("Grindys - ąžuolas, eglutės raštas", BROWN)])
    out = _read(sheet, _rooms(("04", LIVING, None)))
    assert "04" not in out["rooms"]


def test_a_black_legend_is_not_a_colour_key():
    sheet = FloorSheet(rooms=[BATH], hatches=[Hatch(BATH, BLACK, "grid")], legend=[("60 x 60cm plytelė", BLACK)])
    assert _read(sheet, _rooms(("07", BATH, None)))["rooms"] == {}


def test_the_skirting_legend_is_not_a_covering():
    """Real sheet: green = „Grindjuostės (iš plytelių)", drawn along the walls."""
    sheet = FloorSheet(rooms=[LIVING], hatches=[Hatch(LIVING, GREEN, "edges")],
                       legend=[("Grindjuostės (iš plytelių), h-8cm, 24,97m", GREEN)])
    out = _read(sheet, _rooms(("01", LIVING, None)))
    assert out["rooms"] == {} and out["legenda"] == []


def test_lines_along_the_walls_do_not_make_a_hatch():
    """A covering's colour on a few lines at the room's edge is not the floor."""
    sheet = FloorSheet(rooms=[LIVING], hatches=[Hatch(LIVING, GREEN, "edges")], legend=[("60 x 60cm plytelė", GREEN)])
    assert _read(sheet, _rooms(("01", LIVING, None)))["rooms"] == {}


def test_the_heating_plan_is_not_a_covering():
    sheet = FloorSheet(rooms=[LIVING], hatches=[Hatch(LIVING, RED, "planks", (0.2, 0.2))], legend=[("Šildomos grindys", RED)])
    assert _read(sheet, _rooms(("01", LIVING, None)))["rooms"] == {}


def test_a_room_with_nothing_drawn_in_it_stays_a_question():
    sheet = FloorSheet(rooms=[LIVING, BATH], hatches=[Hatch(BATH, GREEN, "grid")], legend=[("60 x 60cm plytelė", GREEN)])
    out = _read(sheet, _rooms(("G", LIVING, None), ("07", BATH, None)))
    assert set(out["rooms"]) == {"07"}


def test_a_label_and_a_hatch_that_disagree_are_not_a_reading():
    sheet = FloorSheet(rooms=[BATH], hatches=[Hatch(BATH, BROWN, "herringbone")],
                       legend=[("Grindys - ąžuolas, eglutės raštas", BROWN)],
                       labels=[(["plytelės", "3.95 m²"], 5.6, 1.0, BLACK)])
    assert _read(sheet, _rooms(("07", BATH, None)))["rooms"] == {}


def test_an_unreadable_file_or_page_reads_nothing():
    assert read_floor_coverings(b"not a pdf", 1, _rooms(("01", LIVING, None))) == {
        "rooms": {}, "legenda": [], "dvi_dangos": {}, "page": 1}
    pdf = build_floor_pdf([FloorSheet(rooms=[LIVING])])
    assert read_floor_coverings(pdf, 9, _rooms(("01", LIVING, None)))["rooms"] == {}
    assert read_floor_coverings(pdf, 1, [])["rooms"] == {}


def test_a_raised_two_is_the_square_of_the_metre():
    """CAD writes „3.95 m" and a small raised „2" as two text runs; read line by
    line that is „2" above „3.95 m" — no area, and a quote nobody would write."""
    sheet = FloorSheet(rooms=[BATH], labels=[(["plytelės", "60X60cm", "13vnt.", "3.95 m^2"], 5.6, 1.0, BLUE)])
    got = _read(sheet, _rooms(("05", BATH, None)))["rooms"]["05"]
    assert got["plotas_m2"] == pytest.approx(3.95)
    assert got["tekstas"] == "plytelės 60X60cm 13vnt. 3.95 m²"


def test_two_coverings_written_in_one_room_are_reported_not_chosen():
    """Real sheet: the living room's label says laminate, the entrance part of
    the same room says tiles with their own area."""
    sheet = FloorSheet(rooms=[LIVING],
                       labels=[(["laminuota", "grindų danga", "76.65 m^2"], 1.0, 1.0, BLUE),
                               (["plytelės", "60X120cm", "7.01 m^2"], 3.4, 3.0, BLUE)])
    out = _read(sheet, _rooms(("01", LIVING, None)))
    assert "01" not in out["rooms"]
    assert out["dvi_dangos"]["01"] == ["laminuota grindų danga 76.65 m²", "plytelės 60X120cm 7.01 m²"]


def test_the_colour_the_labels_are_written_in_is_not_a_hatch_key():
    """A label OUTSIDE every room (a terrace) is written in the sheet's
    annotation colour — the colour of its dimension lines too. It is not a
    legend line, however many lines of that colour cross a room."""
    sheet = FloorSheet(rooms=[LIVING, BATH],
                       hatches=[Hatch(LIVING, BLUE, "grid", (0.5, 0.5))],            # dense blue „dimension" lines
                       labels=[(["plytelės", "3.95 m^2"], 5.6, 1.0, BLUE),            # in the bathroom
                               (["plytelės", "60X60cm", "10.48 m^2"], 8.5, 1.0, BLUE)])   # outside every room
    out = _read(sheet, _rooms(("01", LIVING, None), ("05", BATH, None)))
    assert set(out["rooms"]) == {"05"} and out["legenda"] == []


def test_dimension_strings_among_a_labels_lines_are_not_part_of_it():
    """Real sheet: a small room's label shares its space with „0.586", „2.630"."""
    sheet = FloorSheet(rooms=[BATH], labels=[(["plytelės", "60X60cm", "13vnt.", "3.95 m^2"], 5.6, 1.0, BLUE),
                                             (["0.586"], 5.9, 1.16, BLUE), (["2.630"], 6.3, 1.5, BLUE)])
    got = _read(sheet, _rooms(("05", BATH, None)))["rooms"]["05"]
    assert got["tekstas"] == "plytelės 60X60cm 13vnt. 3.95 m²" and got["plotas_m2"] == pytest.approx(3.95)


def test_a_vertical_dimension_string_does_not_end_up_in_a_label():
    """Its digits sit on the label's baselines by chance (real sheet: „13vnt. 5 0 3.95 m 0")."""
    sheet = FloorSheet(rooms=[BATH], labels=[(["plytelės", "60X60cm", "13vnt.", "3.95 m^2"], 5.5, 1.0, BLUE)],
                       vertical=[("0.586", 6.75, 2.0, BLUE), ("0.800", 5.35, 2.0, BLUE)])
    got = _read(sheet, _rooms(("05", BATH, None)))["rooms"]["05"]
    assert got["tekstas"] == "plytelės 60X60cm 13vnt. 3.95 m²"


def test_a_sheet_stored_sideways_is_read_the_way_it_is_displayed():
    """A landscape drawing stored in a portrait page with /Rotate 90: its labels are
    drawn sideways in the file and read left to right on screen. The reader works in
    the DISPLAYED frame — the room is given there, the label is found there."""
    import io

    import pypdfium2 as pdfium

    from extractor import pdf_vectors
    from synthetic_floor_plan import A3

    sheet = FloorSheet(rooms=[LIVING, BATH], vertical=[("plytelės 3.95 m2", 6.2, 2.0, BLUE)],      # drawn turned in the file…
                       labels=[(["laminuota grindų danga"], 1.0, 1.0, BLUE)])                      # …this one displays sideways
    doc = pdfium.PdfDocument(build_floor_pdf([sheet]))
    doc[0].set_rotation(90)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    W, H = A3

    def displayed(rect):
        # display-frame points (origin top-left) of the unrotated sheet → the page as displayed with /Rotate 90
        return [list(pdf_vectors._to_display(x, H - y, W, H, 1)) for x, y in room_pt(rect)]
    out = read_floor_coverings(buf.getvalue(), 1, [{"nr": "05", "polygon": displayed(BATH), "point": None},
                                                   {"nr": "01", "polygon": displayed(LIVING), "point": None}], m_per_pt=M_PER_PT)
    assert out["rooms"]["05"]["danga"] == "plyteles" and out["rooms"]["05"]["plotas_m2"] == pytest.approx(3.95)
    assert "01" not in out["rooms"]                      # text that displays sideways is not read as a label
    x0, y0, x1, y1 = out["rooms"]["05"]["rect_pct"]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
