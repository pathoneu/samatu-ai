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


# the drawing's door schedule names the frame type — such a project asks nothing about its doors
_SCHEDULE = {"status": "lentele", "beapvadines": 1, "su_apvadais": 0, "lentele": {"page": 1, "eilutes": [
    {"kodas": "D-1", "plotis_mm": 900, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 1}]},
    "sakinys": "Durų žiniaraštyje (1 lapas): D-1 900×2100 beapvadinės ×1; su apvadais nėra."}


def test_a_project_where_everything_was_read_asks_nothing():
    out = build_questions({"patalpos": [_quiet("01"), _quiet("02")], "_duru_ziniarastis": _SCHEDULE})
    assert out["questions"] == []
    assert (out["asked"], out["read"], out["rooms"]) == (0, 12, 2)


def test_the_height_is_asked_once_for_every_room_that_assumes_it():
    rooms = [
        _quiet("01", lubu_aukstis_saltinis="section_average", lubu_aukstis_m=2.82),
        _quiet("02", lubu_aukstis_saltinis="section_average", lubu_aukstis_m=2.82),
        _quiet("03", lubu_aukstis_saltinis="default_fallback", lubu_aukstis_m=2.7),
        _quiet("07", lubu_aukstis_m=2.82),                       # written beside the room — not asked
    ]
    out = build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE})
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
    out = build_questions({"patalpos": rooms, "_meta": {"geometrija": {"lapai": [1]}}, "_duru_ziniarastis": _SCHEDULE})
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
        _quiet("03", elementai=[{"tipas": "duris", "kiekis": 1, "plotis_mm": 1400, "aukstis_mm": 2100}]),   # 03's own door is another opening
    ]
    out = build_questions({"patalpos": rooms})
    q = _q(out, "angos")
    assert q["answer"] == "openings"
    assert [(i["room_nr"], i["tipas"], i["plotis_mm"], i["aukstis_mm"], i["i"]) for i in q["items"]] == [("02", "duris", 800, 2100, "03")]
    assert q["items"][0]["label"] and q["items"][0]["line_pct"]
    assert [m["room_nr"] for m in q["manual"]] == ["09"] and q["manual"][0]["sentence"]
    assert q["title"] == "Sienose matau 1 angą, kurios nėra durų ir langų sąraše"


def test_an_opening_whose_door_the_room_beyond_lists_is_not_proposed_again():
    """2026-09-23: a door between two rooms stands in ONE list — proposing it from the other side doubled the
    reveals and the frameless-door row on objektas_h (70 → 100 m after six adds)."""
    walls = {"page": 1, "angos": [{"plotis_m": 0.8, "storis_m": 0.1, "i": "03", "line_pct": [[0.2, 0.2], [0.2, 0.25]]}]}
    rooms = [
        _quiet("02", pavadinimas="Katilinė", elementai=[], _angos_sienose=walls, polygon_source="vektoriniai_konturai",
               polygon_pct=[[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]),
        _quiet("03"),                                                                        # lists a 0,9 m door: the same opening
    ]
    out = build_questions({"patalpos": rooms})
    assert not [q for q in out["questions"] if q["kind"] == "angos"]
    from extractor.room_facts import build_room_facts
    f = next(x for x in build_room_facts({"patalpos": rooms}, "02")["facts"] if x["key"] == "angos")
    assert "įrašytos prie tos patalpos" in f["sentence"] and f["suggestions"] == []


def test_doors_and_windows_nobody_can_add_with_one_click_still_ask_for_a_look():
    out = build_questions({"patalpos": [_quiet("09", elementai=[])]})
    q = _q(out, "angos")
    assert q["items"] == [] and [m["room_nr"] for m in q["manual"]] == ["09"]
    assert q["title"] == "Durys ir langai: patikrinkite 1 patalpą"
    # 2026-10-06 (contractor walkthrough): no shouting, and each room says what to check in plain words
    # 2026-10-19: answered on the card — the reason says what the answer does, never „open the room"
    assert q["why"] == ("Įrašykite, kiek durų ir langų yra šioje patalpoje — siūlau tiek, kiek nubraižyta sienose. "
                        "Pagal jūsų skaičių perskaičiuosiu angokraščius, dažomą sienų plotą ir grindjuostes.")
    assert q["manual"][0]["sentence"] == ("Durų ir langų šioje patalpoje neradau — "
                                          "šios patalpos sienų brėžinyje neperskaičiau.")
    m = q["manual"][0]
    assert m["durys"] == {"sarase": 0, "sienose": 0, "laisvos": []} and m["langai"]["sarase"] == 0
    assert m["proposed"] == {"durys": 0, "langai": 0} and m["sienos"] is False
    assert q["manual"][0]["details"] == ""


def test_more_openings_than_the_list_names_says_so_and_keeps_the_openings_for_a_second_look():
    """An older blob the walls pass has not seen (no marks on its elements): only the totals are compared.
    A door and a window are listed, the walls show three openings — nothing a click could add, so he is
    told the list may be short, not handed the opening widths to work it out."""
    walls = {"page": 1, "angos": [
        {"plotis_m": 0.8, "storis_m": 0.1, "i": "02", "line_pct": [[0.2, 0.2], [0.2, 0.25]]},
        {"plotis_m": 0.9, "storis_m": 0.1, "i": "03", "line_pct": [[0.3, 0.3], [0.3, 0.35]]},
        {"plotis_m": 1.2, "storis_m": 0.3, "i": "laukas", "line_pct": [[0.1, 0.1], [0.15, 0.1]]},
    ]}
    room = _quiet("01", polygon_source="vektoriniai_konturai", _angos_sienose=walls,
                  polygon_pct=[[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
                  elementai=[{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100},
                             {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500}])
    q = _q(build_questions({"patalpos": [room], "_duru_ziniarastis": _SCHEDULE}), "angos")
    assert q["items"] == [] and [m["room_nr"] for m in q["manual"]] == ["01"]
    m = q["manual"][0]
    assert m["sentence"] == "Sienose matau daugiau angų, nei sąraše yra durų ir langų."
    # an older blob the walls pass has not seen: the list's own numbers on both sides
    assert m["proposed"] == {"durys": 1, "langai": 1}
    assert "Sienose angų daugiau — 3" in m["details"]


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
    # the schedule questions (Pathon v3 W3-A, `lenteles=True`) stand beside the kind they check
    # `lentele_zymos` (W5-D D10): the schedule's codes on the plan, after the two schedule counts
    assert ORDER == ("aukstis", "konturas", "erdve", "perimetras", "plotas", "angos", "durys", "lentele_durys",
                     "lentele_langai", "lentele_zymos", "grindys", "lentele_apdaila", "apdaila", "lentele_suma")
    rooms = [
        _quiet("01", _tile_read_source="none", grindu_danga=None, grindu_danga_saltinis=None, elementai=[],
               lubu_aukstis_saltinis="default_fallback", perimetras_m=None, _perimetras_ivertis_m=9.0,
               plotas_saltinis=None, _konturo_priezastis="patalpos vieta plane nerasta tiksliai"),
        _quiet("02", elementai=[{"tipas": "pasleptos_duris", "kiekis": 1}, {"tipas": "duris", "kiekis": 1}]),
    ]
    kinds = [q["kind"] for q in build_questions({"patalpos": rooms})["questions"]]
    assert kinds == ["aukstis", "konturas", "perimetras", "plotas", "angos", "durys", "grindys", "apdaila"]


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
    assert build_questions({"patalpos": rooms, "_meta": {"geometrija": {"lapai": [1]}}, "_duru_ziniarastis": _SCHEDULE})["questions"] == []


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


def test_the_door_type_is_asked_once_for_the_project_when_only_the_symbols_or_a_finish_board_say_it():
    """2026-09-23, the founder: „kiek durų su apvadais žiniaraštis rodo?" — a frameless door draws like a framed
    one, so the plan's symbols alone propose an answer and ask; the drawing's schedule or his choice settle it."""
    rooms = [_quiet("01", elementai=[{"tipas": "pasleptos_duris", "kiekis": 1}, {"tipas": "duris", "kiekis": 1}]),
             _quiet("02", elementai=[{"tipas": "duris", "kiekis": 2}])]
    out = build_questions({"patalpos": rooms, "_duru_ziniarastis": {"status": "nera", "sakinys": "Durų žiniaraščio ar durų tipo užrašų brėžinyje nėra."}})
    q = _q(out, "durys")
    assert (q["kind"], q["answer"], q["title"]) == ("durys", "choices", "Vidaus durys — beapvadinės ar su apvadais?")
    item = q["items"][0]
    assert (item["room_nr"], item["field"], item["proposed"], item["count"]) == ("", "vidaus_durys_beapvadines", 1, 4)
    assert [c["value"] for c in item["choices"]] == [1, 0] and "patvirtinkite" in item["sentence"]
    assert "Lauko durys" in q["why"]
    # a finish board naming the door products → framed proposed
    board = build_questions({"patalpos": rooms, "_duru_ziniarastis": {"status": "gaminiai", "gaminiai": ["DECO-10 vidaus durys"],
                                                                        "sakinys": "Durų žiniaraščio nėra; apdailos lape nurodyti vidaus durų gaminiai (DECO-10 vidaus durys), beapvadinių niekur neminima."}})
    assert _q(board, "durys")["items"][0]["proposed"] == 0
    # the schedule, a governing note or his own choice settle it — nothing is asked
    assert all(q["kind"] != "durys" for q in build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE})["questions"])
    assert all(q["kind"] != "durys" for q in build_questions({"patalpos": rooms, "_overrides": {"vidaus_durys_beapvadines": False}})["questions"])
    # no interior doors — nothing to ask
    assert all(q["kind"] != "durys" for q in build_questions({"patalpos": [_quiet("01", elementai=[])]})["questions"])
    # exterior doors are not the question's doors
    ext = [_quiet("01", elementai=[{"tipas": "duris", "kiekis": 1, "_exterior": True}])]
    assert all(q["kind"] != "durys" for q in build_questions({"patalpos": ext})["questions"])


# ── 2026-10-06: openings a listed window could stand in are named for a look, not offered ───────────────

def _walls(*angos: tuple) -> dict:
    return {"page": 1, "angos": [{"i": i, "plotis_m": w, "storis_m": 0.3, "line_pct": [[0.1 + 0.02 * k, 0.1], [0.1 + 0.02 * k, 0.12]]}
                                 for k, (i, w) in enumerate(angos)]}


def _outlined(nr: str, pavadinimas: str, elementai: list[dict], *angos: tuple, **kw) -> dict:
    return _quiet(nr, pavadinimas=pavadinimas, elementai=elementai, _angos_sienose=_walls(*angos),
                  polygon_source="vektoriniai_konturai", polygon_pct=[[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]], **kw)


def _el(tipas: str, w: int, h: int, n: int = 1) -> dict:
    return {"tipas": tipas, "kiekis": n, "plotis_mm": w, "aukstis_mm": h}


def test_openings_a_listed_window_could_stand_in_are_named_for_a_look_not_offered():
    """objektas_a on production: „Sienose matau 7 angas, kurių nėra durų ir langų sąraše", all pre-ticked — but
    102's 3,90 and 0,96 m and 104's 1,00 and 2,30 m openings are most likely the windows those rooms already list
    (3,00 m ×2, 1,80 m), read at another width; accepting counted them twice (angokraščiai 82,93 → ~112 m, true
    89,39). 101 and 103 list no window: their openings to the outside are still offered."""
    import copy

    from extractor import universal_rules as ur
    rooms = [
        _outlined("101", "Tambūras", [_el("duris", 1440, 2100), _el("duris", 1150, 2100), _el("pasleptos_duris", 1150, 2100)],
                  ("102", 1.15), ("103", 1.15), ("laukas", 1.44), ("laukas", 1.3), paskirtis="tamburas"),
        _outlined("102", "Svetainė, virtuvė", [_el("langas", 3000, 2600, n=2), _el("langas", 2110, 2600), _el("duris", 1730, 2400)],
                  ("101", 1.15), ("laukas", 2.11), ("laukas", 1.73), ("laukas", 3.9), ("laukas", 0.96)),
        _outlined("103", "Koridorius", [_el("duris", 1150, 2100)], ("101", 1.15), ("104", 1.15), ("laukas", 1.9),
                  paskirtis="koridorius"),
        _outlined("104", "Miegamasis", [_el("langas", 1800, 2000), _el("duris", 1150, 2100)],
                  ("103", 1.15), ("laukas", 1.0), ("laukas", 2.3), paskirtis="miegamasis"),
    ]
    ur.prepare_rooms_for_calc(rooms, overrides={"vidaus_durys_beapvadines": False})
    stored = copy.deepcopy(rooms)
    q = _q(build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE}), "angos")
    assert [(i["room_nr"], i["tipas"], i["plotis_m"], i["i"]) for i in q["items"]] == [
        ("101", "langas", 1.3, "laukas"), ("103", "langas", 1.9, "laukas")]
    assert q["title"] == "Sienose matau 2 angas, kurių nėra durų ir langų sąraše"
    assert [m["room_nr"] for m in q["manual"]] == ["102", "104"]
    assert q["manual"][0]["sentence"] == (
        "Sąraše langai 3,00 m (2 vnt.) neįstatyti į angas, o sienose liko angos 3,90 ir 0,96 m — tikriausiai tai tie "
        "patys langai, tik kito pločio.")
    # the card stands the listed windows in the openings left: as many as listed, at the drawn widths
    assert q["manual"][0]["langai"] == {"sarase": 3, "sienose": 3, "laisvos": [
        {"plotis_m": 3.9, "i": "laukas"}, {"plotis_m": 0.96, "i": "laukas"}]}
    assert q["manual"][1]["sentence"] == (
        "Sąraše langas 1,80 m neįstatytas į angą, o sienose liko angos 1,00 ir 2,30 m — tikriausiai viena iš jų ir yra "
        "tas langas, tik kito pločio.")
    assert q["manual"][0]["details"].startswith("3 langai, 1 durys. Sienose 5 angos:")       # the room sheet's account
    # only what is offered and said changed: the rooms — and every quantity made of them — are as stored
    assert rooms == stored


def test_a_room_with_a_door_to_offer_and_a_window_held_back_is_in_both_lists():
    from extractor import universal_rules as ur
    rooms = [
        _outlined("05", "Svetainė", [_el("langas", 2200, 1500), _el("duris", 900, 2100)],
                  ("07", 0.9), ("06", 0.8), ("laukas", 2.68)),
        _quiet("06", elementai=[_el("duris", 1400, 2100)]),            # its door is another opening
        _quiet("07"),
    ]
    ur.prepare_rooms_for_calc(rooms, overrides={"vidaus_durys_beapvadines": False})
    q = _q(build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE}), "angos")
    assert [(i["room_nr"], i["tipas"], i["plotis_m"], i["i"]) for i in q["items"]] == [("05", "duris", 0.8, "06")]
    assert [m["room_nr"] for m in q["manual"]] == ["05"]
    assert q["manual"][0]["sentence"].startswith("Sąraše langas 2,20 m neįstatytas į angą, o sienose liko anga 2,68 m")


def test_a_held_back_door_opening_is_said_in_place_of_the_bare_count():
    from extractor import universal_rules as ur
    rooms = [_outlined("03", "Koridorius", [_el("duris", 800, 2100), _el("duris", 1200, 2100)], ("07", 0.8), ("vidus", 0.7),
                       paskirtis="koridorius")]
    ur.prepare_rooms_for_calc(rooms, overrides={"vidaus_durys_beapvadines": False})
    q = _q(build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE}), "angos")
    assert q["items"] == [] and q["manual"][0]["sentence"] == (
        "Sąraše durys 1,20 m neįstatytos į angą, o sienose liko anga į gretimą patalpą (0,70 m) — tikriausiai tai tos "
        "pačios durys, tik kito pločio.")
    assert q["manual"][0]["durys"]["laisvos"] == [{"plotis_m": 0.7, "i": "vidus"}]


def test_door_and_window_counts_are_answered_on_the_card_and_the_answered_room_asks_no_more():
    """2026-10-19, the founder on the first v3 walk: „negaliu iškart vietoje pataisyti to, ką reikia". The room
    to check carries the list's number and the walls' number per kind, the walls' as the proposal — and a
    room whose doors no opening backs at all keeps one door (every room has a way in). Once he answered the
    count on the card (`_angos_patikrinta_at`), the room asks no more."""
    from extractor import universal_rules as ur
    rooms = [_outlined("09", "Techninė", [_el("duris", 900, 2100, n=2), _el("langas", 1200, 1500)], ("laukas", 1.2))]
    ur.prepare_rooms_for_calc(rooms, overrides={"vidaus_durys_beapvadines": False})
    q = _q(build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE}), "angos")
    m = q["manual"][0]
    assert m["durys"]["sarase"] == 2 and m["durys"]["sienose"] == 0
    assert m["proposed"] == {"durys": 1, "langai": 1}
    assert m["page"] == 1 and m["rect_pct"] and m["sienos"] is True and m["angos_brezinyje"] == 1
    assert "atidaryk" not in (q["why"] + m["sentence"]).lower()
    rooms[0]["_angos_patikrinta_at"] = "2026-10-19T10:00:00Z"
    assert not [x for x in build_questions({"patalpos": rooms, "_duru_ziniarastis": _SCHEDULE})["questions"]
                if x["kind"] == "angos"]
