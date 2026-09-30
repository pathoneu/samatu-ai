"""One call turns a parsed extraction into located rooms, vector outlines and
summed perimeters — without Vision. Synthetic drawings only."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import geometry_lane as gl  # noqa: E402
from tests.synthetic_plan import build_plan, pocket_and_room, two_rooms  # noqa: E402


def _parsed(**room1):
    r1 = {"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
          "perimetras_m": 13.9, "bbox_pct": {"x": 0.12, "y": 0.10, "w": 0.2, "h": 0.12},
          "polygon_pct": [[0.12, 0.10], [0.32, 0.10], [0.32, 0.22], [0.12, 0.22]], "polygon_source": "synthesized_from_bbox"}
    r1.update(room1)
    return {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}],
            "patalpos": [r1, {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija",
                              "puslapio_nr": 1, "perimetras_m": 12.3}]}


def _two_sheets():
    a = two_rooms()
    a.dims = []                        # the layout sheet: badges, no wall lengths
    b = two_rooms()
    b.badges = []                      # the wall painting plan: wall lengths, no badges
    return build_plan([a, b])


def test_lane_locates_traces_and_sums_on_a_two_sheet_plan():
    parsed = _parsed()
    out = gl.apply_geometry(parsed, _two_sheets())
    r1, r2 = parsed["patalpos"]
    assert r1["_vieta"]["saltinis"] == "zenkliukas"
    assert r1["polygon_source"] == "vektoriniai_konturai" and abs(r1["_konturas"]["plotas_m2"] - 12.0) / 12.0 <= 0.02
    assert r1["_konturas"]["page"] == 1 and r1["_konturas"]["plotas_nesutampa"] is False
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"
    assert r1["_perimetras_pries_geometrija"] == 13.9            # what Vision had said, kept for the record
    assert r2["perimetras_m"] == 12.0
    g = parsed["_meta"]["geometrija"]
    assert g["vietos"] == {"zenkliukas": 2} and g["konturai"] == ["01", "02"] and g["perimetrai_sudeti"] == ["01", "02"]
    assert g["grupes"] == [[1, 2]] and out["status"] == "applied"


def test_lane_is_harmless_on_a_pdf_without_vectors_or_text():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.showPage()
    c.showPage()
    c.save()
    parsed = _parsed()
    out = gl.apply_geometry(parsed, buf.getvalue())
    r1 = parsed["patalpos"][0]
    assert out["status"] in ("insufficient", "no_match")
    assert r1["perimetras_m"] == 13.9 and r1["polygon_source"] == "synthesized_from_bbox"     # untouched
    assert "_perimetras_ivertis_m" not in r1


def test_an_outline_someone_corrected_is_kept_and_its_walls_are_still_summed():
    corrected = [[(60 + x * 28.3465) / 595.2756, (80 + y * 28.3465) / 841.8898] for x, y in ((0.2, 0.2), (4.2, 0.2), (4.2, 3.2), (0.2, 3.2))]
    parsed = _parsed(polygon_pct=corrected, polygon_source="corrected")
    gl.apply_geometry(parsed, _two_sheets())
    r1 = parsed["patalpos"][0]
    assert r1["polygon_source"] == "corrected" and r1["polygon_pct"] == corrected
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"


def test_a_perimeter_the_user_entered_is_never_touched():
    parsed = _parsed(perimetras_m=15.5, perimetras_saltinis="user_override")
    gl.apply_geometry(parsed, _two_sheets())
    assert parsed["patalpos"][0]["perimetras_m"] == 15.5 and parsed["patalpos"][0]["perimetras_saltinis"] == "user_override"


def test_an_open_plan_names_its_members_and_offers_the_shared_walls_as_an_estimate(monkeypatch):
    """When NO boundary can be proposed (2026-09-23: otherwise the lane divides the space itself, see
    test_a_two_room_open_plan_is_divided_by_the_lane_itself…) the shared walls are offered as an estimate."""
    monkeypatch.setattr(gl, "propose_split", lambda *a, **k: {"status": "no_proposal"})
    a = two_rooms()                                                 # (its strings give the sheet a scale)
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]       # no partition: one space, two rooms in the table
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][0]["plotas_m2"] = 12.6
    out = gl.apply_geometry(parsed, build_plan([a]))
    assert out["ribos"] == [] and out["ribos_nepasiulytos"] == [["01", "02"]]
    r1, r2 = parsed["patalpos"]
    assert r1["polygon_source"] == "synthesized_from_bbox" and "atvira erdvė su 02" in r1["_konturo_priezastis"]
    erdve = r1["_atvira_erdve"]
    assert erdve["nariai"] == ["01", "02"] and abs(erdve["perimetras_m"] - 20.4) < 0.4 and len(erdve["polygon_pct"]) >= 4
    assert parsed["_meta"]["geometrija"]["atviros_erdves"] == [["01", "02"]]
    # The walls of the shared space are real; what each room's share of them is, is not written anywhere.
    # objektas_h, 2026-09-19: with the two rooms' guessed perimeters the painted walls came to 340 m², with
    # the shared outline split by area to 320,3 m² — the designer's own legend says 320 m².
    assert r1["perimetras_saltinis"] == "atviros_erdves_ivertis" and r2["perimetras_saltinis"] == "atviros_erdves_ivertis"
    assert r1["perimetras_m"] == r1["_perimetras_ivertis_m"]          # a number the rows are built from; the SOURCE says estimate
    assert r1["_perimetras_ivertis_saltinis"] == "atviros_erdves_konturas" and r1["_perimetras_pries_geometrija"] == 13.9
    assert abs(r1["_perimetras_ivertis_m"] + r2["_perimetras_ivertis_m"] - erdve["perimetras_m"]) < 0.02
    assert abs(r1["_perimetras_ivertis_m"] / r2["_perimetras_ivertis_m"] - 12.6 / 9.0) < 0.01
    assert "atvira erdvė su 02" in r1["_perimetras_priezastis"] and "20," in r1["_perimetras_priezastis"]


def test_an_open_plan_member_whose_perimeter_someone_stated_keeps_it():
    a = two_rooms()
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]
    parsed = _parsed(perimetras_m=15.5, perimetras_saltinis="user_override")
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    gl.apply_geometry(parsed, build_plan([a]))
    r1, r2 = parsed["patalpos"]
    assert r1["perimetras_m"] == 15.5 and r1["perimetras_saltinis"] == "user_override" and "_perimetras_ivertis_m" not in r1
    # the space is still divided (the outline is geometry, not his number) and the OTHER room's walls are read
    assert r1["_konturas"]["saltinis"] == "padalinta_programos" and r2["_konturas"]["saltinis"] == "padalinta_programos"
    assert r2["perimetras_saltinis"] in ("matmenu_eilutes", "konturo_ivertis") and r2["perimetras_m"] > 0


def test_the_lane_never_raises():
    parsed = _parsed()
    out = gl.apply_geometry(parsed, b"not a pdf")
    assert out["status"] in ("insufficient", "no_match", "failed")


def test_rooms_located_on_different_sheets_of_one_plan_meet_on_the_sheet_that_is_traced():
    """objektas_g: eight rooms carry their area label on one sheet, the ninth
    only Vision's box on another. They are the same plan — the box must land
    in its neighbour's face there, not be judged alone on its own sheet."""
    parsed = _parsed()
    parsed["patalpos"].append({"nr": "07", "pavadinimas": "C", "plotas_m2": 12.0, "puslapio_nr": 2,
                               "bbox_pct": {"x": (60 + 1.2 * 28.3465) / 595.2756, "y": (80 + 1.0 * 28.3465) / 841.8898, "w": 0.05, "h": 0.03}})
    gl.apply_geometry(parsed, _two_sheets())
    r7 = parsed["patalpos"][2]
    assert r7.get("polygon_source") != "vektoriniai_konturai"
    assert "pateko į patalpą 01" in r7["_konturo_priezastis"]


def test_an_outline_traced_on_a_sheet_that_is_not_a_plan_still_gets_its_walls_read():
    """objektas_g rooms 02, 03: the raster lane traced them on the plumbing
    plan. That sheet has to be read for strings and aligned like the others."""
    corrected = [[(60 + x * 28.3465) / 595.2756, (80 + y * 28.3465) / 841.8898] for x, y in ((0.2, 0.2), (4.2, 0.2), (4.2, 3.2), (0.2, 3.2))]
    parsed = _parsed(polygon_pct=corrected, polygon_source="sienu_konturas", perimetras_saltinis="sienu_konturas",
                     _konturas={"page": 2, "plotas_m2": 12.0, "perimetras_m": 13.98})
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "plumbing"}]
    gl.apply_geometry(parsed, _two_sheets())
    r1 = parsed["patalpos"][0]
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"
    assert r1["_perimetras_pries_geometrija"] == 13.9


def test_a_sheet_the_classifier_called_something_else_still_gives_its_wall_strings():
    """objektas_g, run 2 (2026-09-10): the dimensioned sheet was classified as
    something other than a plan and every wall was lost. Alignment — the same
    walls in the same place — decides what belongs to the plan, not the label."""
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "electrical"}]
    gl.apply_geometry(parsed, _two_sheets())
    r1 = parsed["patalpos"][0]
    assert r1["perimetras_m"] == 14.0 and r1["_perimetras_suma"]["lapai"] == [2]


def test_nothing_the_lane_writes_for_the_sheet_is_developer_speak():
    """Reasons end up on the check sheet. The 2026-09-04 trust guard bans
    pipeline words there; the lane's own strings must pass it."""
    from extractor.user_text import is_banned
    parsed = _parsed()
    parsed["patalpos"].append({"nr": "07", "pavadinimas": "C", "plotas_m2": 12.0, "puslapio_nr": 2,
                               "bbox_pct": {"x": (60 + 1.2 * 28.3465) / 595.2756, "y": (80 + 1.0 * 28.3465) / 841.8898, "w": 0.05, "h": 0.03}})
    parsed["patalpos"][1]["plotas_m2"] = 30.0                     # far from the 9 m² drawn: refused with a reason
    gl.apply_geometry(parsed, _two_sheets())
    said = [str(r.get(k)) for r in parsed["patalpos"] for k in ("_konturo_priezastis", "_perimetras_priezastis") if r.get(k)]
    assert len(said) >= 2 and not [s for s in said if is_banned(s)], said
    assert all("." not in s.split("m²")[0][-5:] for s in said if "m²" in s), said      # decimal commas


def test_running_the_lane_twice_changes_nothing_the_second_time():
    import copy
    parsed = _parsed()
    a = two_rooms()
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]       # an open plan: estimates, the case that could drift
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    pdf = build_plan([a])
    gl.apply_geometry(parsed, pdf)
    once = copy.deepcopy(parsed["patalpos"])
    gl.apply_geometry(parsed, pdf)
    for before, after in zip(once, parsed["patalpos"]):
        for key in ("perimetras_m", "perimetras_saltinis", "_perimetras_ivertis_m", "_perimetras_pries_geometrija", "polygon_source"):
            assert before.get(key) == after.get(key), (before["nr"], key)


def test_the_lane_says_how_the_plans_sheets_lie_over_each_other():
    """So the room's outline can be shown on the sheet its numbers are written on."""
    a = two_rooms()
    a.dims = []
    b = two_rooms()
    b.badges = []
    b.offset_m = (1.0, -0.5)
    parsed = _parsed()
    gl.apply_geometry(parsed, build_plan([a, b]))
    lapai = parsed["_meta"]["geometrija"]["sutapdinimas"]
    assert lapai["1"] == {"base": 1, "k": 1.0, "kx": 1.0, "ky": 1.0, "dx_pct": 0.0, "dy_pct": 0.0}
    two = lapai["2"]                       # base_pct = k{x,y} · sheet_pct + d{x,y}_pct
    assert two["base"] == 1 and abs(two["k"] - 1.0) < 0.01 and abs(two["kx"] - 1.0) < 0.01
    assert abs(two["dx_pct"] + 28.3465 / 595.2756) < 0.003 and abs(two["dy_pct"] - 0.5 * 28.3465 / 841.8898) < 0.003


# ── the floor covering, read off the floor plan (2026-09-20) ─────────────────

GREEN = (0.07, 0.61, 0.28)
BLUE = (0.0, 0.0, 1.0)


def _with_floor_sheet(floor):
    a = two_rooms()
    a.dims = []                        # the layout sheet: badges, no wall lengths
    b = two_rooms()
    b.badges = []                      # the wall painting plan: wall lengths, no badges
    floor.badges, floor.dims, floor.furniture = [], [], []
    floor.title = "GRINDŲ DANGŲ PLANAS M 1:100"
    parsed = _parsed()
    parsed["puslapiai"].append({"nr": 3, "tipas": "floor_plan"})
    return parsed, build_plan([a, b, floor])


def test_the_floor_plan_says_which_covering_a_room_gets():
    floor = two_rooms()
    floor.texts = [("plytelės", 5.2, 1.4, BLUE), ("60X60cm", 5.2, 1.65, BLUE), ("8,95 m2", 5.2, 1.9, BLUE)]
    parsed, pdf = _with_floor_sheet(floor)
    out = gl.apply_geometry(parsed, pdf)
    r1, r2 = parsed["patalpos"]
    assert r2["grindu_danga"] == "plyteles" and r2["grindu_danga_saltinis"] == "grindu_planas"
    ev = r2["_grindu_danga"]
    assert ev["page"] == 3 and ev["irodymas"] == "uzrasas" and ev["plotas_m2"] == 8.95 and ev["danga"] == "plyteles"
    assert ev["tekstas"].startswith("plytelės 60X60cm") and len(ev["rect_pct"]) == 4
    assert "grindu_danga" not in r1                               # nothing is written there: stays a question
    g = parsed["_meta"]["geometrija"]["grindu_dangos"]
    assert g["lapai"] == [3] and g["perskaityta"] == {"02": "plyteles"}
    assert out["grindu_dangos"]["perskaityta"] == {"02": "plyteles"}


def test_a_hatch_in_its_legend_colour_is_read_through_the_rooms_outline():
    floor = two_rooms()
    floor.hatches = [(4.4, 0.2, 7.4, 3.2, GREEN, 0.6)]
    floor.legend = [("60 x 60cm plytelė", GREEN)]
    parsed, pdf = _with_floor_sheet(floor)
    gl.apply_geometry(parsed, pdf)
    r1, r2 = parsed["patalpos"]
    assert r2["grindu_danga"] == "plyteles" and r2["_grindu_danga"]["irodymas"] == "rastas"
    assert "grindu_danga" not in r1


def test_his_own_choice_of_covering_is_never_overwritten():
    floor = two_rooms()
    floor.texts = [("plytelės", 5.2, 1.4, BLUE)]
    parsed, pdf = _with_floor_sheet(floor)
    parsed["patalpos"][1].update({"grindu_danga": "minksta", "grindu_danga_saltinis": "user_override"})
    gl.apply_geometry(parsed, pdf)
    r2 = parsed["patalpos"][1]
    assert r2["grindu_danga"] == "minksta" and r2["grindu_danga_saltinis"] == "user_override"
    # …but what the floor plan draws there is kept beside it, so the sheet can say the two differ
    assert r2["_grindu_danga"]["danga"] == "plyteles" and r2["_grindu_danga"]["page"] == 3


def test_a_reading_that_is_gone_on_the_next_run_is_taken_back():
    parsed, pdf = _with_floor_sheet(two_rooms())                   # a floor sheet that says nothing
    parsed["patalpos"][1].update({"grindu_danga": "plyteles", "grindu_danga_saltinis": "grindu_planas",
                                  "_grindu_danga": {"page": 3}})
    gl.apply_geometry(parsed, pdf)
    r2 = parsed["patalpos"][1]
    assert "grindu_danga" not in r2 and "_grindu_danga" not in r2 and "grindu_danga_saltinis" not in r2


def test_two_coverings_written_in_one_room_are_put_on_the_room_as_a_note():
    floor = two_rooms()
    floor.texts = [("laminuota grindų danga", 0.6, 1.0, BLUE), ("plytelės 7,01 m2", 2.6, 2.6, BLUE)]
    parsed, pdf = _with_floor_sheet(floor)
    gl.apply_geometry(parsed, pdf)
    r1 = parsed["patalpos"][0]
    assert "grindu_danga" not in r1
    assert r1["_grindu_dangos_dvi"] == {"page": 3, "tekstai": ["laminuota grindų danga", "plytelės 7,01 m2"]}


def test_without_a_floor_sheet_nothing_about_floors_is_written():
    parsed = _parsed()
    gl.apply_geometry(parsed, _two_sheets())
    assert all("grindu_danga" not in r for r in parsed["patalpos"])
    assert parsed["_meta"]["geometrija"]["grindu_dangos"] == {"lapai": [], "perskaityta": {}, "dvi_dangos": []}


# ── the openings the wall solid shows (2026-09-20) ───────────────────────────

def test_a_traced_room_carries_the_openings_in_its_walls():
    parsed = _parsed()
    gl.apply_geometry(parsed, _two_sheets())
    r1, r2 = parsed["patalpos"]
    assert r1["_angos_sienose"]["page"] == 1
    assert [(a["i"], a["plotis_m"]) for a in r1["_angos_sienose"]["angos"]] == [("02", 0.9)]
    assert sorted(a["i"] for a in r2["_angos_sienose"]["angos"]) == ["01", "laukas"]


def test_an_outline_someone_corrected_gets_its_openings_too():
    corrected = [[(60 + x * 28.3465) / 595.2756, (80 + y * 28.3465) / 841.8898] for x, y in ((0.25, 0.25), (4.15, 0.25), (4.15, 3.15), (0.25, 3.15))]
    parsed = _parsed(polygon_pct=corrected, polygon_source="corrected")
    gl.apply_geometry(parsed, _two_sheets())
    r1 = parsed["patalpos"][0]
    assert r1["polygon_source"] == "corrected"
    assert [a["i"] for a in r1["_angos_sienose"]["angos"]] == ["02"]


def test_a_room_without_an_outline_has_no_openings_and_a_stale_record_is_dropped():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.showPage()
    c.showPage()
    c.save()
    parsed = _parsed(_angos_sienose={"page": 1, "angos": [{"i": "02", "plotis_m": 0.9}]})
    gl.apply_geometry(parsed, buf.getvalue())
    assert "_angos_sienose" not in parsed["patalpos"][0]


def test_a_neighbour_outlined_on_another_sheet_of_the_plan_is_still_named():
    """objektas_g: the raster lane left every room's outline on a different sheet of the same plan, so
    each room's openings led to a space „without an outline". Every trusted outline of the plan is laid
    onto the sheet that is read; what is written back is in the room's OWN outline's frame."""
    a = two_rooms()
    a.dims = []
    b = two_rooms()
    b.badges = []
    b.offset_m = (0.5, 0.3)                                      # the same plan, drawn elsewhere on its sheet
    fx = lambda m: (60 + (m + 0.5) * 28.3465) / 595.2756       # noqa: E731
    fy = lambda m: (80 + (m + 0.3) * 28.3465) / 841.8898       # noqa: E731
    corrected = [[fx(x), fy(y)] for x, y in ((0.2, 0.2), (4.2, 0.2), (4.2, 3.2), (0.2, 3.2))]
    parsed = _parsed(polygon_pct=corrected, polygon_source="corrected", puslapio_nr=2)
    gl.apply_geometry(parsed, build_plan([a, b]))
    r1, r2 = parsed["patalpos"]
    assert r2["polygon_source"] == "vektoriniai_konturai" and r2["_konturas"]["page"] == 1
    assert r1["_angos_sienose"]["page"] == 2
    (door,) = r1["_angos_sienose"]["angos"]
    assert door["i"] == "02" and door["plotis_m"] == 0.9
    (x0, y0), (x1, y1) = door["line_pct"]
    assert abs(x0 - fx(4.3)) < 0.002 and abs(x1 - fx(4.3)) < 0.002
    assert sorted([round(y0, 3), round(y1, 3)]) == sorted([round(fy(1.0), 3), round(fy(1.9), 3)])
    assert parsed["_meta"]["geometrija"]["angos_sienose"] == ["01", "02"]


def test_a_two_room_open_plan_is_divided_by_the_lane_itself_and_the_boundary_is_never_a_wall():
    """2026-09-23, the founder: „o koks tau skirtumas, kur riba?" — none to the wall total; so the program
    takes its own proposal (vector_rooms.propose_split) instead of asking, says where and why, and a person
    may still redraw it."""
    a = two_rooms()
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]       # no partition: one space, two rooms in the table
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][0]["plotas_m2"] = 12.6
    out = gl.apply_geometry(parsed, build_plan([a]))
    r1, r2 = parsed["patalpos"]
    for r, other in ((r1, "02"), (r2, "01")):
        k = r["_konturas"]
        assert r["polygon_source"] == "vektoriniai_konturai" and len(r["polygon_pct"]) >= 4
        assert k["saltinis"] == "padalinta_programos" and k["pagal"] in ("kampas", "plotai") and k["su"] == [other]
        assert len(k["menamos"]) == 1 and len(k["riba_pct"]) == 2
        assert r["_atvira_erdve"]["nariai"] == ["01", "02"]        # the shared outline stays: shown dashed, redrawable
        assert "_konturo_priezastis" not in r
        assert r["perimetras_saltinis"] != "atviros_erdves_ivertis"  # not the share by area any more: this side's own walls
        assert r["perimetras_m"] > 0
    assert abs(r1["_konturas"]["plotas_m2"] / r2["_konturas"]["plotas_m2"] - 12.6 / 9.0) < 0.06
    # the boundary is an edge of both outlines and a wall of neither: the two perimeters add up to the space's walls
    assert abs(r1["perimetras_m"] + r2["perimetras_m"] - r1["_atvira_erdve"]["perimetras_m"]) < 0.3
    assert out["ribos"] == [{"nariai": ["01", "02"], "pagal": r1["_konturas"]["pagal"]}] and out["ribos_nepasiulytos"] == []
    assert set(out["konturai"]) >= {"01", "02"} and not ({"01", "02"} & set(out["perimetrai_tusti"]) - set(out["perimetrai_sudeti"]) & set()) 
    assert out["atviros_erdves"] == [["01", "02"]]
    assert gl.LANE_VERSION >= 8


def test_a_room_whose_walls_close_a_different_area_than_the_table_gets_a_proposed_outline():
    """objektas_h tambūras, 2026-09-23: 2,86 m² around the number, 4,48 in the table — no outline, but what
    the walls close is kept on the room as a proposal (the question list shows it; „Tinka" takes it)."""
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][1]["plotas_m2"] = 30.0                     # far from the 9 m² drawn
    out = gl.apply_geometry(parsed, build_plan([two_rooms()]))
    r2 = parsed["patalpos"][1]
    assert "_konturas" not in r2 and r2["_konturo_priezastis"] == "sienos prie numerio uždaro 9,00 m², lentelėje 30,00 m²"
    cand = r2["_konturo_siulymas"]
    assert cand["page"] == 1 and abs(cand["plotas_m2"] - 9.0) < 0.2 and cand["plotas_uzrasas_m2"] == 30.0
    assert len(cand["polygon_pct"]) >= 4 and len(cand["taskas_pct"]) == 2 and out["konturu_siulymai"] == ["02"]
    # the table agrees the next time (a corrected table, a re-read): the proposal goes, the outline comes
    parsed["patalpos"][1]["plotas_m2"] = 9.0
    gl.apply_geometry(parsed, build_plan([two_rooms()]))
    assert "_konturo_siulymas" not in parsed["patalpos"][1] and parsed["patalpos"][1]["_konturas"]["plotas_nesutampa"] is False


def test_a_pocket_the_table_gives_more_than_its_walls_close_is_joined_to_its_neighbour_and_divided():
    """objektas_h tambūras (2026-09-23): 2,86 m² around the number, 4,48 in the table, the rest a strip of the
    corridor beyond a doorless opening. The lane joins the two into one space and divides it by its own boundary."""
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][0].update({"plotas_m2": 4.5, "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.05, "h": 0.1},
                                  "polygon_pct": [[0.1, 0.1], [0.15, 0.1], [0.15, 0.2], [0.1, 0.2]]})
    parsed["patalpos"][1]["plotas_m2"] = 13.5
    out = gl.apply_geometry(parsed, build_plan([pocket_and_room()]))
    r1, r2 = parsed["patalpos"]
    assert out["atviros_erdves"] == [["01", "02"]] and out["ribos"] == [{"nariai": ["01", "02"], "pagal": "plotai"}]
    for r, other in ((r1, "02"), (r2, "01")):
        assert r["_konturas"]["saltinis"] == "padalinta_programos" and r["_konturas"]["su"] == [other]
        assert r["_atvira_erdve"]["kisene"] == "01" and "_konturo_siulymas" not in r
    assert abs(r1["_konturas"]["plotas_m2"] - 4.5) / 4.5 <= 0.08 and abs(r2["_konturas"]["plotas_m2"] - 13.5) / 13.5 <= 0.08
    # …and the second run, over its own outlines, lands on the same thing
    again = gl.apply_geometry(parsed, build_plan([pocket_and_room()]))
    assert again["ribos"] == out["ribos"] and parsed["patalpos"][0]["_konturas"]["plotas_m2"] == r1["_konturas"]["plotas_m2"]


def test_a_pocket_beside_an_outline_a_person_owns_is_neither_joined_nor_divided():
    """The neighbour's outline is his (corrected): the lane proposes the pocket, and leaves his outline alone."""
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][0].update({"plotas_m2": 4.5, "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.05, "h": 0.1},
                                  "polygon_pct": [[0.1, 0.1], [0.15, 0.1], [0.15, 0.2], [0.1, 0.2]]})
    parsed["patalpos"][1]["plotas_m2"] = 13.5
    gl.apply_geometry(parsed, build_plan([pocket_and_room()]))          # the lane divides them once…
    his = parsed["patalpos"][1]
    his.update({"polygon_source": "corrected", "_konturas": {**his["_konturas"], "saltinis": "parodyta"}})
    his.pop("_atvira_erdve", None)                                        # a pointed-at outline stands alone (api/room_outline.py)
    kept = [list(pt) for pt in his["polygon_pct"]]
    parsed["patalpos"][0].update({"polygon_source": "synthesized_from_bbox", "polygon_pct": [[0.1, 0.1], [0.15, 0.1], [0.15, 0.2], [0.1, 0.2]]})
    for k in ("_konturas", "_atvira_erdve", "_angos_sienose", "_sienos", "_perimetras_suma"):
        parsed["patalpos"][0].pop(k, None)
    out = gl.apply_geometry(parsed, build_plan([pocket_and_room()]))      # …then room 02's outline became HIS
    assert his["polygon_pct"] == kept and his["polygon_source"] == "corrected" and "_atvira_erdve" not in his
    r1 = parsed["patalpos"][0]
    assert out["atviros_erdves"] == [] and "_konturo_siulymas" in r1 and "_konturas" not in r1


# ── 2026-09-29: a later run that can no longer outline a room this lane outlined before ─────────────────────
# (the table's area was corrected, a re-read, a lane that learned something). Before: the room kept the old
# outline, its walls and a „read" perimeter while its new reason said the walls close nothing that fits.

_FROM_THE_OUTLINE = ("polygon_pct", "polygon_source", "_konturas", "_atvira_erdve", "_angos_sienose", "_sienos", "_perimetras_suma")


def _outlined_once():
    parsed = _parsed()
    pdf = _two_sheets()
    gl.apply_geometry(parsed, pdf)
    r1 = parsed["patalpos"][0]
    assert r1["polygon_source"] == "vektoriniai_konturai" and r1["_sienos"] and r1["_angos_sienose"]
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes" and r1["_perimetras_pries_geometrija"] == 13.9
    return parsed, pdf


def test_a_room_outlined_on_the_first_run_and_not_found_on_the_second_loses_the_outline_and_gets_its_earlier_perimeter():
    import copy
    parsed, pdf = _outlined_once()
    r1, r2 = parsed["patalpos"]
    neighbour = {k: copy.deepcopy(r2.get(k)) for k in ("polygon_pct", "polygon_source", "_konturas", "perimetras_m",
                                                       "perimetras_saltinis", "_sienos", "_perimetras_suma")}
    r1["plotas_m2"] = 30.0                      # the table now says an area the walls around 01 do not close
    out = gl.apply_geometry(parsed, pdf)
    assert [k for k in _FROM_THE_OUTLINE if k in r1] == []
    assert r1["perimetras_m"] == 13.9           # the figure it had before the lane added the wall strings
    assert "perimetras_saltinis" not in r1 and "_perimetras_pries_geometrija" not in r1
    assert r1["_konturo_priezastis"] == "sienos prie numerio uždaro 12,00 m², lentelėje 30,00 m²"
    assert r1["_konturo_siulymas"]["plotas_uzrasas_m2"] == 30.0          # what the walls close is offered instead
    assert "01" not in out["konturai"] and "01" in out["konturu_siulymai"]
    assert {k: r2.get(k) for k in neighbour} == neighbour                 # the room found on both runs is unchanged


def test_without_an_earlier_figure_the_perimeter_stays_but_is_no_longer_called_read():
    parsed, pdf = _outlined_once()
    r1 = parsed["patalpos"][0]
    del r1["_perimetras_pries_geometrija"]      # the plan gave no perimeter before the lane added one
    r1["plotas_m2"] = 30.0
    gl.apply_geometry(parsed, pdf)
    assert r1["perimetras_m"] == 14.0 and "perimetras_saltinis" not in r1 and "polygon_pct" not in r1
    from extractor.room_facts import _fact_perimetras
    fact = _fact_perimetras(parsed, r1, None)
    assert fact["status"] == "assumed" and fact["value"] == 14.0 and "nepatikrintas" in fact["sentence"]


@pytest.mark.parametrize("his", [
    {"user_verified_at": "2026-09-29T10:00:00+00:00"},                    # he marked the room checked
    {"_angos_user_at": "2026-09-29T10:00:00+00:00"},                      # he corrected its openings
    {"perimetras_m": 15.5, "perimetras_saltinis": "user_override"},       # he typed the perimeter
    {"polygon_source": "corrected"},                                      # he took / fixed the outline
])
def test_a_room_he_corrected_keeps_everything_when_the_lane_cannot_outline_it_again(his):
    import copy
    parsed, pdf = _outlined_once()
    r1 = parsed["patalpos"][0]
    r1.update(his)
    kept = {k: copy.deepcopy(r1.get(k)) for k in _FROM_THE_OUTLINE + ("perimetras_m", "perimetras_saltinis", "_perimetras_pries_geometrija")}
    r1["plotas_m2"] = 30.0
    gl.apply_geometry(parsed, pdf)
    assert {k: r1.get(k) for k in kept} == kept


def test_a_room_the_lane_outlines_on_both_runs_is_unchanged():
    import copy
    parsed, pdf = _outlined_once()
    once = copy.deepcopy(parsed["patalpos"])
    gl.apply_geometry(parsed, pdf)
    assert parsed["patalpos"] == once


# ── 2026-09-29 (2): the rooms that never reach the trace on the later run ────────────────────────────────────
# A room this lane outlined before that today's reading does not even place, or whose plan sheet has no scale
# today, was never traced — and so kept the old outline, its walls and the summed perimeter.

_OUTLINE_KEYS = ("polygon_pct", "polygon_source", "_konturas", "perimetras_m", "perimetras_saltinis", "_sienos", "_perimetras_suma")


def _not_placed(monkeypatch, parsed, nr="01"):
    """Today's reading does not place room `nr` (and the room carries no position from before)."""
    real = gl.locate_rooms
    monkeypatch.setattr(gl, "locate_rooms", lambda b, rooms, pages: {k: v for k, v in real(b, rooms, pages).items() if k != nr})
    for r in parsed["patalpos"]:
        if r["nr"] == nr:
            r.pop("_vieta", None)


def _no_scale(pdf):
    """Today's strings carry no scale for the plan's sheets."""
    return [{**d, "scale_m_per_pt": None} for d in gl.read_dimension_strings(pdf, pages=None)]


def test_a_room_outlined_before_that_is_not_placed_today_loses_the_outline_and_gets_its_earlier_perimeter(monkeypatch):
    import copy
    parsed, pdf = _outlined_once()
    r1, r2 = parsed["patalpos"]
    neighbour = {k: copy.deepcopy(r2.get(k)) for k in _OUTLINE_KEYS}
    _not_placed(monkeypatch, parsed)
    out = gl.apply_geometry(parsed, pdf)
    assert [k for k in _FROM_THE_OUTLINE if k in r1] == []
    assert r1["perimetras_m"] == 13.9 and "perimetras_saltinis" not in r1 and "_perimetras_pries_geometrija" not in r1
    assert "01" not in out["konturai"] and "01" not in out["perimetrai_sudeti"]
    assert {k: r2.get(k) for k in _OUTLINE_KEYS} == neighbour             # the room confirmed today is untouched


def test_rooms_outlined_before_on_a_sheet_without_a_scale_today_lose_their_outlines():
    parsed, pdf = _outlined_once()
    r1, r2 = parsed["patalpos"]
    assert r2["_perimetras_pries_geometrija"] == 12.3
    out = gl.apply_geometry(parsed, pdf, dims=_no_scale(pdf))
    for r, earlier in ((r1, 13.9), (r2, 12.3)):
        assert [k for k in _FROM_THE_OUTLINE if k in r] == [], r["nr"]
        assert r["perimetras_m"] == earlier and "perimetras_saltinis" not in r and "_perimetras_pries_geometrija" not in r
    assert out["konturai"] == []


@pytest.mark.parametrize("today", ["not_placed", "no_scale"])
@pytest.mark.parametrize("his", [
    {"user_verified_at": "2026-09-29T10:00:00+00:00"},
    {"_angos_user_at": "2026-09-29T10:00:00+00:00"},
    {"perimetras_m": 15.5, "perimetras_saltinis": "user_override"},
    {"polygon_source": "corrected"},
])
def test_a_room_he_worked_on_keeps_everything_when_it_is_not_traced_today(monkeypatch, his, today):
    import copy
    parsed, pdf = _outlined_once()
    r1 = parsed["patalpos"][0]
    r1.update(his)
    # (the openings read in its walls are evidence the openings reader redoes on every run, and drops for any
    # outline on a sheet it cannot measure — not part of this reset)
    kept = {k: copy.deepcopy(r1.get(k)) for k in _FROM_THE_OUTLINE + ("perimetras_m", "perimetras_saltinis", "_perimetras_pries_geometrija")
            if not (today == "no_scale" and k == "_angos_sienose")}
    if today == "not_placed":
        _not_placed(monkeypatch, parsed)
        gl.apply_geometry(parsed, pdf)
    else:
        gl.apply_geometry(parsed, pdf, dims=_no_scale(pdf))
    assert {k: r1.get(k) for k in kept} == kept


def test_a_room_that_gets_its_own_outline_today_drops_the_open_space_it_was_part_of():
    """The pocket joined to its neighbour on the first run (table 4,5 / 13,5); the table is corrected to what
    the walls close (3 / 15): each room is outlined on its own, and neither is part of an open space any more."""
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][0].update({"plotas_m2": 4.5, "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.05, "h": 0.1},
                                  "polygon_pct": [[0.1, 0.1], [0.15, 0.1], [0.15, 0.2], [0.1, 0.2]]})
    parsed["patalpos"][1]["plotas_m2"] = 13.5
    pdf = build_plan([pocket_and_room()])
    gl.apply_geometry(parsed, pdf)
    r1, r2 = parsed["patalpos"]
    assert r1["_atvira_erdve"]["kisene"] == "01" and r2["_atvira_erdve"]["nariai"] == ["01", "02"]
    r1["plotas_m2"], r2["plotas_m2"] = 3.0, 15.0
    out = gl.apply_geometry(parsed, pdf)
    assert set(out["konturai"]) == {"01", "02"} and out["atviros_erdves"] == [] and out["ribos"] == []
    for r in (r1, r2):
        assert r["polygon_source"] == "vektoriniai_konturai" and r["_konturas"]["saltinis"] == "vektoriniai_konturai"
        assert "_atvira_erdve" not in r, r["nr"]


def test_a_room_placed_in_an_open_space_today_carries_todays_record_of_it(monkeypatch):
    monkeypatch.setattr(gl, "propose_split", lambda *a, **k: {"status": "no_proposal"})
    a = two_rooms()
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]       # no partition: one space
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    stale = {"nariai": ["01", "02", "03"], "polygon_pct": [[0, 0], [1, 0], [1, 1]], "plotas_m2": 99.0, "perimetras_m": 40.0, "page": 1}
    for r in parsed["patalpos"]:
        r["_atvira_erdve"] = dict(stale)
    out = gl.apply_geometry(parsed, build_plan([a]))
    assert out["atviros_erdves"] == [["01", "02"]]
    for r in parsed["patalpos"]:
        assert r["_atvira_erdve"]["nariai"] == ["01", "02"] and r["_atvira_erdve"]["plotas_m2"] != 99.0
