"""The perimeter fact shows the strings that were added — on the sheet they
were read from, framed on the room — or a blank with the reason and the
outline's estimate to accept."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.room_facts import build_room_facts  # noqa: E402

OUTLINE = [[0.5, 0.2], [0.7, 0.2], [0.7, 0.4], [0.5, 0.4]]


def _project(room):
    return {"patalpos": [room], "puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 6, "tipas": "floor_plan"}]}


def _wall(texts, metres, saltinis="eilute", page=6):
    return {"edge_pct": [[0.5, 0.2], [0.7, 0.2]], "ilgis_m": metres, "saltinis": saltinis, "kontrole_m": metres,
            "eilutes": [{"text": t, "value_m": int(t) / 1000, "page": page} for t in texts]}


def _perimetras(room):
    return {f["key"]: f for f in build_room_facts(_project(room), room["nr"])["facts"]}["perimetras"]


def test_summed_strings_are_written_out_with_their_sheet_and_framed_on_the_room():
    room = {"nr": "02", "pavadinimas": "Katilinė", "plotas_m2": 6.9, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 12.17, "perimetras_saltinis": "matmenu_eilutes", "_walls_perimetras_m": 12.17,
            "_perimetras_suma": {"suma_m": 12.17, "kontrole_m": 12.2, "sutampa": True, "lapai": [6], "is_konturo_m": 0, "pakartota": 0,
                                 "eilutes": ["1586", "4500", "1586", "4500"]},
            "_sienos": [_wall(["1586"], 1.586), _wall(["4500"], 4.5), _wall(["1586"], 1.586), _wall(["4500"], 4.5)],
            "_konturas": {"page": 1}, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai"}
    p = _perimetras(room)
    assert p["value"] == 12.17 and p["status"] == "read" and p["source"]["kind"] == "planas"
    assert "1586 + 4500 + 1586 + 4500 = 12,17 m" in p["sentence"] and "6 psl." in p["sentence"]
    assert "12,20 m" in p["sentence"]                                   # the outline's check, said
    assert p["source"]["page"] == 6                                     # the sheet the numbers are on…
    x0, y0, x1, y1 = p["source"]["rect_pct"]
    assert x0 < 0.5 and y0 < 0.2 and x1 > 0.7 and y1 > 0.4 and x1 - x0 < 0.5   # …framed on the room, not the whole sheet
    assert "suggestion" not in p


def test_a_length_used_for_the_wall_opposite_and_a_piece_from_the_outline_are_said():
    room = {"nr": "04", "pavadinimas": "Miegamasis", "plotas_m2": 10.05, "puslapio_nr": 2, "lubu_aukstis_m": 2.7,
            "perimetras_m": 12.86, "perimetras_saltinis": "matmenu_eilutes",
            "_perimetras_suma": {"suma_m": 12.86, "kontrole_m": 12.9, "sutampa": True, "lapai": [7], "is_konturo_m": 0.15, "pakartota": 1,
                                 "eilutes": ["3290", "3065", "3290"]},
            "_sienos": [_wall(["3290"], 3.29, page=7), _wall(["3065"], 3.065, page=7), _wall(["3290"], 3.29, page=7),
                        _wall(["3065"], 3.065, "priesinga_siena", page=7), _wall([], 0.15, "konturas")],
            "_konturas": {"page": 2}, "polygon_pct": OUTLINE, "polygon_source": "sienu_konturas"}
    s = _perimetras(room)["sentence"]
    assert "3290 + 3065 + 3290 + 3065 + 0,15 = 12,86 m" in s
    assert "priešing" in s and "0,15 m" in s and "kontūr" in s


def test_blank_perimeter_gives_the_reason_and_offers_the_outline_estimate():
    room = {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 21.23, "perimetras_saltinis": "konturo_ivertis",
            "_perimetras_priezastis": "2 iš 8 sienų be matmens", "_walls_perimetras_m": 21.23,
            "_perimetras_ivertis_m": 21.23, "_perimetras_ivertis_saltinis": "konturas", "_perimetras_pries_geometrija": 16.4,
            "_konturas": {"page": 1}, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai"}
    p = _perimetras(room)
    assert p["value"] is None and p["status"] == "missing"
    assert "2 iš 8 sienų be matmens" in p["sentence"] and "21,23 m" in p["sentence"]
    assert p["suggestion"] == {"value": 21.23, "label": "Priimti 21,23 m"}
    assert p["editable"] == {"field": "perimetras_m", "kind": "number"}
    assert p["source"]["page"] == 1 and p["source"]["rect_pct"][2] - p["source"]["rect_pct"][0] < 0.5


def test_a_perimeter_he_typed_after_a_blank_is_his():
    room = {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 21.0, "perimetras_saltinis": "user_override", "_perimetras_priezastis": "2 iš 8 sienų be matmens",
            "_perimetras_ivertis_m": 21.23, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai"}
    p = _perimetras(room)
    assert p["value"] == 21.0 and "įrašėte patys" in p["sentence"] and "suggestion" not in p


def test_an_open_plan_member_is_told_how_its_share_was_made():
    space = {"nariai": ["04", "05"], "polygon_pct": OUTLINE, "perimetras_m": 37.77, "plotas_m2": 60.55, "page": 1}
    room = {"nr": "04", "pavadinimas": "Virtuvė", "plotas_m2": 26.31, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 16.08, "perimetras_saltinis": "atviros_erdves_ivertis",
            "_perimetras_ivertis_m": 16.08, "_perimetras_ivertis_saltinis": "atviros_erdves_konturas",
            "_perimetras_priezastis": "atvira erdvė su 05 — sienos šių patalpų neskiria; bendras erdvės sienų ilgis 37,77 m padalytas pagal plotą",
            "_atvira_erdve": space, "polygon_source": "synthesized_from_bbox",
            "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]}
    p = _perimetras(room)
    assert p["value"] is None and p["suggestion"]["value"] == 16.08
    assert "atvira erdvė su 05" in p["sentence"] and "37,77 m" in p["sentence"] and "tenka 16,08 m" in p["sentence"]
    assert p["source"]["rect_pct"][0] > 0.4                     # framed on the shared space, not on Vision's box


def test_accepting_the_estimate_is_not_called_typing_it():
    room = {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 21.23, "perimetras_saltinis": "user_override", "_perimetras_priezastis": "2 iš 8 sienų be matmens",
            "_perimetras_ivertis_m": 21.23, "_perimetras_ivertis_saltinis": "konturas",
            "_konturas": {"page": 1}, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai"}
    p = _perimetras(room)
    assert p["value"] == 21.23 and "suggestion" not in p
    assert "Priėmėte" in p["sentence"] and "2 iš 8 sienų be matmens" in p["sentence"] and "įrašėte patys" not in p["sentence"]


def test_a_stored_blank_from_before_the_estimate_became_a_number_still_reads_as_a_blank():
    room = {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": None, "_perimetras_priezastis": "2 iš 8 sienų be matmens", "_perimetras_ivertis_m": 21.23,
            "_konturas": {"page": 1}, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai"}
    p = _perimetras(room)
    assert p["value"] is None and p["suggestion"]["value"] == 21.23


# ── what the drawing pane needs: the walls and the outline, on the fact ─────────

def _summed_room():
    walls = [_wall(["1586"], 1.586), _wall(["4500"], 4.5), _wall(["1586"], 1.586), _wall(["4500"], 4.5, "priesinga_siena")]
    for w in walls:
        for e in w["eilutes"]:
            e["line_pct"] = [[0.39, 0.25], [0.46, 0.25]]
    return {"nr": "02", "pavadinimas": "Katilinė", "plotas_m2": 6.9, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 12.17, "perimetras_saltinis": "matmenu_eilutes",
            "_perimetras_suma": {"suma_m": 12.17, "kontrole_m": 12.2, "sutampa": True, "lapai": [6], "is_konturo_m": 0, "pakartota": 1,
                                 "eilutes": ["1586", "4500", "1586"]},
            "_sienos": walls, "_konturas": {"page": 1}, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai"}


def test_the_perimeter_fact_carries_every_wall_with_its_strings_and_the_outline():
    p = _perimetras(_summed_room())
    assert p["outline"] == {"page": 1, "polygon_pct": OUTLINE}
    assert len(p["walls"]) == 4
    first, borrowed = p["walls"][0], p["walls"][3]
    assert first["page"] == 1 and first["edge_pct"] == [[0.5, 0.2], [0.7, 0.2]] and first["ilgis_m"] == 1.586
    assert first["saltinis"] == "eilute" and first["eilutes"] == [{"text": "1586", "page": 6, "line_pct": [[0.39, 0.25], [0.46, 0.25]]}]
    assert borrowed["saltinis"] == "priesinga_siena"


def test_a_room_whose_walls_could_not_all_be_read_still_shows_which_ones():
    room = _summed_room()
    room["_sienos"][2] = {"edge_pct": [[0.7, 0.4], [0.5, 0.4]], "ilgis_m": None, "saltinis": None, "kontrole_m": 1.585, "eilutes": []}
    room.update({"perimetras_m": 12.2, "perimetras_saltinis": "konturo_ivertis", "_perimetras_ivertis_m": 12.2,
                 "_perimetras_priezastis": "1 iš 4 sienų be matmens"})
    p = _perimetras(room)
    assert p["value"] is None and [w["ilgis_m"] for w in p["walls"]].count(None) == 1
    assert p["walls"][2]["kontrole_m"] == 1.585


def test_visions_box_is_not_an_outline_and_has_no_walls():
    room = {"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 4.48, "puslapio_nr": 1, "lubu_aukstis_m": 2.7, "perimetras_m": 8.6,
            "polygon_pct": OUTLINE, "polygon_source": "synthesized_from_bbox",
            "_konturo_priezastis": "nesutampa su lentele: kontūras 2,86 m², lentelė 4,48 m²"}
    p = _perimetras(room)
    assert p["outline"] is None and p["walls"] == [] and p["outline_reason"].startswith("nesutampa su lentele")


def test_an_open_plan_member_gets_the_shared_outline():
    space = {"nariai": ["04", "05"], "polygon_pct": OUTLINE, "perimetras_m": 37.77, "plotas_m2": 60.55, "page": 1}
    room = {"nr": "04", "pavadinimas": "Virtuvė", "plotas_m2": 26.31, "puslapio_nr": 1, "lubu_aukstis_m": 2.7,
            "perimetras_m": 16.08, "perimetras_saltinis": "atviros_erdves_ivertis", "_perimetras_ivertis_m": 16.08,
            "_perimetras_ivertis_saltinis": "atviros_erdves_konturas", "_perimetras_priezastis": "atvira erdvė su 05",
            "_atvira_erdve": space, "polygon_source": "synthesized_from_bbox", "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]}
    p = _perimetras(room)
    assert p["outline"] == {"page": 1, "polygon_pct": None,
                            "open_space": {"nariai": ["04", "05"], "polygon_pct": OUTLINE, "perimetras_m": 37.77, "page": 1}}
    assert p["walls"] == []


def test_the_room_number_found_on_the_plan_is_the_rooms_marker():
    from extractor.room_facts import build_room_facts
    room = {"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 4.48, "puslapio_nr": 1, "lubu_aukstis_m": 2.7, "perimetras_m": 8.6,
            "_vieta": {"page": 1, "cx": 0.429, "cy": 0.428, "saltinis": "zenkliukas"}}
    sheet = build_room_facts(_project(room), "01")
    assert sheet["room"]["marker_pct"] == [0.429, 0.428]
    room["_vieta"]["saltinis"] = "bbox"                       # Vision's box is a guess, not the printed number
    assert build_room_facts(_project(room), "01")["room"]["marker_pct"] is None


def test_a_figure_nobody_could_check_is_not_called_read_from_the_outline():
    """objektas_h room 01 after the geometry lane: no outline, no strings — the
    8,6 m is what the program estimated from the picture of the plan. The sheet
    used to say „pagal patalpos kontūrą plane" with a quiet, read-looking row."""
    room = {"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 4.48, "puslapio_nr": 1, "lubu_aukstis_m": 2.7, "perimetras_m": 8.6,
            "polygon_pct": OUTLINE, "polygon_source": "synthesized_from_bbox",
            "_konturo_priezastis": "nesutampa su lentele: kontūras 2,86 m², lentelė 4,48 m²"}
    project = _project(room)
    project["_meta"] = {"geometrija": {"konturai": []}}                 # the lane ran and could not read this room's walls
    p = {f["key"]: f for f in build_room_facts(project, "01")["facts"]}["perimetras"]
    assert p["status"] == "assumed" and p["value"] == 8.6
    assert "kontūrą plane" not in p["sentence"] and "nepatikrin" in p["sentence"]
    # a project the lane never ran on keeps the sentence it had (nothing new is known about it)
    old = {f["key"]: f for f in build_room_facts(_project(room), "01")["facts"]}["perimetras"]
    assert old["status"] == "read"


def test_a_boundary_the_lane_proposed_is_said_to_be_the_programs_and_changeable():
    """2026-09-23: the founder asked what difference the boundary makes — none to the wall total, so the lane
    takes its own proposal; the sheet says so, says where, and that it can be changed."""
    room = _summed_room()
    room.update({"nr": "04", "pavadinimas": "Virtuvė", "plotas_m2": 26.31, "perimetras_m": 17.93,
                 "_konturas": {"page": 1, "plotas_m2": 25.74, "plotas_uzrasas_m2": 26.31, "paklaida": 0.0217, "pagal": "kampas",
                               "menamos": [[[0.625, 0.572], [0.625, 0.659]]], "su": ["05"], "saltinis": "padalinta_programos"},
                 "_atvira_erdve": {"nariai": ["04", "05"], "polygon_pct": OUTLINE, "perimetras_m": 37.77, "plotas_m2": 60.55, "page": 1}})
    room["_perimetras_suma"]["suma_m"] = 17.93
    p = _perimetras(room)
    assert p["status"] == "read" and p["value"] == 17.93
    assert "Bendrą erdvę su patalpa 05 padalijau pats — riba per sienos galą, kur su ja sutinka lentelės plotai." in p["sentence"]
    assert "sienų sumai įtakos neturi" in p["sentence"] and "Padalinti erdvę" in p["sentence"] and "padalijote" not in p["sentence"]
    assert p["outline"]["menamos"] == [[[0.625, 0.572], [0.625, 0.659]]] and p["outline"]["open_space"]["nariai"] == ["04", "05"]
    assert p["outline"]["riba"] == "programos"                     # the sheet keeps „Padalinti erdvę" for a redraw
    room["_konturas"]["pagal"] = "plotai"
    assert "ten, kur plotai pasidalija lentelės santykiu" in _perimetras(room)["sentence"]


def test_what_the_walls_close_around_the_number_is_proposed_when_the_table_disagrees():
    """objektas_h tambūras (2026-09-23): no outline — but the 2,86 m² the walls close is offered on the drawing."""
    room = {"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 4.48, "puslapio_nr": 1, "lubu_aukstis_m": 2.7, "perimetras_m": 8.6,
            "polygon_pct": OUTLINE, "polygon_source": "synthesized_from_bbox",
            "_konturo_priezastis": "sienos prie numerio uždaro 2,86 m², lentelėje 4,48 m²",
            "_konturo_siulymas": {"page": 1, "polygon_pct": [[0.39, 0.39], [0.46, 0.39], [0.46, 0.44], [0.39, 0.44]], "plotas_m2": 2.86,
                                  "perimetras_m": 6.77, "paklaida": 0.3616, "sujungta": 1, "durys_m": 1.6, "taskas_pct": [0.42, 0.41]}}
    p = _perimetras(room)
    assert p["outline"] is None and p["outline_reason"].startswith("sienos prie numerio")
    assert p["outline_proposal"] == {"page": 1, "polygon_pct": [[0.39, 0.39], [0.46, 0.39], [0.46, 0.44], [0.39, 0.44]], "plotas_m2": 2.86,
                                     "perimetras_m": 6.77, "paklaida": 0.3616, "plotas_uzrasas_m2": 4.48, "taskas_pct": [0.42, 0.41]}
    room["polygon_source"] = "corrected"                         # once he has an outline, nothing is proposed
    assert "outline_proposal" not in _perimetras(room)
