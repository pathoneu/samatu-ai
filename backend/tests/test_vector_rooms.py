"""Room outlines from the vector walls: the free-space faces of the merged wall
solid once its openings are bridged; a face is a room when exactly one located
room lies inside and its area agrees with the table. Every case below was
first seen on a real sheet (objektas_g, objektas_h, 2026-09-19) and is
redrawn here with invented geometry."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import vector_rooms as vr  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402

SCALE = 1 / PT_PER_M           # metres per point at 1:100


def _at(x_m: float, y_m: float, saltinis: str = "zenkliukas") -> dict:
    return {"page": 1, "cx": (60 + x_m * PT_PER_M) / 595.2756, "cy": (80 + y_m * PT_PER_M) / 841.8898, "saltinis": saltinis}


def _locations():
    return {"01": _at(2.2, 1.5), "02": _at(5.7, 1.5)}


def test_two_rooms_are_traced_within_two_percent_of_their_areas():
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert set(out["rooms"]) == {"01", "02"}, out
    a = out["rooms"]["01"]
    b = out["rooms"]["02"]
    assert abs(a["plotas_m2"] - 12.0) / 12.0 <= 0.02 and abs(b["plotas_m2"] - 9.0) / 9.0 <= 0.02
    assert abs(a["perimetras_m"] - 14.0) <= 0.3 and abs(b["perimetras_m"] - 12.0) <= 0.3
    assert 4 <= len(a["polygon_pct"]) <= 8 and all(0 <= v <= 1 for p in a["polygon_pct"] for v in p)
    assert a["plotas_nesutampa"] is False and a["page"] == 1


def test_walls_exported_as_triangles_trace_the_same_rooms():
    """CAD exports fill a wall as triangles (objektas_h: 176 of them). A
    triangle's own axis points anywhere; the MERGED solid is what has walls."""
    sheet = two_rooms()
    sheet.triangulate = True
    out = vr.trace_vector_rooms(build_plan([sheet]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert set(out["rooms"]) == {"01", "02"}, out
    assert abs(out["rooms"]["01"]["plotas_m2"] - 12.0) / 12.0 <= 0.02


def test_the_outside_is_not_a_room_and_a_far_off_area_is_refused_but_proposed():
    """2026-09-23 (objektas_h tambūras: the walls close 2,86 m² around the number, the table says 4,48): the face
    is not taken as the room — but it is PROPOSED, with the reason said as walls vs table, so that a person can
    say „Tinka" instead of guessing where to click."""
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 30.0, "02": 9.0}, SCALE)
    assert "01" not in out["rooms"] and out["reasons"]["01"] == "sienos prie numerio uždaro 12,00 m², lentelėje 30,00 m²"
    assert "02" in out["rooms"] and "02" not in out["siulymai"]
    cand = out["siulymai"]["01"]
    assert abs(cand["plotas_m2"] - 12.0) / 12.0 <= 0.02 and abs(cand["perimetras_m"] - 14.0) <= 0.3 and cand["page"] == 1
    assert 0.59 < cand["paklaida"] < 0.61 and len(cand["polygon_pct"]) >= 4
    from shapely.geometry import Point, Polygon
    assert Polygon(cand["polygon_pct"]).contains(Point(cand["taskas_pct"]))     # „Tinka" clicks here for him


def test_a_table_that_is_a_little_off_keeps_the_outline_and_says_so():
    """objektas_h: the designer moved partitions and kept the architect's
    areas — room 07 is drawn 4,04 m², listed 4,90 m². The outline is the
    room's; the disagreement is shown, not hidden."""
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 13.8, "02": 9.0}, SCALE)   # 12 drawn, −13 %
    assert out["rooms"]["01"]["plotas_nesutampa"] is True and 0.12 < out["rooms"]["01"]["paklaida"] < 0.14
    assert out["rooms"]["02"]["plotas_nesutampa"] is False


def test_an_open_plan_is_a_group_not_an_invented_cut():
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if not (abs(w[0] - 4.2) < 0.01)]     # remove the partition
    out = vr.trace_vector_rooms(build_plan([sheet]), 1, _locations(), {"01": 12.6, "02": 9.0}, SCALE)   # 7,2 × 3,0 = 21,6 together
    assert out["rooms"] == {}
    assert "atvira erdvė" in out["reasons"]["01"] and "02" in out["reasons"]["01"]
    assert len(out["groups"]) == 1
    g = out["groups"][0]
    assert g["nariai"] == ["01", "02"] and abs(g["plotas_m2"] - 21.6) < 0.4 and abs(g["lenteles_suma_m2"] - 21.6) < 0.01
    assert len(g["polygon_pct"]) >= 4


def test_no_walls_means_a_reason_not_a_crash():
    out = vr.trace_vector_rooms(build_plan([Sheet(badges=[("1", 1, 1)])]), 1, _locations(), {"01": 12.0}, SCALE)
    assert out["rooms"] == {} and out["reasons"]["01"] == "nėra vektorinių sienų"


def test_a_room_whose_walls_do_not_close_gets_a_reason():
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if w[1] != 0.0]          # drop the top wall: rooms open to the outside
    out = vr.trace_vector_rooms(build_plan([sheet]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out["rooms"] == {}
    assert all("neuždaro" in r for r in out["reasons"].values()), out["reasons"]


def _box(x0, y0, x1, y1, t=0.2, gaps=()):
    """The four walls of a box whose INNER faces are x0…x1 × y0…y1; `gaps` are
    (side, from, to) openings along a side's own axis ("top"/"bottom": x, "left"/"right": y)."""
    def pieces(a0, a1, side):
        cuts = sorted((g[1], g[2]) for g in gaps if g[0] == side)
        out, cur = [], a0
        for c0, c1 in cuts:
            if c0 > cur:
                out.append((cur, c0))
            cur = c1
        if cur < a1:
            out.append((cur, a1))
        return out
    walls = []
    walls += [(a, y0 - t, b, y0) for a, b in pieces(x0 - t, x1 + t, "top")]
    walls += [(a, y1, b, y1 + t) for a, b in pieces(x0 - t, x1 + t, "bottom")]
    walls += [(x0 - t, a, x0, b) for a, b in pieces(y0, y1, "left")]
    walls += [(x1, a, x1 + t, b) for a, b in pieces(y0, y1, "right")]
    return walls


def test_a_door_between_two_corners_is_closed():
    """objektas_h room 11: the door stands between the corner of one wall box
    and the corner of the next — no wall END faces it, two wall FACES do."""
    walls = [(1.0, 0.0, 3.2, 0.2), (1.0, 1.9, 3.2, 2.1), (1.0, 0.0, 1.2, 2.1), (3.0, 0.0, 3.2, 2.1)]   # a closed box, 1,8 × 1,7 m inside
    walls += [(3.0, -0.2, 7.2, 0.0), (7.0, -0.2, 7.2, 3.2), (3.0, 3.0, 7.2, 3.2)]   # the room to its right: top, right, bottom
    # the room's left side is the box's wall down to y = 2,1, then a 0,9 m door
    # between the box's bottom face and the bottom wall's top face (they overlap 0,2 m)
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"01": _at(2.1, 1.05), "02": _at(5.0, 1.5)},
                                {"01": 3.06, "02": 11.4}, SCALE)
    assert set(out["rooms"]) == {"01", "02"}, out["reasons"]
    assert abs(out["rooms"]["02"]["plotas_m2"] - 11.4) < 0.3


def test_a_window_in_a_thin_outside_wall_is_closed():
    """objektas_h: outside walls 0,2 m thick with 2 m windows — thickness cannot
    decide what may be bridged; two wall ENDS facing each other do."""
    walls = _box(0, 0, 4, 3, gaps=(("top", 1.0, 3.0),))
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"01": _at(2, 1.5)}, {"01": 12.0}, SCALE)
    assert "01" in out["rooms"], out["reasons"]
    assert abs(out["rooms"]["01"]["plotas_m2"] - 12.0) < 0.3


def test_a_short_wall_piece_facing_the_wall_opposite_is_not_a_door():
    """objektas_h room 10 (1,09 m wide): the 0,5 m of wall beside its door
    faces the wall across the room at door distance. That is the room, not an
    opening — an opening has free space on both of its sides."""
    walls = _box(0, 0, 1.1, 2.4, gaps=(("left", 0.5, 1.4),))             # a 0,9 m door, 0,5 m from the corner
    walls += _box(-3.2, 0, -0.2, 2.4, gaps=(("right", 0.5, 1.4),))       # the room the door opens to
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls, offset_m=(3.5, 0))]), 1,
                                {"10": _at(3.5 + 0.55, 1.2), "09": _at(3.5 - 1.7, 1.2)}, {"10": 2.64, "09": 7.2}, SCALE)
    assert "10" in out["rooms"], out["reasons"]
    assert abs(out["rooms"]["10"]["plotas_m2"] - 2.64) < 0.15


def test_an_opening_without_a_door_joins_the_two_parts_the_table_counts_as_one_room():
    """objektas_g room 01: the kitchen is reached through a 1,15 m opening with
    no door. Every gap that narrow is bridged, so the room arrives in two
    faces; the part without a room of its own is added when that is what makes
    the area agree with the table."""
    walls = _box(0, 0, 4, 3, gaps=(("right", 1.0, 2.15),)) + _box(4.2, 0, 6.2, 3, gaps=(("left", 1.0, 2.15),))
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"01": _at(2, 1.5)}, {"01": 18.2}, SCALE)
    assert "01" in out["rooms"], out["reasons"]
    assert abs(out["rooms"]["01"]["plotas_m2"] - 18.2) < 0.5 and out["rooms"]["01"]["sujungta"] == 2


def test_a_part_is_not_added_when_the_room_already_agrees():
    walls = _box(0, 0, 4, 3, gaps=(("right", 1.0, 2.15),)) + _box(4.2, 0, 6.2, 3, gaps=(("left", 1.0, 2.15),))
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"01": _at(2, 1.5)}, {"01": 12.0}, SCALE)
    assert abs(out["rooms"]["01"]["plotas_m2"] - 12.0) < 0.3 and out["rooms"]["01"]["sujungta"] == 1


def test_a_room_located_only_by_visions_box_does_not_break_the_room_it_lands_in():
    """objektas_g: room 07 had no label, and Vision's box put it inside room 06."""
    locs = {"01": _at(2.2, 1.5), "02": _at(5.7, 1.5), "07": _at(2.6, 2.0, "bbox")}
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, locs, {"01": 12.0, "02": 9.0, "07": 5.0}, SCALE)
    assert {"01", "02"} <= set(out["rooms"])
    assert "07" not in out["rooms"] and "pateko į patalpą 01" in out["reasons"]["07"]


def test_a_location_on_a_doorway_takes_the_parts_on_both_sides():
    """objektas_g room 05: the area label sits in the opening between the
    room's two parts."""
    walls = _box(0, 0, 2, 2, gaps=(("right", 0.5, 1.5),)) + _box(2.2, 0, 3.4, 2, gaps=(("left", 0.5, 1.5),))
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"05": _at(2.1, 1.0, "plotas_uzrasas")}, {"05": 6.6}, SCALE)
    assert "05" in out["rooms"], out["reasons"]
    assert abs(out["rooms"]["05"]["plotas_m2"] - 6.6) < 0.3


def test_a_wider_opening_is_bridged_only_for_rooms_the_narrow_limit_left_open():
    """objektas_h rooms 08 | 09: a 1,4 m opening (a demolished wall, now a door
    and a glass screen drawn as lines). objektas_g room 01 must NOT be cut at
    1,6 m — so the wider limit is a second pass, for the rooms still open."""
    # the partition stops 1,4 m short of the bottom wall: a wall END facing a wall FACE
    # (two ENDS facing each other would be a window, bridged at any width)
    walls = [w for w in _box(0, 0, 6.2, 3)] + [(4.0, 0.0, 4.2, 1.6)]
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"09": _at(2, 1.5), "08": _at(5.2, 1.5)},
                                {"09": 12.0, "08": 6.0}, SCALE)
    assert set(out["rooms"]) == {"08", "09"}, out["reasons"]
    assert out["rooms"]["09"]["durys_m"] == 1.6 and out["groups"] == []
    # …and a room the narrow limit already solved keeps that outline
    solved = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert solved["rooms"]["01"]["durys_m"] == 1.25


# ── the openings the wall solid shows (2026-09-20) ───────────────────────────
# The door-and-window fact was the one fact with no evidence on the drawing („brėžinys jų vietos
# nenurodo"), while the solid the outlines are traced from already knows every gap in every wall.

def _opening_to(room: dict, other: str) -> dict:
    hits = [a for a in room["angos"] if a["i"] == other]
    assert len(hits) == 1, room["angos"]
    return hits[0]


def test_a_rooms_openings_say_how_wide_they_are_and_where_they_lead():
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    one, two = out["rooms"]["01"], out["rooms"]["02"]
    assert [a["i"] for a in one["angos"]] == ["02"]
    assert sorted(a["i"] for a in two["angos"]) == ["01", "laukas"]
    door = _opening_to(one, "02")
    assert abs(door["plotis_m"] - 0.9) <= 0.03 and abs(door["storis_m"] - 0.2) <= 0.03
    assert abs(_opening_to(two, "laukas")["plotis_m"] - 0.9) <= 0.03
    # the same door, seen from the other room, is the same place
    assert _opening_to(two, "01")["line_pct"] == door["line_pct"]


def test_an_openings_line_crosses_the_gap_on_the_walls_axis():
    """The partition is 0,2 m thick at x = 4,2…4,4 m, its door at y = 1,0…1,9 m."""
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    (x0, y0), (x1, y1) = _opening_to(out["rooms"]["01"], "02")["line_pct"]
    fx = lambda m: (60 + m * PT_PER_M) / 595.2756            # noqa: E731
    fy = lambda m: (80 + m * PT_PER_M) / 841.8898            # noqa: E731
    assert abs(x0 - fx(4.3)) < 0.002 and abs(x1 - fx(4.3)) < 0.002
    assert sorted([round(y0, 3), round(y1, 3)]) == sorted([round(fy(1.0), 3), round(fy(1.9), 3)])


def test_an_opening_inside_one_room_is_not_an_opening_of_it():
    """Two parts the table counts as ONE room are joined through their opening — that gap is inside the room."""
    walls = _box(0, 0, 4, 3, gaps=(("right", 1.0, 2.15),)) + _box(4.2, 0, 6.2, 3, gaps=(("left", 1.0, 2.15),))
    out = vr.trace_vector_rooms(build_plan([Sheet(walls=walls)]), 1, {"01": _at(2, 1.5)}, {"01": 18.2}, SCALE)
    assert out["rooms"]["01"]["sujungta"] == 2
    assert out["rooms"]["01"]["angos"] == []


def test_an_opening_to_a_space_without_an_outline_of_its_own_says_so():
    """The neighbour exists (an interior face) but has no room standing in it — not the outside."""
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, {"01": _at(2.2, 1.5)}, {"01": 12.0}, SCALE)
    assert [a["i"] for a in out["rooms"]["01"]["angos"]] == ["vidus"]


def test_openings_for_an_outline_that_came_from_elsewhere():
    """A raster-traced or hand-corrected outline sits a little off the wall face; its openings are still read."""
    fx = lambda m: (60 + m * PT_PER_M) / 595.2756            # noqa: E731
    fy = lambda m: (80 + m * PT_PER_M) / 841.8898            # noqa: E731
    inset = 0.06                                              # metres inside the wall face, all round
    one = [[fx(0.2 + inset), fy(0.2 + inset)], [fx(4.2 - inset), fy(0.2 + inset)], [fx(4.2 - inset), fy(3.2 - inset)], [fx(0.2 + inset), fy(3.2 - inset)]]
    two = [[fx(4.4 + inset), fy(0.2 + inset)], [fx(7.4 - inset), fy(0.2 + inset)], [fx(7.4 - inset), fy(3.2 - inset)], [fx(4.4 + inset), fy(3.2 - inset)]]
    out = vr.wall_openings(build_plan([two_rooms()]), 1, {"01": one, "02": two}, SCALE)
    assert [a["i"] for a in out["01"]] == ["02"]
    assert sorted(a["i"] for a in out["02"]) == ["01", "laukas"]
    assert vr.wall_openings(build_plan([Sheet(walls=[])]), 1, {"01": one}, SCALE) == {}
    assert vr.wall_openings(build_plan([two_rooms()]), 1, {}, SCALE) == {}


def test_an_opening_in_a_thin_partition_still_leads_somewhere_else():
    """A 6 cm partition at 1:100 is thinner than the tolerance a foreign outline is looked up with: the
    far side of its door is "near" the very room the door belongs to. Two sides of one opening are the
    same room only when both truly lie INSIDE it; otherwise the nearer side keeps the room."""
    walls = [(-0.2, -0.2, 7.2, 0.0), (-0.2, 3.0, 7.2, 3.2), (-0.2, 0.0, 0.0, 3.0), (7.0, 0.0, 7.2, 3.0),
             (4.0, 0.0, 4.06, 1.0), (4.0, 1.9, 4.06, 3.0)]
    fx = lambda m: (60 + m * PT_PER_M) / 595.2756            # noqa: E731
    fy = lambda m: (80 + m * PT_PER_M) / 841.8898            # noqa: E731
    one = [[fx(0.0), fy(0.0)], [fx(4.0), fy(0.0)], [fx(4.0), fy(3.0)], [fx(0.0), fy(3.0)]]
    out = vr.wall_openings(build_plan([Sheet(walls=walls)]), 1, {"01": one}, SCALE)
    assert [(a["i"], a["plotis_m"]) for a in out["01"]] == [("vidus", 0.9)]
    two = [[fx(4.06), fy(0.0)], [fx(7.0), fy(0.0)], [fx(7.0), fy(3.0)], [fx(4.06), fy(3.0)]]
    both = vr.wall_openings(build_plan([Sheet(walls=walls)]), 1, {"01": one, "02": two}, SCALE)
    assert [a["i"] for a in both["01"]] == ["02"] and [a["i"] for a in both["02"]] == ["01"]


def test_an_outline_that_reaches_over_the_wall_does_not_take_the_neighbours_side():
    """A hand-drawn outline often runs along the wall's far face. The side of the door that lies inside
    BOTH outlines belongs to the one it lies deeper in."""
    fx = lambda m: (60 + m * PT_PER_M) / 595.2756            # noqa: E731
    fy = lambda m: (80 + m * PT_PER_M) / 841.8898            # noqa: E731
    one = [[fx(0.2), fy(0.2)], [fx(4.45), fy(0.2)], [fx(4.45), fy(3.2)], [fx(0.2), fy(3.2)]]     # over the partition, 5 cm into 02
    two = [[fx(4.4), fy(0.2)], [fx(7.4), fy(0.2)], [fx(7.4), fy(3.2)], [fx(4.4), fy(3.2)]]
    out = vr.wall_openings(build_plan([two_rooms()]), 1, {"01": one, "02": two}, SCALE)
    assert [a["i"] for a in out["01"]] == ["02"]
    assert sorted(a["i"] for a in out["02"]) == ["01", "laukas"]


# ── the room a PERSON points at (2026-09-20) ─────────────────────────────────
# Patikra could only show WHY a room has no outline; one click inside the room now gives it the face of
# the wall solid under the click. The person is the authority on which room it is — the table's area is
# only compared, never a reason to refuse — but a click never takes another room's space.

def _pct(x_m: float, y_m: float) -> tuple[float, float]:
    return (60 + x_m * PT_PER_M) / 595.2756, (80 + y_m * PT_PER_M) / 841.8898


def test_a_click_inside_a_room_gives_its_outline():
    x, y = _pct(2.0, 2.5)                                  # anywhere in room 1, not where its badge stands
    out = vr.outline_at(build_plan([two_rooms()]), 1, x, y, 12.0, SCALE)
    assert out["status"] == "ok" and out["page"] == 1
    assert abs(out["plotas_m2"] - 12.0) / 12.0 <= 0.02 and abs(out["perimetras_m"] - 14.0) <= 0.3
    assert out["paklaida"] <= 0.02 and 4 <= len(out["polygon_pct"]) <= 8


def test_the_tables_area_is_compared_not_obeyed():
    x, y = _pct(2.0, 2.5)
    off = vr.outline_at(build_plan([two_rooms()]), 1, x, y, 17.0, SCALE)          # the table says 17, the walls close 12
    assert off["status"] == "ok" and abs(off["plotas_m2"] - 12.0) < 0.3 and 0.28 < off["paklaida"] < 0.31
    blank = vr.outline_at(build_plan([two_rooms()]), 1, x, y, None, SCALE)        # no area in the table at all
    assert blank["status"] == "ok" and blank["paklaida"] is None


def test_a_click_never_takes_another_rooms_space():
    two = [list(_pct(4.4, 0.2)), list(_pct(7.4, 0.2)), list(_pct(7.4, 3.2)), list(_pct(4.4, 3.2))]
    x, y = _pct(5.5, 1.0)
    out = vr.outline_at(build_plan([two_rooms()]), 1, x, y, 12.0, SCALE, others_pct={"02": two})
    assert out == {"status": "taken", "nr": "02"}


def test_a_click_outside_the_walls_or_on_a_sheet_without_walls():
    x, y = _pct(-2.0, 1.0)
    assert vr.outline_at(build_plan([two_rooms()]), 1, x, y, 12.0, SCALE) == {"status": "outside"}
    assert vr.outline_at(build_plan([Sheet(walls=[])]), 1, 0.5, 0.5, 12.0, SCALE) == {"status": "no_walls"}


def test_a_space_the_walls_do_not_divide_is_not_given_to_one_room():
    """An open plan: the walls close 21 m² and the table gives this room 9 — the outline would be two rooms'."""
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if abs(w[0] - 4.2) > 0.01]              # no partition between the two rooms
    x, y = _pct(2.0, 1.5)
    out = vr.outline_at(build_plan([sheet]), 1, x, y, 9.0, SCALE)
    assert out["status"] == "open" and abs(out["plotas_m2"] - 21.6) < 0.6 and out["su"] == []
    # …and whatever the areas say, a space another room's printed number stands in is shared
    sx, sy = _pct(5.7, 1.5)
    shared = vr.outline_at(build_plan([sheet]), 1, x, y, 21.0, SCALE, other_seats_pct={"02": (sx, sy)})
    assert shared["status"] == "open" and shared["su"] == ["02"]


def test_a_click_is_one_space_unless_taking_the_next_one_in_explains_the_table():
    """objektas_g room 01: the kitchen behind a doorless 1,15 m opening belongs to the living room — the
    table's area says so. A neighbour that merely brings the area CLOSER is not taken in."""
    walls = _box(0, 0, 4, 3, gaps=(("right", 1.0, 2.15),)) + _box(4.2, 0, 6.2, 3, gaps=(("left", 1.0, 2.15),))
    x, y = _pct(2.0, 1.5)
    both = vr.outline_at(build_plan([Sheet(walls=walls)]), 1, x, y, 18.2, SCALE)
    assert both["status"] == "ok" and both["sujungta"] == 2 and both["paklaida"] <= 0.08
    one = vr.outline_at(build_plan([Sheet(walls=walls)]), 1, x, y, 15.5, SCALE)       # 12 → 18,2 would be closer, not right
    assert one["status"] == "ok" and one["sujungta"] == 1 and abs(one["plotas_m2"] - 12.0) < 0.3


# ── two rooms no wall separates, divided by ONE line a person draws (2026-09-21) ─────────────
# A kitchen and a living room are usually the biggest rooms of a flat and share one space. The lane says
# so and gives each an ESTIMATE (the shared walls by floor area). Only a person knows where one room ends.

def _open_plan() -> Sheet:
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if abs(w[0] - 4.2) > 0.01]              # no partition: one space 7,2 × 3 m
    return sheet


def _seats():
    return {"01": _pct(2.2, 1.5), "02": _pct(5.7, 1.5)}


def test_a_line_between_the_two_numbers_gives_each_room_its_own_outline():
    a, b = _pct(4.3, 0.1), _pct(4.3, 3.3)                                         # drawn a little past both walls
    out = vr.split_space(build_plan([_open_plan()]), 1, a, b, _seats(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out["status"] == "ok" and set(out["rooms"]) == {"01", "02"}
    one, two = out["rooms"]["01"], out["rooms"]["02"]
    assert abs(one["plotas_m2"] - 4.1 * 3.0) < 0.3 and abs(two["plotas_m2"] - 3.1 * 3.0) < 0.3
    assert one["page"] == 1 and len(one["polygon_pct"]) == 4
    # the boundary between them is NOT a wall: one imaginary edge each, the same place, left out of the perimeter
    assert len(one["menamos"]) == 1 and len(two["menamos"]) == 1
    (p, q), = one["menamos"]
    fx = (60 + 4.3 * PT_PER_M) / 595.2756
    assert abs(p[0] - fx) < 0.002 and abs(q[0] - fx) < 0.002
    assert abs(one["perimetras_m"] - (4.1 + 3.0 + 4.1)) < 0.2 and abs(two["perimetras_m"] - (3.1 + 3.0 + 3.1)) < 0.2
    assert one["paklaida"] is not None and one["paklaida"] < 0.05


def test_a_line_that_does_not_separate_the_two_numbers_is_refused():
    a, b = _pct(6.8, 0.1), _pct(6.8, 3.3)                                         # both numbers stay on its left
    out = vr.split_space(build_plan([_open_plan()]), 1, a, b, _seats(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out == {"status": "bad_line"}


def test_a_line_outside_the_shared_space_or_a_space_of_three():
    pdf = build_plan([_open_plan()])
    far = vr.split_space(pdf, 1, _pct(-3.0, 0.1), _pct(-3.0, 3.3), _seats(), {"01": 12.0, "02": 9.0}, SCALE)
    assert far == {"status": "bad_line"}
    apart = vr.split_space(build_plan([two_rooms()]), 1, _pct(4.3, 0.1), _pct(4.3, 3.3), _seats(), {}, SCALE)
    assert apart == {"status": "not_shared"}                                       # a wall already separates them
    three = {**_seats(), "03": _pct(3.6, 2.6)}
    assert vr.split_space(pdf, 1, _pct(4.3, 0.1), _pct(4.3, 3.3), three, {}, SCALE) == {"status": "too_many"}
    assert vr.split_space(build_plan([Sheet(walls=[])]), 1, (0.4, 0.2), (0.4, 0.6), _seats(), {}, SCALE) == {"status": "no_walls"}


def test_a_sliver_the_line_cuts_off_a_niche_goes_to_the_room_it_touches():
    """objektas_h: the line between kitchen and living room runs through a small recess in a wall stub and
    leaves a 0,1 m² third piece. That is not a bad line — the sliver belongs to the room it touches most."""
    sheet = _open_plan()
    # a stub hanging from the top wall at x 4,2…4,8 m down to y = 1,3 m, with a 0,4 × 0,5 m recess on its left side
    sheet.walls = sheet.walls + [(4.6, 0.2, 4.8, 1.3), (4.2, 0.2, 4.6, 0.5), (4.2, 1.0, 4.6, 1.3)]
    a, b = _pct(4.3, 0.1), _pct(4.3, 3.3)                                         # through the recess: 0,15 m² cut off
    out = vr.split_space(build_plan([sheet]), 1, a, b, _seats(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out["status"] == "ok", out
    total = out["rooms"]["01"]["plotas_m2"] + out["rooms"]["02"]["plotas_m2"]
    assert abs(total - (7.2 * 3.0 - 0.6 * 1.1 + 0.4 * 0.5)) < 0.1                  # nothing of the space is lost


def test_the_space_is_the_one_whose_area_agrees_with_the_two_rooms():
    """objektas_h: at the narrow door limit a 1,4 m opening stays open and the „space" is 71 m² with a
    neighbour in it; at the wider limit it is the 60 m² the two rooms add up to."""
    sheet = _open_plan()
    # room 3 beyond the right wall; that wall stops 1,4 m short of the bottom wall — an opening between a wall
    # END and a wall FACE, wider than the first door limit
    sheet.walls = [w for w in sheet.walls if abs(w[0] - 7.4) > 0.01] + [(7.4, 0.0, 7.6, 1.8),
                                                                         (7.6, 0.0, 10.8, 0.2), (7.6, 3.2, 10.8, 3.4), (10.6, 0.0, 10.8, 3.4)]
    out = vr.split_space(build_plan([sheet]), 1, _pct(4.3, 0.1), _pct(4.3, 3.3), _seats(), {"01": 12.3, "02": 9.3}, SCALE)
    assert out["status"] == "ok"
    assert abs(out["rooms"]["02"]["plotas_m2"] - 3.1 * 3.0) < 0.4                  # not 9,3 + the 9 m² of room 3


# ── the boundary the PROGRAM proposes for such a space (2026-09-21) ───────────────────────────────────
# Founder, after dividing a real kitchen and living room himself: „pasidaro apibrėžimas, bet nėra
# instrukcijų — tik tu ir aš jas žinom". Nobody can know where a boundary with no wall „should" be; what is
# known is the two areas the table gives. So the program proposes the line and the person says „Tinka".

def test_the_proposed_boundary_divides_the_space_by_the_tables_areas():
    out = vr.propose_split(build_plan([_open_plan()]), 1, _seats(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out["status"] == "ok" and out["pagal"] == "plotai" and set(out["rooms"]) == {"01", "02"}
    one, two = out["rooms"]["01"], out["rooms"]["02"]
    assert abs(one["plotas_m2"] / two["plotas_m2"] - 12.0 / 9.0) < 0.03          # 7,2 × 3 m shared in the table's ratio
    assert one["paklaida"] < 0.05 and two["paklaida"] < 0.05
    (x0, y0), (x1, y1) = out["line_pct"]
    assert abs(x0 - x1) < 1e-4 and abs(y0 - y1) > 0.05                            # the numbers stand side by side → an upright line
    assert len(one["menamos"]) == 1 and len(two["menamos"]) == 1                  # …which is never a wall
    assert abs(one["perimetras_m"] + two["perimetras_m"] - (7.2 * 2 + 3.0 * 2)) < 0.3


def test_a_wall_end_between_the_two_numbers_is_the_natural_boundary():
    sheet = _open_plan()
    sheet.walls = sheet.walls + [(4.2, 0.2, 4.4, 1.0)]                            # a stub of the old partition hangs from the top wall
    out = vr.propose_split(build_plan([sheet]), 1, _seats(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out["status"] == "ok" and out["pagal"] == "kampas"
    x = out["line_pct"][0][0] * 595.2756
    faces = [60 + 4.2 * PT_PER_M, 60 + 4.4 * PT_PER_M]
    assert min(abs(x - f) for f in faces) < 1.5                                   # along one face of the stub
    assert all(r["paklaida"] <= 0.08 for r in out["rooms"].values())
    # The line runs ALONG the stub's face for 0,8 m and only then through open space. The face stays a real
    # wall of the room beside it: what is imaginary is the 2,2 m below the stub — for both rooms alike — and
    # no wall is lost (objektas_h, measured: the face was dropped from both rooms, 36,77 m of 37,77).
    for room in out["rooms"].values():
        (p, q), = room["menamos"]
        assert abs(abs(p[1] - q[1]) * 841.8898 / PT_PER_M - 2.2) < 0.1
    walls = sum(r["perimetras_m"] for r in out["rooms"].values())
    assert abs(walls - (2 * (7.2 + 3.0) + 2 * 0.8)) < 0.25


def test_rooms_one_above_the_other_get_a_level_boundary():
    walls = _box(0, 0, 3, 7.2)
    seats = {"01": _pct(1.5, 2.0), "02": _pct(1.5, 5.6)}
    out = vr.propose_split(build_plan([Sheet(walls=walls)]), 1, seats, {"01": 12.0, "02": 9.0}, SCALE)
    assert out["status"] == "ok"
    (x0, y0), (x1, y1) = out["line_pct"]
    assert abs(y0 - y1) < 1e-4 and abs(x0 - x1) > 0.05
    assert abs(out["rooms"]["01"]["plotas_m2"] / out["rooms"]["02"]["plotas_m2"] - 12.0 / 9.0) < 0.03


def test_no_table_areas_means_an_even_split_and_nothing_to_propose_is_said():
    out = vr.propose_split(build_plan([_open_plan()]), 1, _seats(), {}, SCALE)
    assert out["status"] == "ok"
    assert abs(out["rooms"]["01"]["plotas_m2"] - out["rooms"]["02"]["plotas_m2"]) < 0.4
    assert vr.propose_split(build_plan([two_rooms()]), 1, _seats(), {}, SCALE) == {"status": "not_shared"}
    three = {**_seats(), "03": _pct(3.6, 2.6)}
    assert vr.propose_split(build_plan([_open_plan()]), 1, three, {}, SCALE) == {"status": "too_many"}
    assert vr.propose_split(build_plan([Sheet(walls=[])]), 1, _seats(), {}, SCALE) == {"status": "no_walls"}
    level = {"01": _pct(2.2, 1.5), "02": _pct(2.2, 1.5)}                          # both numbers in one place: no line separates them
    assert vr.propose_split(build_plan([_open_plan()]), 1, level, {"01": 12.0, "02": 9.0}, SCALE) == {"status": "no_proposal"}


def test_a_pocket_that_the_table_gives_more_than_its_walls_close_joins_its_neighbours_face():
    """objektas_h tambūras, 2026-09-23: the walls close 2,86 m² around the number, the table says 4,48 — the rest
    is a strip of the corridor's face beyond a doorless opening, with an imaginary boundary. When a boundary leaves
    BOTH rooms within the table's tolerance, the two are ONE shared space to divide (the pocket is no proposal any
    more); when it cannot, the pocket stays a proposal and the neighbour keeps its face."""
    from tests.synthetic_plan import pocket_and_room
    where = {"01": _at(0.7, 1.5), "02": _at(4.0, 1.5)}
    out = vr.trace_vector_rooms(build_plan([pocket_and_room()]), 1, where, {"01": 4.5, "02": 13.5}, SCALE)
    assert "01" not in out["rooms"] and "02" not in out["rooms"] and out["siulymai"] == {}
    assert "atvira erdvė su 02" in out["reasons"]["01"] and "atvira erdvė su 01" in out["reasons"]["02"]
    (g,) = out["groups"]
    assert g["nariai"] == ["01", "02"] and g["kisene"] == "01" and abs(g["plotas_m2"] - 18.2) < 0.3 and g["lenteles_suma_m2"] == 18.0
    # the boundary the lane will divide it by: through the joined space, both parts within the table
    cut = vr.propose_split(build_plan([pocket_and_room()]), 1, {nr: (v["cx"], v["cy"]) for nr, v in where.items()},
                           {"01": 4.5, "02": 13.5}, SCALE, face_pct=g["polygon_pct"])
    assert cut["status"] == "ok" and cut["pagal"] == "plotai"
    assert abs(cut["rooms"]["01"]["plotas_m2"] - 4.5) / 4.5 <= 0.08 and abs(cut["rooms"]["02"]["plotas_m2"] - 13.5) / 13.5 <= 0.08
    assert len(cut["rooms"]["01"]["menamos"]) == 1 and len(cut["rooms"]["02"]["menamos"]) == 1
    # the table agrees with the walls: no joining, two ordinary rooms
    plain = vr.trace_vector_rooms(build_plan([pocket_and_room()]), 1, where, {"01": 3.0, "02": 15.0}, SCALE)
    assert set(plain["rooms"]) == {"01", "02"} and plain["groups"] == []
    # the table gives the pocket far more than the neighbour can spare: the pocket stays a proposal
    greedy = vr.trace_vector_rooms(build_plan([pocket_and_room()]), 1, where, {"01": 9.0, "02": 15.0}, SCALE)
    assert "02" in greedy["rooms"] and "01" in greedy["siulymai"] and greedy["groups"] == []


def test_the_joined_space_of_a_pocket_and_a_neighbours_outline_is_one_outline():
    from tests.synthetic_plan import pocket_and_room
    pdf = build_plan([pocket_and_room()])
    where = {"01": _at(0.7, 1.5), "02": _at(4.0, 1.5)}
    plain = vr.trace_vector_rooms(pdf, 1, where, {"01": 3.0, "02": 15.0}, SCALE)
    union = vr.joined_space(pdf, 1, (where["01"]["cx"], where["01"]["cy"]), plain["rooms"]["02"]["polygon_pct"], SCALE)
    from shapely.geometry import Point, Polygon
    poly = Polygon(union)
    assert poly.is_valid and 4 <= len(union) <= 20
    for nr in ("01", "02"):
        assert poly.contains(Point(where[nr]["cx"], where[nr]["cy"]))
    # a seat that does not sit in a pocket beside that outline: nothing to join
    assert vr.joined_space(pdf, 1, (where["02"]["cx"], where["02"]["cy"]), plain["rooms"]["02"]["polygon_pct"], SCALE) is None
