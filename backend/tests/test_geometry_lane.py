"""One call turns a parsed extraction into located rooms, vector outlines and
summed perimeters — without Vision. Synthetic drawings only."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import geometry_lane as gl  # noqa: E402
from tests.synthetic_plan import build_plan, two_rooms  # noqa: E402


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


def test_an_open_plan_names_its_members_and_offers_the_shared_walls_as_an_estimate():
    a = two_rooms()                                                 # (its strings give the sheet a scale)
    a.walls = [w for w in a.walls if abs(w[0] - 4.2) > 0.01]       # no partition: one space, two rooms in the table
    parsed = _parsed()
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}]
    parsed["patalpos"][0]["plotas_m2"] = 12.6
    gl.apply_geometry(parsed, build_plan([a]))
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
    assert r1["perimetras_m"] == 15.5 and "_perimetras_ivertis_m" not in r1
    assert r2["perimetras_saltinis"] == "atviros_erdves_ivertis" and r2["_perimetras_ivertis_m"] > 0


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
    assert ev["page"] == 3 and ev["irodymas"] == "uzrasas" and ev["plotas_m2"] == 8.95
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
