"""Patikra as a short list of QUESTIONS for the whole project (2026-09-21).

Founder, after walking a real project on the check sheet: „viskas pasižymi labai gerai ir tiksliai…
bet per daug veiksmų visokių būtų rangovui". Measured on that project: 66 facts on screen, 22 of them
need a person, and those are 3 KINDS of question. `build_questions` gathers the facts that wait for a
person (status ≠ read) — the very same facts the room sheet shows, nothing read anew — groups them by
kind, and gives each the program's own proposed answer: „programa siūlo — jūs patvirtinate".
"""
from __future__ import annotations

from extractor.project_questions import ORDER, build_questions


def _quiet(nr: str, **kw) -> dict:
    """A room every fact of which is READ — it asks nothing."""
    room = {
        "nr": nr, "pavadinimas": f"Kambarys {nr}", "puslapio_nr": 1, "paskirtis": "gyvenamoji",
        "plotas_m2": 12.0, "plotas_saltinis": "inline_label",
        "perimetras_m": 14.0,
        "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "per_room",
        "_tile_read_source": "apdailos",
        "grindu_danga": "minksta", "grindu_danga_saltinis": "user_override",
        "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}],
    }
    room.update(kw)
    return room


def _q(out: dict, qid: str) -> dict:
    return next(q for q in out["questions"] if q["id"] == qid)


def test_a_project_where_everything_was_read_asks_nothing():
    out = build_questions({"patalpos": [_quiet("01"), _quiet("02")]})
    assert out["questions"] == []
    assert (out["asked"], out["read"], out["rooms"]) == (0, 12, 2)


def test_the_height_is_asked_once_for_every_room_that_assumes_it():
    rooms = [
        _quiet("01", lubu_aukstis_saltinis="section_average", lubu_aukstis_m=2.82),
        _quiet("02", lubu_aukstis_saltinis="section_average", lubu_aukstis_m=2.82),
        _quiet("03", lubu_aukstis_saltinis="default_fallback", lubu_aukstis_m=2.7),
        _quiet("07", lubu_aukstis_m=2.82),                       # written beside the room — not asked
    ]
    out = build_questions({"patalpos": rooms})
    assert [q["id"] for q in out["questions"]] == ["aukstis"]
    q = _q(out, "aukstis")
    assert (q["kind"], q["answer"], q["unit"]) == ("aukstis", "number_all", "m")
    assert [i["room_nr"] for i in q["items"]] == ["01", "02", "03"]
    assert q["proposed"] == 2.82                                 # the height most of them are computed with
    assert [i["proposed"] for i in q["items"]] == [2.82, 2.82, 2.7]
    assert all(i["field"] == "lubu_auksciai" for i in q["items"])
    assert q["title"] == "Kokio aukščio lubos?"
    assert "07" in q["why"] and "2,82 m" in q["why"]             # where a height WAS read is said
    assert (out["asked"], out["read"]) == (3, 21)


def test_a_height_nobody_wrote_anywhere_says_what_it_is_computed_with():
    out = build_questions({"patalpos": [_quiet("01", lubu_aukstis_saltinis="default_fallback", lubu_aukstis_m=2.7)]})
    q = _q(out, "aukstis")
    assert "neradau" in q["why"] and "2,70 m" in q["why"]


def test_perimeters_the_plan_does_not_state_come_as_one_list_with_the_numbers_in_use():
    rooms = [
        _quiet("03", perimetras_m=21.23, perimetras_saltinis="konturo_ivertis", _perimetras_ivertis_m=21.23,
               _perimetras_priezastis="2 iš 8 sienų be matmens"),
        _quiet("07", perimetras_m=None, _perimetras_ivertis_m=8.6, _perimetras_priezastis="1 iš 4 sienų be matmens"),
        _quiet("09"),
    ]
    out = build_questions({"patalpos": rooms})
    q = _q(out, "perimetras")
    assert (q["answer"], q["unit"]) == ("numbers", "m")
    assert [(i["room_nr"], i["proposed"], i["field"]) for i in q["items"]] == [("03", 21.23, "perimetras_m"), ("07", 8.6, "perimetras_m")]
    assert q["title"] == "2 patalpų sienų ilgiai plane neužrašyti"
    assert all(i["sentence"] for i in q["items"])


def test_one_room_is_named_in_the_title():
    rooms = [_quiet("03", pavadinimas="Koridorius", perimetras_m=21.23, perimetras_saltinis="konturo_ivertis",
                    _perimetras_ivertis_m=21.23)]
    assert _q(build_questions({"patalpos": rooms}), "perimetras")["title"] == "Patalpos 03 Koridorius sienų ilgiai plane neužrašyti"


def test_a_room_the_walls_gave_no_outline_is_pointed_at_and_a_shared_space_is_divided():
    space = {"nariai": ["04", "05"], "page": 1, "perimetras_m": 37.77,
             "polygon_pct": [[0.1, 0.1], [0.6, 0.1], [0.6, 0.5], [0.1, 0.5]]}
    rooms = [
        _quiet("01", pavadinimas="Tambūras", _konturo_priezastis="nesutampa su lentele: kontūras 2,86 m², lentelė 4,48 m²",
               polygon_source="synthesized_from_bbox", _vieta={"page": 1, "cx": 0.2, "cy": 0.7, "saltinis": "numeris"}),
        _quiet("04", pavadinimas="Virtuvė", plotas_m2=26.31, _atvira_erdve=space, perimetras_m=16.08,
               perimetras_saltinis="atviros_erdves_ivertis", _perimetras_ivertis_m=16.08,
               _perimetras_ivertis_saltinis="atviros_erdves_konturas", _konturo_priezastis="atvira erdvė su 05"),
        _quiet("05", pavadinimas="Svetainė", plotas_m2=35.5, _atvira_erdve=space, perimetras_m=21.69,
               perimetras_saltinis="atviros_erdves_ivertis", _perimetras_ivertis_m=21.69,
               _perimetras_ivertis_saltinis="atviros_erdves_konturas", _konturo_priezastis="atvira erdvė su 04"),
    ]
    out = build_questions({"patalpos": rooms, "_meta": {"geometrija": {"lapai": [1]}}})
    assert [q["id"] for q in out["questions"]] == ["konturas", "erdve:04+05", "perimetras"]

    k = _q(out, "konturas")
    assert k["answer"] == "outline" and [i["room_nr"] for i in k["items"]] == ["01"]     # 04/05 share a space: a click finds it again
    assert "nesutampa su lentele" in k["items"][0]["reason"] and k["items"][0]["page"] == 1
    assert k["items"][0]["perimetras_dabar"] == 14.0 and "proposed_outline" not in k["items"][0]

    e = _q(out, "erdve:04+05")
    assert (e["kind"], e["answer"]) == ("erdve", "split")
    assert [i["room_nr"] for i in e["items"]] == ["04", "05"]
    assert e["title"] == "Kur riba tarp patalpų 04 Virtuvė ir 05 Svetainė?"
    assert "26,31" in e["why"] and "35,50" in e["why"] and "sienos" in e["why"].lower()

    # until they are answered, their perimeters stay questions too — each with the number in use
    assert [(i["room_nr"], i["proposed"]) for i in _q(out, "perimetras")["items"]] == [("01", 14.0), ("04", 16.08), ("05", 21.69)]


def test_a_space_of_three_rooms_is_not_offered_for_dividing():
    space = {"nariai": ["04", "05", "06"], "page": 1, "polygon_pct": [[0.1, 0.1], [0.6, 0.1], [0.6, 0.5], [0.1, 0.5]]}
    rooms = [_quiet(nr, _atvira_erdve=space, _konturo_priezastis="atvira erdvė") for nr in ("04", "05", "06")]
    out = build_questions({"patalpos": rooms})
    assert not [q for q in out["questions"] if q["kind"] in ("erdve", "konturas")]


def test_openings_the_walls_show_become_one_checklist_and_the_rest_is_named_for_a_look():
    walls = {"page": 1, "angos": [{"plotis_m": 0.8, "storis_m": 0.1, "i": "03", "line_pct": [[0.2, 0.2], [0.2, 0.25]]}]}
    rooms = [
        _quiet("02", pavadinimas="Katilinė", elementai=[], _angos_sienose=walls, polygon_source="vektoriniai_konturai",
               polygon_pct=[[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]),
        _quiet("09", pavadinimas="Miegamasis", elementai=[]),                              # nothing counted, walls show nothing
        _quiet("03"),
    ]
    out = build_questions({"patalpos": rooms})
    q = _q(out, "angos")
    assert q["answer"] == "openings"
    assert [(i["room_nr"], i["tipas"], i["plotis_mm"], i["aukstis_mm"], i["i"]) for i in q["items"]] == [("02", "duris", 800, 2100, "03")]
    assert q["items"][0]["label"] and q["items"][0]["line_pct"]
    assert [m["room_nr"] for m in q["manual"]] == ["09"] and q["manual"][0]["sentence"]
    assert q["title"] == "Sienose matau 1 angą, kurios nėra durų ir langų sąraše"


def test_doors_and_windows_nobody_can_add_with_one_click_still_ask_for_a_look():
    out = build_questions({"patalpos": [_quiet("09", elementai=[])]})
    q = _q(out, "angos")
    assert q["items"] == [] and [m["room_nr"] for m in q["manual"]] == ["09"]
    assert q["title"] == "Durys ir langai: patikrinkite 1 patalpą"


def test_floor_coverings_and_wall_finishes_chosen_by_purpose_are_offered_as_choices():
    rooms = [
        _quiet("01", grindu_danga=None, grindu_danga_saltinis=None, paskirtis="vonia", plyteles_grindys_m2=4.0),
        _quiet("02", _tile_read_source="paskirtis_default", walls_paintable_m2=30.0),
    ]
    out = build_questions({"patalpos": rooms})
    g = _q(out, "grindys")
    assert g["answer"] == "choices"
    item = g["items"][0]
    assert (item["room_nr"], item["field"], item["proposed"], item["proposed_label"]) == ("01", "grindu_danga", "plyteles", "plytelės")
    assert {c["value"] for c in item["choices"]} == {"plyteles", "minksta", "be_dangos"}

    a = _q(out, "apdaila")
    item = a["items"][0]
    assert (item["room_nr"], item["field"], item["proposed"]) == ("02", "walls_paint_override", 1)
    assert [c["value"] for c in item["choices"]] == [1, 0]


def test_an_area_the_plan_does_not_write_is_asked_with_the_number_in_use():
    out = build_questions({"patalpos": [_quiet("07", plotas_saltinis=None, _area_unconfirmed=True)]})
    q = _q(out, "plotas")
    assert (q["answer"], q["unit"], q["items"][0]["proposed"], q["items"][0]["field"]) == ("numbers", "m²", 12.0, "plotas_m2")


def test_a_room_left_out_of_the_estimate_asks_nothing():
    rooms = [_quiet("01", lubu_aukstis_saltinis="default_fallback"), _quiet("02", lubu_aukstis_saltinis="default_fallback")]
    out = build_questions({"patalpos": rooms, "_apimtis": {"patalpos_ne": ["02"]}})
    assert [i["room_nr"] for i in _q(out, "aukstis")["items"]] == ["01"]
    assert out["rooms"] == 1


def test_questions_come_in_the_order_that_lets_one_answer_settle_the_next():
    assert ORDER == ("aukstis", "konturas", "erdve", "perimetras", "plotas", "angos", "grindys", "apdaila")
    rooms = [
        _quiet("01", _tile_read_source="none", grindu_danga=None, grindu_danga_saltinis=None, elementai=[],
               lubu_aukstis_saltinis="default_fallback", perimetras_m=None, _perimetras_ivertis_m=9.0,
               plotas_saltinis=None, _konturo_priezastis="patalpos vieta plane nerasta tiksliai"),
    ]
    kinds = [q["kind"] for q in build_questions({"patalpos": rooms})["questions"]]
    assert kinds == ["aukstis", "konturas", "perimetras", "plotas", "angos", "grindys", "apdaila"]


def test_the_rebuilt_rooms_are_the_ones_asked_about():
    project = {"patalpos": [_quiet("01")], "v8_rooms": [_quiet("01", lubu_aukstis_saltinis="default_fallback")]}
    # room_facts reads `patalpos`; the questions must agree with the sheet, whatever it reads
    from extractor.room_facts import build_room_facts
    sheet = next(f for f in build_room_facts(project, "01")["facts"] if f["key"] == "aukstis")
    asked = [q["kind"] for q in build_questions(project)["questions"]]
    assert ("aukstis" in asked) == (sheet["status"] != "read")


def test_no_pipeline_words_reach_a_person():
    rooms = [_quiet("01", _tile_read_source="none", grindu_danga=None, grindu_danga_saltinis=None, elementai=[],
                    lubu_aukstis_saltinis="default_fallback", perimetras_m=None, _perimetras_ivertis_m=9.0)]
    text = " ".join(str(q.get(k) or "") for q in build_questions({"patalpos": rooms})["questions"] for k in ("title", "why"))
    for banned in ("Vision", "fallback", "bbox", "polygon", "status", "assumed", "override", "geometrij"):
        assert banned.lower() not in text.lower(), banned


def test_a_room_whose_perimeter_he_typed_himself_is_not_asked_to_be_pointed_at():
    rooms = [_quiet("01", _konturo_priezastis="nesutampa su lentele", polygon_source="synthesized_from_bbox",
                    perimetras_m=9.4, perimetras_saltinis="user_override")]
    assert build_questions({"patalpos": rooms, "_meta": {"geometrija": {"lapai": [1]}}})["questions"] == []


def test_a_room_with_a_proposed_outline_is_offered_it_with_the_reason_and_the_ways_round():
    """objektas_h tambūras, 2026-09-23: „paspaudus du kartus ant tambūro … neaišku, kaip čia pažymėti"."""
    room = _quiet("01", pavadinimas="Tambūras", plotas_m2=4.48, perimetras_m=8.6, polygon_source="synthesized_from_bbox",
                  _konturo_priezastis="sienos prie numerio uždaro 2,86 m², lentelėje 4,48 m²",
                  _vieta={"page": 1, "cx": 0.43, "cy": 0.43, "saltinis": "zenkliukas"},
                  _konturo_siulymas={"page": 1, "polygon_pct": [[0.39, 0.39], [0.46, 0.39], [0.46, 0.44], [0.39, 0.44]], "plotas_m2": 2.86,
                                     "perimetras_m": 6.77, "paklaida": 0.3616, "taskas_pct": [0.42, 0.41]})
    out = build_questions({"patalpos": [room], "_meta": {"geometrija": {"lapai": [1]}}})
    k = _q(out, "konturas")
    item = k["items"][0]
    assert item["proposed_outline"]["polygon_pct"] == [[0.39, 0.39], [0.46, 0.39], [0.46, 0.44], [0.39, 0.44]]
    assert item["proposed_outline"]["taskas_pct"] == [0.42, 0.41] and item["proposed_outline"]["page"] == 1
    assert item["sentence"] == ("Prie numerio 01 sienos uždaro 2,86 m² (sienų 6,77 m), lentelėje 4,48 m² (−36 %) — todėl kontūro "
                                "pats nepriėmiau. Jei tai visa patalpa — „Tinka“. Jei patalpa didesnė, spustelėkite kitoje jos "
                                "vietoje brėžinyje. Arba įrašykite sienų ilgį ranka.")
    assert item["perimetras_dabar"] == 8.6
