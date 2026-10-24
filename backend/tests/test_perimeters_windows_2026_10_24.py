"""2026-10-24 (v4, objektas_i) — two levers on the contractor's project, synthetic drawings only.

1. Perimeters READ, not estimated: a wall face without its own dimension string is completed — (a) a short face
   from the outline, (c) the difference of the strings on the same axis („matmenų grandinė"), (b) from the outline
   when the opposite parallel face's string agrees with its outline — each completed face listed, never silently;
   more than a quarter of the perimeter off the outline keeps it an estimate.
2. Windows drawn as an outlined thin rectangle (one frame, or one per sash), or as the same rectangle stored as a
   closed path, are glazing."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor import drawn_openings as do  # noqa: E402
from extractor import plan_dimensions as pdim  # noqa: E402
from extractor import sheet_alignment as sa  # noqa: E402
from extractor.room_facts import build_room_facts  # noqa: E402
from extractor.user_text import is_banned  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan  # noqa: E402

SCALE = {1: 1 / PT_PER_M}
W_PT, H_PT = 595.2756, 841.8898


def _outline(nr, pts_m):
    area = abs(sum(pts_m[i][0] * pts_m[(i + 1) % len(pts_m)][1] - pts_m[(i + 1) % len(pts_m)][0] * pts_m[i][1]
                   for i in range(len(pts_m)))) / 2
    return {"nr": nr, "plotas_m2": round(area, 2), "puslapio_nr": 1, "polygon_source": "vektoriniai_konturai",
            "_konturas": {"page": 1, "plotas_nesutampa": False},
            "polygon_pct": [[(60 + x * PT_PER_M) / W_PT, (80 + y * PT_PER_M) / H_PT] for x, y in pts_m]}


def _run(dims, rooms):
    pdf = build_plan([Sheet(dims=dims)])
    strings = pdim.read_dimension_strings(pdf, pages=[1])
    return ds.sum_perimeters(rooms, strings, sa.align_sheets(pdf, [1]), SCALE)


# ---------------------------------------------------------------- perimeters

def test_the_short_face_limit_is_eight_millimetres_on_paper_capped_at_sixty_centimetres():
    pt = 0.0254 / 72
    assert abs(ds.short_face_m(pt * 50) - (0.40 + ds.SHORT_FACE_TOL_M)) < 1e-3       # 1:50 — the old 0,4 m
    assert abs(ds.short_face_m(pt * 75) - (0.60 + ds.SHORT_FACE_TOL_M)) < 1e-3       # 1:75 — objektas_i's returns
    assert abs(ds.short_face_m(pt * 200) - (0.60 + ds.SHORT_FACE_TOL_M)) < 1e-9      # never more than 0,6 m


def test_a_face_without_a_string_is_the_difference_of_the_strings_on_its_axis():
    """An L-shaped room: the 1,0 m step has no string; the top „4000" minus the bottom „3000" is its length."""
    room = _outline("01", [(0.2, 0.2), (4.2, 0.2), (4.2, 1.6), (3.2, 1.6), (3.2, 3.2), (0.2, 3.2)])
    out = _run([("4000", 0.2, 0.35, 4.2, 0.35), ("1400", 4.05, 0.2, 4.05, 1.6), ("1600", 3.05, 1.6, 3.05, 3.2),
                ("3000", 0.2, 3.05, 3.2, 3.05), ("3000", 0.35, 0.2, 0.35, 3.2)], [room])
    assert out["stated"] == ["01"], (room.get("_perimetras_priezastis"), room.get("_sienos"))
    assert room["perimetras_m"] == 14.0 and room["perimetras_saltinis"] == "matmenu_eilutes"
    step = next(w for w in room["_sienos"] if w["saltinis"] == "grandine")
    assert step["ilgis_m"] == 1.0 and step["budas"] == "grandine" and not step["eilutes"]
    assert sorted((g["ilgis_m"], g["zenklas"]) for g in step["grandine"]) == [(3.0, -1), (4.0, 1)]
    suma = room["_perimetras_suma"]
    assert suma["is_grandines_m"] == 1.0 and suma["is_konturo_m"] == 0
    assert suma["papildyta"] == [{"siena": room["_sienos"].index(step), "ilgis_m": 1.0, "kontrole_m": step["kontrole_m"],
                                  "saltinis": "grandine", "budas": "grandine"}]
    assert suma["sienu_is_matmenu"] == 5 and suma["sienu"] == 6


def test_a_difference_that_disagrees_with_the_faces_outline_is_not_taken():
    room = _outline("01", [(0.2, 0.2), (4.2, 0.2), (4.2, 1.6), (3.2, 1.6), (3.2, 3.2), (0.2, 3.2)])
    # the bottom string says 2,5 m — the step would be 1,5 m against its 1,0 m outline: neither read nor guessed
    _run([("4000", 0.2, 0.35, 4.2, 0.35), ("1400", 4.05, 0.2, 4.05, 1.6), ("1600", 3.05, 1.6, 3.05, 3.2),
          ("2500", 0.2, 3.05, 3.2, 3.05), ("3000", 0.35, 0.2, 0.35, 3.2)], [room])
    assert not any(w["saltinis"] == "grandine" for w in room["_sienos"])
    assert room["perimetras_saltinis"] == "konturo_ivertis"


def test_a_jamb_return_nobody_dimensioned_is_taken_from_the_outline():
    """0,5 m returns either side of a recess (above the old 0,4 m piece limit, below 0,6 m at 1:100): from the
    outline, listed as short pieces, and the perimeter is read."""
    pts = [(0.2, 0.2), (4.2, 0.2), (4.2, 3.2), (2.7, 3.2), (2.7, 3.7), (1.7, 3.7), (1.7, 3.2), (0.2, 3.2)]
    room = _outline("01", pts)
    out = _run([("4000", 0.2, 0.35, 4.2, 0.35), ("3000", 4.05, 0.2, 4.05, 3.2), ("1500", 2.7, 3.05, 4.2, 3.05),
                ("1000", 1.7, 3.55, 2.7, 3.55), ("1500", 0.2, 3.05, 1.7, 3.05), ("3000", 0.35, 0.2, 0.35, 3.2)], [room])
    assert out["stated"] == ["01"], (room.get("_perimetras_priezastis"), [(w["kontrole_m"], w["saltinis"]) for w in room["_sienos"]])
    short = [w for w in room["_sienos"] if w.get("budas") == "trumpa"]
    assert len(short) == 2 and all(abs(w["ilgis_m"] - 0.5) < 0.02 and w["saltinis"] == "konturas" for w in short)
    assert abs(room["perimetras_m"] - 15.0) < 0.03 and abs(room["_perimetras_suma"]["is_konturo_m"] - 1.0) < 0.03


def test_more_than_a_quarter_off_the_outline_stays_an_estimate_with_the_reason():
    """A notch on the right: five faces, 5 m of 16 m, have no string and no difference to give them — (b) takes
    each from the outline because the opposite string agrees with it, but 31 % off the outline is not „read"."""
    pts = [(0.2, 0.2), (4.2, 0.2), (4.2, 1.2), (3.2, 1.2), (3.2, 2.2), (4.2, 2.2), (4.2, 3.2), (0.2, 3.2)]
    room = _outline("01", pts)
    out = _run([("4000", 0.2, 0.35, 4.2, 0.35), ("4000", 0.2, 3.05, 4.2, 3.05), ("3000", 0.35, 0.2, 0.35, 3.2),
                ("2000", 6.0, 5.0, 6.0, 7.0), ("2500", 6.0, 8.0, 8.5, 8.0)], [room])   # elsewhere: enough strings for a scale
    assert out["blank"] == ["01"] and room["perimetras_saltinis"] == "konturo_ivertis"
    assert room["_perimetras_priezastis"].startswith("5 iš 8 sienų be matmens — jų ilgis iš kontūro (5,00 m, 31 % perimetro)")
    assert abs(room["perimetras_m"] - 16.0) < 0.05


def test_the_fact_lists_every_completed_wall():
    room = {"nr": "04", "pavadinimas": "Miegamasis", "plotas_m2": 11.95, "puslapio_nr": 4, "lubu_aukstis_m": 2.7,
            "perimetras_m": 14.82, "perimetras_saltinis": "matmenu_eilutes",
            "_perimetras_suma": {"suma_m": 14.82, "kontrole_m": 14.81, "sutampa": True, "lapai": [4], "is_konturo_m": 0.6,
                                 "pakartota": 0, "eilutes": ["2450", "2240", "2120", "4360"], "is_grandines_m": 3.05,
                                 "papildyta": [{"siena": 2, "ilgis_m": 0.6, "kontrole_m": 0.6, "saltinis": "konturas", "budas": "trumpa"},
                                               {"siena": 4, "ilgis_m": 3.05, "kontrole_m": 3.048, "saltinis": "grandine", "budas": "grandine"}],
                                 "sienu_is_matmenu": 4, "sienu": 6},
            "_sienos": [{"edge_pct": [[0.5, 0.2], [0.7, 0.2]], "ilgis_m": v, "saltinis": s, "kontrole_m": v,
                         "eilutes": [{"text": t, "value_m": v, "page": 4}] if t else []}
                        for t, v, s in (("2450", 2.45, "eilute"), ("2240", 2.24, "eilute"), (None, 0.6, "konturas"),
                                        ("2120", 2.12, "eilute"), (None, 3.05, "grandine"), ("4360", 4.36, "eilute"))],
            "_konturas": {"page": 4}, "polygon_pct": [[0.5, 0.2], [0.7, 0.2], [0.7, 0.4], [0.5, 0.4]],
            "polygon_source": "vektoriniai_konturai"}
    facts = {f["key"]: f for f in build_room_facts({"patalpos": [room], "puslapiai": [{"nr": 4, "tipas": "floor_plan"}]}, "04")["facts"]}
    p = facts["perimetras"]
    s = p["sentence"]
    assert p["status"] == "read" and "2450 + 2240 + 0,60 + 2120 + 3,05 + 4360 = 14,82 m" in s
    assert "Sudėta iš matmenų (4 iš 6 sienų)" in s and "grandinės" in s and "3,05 m" in s and "kontūro: 0,60 m" in s
    assert not is_banned(s)


# ---------------------------------------------------------------- windows

reportlab = pytest.importorskip("reportlab")
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

M_PER_PT = 0.0254 / 72 * 75      # 1:75, objektas_i's sheet
WALL = 18.96                     # 0,50 m
H = A4[1]


def _y(top: float) -> float:
    return H - top


def _window_sheet() -> bytes:
    """A horizontal wall band top=300..318,96 with gaps; each gap carries one way of drawing a window (or not)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFillGray(0.4)
    c.setStrokeGray(0.0)
    edges = (20, 60, 135, 175, 250, 290, 365, 405, 480, 520, 575)
    for x0, x1 in zip(edges[0::2], edges[1::2]):
        c.rect(x0, _y(300 + WALL), x1 - x0, WALL, stroke=0, fill=1)
    c.setStrokeColorRGB(0.55, 0.89, 0.86)
    c.setLineWidth(0.24)
    mid = 300 + WALL / 2
    # gap 60..135 — one outlined frame rectangle 3 pt deep + the glass line through it (objektas_i)
    c.rect(63, _y(mid + 1.5), 69, 3.0, stroke=1, fill=0)
    c.line(63, _y(mid), 132, _y(mid))
    # gap 175..250 — the same frame stored as a closed path whose corner drifts 0,12 pt
    p = c.beginPath()
    p.moveTo(178, _y(mid + 1.5))
    p.lineTo(247, _y(mid + 1.62))
    p.lineTo(247, _y(mid - 1.5))
    p.lineTo(178, _y(mid - 1.5))
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    # gap 290..365 — two sashes, each frame 0,42 of the gap
    c.rect(293, _y(mid + 1.5), 31.7, 3.0, stroke=1, fill=0)
    c.rect(331, _y(mid + 1.5), 31.7, 3.0, stroke=1, fill=0)
    # gap 405..480 — ONE short frame (0,42 of the gap): not a window
    c.rect(408, _y(mid + 1.5), 31.7, 3.0, stroke=1, fill=0)
    # gap 520..575 — a deep outlined box in the gap (a radiator, 0,3 m deep): not a frame
    c.rect(523, _y(mid + 5.7), 49, 11.4, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def window_marks():
    m = do.page_marks(_window_sheet(), 1, M_PER_PT)
    assert m is not None
    return m


def _kind(marks, x0, x1):
    mid = 300 + WALL / 2
    return do.opening_kind([[x0, mid], [x1, mid]], (x1 - x0) * M_PER_PT, WALL * M_PER_PT, marks, M_PER_PT, set())[0]


def test_an_outlined_frame_rectangle_is_glazing(window_marks):
    assert _kind(window_marks, 60, 135) == "langas"


def test_the_frame_stored_as_a_closed_path_is_glazing(window_marks):
    assert _kind(window_marks, 175, 250) == "langas"


def test_two_sash_frames_that_together_span_the_gap_are_glazing(window_marks):
    assert _kind(window_marks, 290, 365) == "langas"


def test_one_short_frame_or_a_deep_box_is_not_a_window(window_marks):
    assert _kind(window_marks, 405, 480) is None
    assert _kind(window_marks, 520, 575) is None


def _balcony_sheet(hinge_far: bool = False) -> bytes:
    """A 2,4 m glazed gap (x 100..190.7) with a 0,76 m leaf hinged at its left end, swinging out (above the band);
    with `hinge_far` the same arc stands 1 m away along the wall — another door's, not this gap's."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFillGray(0.4)
    c.rect(20, _y(300 + WALL), 80, WALL, stroke=0, fill=1)
    c.rect(190.7, _y(300 + WALL), 200, WALL, stroke=0, fill=1)
    mid = 300 + WALL / 2
    c.setStrokeColorRGB(0.55, 0.89, 0.86)
    c.setLineWidth(0.24)
    c.rect(103, _y(mid + 1.5), 84.7, 3.0, stroke=1, fill=0)
    c.line(103, _y(mid), 187.7, _y(mid))
    hx = 230.0 if hinge_far else 101.0
    r = 0.76 / M_PER_PT
    p = c.beginPath()
    p.arc(hx - r, _y(mid + r), hx + r, _y(mid - r), startAng=0, extent=90)   # from along the wall to straight out
    c.drawPath(p, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_a_glazed_gap_with_one_leaf_hinged_at_its_end_is_a_door():
    marks = do.page_marks(_balcony_sheet(), 1, M_PER_PT)
    assert any(abs(a.r * M_PER_PT - 0.76) < 0.03 for a in marks.arcs), [(a.cx, a.cy, a.r) for a in marks.arcs]
    used: set[int] = set()
    mid = 300 + WALL / 2
    kind, k = do.opening_kind([[100, mid], [190.7, mid]], 2.4, WALL * M_PER_PT, marks, M_PER_PT, used)
    assert kind == "durys" and used == {k}
    far = do.page_marks(_balcony_sheet(hinge_far=True), 1, M_PER_PT)
    assert do.opening_kind([[100, mid], [190.7, mid]], 2.4, WALL * M_PER_PT, far, M_PER_PT, set())[0] == "langas"


# ---------------------------------------------------------------- the walls pass: listed windows and drawn glazing

def _walls_room(elementai, angos):
    return {"nr": "102", "pavadinimas": "Svetainė", "paskirtis": "svetaine", "puslapio_nr": 2, "plotas_m2": 30.0,
            "perimetras_m": 24.0, "lubu_aukstis_m": 2.7, "polygon_pct": [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]],
            "polygon_source": "vektoriniai_konturai", "_konturas": {"page": 1}, "elementai": elementai,
            "_angos_sienose": {"page": 1, "angos": [
                {"i": i, "plotis_m": w, "storis_m": 0.3, "line_pct": [[0.2 + 0.03 * k, 0.1], [0.22 + 0.03 * k, 0.1]],
                 **({"nupiesta": n} if n else {})} for k, (i, w, n) in enumerate(angos)]}}


def test_a_listed_window_whose_size_fits_no_opening_takes_a_glazed_one_instead_of_a_second_window_being_added():
    """objektas_a 102 once the glazing is read: „langas 2750 ×2" + „3300" fit none of the glazed 2,11 / 1,73 /
    0,96 m openings; the listed units stand in them — three windows, not three listed + three drawn."""
    from extractor import universal_rules as ur
    room = _walls_room([{"tipas": "langas", "kiekis": 2, "plotis_mm": 2750, "aukstis_mm": 2400},
                        {"tipas": "langas", "kiekis": 1, "plotis_mm": 3300, "aukstis_mm": 2400}],
                       [("laukas", 2.11, "langas"), ("laukas", 1.73, "langas"), ("laukas", 0.96, "langas")])
    out = ur.reconcile_openings_with_walls([room])
    windows = [e for e in room["elementai"] if e.get("tipas") == "langas"]
    assert sum(ur._el_units(e) for e in windows) == 3 and out["added_windows"] == 0
    assert sorted(k for e in windows for k in e.get(ur.OPENING_INDEX_KEY) or []) == [0, 1, 2]
    # an opening showing nothing is not taken this way (the older steps' rules for those stay as they were)
    plain = _walls_room([{"tipas": "langas", "kiekis": 1, "plotis_mm": 3300, "aukstis_mm": 2400}], [("laukas", 2.11, None)])
    ur.reconcile_openings_with_walls([plain])
    assert not plain["elementai"][0].get(ur.OPENING_INDEX_KEY)
