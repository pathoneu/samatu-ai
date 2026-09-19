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
    assert r1["perimetras_m"] == 13.9                              # Vision's figure stays until someone decides


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
    assert "pataikė į patalpą 01" in r7["_konturo_priezastis"]


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
