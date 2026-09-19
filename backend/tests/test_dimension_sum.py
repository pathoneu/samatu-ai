"""Perimeter = the sum of the dimension strings written along the room's
walls; the outline only says which strings are this room's walls and checks
the sum. The rules were measured on objektas_h's wall painting plan
(2026-09-19): a wall's string runs corner to corner (its line ends within
0,02 m of the wall's ends) and usually sits 0,11–0,22 m inside the room, but
the designer moves it up to ~1 m away when the wall is crowded — so the ENDS
decide, not the distance. Synthetic drawings only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor import plan_dimensions as pdim  # noqa: E402
from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402

SCALE = {1: 1 / PT_PER_M, 2: 1 / PT_PER_M}
W_PT, H_PT = 595.2756, 841.8898


def _outline(nr, pts_m, **extra):
    """A room whose traced outline is the polygon `pts_m` (metres on the synthetic sheet)."""
    xs = [p[0] for p in pts_m]
    ys = [p[1] for p in pts_m]
    area = abs(sum(pts_m[i][0] * pts_m[(i + 1) % len(pts_m)][1] - pts_m[(i + 1) % len(pts_m)][0] * pts_m[i][1]
                   for i in range(len(pts_m)))) / 2
    room = {"nr": nr, "plotas_m2": round(area, 2), "puslapio_nr": 1, "polygon_source": "vektoriniai_konturai",
            "_konturas": {"page": 1, "plotas_nesutampa": False},
            "polygon_pct": [[(60 + x * PT_PER_M) / W_PT, (80 + y * PT_PER_M) / H_PT] for x, y in pts_m]}
    assert min(xs) >= -2 and min(ys) >= -2
    room.update(extra)
    return room


def _room(nr, x0, y0, x1, y1, **extra):
    return _outline(nr, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **extra)


def _run(sheets, rooms, pages=(1,)):
    pdf = build_plan(sheets)
    dims = pdim.read_dimension_strings(pdf, pages=list(pages))
    return ds.sum_perimeters(rooms, dims, sa.align_sheets(pdf, list(pages)), SCALE)


def test_every_wall_dimensioned_gives_a_stated_perimeter():
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2), _room("02", 4.4, 0.2, 7.4, 3.2)]
    out = _run([two_rooms()], rooms)
    r1, r2 = rooms
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes", r1.get("_sienos")
    assert r2["perimetras_m"] == 12.0
    assert len(r1["_sienos"]) == 4 and all(s["ilgis_m"] and s["saltinis"] == "eilute" for s in r1["_sienos"])
    assert sorted(e["text"] for s in r1["_sienos"] for e in s["eilutes"]) == ["3000", "3000", "4000", "4000"]
    suma = r1["_perimetras_suma"]
    assert suma["sutampa"] is True and suma["suma_m"] == 14.0 and abs(suma["kontrole_m"] - 14.0) < 0.1 and suma["is_konturo_m"] == 0
    assert out["stated"] == ["01", "02"] and out["blank"] == []


def test_a_wall_without_a_string_leaves_the_perimeter_blank_with_the_outline_estimate():
    sheet = two_rooms()
    # neither of room 1's 3 m walls is written — nor the partition's other side
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and min(abs(d[1] - x) for x in (0.35, 4.05, 4.55)) < 1e-6)]
    sheet.dims.append(("2000", 9.0, 5.0, 9.0, 7.0))                   # elsewhere: the reader wants 8 characters per text direction
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    out = _run([sheet], rooms)
    r = rooms[0]
    # not read — an ESTIMATE the sheet shows as a blank; it is still a number, the sąmata rows are built from it
    assert r["perimetras_saltinis"] == "konturo_ivertis" and r["perimetras_m"] == r["_perimetras_ivertis_m"]
    assert "2 iš 4 sienų be matmens" in r["_perimetras_priezastis"]
    assert abs(r["_perimetras_ivertis_m"] - 14.0) < 0.2 and r["_perimetras_ivertis_saltinis"] == "konturas"
    assert [s["ilgis_m"] for s in r["_sienos"]].count(None) == 2 and out["blank"] == ["01"]


def test_strings_on_an_aligned_second_sheet_count():
    a = two_rooms()
    a.dims = []                                       # the layout sheet has no wall lengths…
    b = two_rooms()
    b.badges = []                                     # …the painting plan has them
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([a, b], rooms, pages=(1, 2))
    assert rooms[0]["perimetras_m"] == 14.0 and rooms[0]["_perimetras_suma"]["lapai"] == [2]


def test_a_stated_or_user_perimeter_is_never_overwritten():
    r = _room("01", 0.2, 0.2, 4.2, 3.2, perimetras_m=99.0, perimetras_saltinis="user_override")
    out = _run([two_rooms()], [r])
    assert r["perimetras_m"] == 99.0 and out["skipped"] == ["01"] and "_sienos" not in r


def test_a_box_outline_is_not_good_enough_to_assign_strings():
    r = _room("01", 0.2, 0.2, 4.2, 3.2, polygon_source="synthesized_from_bbox")
    out = _run([two_rooms()], [r])
    assert "perimetras_m" not in r and out["skipped"] == ["01"]


def test_a_furniture_string_beside_the_wall_is_not_the_walls_length():
    """objektas_h's layout sheet: 91 of 109 strings are furniture sizes, many
    of them parallel to a wall and closer to it than the wall's own string."""
    sheet = two_rooms()
    sheet.dims.append(("1500", 0.5, 0.28, 2.0, 0.28))            # a wardrobe along room 1's top wall, 0,08 m off it
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    assert rooms[0]["perimetras_m"] == 14.0
    assert "1500" not in [e["text"] for s in rooms[0]["_sienos"] for e in s["eilutes"]]


def test_a_chain_of_strings_states_the_wall_it_runs_along():
    """A partition plan dimensions a wall in pieces — corner to door, the door, door to corner."""
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "4000" and abs(d[2] - 0.35) < 1e-6)]      # room 1's top string out…
    sheet.dims += [("1200", 0.2, 0.35, 1.4, 0.35), ("900", 1.4, 0.35, 2.3, 0.35), ("1900", 2.3, 0.35, 4.2, 0.35)]   # …a chain in
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    top = rooms[0]["_sienos"][0]
    assert rooms[0]["perimetras_m"] == 14.0 and top["ilgis_m"] == 4.0
    assert [e["text"] for e in top["eilutes"]] == ["1200", "900", "1900"]


def test_a_chain_with_a_hole_in_it_does_not_state_the_wall():
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if d[0] != "4000"]                                         # neither 4 m wall has its string…
    sheet.dims += [("1200", 0.2, 0.35, 1.4, 0.35), ("1900", 2.3, 0.35, 4.2, 0.35)]                 # …and the chain's 0,9 m middle is not written
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    assert rooms[0]["perimetras_saltinis"] == "konturo_ivertis" and rooms[0]["_sienos"][0]["ilgis_m"] is None


def test_a_string_moved_away_from_a_crowded_wall_still_states_it():
    """objektas_h: „2445" is written 0,94 m from its wall; its line still runs corner to corner."""
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "4000" and abs(d[2] - 0.35) < 1e-6)]
    sheet.dims.append(("4000", 0.2, 1.1, 4.2, 1.1))                # 0,9 m into the room
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    assert rooms[0]["perimetras_m"] == 14.0


def test_a_string_that_runs_past_the_walls_corners_is_not_its_length():
    """An architect's outside chain measures to the wall axes: „4300" over a
    wall that is 4,00 m long inside. Close is not the wall's length."""
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if d[0] != "4000"]
    sheet.dims.append(("4300", 0.05, 0.35, 4.35, 0.35))
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    assert rooms[0]["perimetras_saltinis"] == "konturo_ivertis" and "2 iš 4 sienų be matmens" in rooms[0]["_perimetras_priezastis"]


def test_a_short_jog_nobody_dimensioned_is_taken_from_the_outline_and_said_so():
    """objektas_g room 01: a 0,15 m step in the outline. There is no number to
    read for it; it is counted from the outline and disclosed."""
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and abs(d[1] - 4.05) < 1e-6)]      # room 1's right wall string out…
    sheet.dims += [("1400", 4.05, 0.2, 4.05, 1.6), ("1600", 3.9, 1.6, 3.9, 3.2)]                   # …two pieces, either side of a jog
    jog = [(0.2, 0.2), (4.2, 0.2), (4.2, 1.6), (4.05, 1.6), (4.05, 3.2), (0.2, 3.2)]
    sheet.dims = [d for d in sheet.dims if not (d[0] == "4000" and abs(d[2] - 3.05) < 1e-6)]      # the bottom wall is 3,85 m now
    sheet.dims.append(("3850", 0.2, 3.05, 4.05, 3.05))
    rooms = [_outline("01", jog)]
    _run([sheet], rooms)
    r = rooms[0]
    assert r["perimetras_saltinis"] == "matmenu_eilutes", (r.get("_perimetras_priezastis"), r.get("_sienos"))
    assert r["perimetras_m"] == 14.0 and r["_perimetras_suma"]["is_konturo_m"] == 0.15
    assert [s["saltinis"] for s in r["_sienos"]].count("konturas") == 1


def test_an_outline_that_disagrees_with_the_table_states_nothing():
    """Table or outline — one of them is wrong, and a sum along the wrong walls
    would look exact. Blank, with the estimate and the reason."""
    r = _room("01", 0.2, 0.2, 4.2, 3.2)
    r["_konturas"]["plotas_nesutampa"] = True
    out = _run([two_rooms()], [r])
    assert r["perimetras_saltinis"] == "konturo_ivertis" and "nesutampa su lentele" in r["_perimetras_priezastis"]
    assert abs(r["_perimetras_ivertis_m"] - 14.0) < 0.2 and out["blank"] == ["01"]


def test_a_slanted_wall_has_no_string_the_reader_can_read():
    sheet = two_rooms()
    cut = [(0.2, 0.2), (3.2, 0.2), (4.2, 1.2), (4.2, 3.2), (0.2, 3.2)]                             # the top-right corner cut at 45°
    rooms = [_outline("01", cut)]
    _run([sheet], rooms)
    assert rooms[0]["perimetras_saltinis"] == "konturo_ivertis"
    assert "įstriž" in rooms[0]["_perimetras_priezastis"]


def test_rows_on_different_sheets_are_different_rows():
    """objektas_h room 02: the layout sheet dimensions a worktop „1189 | 397"
    on exactly the line where the painting plan writes the wall's „1586". Read
    as one row they overlap and state nothing; each sheet's row is its own —
    and the wall's single string is preferred to a chain that adds up to it."""
    a = two_rooms()
    a.dims = [("2500", 0.2, 0.35, 2.7, 0.35), ("1500", 2.7, 0.35, 4.2, 0.35)]      # sheet 1: a chain on the same line
    b = two_rooms()
    b.badges = []
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([a, b], rooms, pages=(1, 2))
    top = rooms[0]["_sienos"][0]
    assert rooms[0]["perimetras_m"] == 14.0 and [e["text"] for e in top["eilutes"]] == ["4000"]


def test_a_row_that_fits_the_corners_loosely_but_not_the_length_is_not_the_walls():
    """objektas_g room 06: a 0,95 m wall took a door's „0.800" — each end was
    inside the corner tolerance, the length was 16 % off. A short wall needs
    its length to agree too."""
    sheet = two_rooms()
    sheet.dims.append(("800", 4.27, 1.0, 4.27, 1.8))              # a door dimension in the partition's thickness
    nook = [(0.2, 0.2), (4.2, 0.2), (4.2, 0.95), (4.35, 0.95), (4.35, 1.85), (4.2, 1.85), (4.2, 3.2), (0.2, 3.2)]   # the door recess, 0,9 m
    rooms = [_outline("01", nook)]
    _run([sheet], rooms)
    recess = next(s for s in rooms[0]["_sienos"] if abs(s["kontrole_m"] - 0.9) < 0.02)
    assert recess["ilgis_m"] is None, recess


def test_a_wall_written_once_states_the_equal_wall_opposite():
    """Designers rarely write a length twice. The wall opposite, with the same
    extent, is as long — its number is read for both, and the sheet says so."""
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "4000" and abs(d[2] - 3.05) < 1e-6)]       # room 1's bottom string out
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and abs(d[1] - 4.05) < 1e-6)]       # …and its right one
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and abs(d[1] - 4.55) < 1e-6)]       # …and the one beyond the partition
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    r = rooms[0]
    assert r["perimetras_m"] == 14.0 and r["perimetras_saltinis"] == "matmenu_eilutes"
    assert sorted(s["saltinis"] for s in r["_sienos"]) == ["eilute", "eilute", "priesinga_siena", "priesinga_siena"]
    assert r["_perimetras_suma"]["pakartota"] == 2


def test_the_wall_opposite_is_not_borrowed_when_it_is_not_the_same_length():
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and abs(d[1] - 4.05) < 1e-6)]       # no string on the right side…
    sheet.dims = [d for d in sheet.dims if not (d[0] == "4000" and abs(d[2] - 0.35) < 1e-6)] + [("3000", 0.2, 0.35, 3.2, 0.35)]
    cut = [(0.2, 0.2), (3.2, 0.2), (3.2, 1.2), (4.2, 1.2), (4.2, 3.2), (0.2, 3.2)]                 # …which is 2 m here, 3 m on the left
    rooms = [_outline("01", cut)]
    _run([sheet], rooms)
    right = next(s for s in rooms[0]["_sienos"] if abs(s["kontrole_m"] - 2.0) < 0.02)
    assert right["ilgis_m"] is None and rooms[0]["perimetras_saltinis"] == "konturo_ivertis"


def test_an_estimate_is_tried_again_on_the_next_run_and_replaced_when_the_walls_can_be_read():
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and min(abs(d[1] - x) for x in (0.35, 4.05, 4.55)) < 1e-6)]
    sheet.dims.append(("2000", 9.0, 5.0, 9.0, 7.0))
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([sheet], rooms)
    assert rooms[0]["perimetras_saltinis"] == "konturo_ivertis"
    out = _run([two_rooms()], rooms)                       # a later run reads every wall
    assert out["stated"] == ["01"] and rooms[0]["perimetras_m"] == 14.0 and rooms[0]["perimetras_saltinis"] == "matmenu_eilutes"
    assert "_perimetras_priezastis" not in rooms[0]


def test_every_read_string_says_where_it_is_written_on_its_own_sheet():
    """The check sheet marks the very numbers that were added — on the sheet
    they are written on, which need not be the sheet the outline was traced on."""
    a = two_rooms()
    a.dims = []
    b = two_rooms()
    b.badges = []
    b.offset_m = (1.0, -0.5)                                   # the painting plan is drawn 1 m right, 0,5 m up
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    _run([a, b], rooms, pages=(1, 2))
    top = rooms[0]["_sienos"][0]
    assert rooms[0]["perimetras_m"] == 14.0 and [e["page"] for e in top["eilutes"]] == [2]
    (x0, y0), (x1, y1) = top["eilutes"][0]["line_pct"]
    # on sheet 2 the string's line runs from x = 0,2+1 m to 4,2+1 m at y = 0,35−0,5 m
    assert abs(min(x0, x1) - (60 + 1.2 * PT_PER_M) / W_PT) < 0.002 and abs(max(x0, x1) - (60 + 5.2 * PT_PER_M) / W_PT) < 0.002
    assert abs(y0 - (80 - 0.15 * PT_PER_M) / H_PT) < 0.002 and abs(y0 - y1) < 1e-6
    left = next(s for s in rooms[0]["_sienos"] if s["eilutes"] and abs(s["eilutes"][0]["line_pct"][0][0] - s["eilutes"][0]["line_pct"][1][0]) < 1e-6)
    assert abs(left["eilutes"][0]["line_pct"][0][1] - left["eilutes"][0]["line_pct"][1][1]) > 0.05      # a vertical line
    # a borrowed wall shows the string it borrowed — with the same place
    assert all(e.get("line_pct") for s in rooms[0]["_sienos"] for e in s["eilutes"])


def test_only_wall_exact_or_human_outlines_assign_strings():
    """objektas_g room 07 (local demo, 2026-09-19): a ragged browser flood-fill
    outline — 45 edges, 23 of them slanted — produced „45 iš 45 sienų be
    matmens" and an estimate from its jagged length. Such an outline is a place
    on the plan, not the room's walls."""
    r = _room("01", 0.2, 0.2, 4.2, 3.2, polygon_source="auto_floodfill", perimetras_m=13.9)
    out = _run([two_rooms()], [r])
    assert out["skipped"] == ["01"] and r["perimetras_m"] == 13.9 and "_sienos" not in r
    for source in ("vektoriniai_konturai", "sienu_konturas", "corrected", "manual"):
        ok = _room("01", 0.2, 0.2, 4.2, 3.2, polygon_source=source)
        assert _run([two_rooms()], [ok])["stated"] == ["01"], source
