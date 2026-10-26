"""Wall finishes read from the drawing as drawn, per wall face (v4, 2026-10-26).

extractor/wall_finishes.py (the wall-finish plan's coloured lines along each room's outline), extractor/
elevation_panels.py (the elevations' marker rows, leader-named zones, tile layouts, and the match of their faces to
the plan's rooms) and universal_rules.resolve_drawn_wall_finish (what the calculation takes from them). Synthetic
drawings only (tests/synthetic_wall_finishes.py); no client data, no model.
"""
from __future__ import annotations

import pytest

from extractor import elevation_panels as ep
from extractor import wall_finishes as wf
from extractor.universal_rules import calc_room_quantities, resolve_drawn_wall_finish, translate_user_prefs_to_room_rules
from tests import synthetic_wall_finishes as sw


# ── the wall-finish plan ─────────────────────────────────────────────────────

def test_finish_class_vocabulary():
    assert wf.finish_class("Dažymas balta spalva") == "dazymas"
    assert wf.finish_class("Glaistoma dažoma (baltai - s0601G) 202 m2") == "dazymas"
    assert wf.finish_class("Plytelės kronosceramiche lux falda 1200x1200mm") == "plyteles"
    assert wf.finish_class("Akmens masės plytelės") == "plyteles"
    assert wf.finish_class("Vaikiški tapetai") == "tapetai"
    assert wf.finish_class("Siena dengiama plokšte") == "plokste"
    assert wf.finish_class("Tekstūrinis tinkas") == "molio_tinkas"
    assert wf.finish_class("Veidrodis") == "veidrodis"
    # not a wall finish: the floor, skirting, lights
    assert wf.finish_class("Plytelės grindims 60x60") is None
    assert wf.finish_class("Grindjuostės h=60 mm") is None


def test_legend_read_with_colours():
    pdf = sw.build_finish_plan()
    leg = wf.read_legend(pdf, 1)
    by = {r["klase"]: r["colour"] for r in leg["rows"]}
    assert by["dazymas"] == pytest.approx(sw.MAGENTA, abs=0.02)
    assert by["plyteles"] == pytest.approx(sw.GREEN, abs=0.02)
    assert by["plokste"] == pytest.approx(sw.RED, abs=0.02)
    assert leg["title"] is True
    assert wf.is_wall_finish_legend(leg)


def test_floor_legend_is_no_wall_plan():
    pdf = sw.build_finish_plan(legend=[("Plytelės 60x120 cm", sw.GREEN)], title="GRINDŲ PLANAS")
    assert not wf.is_wall_finish_legend(wf.read_legend(pdf, 1))
    assert wf.find_finish_sheets(pdf, [1]) == {}


def _read(pdf, **kw):
    leg = wf.read_legend(pdf, 1)
    rings = {"A": sw.room_ring(sw.ROOM_A), "B": sw.room_ring(sw.ROOM_B)}
    return wf.read_rooms(pdf, 1, leg, sw.M_PER_PT, rings, **kw)


def test_lines_measured_per_room_and_face():
    got = _read(sw.build_finish_plan())
    a, b = got["A"], got["B"]
    assert a["konturas_m"] == pytest.approx(14.0, abs=0.05)
    # three walls painted (4 + 3 + 4 m), the east wall (3 m) has no line
    assert a["klases_m"]["dazymas"] == pytest.approx(11.0, abs=0.4)
    assert "plyteles" not in a["klases_m"]          # B's tile line beyond the partition is B's
    assert a["nepazymeta_m"] == pytest.approx(3.0, abs=0.4)
    east = [f for f in a["sienos"] if f.get("nepazymeta")]
    assert len(east) == 1 and east[0]["ilgis_m"] == pytest.approx(3.0, abs=0.05)
    assert b["klases_m"]["plyteles"] == pytest.approx(10.0, abs=0.4)
    assert "dazymas" not in b["klases_m"]
    assert wf.is_read(a) and wf.is_read(b)


def test_opening_is_not_an_unfinished_wall():
    # a 1,0 m door in A's east wall: the rest of that wall (2 m) is still a wall the plan leaves unfinished; a door
    # as wide as the wall leaves nothing
    pdf = sw.build_finish_plan()
    door = (sw.display_pt(4.0, 1.0), sw.display_pt(4.0, 2.0), 1.0)
    got = _read(pdf, openings={"A": [door]})
    assert got["A"]["nepazymeta_m"] == pytest.approx(2.0, abs=0.4)
    wide = (sw.display_pt(4.0, 0.0), sw.display_pt(4.0, 3.0), 3.0)
    assert _read(pdf, openings={"A": [wide]})["A"]["nepazymeta_m"] == pytest.approx(0.0, abs=0.4)


def test_room_without_lines_on_a_finishing_plan_is_unfinished():
    pdf = sw.build_finish_plan(b_walls={})
    # with only two rooms on the sheet the plan does not finish enough rooms to call B unfinished
    got = _read(pdf)
    assert not got["B"].get("tuscia")
    assert not wf.is_read(got["B"])


# ── the elevations ───────────────────────────────────────────────────────────

def test_elevation_faces_zone_and_furniture():
    pdf = sw.build_elevation()
    res = ep.read_sheet(pdf, 1, sw.M_PER_PT)
    faces = [(f["a"], f["b"]) for f in res["faces"]]
    assert faces == [("x1", "x2"), ("x2", "x3")]
    assert len(res["zonos"]) == 1
    z = res["zonos"][0]
    assert (z["a"], z["b"], z["klase"]) == ("x1", "x2", "plyteles")
    assert z["plotis_m"] == pytest.approx(2.6, abs=0.03)
    assert z["aukstis_m"] == pytest.approx(0.6, abs=0.03)
    assert z["plotas_m2"] == pytest.approx(1.56, abs=0.04)
    # the wardrobe is furniture, not a wall finish — kept as evidence, never a zone
    assert [(b["a"], b["b"], b["klase"]) for b in res["baldai"]] == [("x2", "x3", "baldai")]


def test_elevation_without_scale_measures_nothing():
    res = ep.read_sheet(sw.build_elevation(), 1, None)
    assert res["faces"] == [] and res["zonos"] == []


def test_label_class_furniture_vs_wall():
    assert ep.label_class("Gaminama iš baltos spalvos plokštės") == "baldai"
    assert ep.label_class("Dengiama siena iš mėlynos spalvos plokštės") == "plokste"
    assert ep.label_class("Kronosceramiche plytelės lux venna 280x120cm") == "plyteles"


def test_face_with_markers_inside_the_room_still_matches():
    """A marker drawn slightly INSIDE the room polygon used to be measured against the exterior ring in
    both branches of the ternary (identical expressions, 2026-10-26 fix) — an inset marker further than
    `reach_m` from the ring could not match its own room. The polygon-contains case now returns distance 0.
    """
    faces = [{"a": "x1", "b": "x2"}]
    # markers inside ROOM_A, further than reach_m from any wall of a smaller 1-m-tolerance ring
    inside = {"x1": (sw.display_pt(1.4, 1.4)[0], sw.display_pt(1.4, 1.4)[1]),
              "x2": (sw.display_pt(2.6, 1.4)[0], sw.display_pt(2.6, 1.4)[1])}
    rings = {"A": sw.room_ring(sw.ROOM_A)}
    got = ep.match_faces(faces, inside, rings, sw.M_PER_PT, reach_m=0.3)
    assert got == {("x1", "x2"): "A"}


def test_faces_matched_to_the_plan_room():
    plan = sw.build_finish_plan()
    markers = ep.plan_markers(plan, 1)
    assert set(markers) == {"x1", "x2", "x3"}
    faces = ep.read_sheet(sw.build_elevation(), 1, sw.M_PER_PT)["faces"]
    rings = {"A": sw.room_ring(sw.ROOM_A), "B": sw.room_ring(sw.ROOM_B)}
    got = ep.match_faces(faces, markers, rings, sw.M_PER_PT)
    assert got == {("x1", "x2"): "A", ("x2", "x3"): "A"}


def test_plan_record_carries_the_elevation_faces():
    plan = sw.build_finish_plan()
    elev = ep.read_sheet(sw.build_elevation(), 1, sw.M_PER_PT)
    elev["page"] = 2
    markers = ep.plan_markers(plan, 1)
    rings = {"A": sw.room_ring(sw.ROOM_A), "B": sw.room_ring(sw.ROOM_B)}
    fr = ep.match_faces(elev["faces"], markers, rings, sw.M_PER_PT)
    got = _read(plan, markers=markers, elevation=[elev], face_rooms=fr)
    el = got["A"]["isklotines"]
    assert set(el["sienos"]) == {"x1–x2", "x2–x3"}
    assert el["sienos"]["x1–x2"]["klases"].get("dazymas", 0) > 3.0      # the north wall is painted on the plan
    assert el["sienos"]["x2–x3"]["klases"].get("dazymas", 0) < 0.5      # the east wall has no line
    assert [z["siena"] for z in el["zonos"]] == ["x1–x2"]
    assert el["puslapiai"] == [2]


# ── what the calculation takes ───────────────────────────────────────────────

def _record(klases, konturas=14.0, angos=0.0, nepazymeta=0.0, legenda=("dazymas", "plyteles", "plokste"), **el):
    rec = {"saltinis": wf.SOURCE, "page": 10, "konturas_m": konturas, "klases_m": klases,
           "padengta_m": sum(klases.values()), "angos_m": angos, "nepazymeta_m": nepazymeta, "sienos": [],
           "legenda": [{"klase": k, "tekstas": k} for k in legenda]}
    if el:
        rec["isklotines"] = el
    return rec


def _room(rec, paskirtis="gyvenamoji", **kw):
    return {"nr": "1", "pavadinimas": "Patalpa", "paskirtis": paskirtis, "plotas_m2": 12.0, "perimetras_m": 14.0,
            "perimetras_saltinis": "matmenu_eilutes", "lubu_aukstis_m": 2.8, "n_doors": 0, "n_windows": 0,
            "_sienu_apdaila": rec, **kw}


def test_hall_painted_as_drawn_not_by_purpose():
    out = calc_room_quantities(_room(_record({"dazymas": 14.0}), paskirtis="tamburas"))
    assert out["walls_paintable_m2"] == pytest.approx(14.0 * 2.8, abs=0.1)
    assert out["_tile_read_source"] in ("brezinys", "none")
    assert any("sienų apdailos plano" in n for n in out["_wall_finish_assumptions"])


def test_kitchen_backsplash_is_the_drawn_zone_not_a_band():
    zone = {"siena": "x1–x2", "klase": "plyteles", "plotis_m": 2.6, "aukstis_m": 0.6, "plotas_m2": 1.56, "page": 11}
    rec = _record({"dazymas": 11.0}, nepazymeta=3.0, sienos={"x1–x2": {"ilgis_m": 4.0, "klases": {}}}, zonos=[zone])
    # uz_baldu_dazoma=False: test documents the pre-2026-10-26 behaviour where the wall behind
    # the cabinet was left out of paint; with the default True the 3 m would be folded into paint.
    out = calc_room_quantities(_room(rec, paskirtis="virtuve"), rules={"_profilis": {"uz_baldu_dazoma": False}})
    assert out["plyteles_sienos_m2"] == pytest.approx(1.56, abs=0.01)
    # 3 m of wall the plan does not finish (behind the cabinets) is not painted: 11/14 of the walls
    assert out["walls_paintable_m2"] == pytest.approx(11.0 / 14.0 * 14.0 * 2.8, abs=0.2)
    notes = " ".join(out["_wall_finish_assumptions"])
    assert "1,56 m²" in notes and "nepažymėta" in notes


def test_zone_on_a_painted_face_takes_its_paint():
    zone = {"siena": "x1–x2", "klase": "plyteles", "plotis_m": 2.0, "aukstis_m": 0.6, "plotas_m2": 1.2, "page": 11}
    rec = _record({"dazymas": 14.0}, sienos={"x1–x2": {"ilgis_m": 4.0, "klases": {"dazymas": 4.0}}}, zonos=[zone])
    out = calc_room_quantities(_room(rec))
    assert out["plyteles_sienos_m2"] == pytest.approx(1.2, abs=0.01)
    assert out["walls_paintable_m2"] == pytest.approx(14.0 * 2.8 - 1.2, abs=0.1)


def test_bathroom_tile_layout_to_the_ceiling_is_full_tile():
    rec = _record({"plyteles": 14.0}, plyteles=[{"siena": "x1–x2", "aukstis_m": 2.64}])
    out = calc_room_quantities(_room(rec, paskirtis="vonia"))
    assert out["walls_paintable_m2"] == pytest.approx(0.0)
    assert out["plyteles_sienos_m2"] == pytest.approx(14.0 * 2.8, abs=0.1)


def test_tiles_without_a_layout_use_the_standard_band_and_say_so():
    out = calc_room_quantities(_room(_record({"plyteles": 14.0}), paskirtis="vonia"))
    notes = " ".join(out["_wall_finish_assumptions"])
    assert "Plytelių aukščio išklotinėse neradau" in notes
    assert out["walls_paintable_m2"] > 0                       # painted above the band, not tiled to the ceiling


def test_drawn_zone_replaces_the_kitchen_ladder_band():
    """A painting plan (no tile line in legend) paints a kitchen; an elevation draws a backsplash zone on
    one wall. The ladder posts a kitchen counter band (3 m × 0,6 m); the fix of 2026-10-26 keeps the drawn
    zone and drops the band — the two were summed before, double-counting the backsplash."""
    # a 2,0 × 0,6 m backsplash on a 4 m wall (half the kitchen's north wall)
    zone = {"siena": "x1–x2", "klase": "plyteles", "plotis_m": 2.0, "aukstis_m": 0.6, "plotas_m2": 1.2, "page": 11}
    rec = _record({"dazymas": 11.0}, konturas=14.0, nepazymeta=3.0, legenda=("dazymas",),
                  sienos={"x1–x2": {"ilgis_m": 4.0, "klases": {"dazymas": 4.0}}},
                  zonos=[zone])
    out = calc_room_quantities(_room(rec, paskirtis="virtuve"))
    # tile = the drawn zone only, no 3 m × 0,6 m ladder band on top
    assert out["plyteles_sienos_m2"] == pytest.approx(1.2, abs=0.01)
    notes = " ".join(out["_wall_finish_assumptions"])
    assert "pakeista išklotinėje nubraižytais plytelių laukais" in notes


def test_drawn_zone_replaces_the_bathroom_ladder_band_without_a_plan_tile_line():
    """A bathroom without a plan tile line (legend keys paint only) and one drawn zone: the paskirtis
    ladder would post a 1,2 m band × perimeter; the fix drops the band and keeps the zone."""
    zone = {"siena": "x1–x2", "klase": "plyteles", "plotis_m": 1.5, "aukstis_m": 1.2, "plotas_m2": 1.8, "page": 11}
    rec = _record({"dazymas": 10.0}, konturas=12.0, nepazymeta=2.0, legenda=("dazymas",),
                  sienos={"x1–x2": {"ilgis_m": 2.0, "klases": {"dazymas": 2.0}}},
                  zonos=[zone])
    out = calc_room_quantities(_room(rec, paskirtis="vonia", perimetras_m=12.0))
    assert out["plyteles_sienos_m2"] == pytest.approx(1.8, abs=0.01)
    notes = " ".join(out["_wall_finish_assumptions"])
    assert "pakeista išklotinėje nubraižytais plytelių laukais" in notes


def test_painting_plan_without_tiles_keeps_the_tile_ladder():
    # a „sienų dažymo planas" keys paint only: a bathroom it paints along 3 m keeps its tile band from the ladder,
    # but the band does not run along the painted wall
    rec = _record({"dazymas": 3.0}, konturas=12.0, legenda=("dazymas",))
    room = _room(rec, paskirtis="vonia", perimetras_m=12.0)
    out = calc_room_quantities(room)
    assert out["walls_paintable_m2"] == pytest.approx(3.0 / 12.0 * 12.0 * 2.8, abs=0.2)
    assert out["plyteles_sienos_m2"] <= (1 - 3.0 / 12.0) * 12.0 * 2.8 + 0.01


def test_no_drawing_no_text_hall_is_painted_with_sentence():
    room = _room(None, paskirtis="tamburas")
    room.pop("_sienu_apdaila")
    out = calc_room_quantities(room)
    assert out["walls_paintable_m2"] > 0
    assert any("Išklotinės šiai patalpai nėra" in n for n in out["_wall_finish_assumptions"])


def test_his_no_paint_choice_stands():
    # a storeroom is painted by its standard; his „not painted" differs from it — it is his answer and stands
    room = _room(None, paskirtis="sandeliukas")
    room.pop("_sienu_apdaila")
    rules = translate_user_prefs_to_room_rules({"sandeliukas_painted": False})
    out = calc_room_quantities(room, rules=rules)
    assert out["walls_paintable_m2"] == 0
    assert any("pažymėjote" in n for n in out["_wall_finish_assumptions"])


def test_default_answers_are_no_choice():
    # the wizard posts every default (default_paint_prefs): „garage not painted" equal to the standard is no answer,
    # so a garage with no finish on the drawing is taken as painted — and told so
    from extractor.universal_rules import default_paint_prefs
    room = _room(None, paskirtis="garazas")
    room.pop("_sienu_apdaila")
    out = calc_room_quantities(room, rules=translate_user_prefs_to_room_rules(default_paint_prefs()))
    assert out["walls_paintable_m2"] > 0
    assert any("Išklotinės šiai patalpai nėra" in n for n in out["_wall_finish_assumptions"])


def test_record_the_plan_barely_reaches_falls_back():
    rec = _record({"dazymas": 1.0})
    assert resolve_drawn_wall_finish(_room(rec), 2.8, 14.0, 39.2, 39.2, 0.0) is None


def test_free_reread_returns_the_record():
    from api.room_outline import GEOMETRY_ROOM_KEYS
    from api.room_recalc import _recalc_room  # noqa: F401 — the allowlist module imports
    assert "_sienu_apdaila" in GEOMETRY_ROOM_KEYS


# ── uz_baldu_dazoma — founder decision 2026-10-26 ─────────────────────────────

def test_uz_baldu_dazoma_default_true_paints_unmarked_wall():
    """3 m of a 10 m wall is unmarked (behind a wardrobe). With the default uz_baldu_dazoma=True
    (founder decision 2026-10-26) the unmarked fraction is folded into paint: all 10 m → painted.
    The sentence says the unmarked length was counted as painted and refers to Nustatymai."""
    rec = _record({"dazymas": 7.0}, konturas=10.0, nepazymeta=3.0, legenda=("dazymas",))
    out = calc_room_quantities(_room(rec, perimetras_m=10.0))
    # full 10 m painted → 10 * 2.8 = 28 m²
    assert out["walls_paintable_m2"] == pytest.approx(10.0 * 2.8, abs=0.3)
    notes = " ".join(out["_wall_finish_assumptions"])
    assert "prieš montuojant baldus" in notes, f"Expected new sentence, got: {notes[:200]}"


def test_uz_baldu_dazoma_false_leaves_unmarked_wall_out():
    """Same room with uz_baldu_dazoma=False: the old behaviour — the 3 m behind the wardrobe is
    not painted, and the sentence says so."""
    rec = _record({"dazymas": 7.0}, konturas=10.0, nepazymeta=3.0, legenda=("dazymas",))
    out = calc_room_quantities(_room(rec, perimetras_m=10.0), rules={"_profilis": {"uz_baldu_dazoma": False}})
    # only 7 m painted → 7/10 * 10 * 2.8 = 19.6 m²
    assert out["walls_paintable_m2"] == pytest.approx(7.0 * 2.8, abs=0.3)
    notes = " ".join(out["_wall_finish_assumptions"])
    assert "nedažomas" in notes, f"Expected old sentence, got: {notes[:200]}"
