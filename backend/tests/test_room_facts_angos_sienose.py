"""The door-and-window fact against the openings the WALLS show.

Until 2026-09-20 this was the one fact with no evidence on the drawing („Brėžinys jų
vietos nenurodo, todėl pažymėti negaliu"), and its count came from Vision alone: on
objektas_h four rooms had no door at all while the wall solid shows each of their
doors. The geometry lane now leaves `_angos_sienose` on every outlined room; the
fact marks those openings on the drawing, says whether the counted list agrees
with them, and offers a one-click add only where nothing else could be meant.

Quantities never change on their own — only when he adds the opening.
"""
from __future__ import annotations

from extractor import universal_rules as ur
from extractor.project_questions import build_questions
from extractor.room_facts import build_room_facts

OUTLINE = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]]


def _opening(i: str, width: float, x: float = 0.4) -> dict:
    return {"i": i, "plotis_m": width, "storis_m": 0.2, "line_pct": [[x, 0.25], [x, 0.29]]}


def _fact(elementai: list[dict], angos: list[dict] | None, **room) -> dict:
    r = {"nr": "06", "puslapio_nr": 2, "plotas_m2": 12.0, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai",
         "_konturas": {"page": 1}, "elementai": elementai, **room}
    if angos is not None:
        r["_angos_sienose"] = {"page": 1, "angos": angos}
    facts = build_room_facts({"patalpos": [r]}, "06")["facts"]
    return next(f for f in facts if f["key"] == "angos")


DOOR = {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}
WINDOW = {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500}


def test_a_list_that_agrees_with_the_walls_is_read_and_marked_on_the_drawing():
    f = _fact([WINDOW, DOOR], [_opening("03", 0.77), _opening("laukas", 1.37, x=0.2)])
    assert f["status"] == "read" and f["value"] == 2
    assert f["sentence"] == ("1 langas, 1 durys. Sienose tiek pat angų: į patalpą 03 (0,77 m), į lauką (1,37 m) — "
                             "pažymėtos brėžinyje.")
    # the crop and the marks are on the sheet the room's outline is drawn on
    assert f["source"]["page"] == 1 and f["source"]["kind"] == "sienu_angos"
    assert f["source"]["rect_pct"] == [0.17, 0.17, 0.43, 0.38]
    assert f["openings"] == {"page": 1, "items": [
        {"line_pct": [[0.4, 0.25], [0.4, 0.29]], "plotis_m": 0.77, "i": "03", "lauko": False},
        {"line_pct": [[0.2, 0.25], [0.2, 0.29]], "plotis_m": 1.37, "i": "laukas", "lauko": True}]}
    assert f["suggestions"] == []


def test_a_door_the_list_lacks_is_asked_about_and_offered():
    """objektas_h room 06: one window counted, no door — and a 0,77 m opening to the corridor in its wall."""
    f = _fact([WINDOW], [_opening("03", 0.77), _opening("laukas", 1.37, x=0.2)])
    assert f["status"] == "assumed"
    assert f["sentence"] == ("1 langas. Sienose angų daugiau — 2: į patalpą 03 (0,77 m), į lauką (1,37 m). "
                             "Durų nesuskaičiuota, nors sienoje yra anga į patalpą 03 — patikrinkite brėžinyje ir pridėkite.")
    assert f["suggestions"] == [{"tipas": "duris", "plotis_mm": 800, "aukstis_mm": 2100, "i": "03", "plotis_m": 0.77,
                                 "label": "Pridėti duris 0,80 × 2,10 m — anga į patalpą 03",
                                 "line_pct": [[0.4, 0.25], [0.4, 0.29]]}]


def test_a_window_the_list_lacks_is_offered_at_the_standard_height():
    f = _fact([DOOR], [_opening("03", 0.9), _opening("laukas", 1.37, x=0.2)])
    assert f["status"] == "assumed"
    assert "Langų nesuskaičiuota, nors sienoje yra anga į lauką" in f["sentence"]
    assert [(s["tipas"], s["plotis_mm"], s["aukstis_mm"]) for s in f["suggestions"]] == [("langas", 1400, 1500)]
    assert f["suggestions"][0]["label"] == "Pridėti langą 1,40 × 1,50 m — anga į lauką"


def test_a_room_with_nothing_counted_stays_a_blank_but_shows_what_the_walls_have():
    f = _fact([], [_opening("03", 0.8)])
    assert f["status"] == "missing" and f["value"] == 0 and f["details"] == []
    assert f["sentence"] == ("Durų ir langų nesuskaičiuota, o sienose yra 1 anga: į patalpą 03 (0,80 m). "
                             "Patikrinkite brėžinyje ir pridėkite.")
    assert [s["tipas"] for s in f["suggestions"]] == ["duris"]
    assert len(f["openings"]["items"]) == 1


def test_more_openings_than_counted_without_an_obvious_gap_asks_but_offers_nothing():
    """One door counted, three openings to other rooms: which two are missing is his to say."""
    f = _fact([DOOR, WINDOW], [_opening("03", 0.87), _opening("08", 1.4), _opening("10", 1.18), _opening("laukas", 0.97, x=0.2)])
    assert f["status"] == "assumed" and f["suggestions"] == []
    assert f["sentence"] == ("1 durys, 1 langas. Sienose angų daugiau — 4: į patalpą 03 (0,87 m), į patalpą 08 (1,40 m), "
                             "į patalpą 10 (1,18 m), į lauką (0,97 m). Patikrinkite brėžinyje, ar sąraše netrūksta durų ar lango.")


def test_fewer_openings_in_the_walls_is_said_without_alarm():
    """The walls do not show everything (a window behind a sill fill, a glazed wall): the count stands."""
    f = _fact([DOOR, DOOR, WINDOW], [_opening("03", 0.8)])
    assert f["status"] == "read" and f["suggestions"] == []
    assert f["sentence"] == ("2 durys, 1 langas. Sienose matyti 1 anga: į patalpą 03 (0,80 m); kitų angų sienos nerodo — "
                             "jei jų tikrai nėra, sumažinkite skaičių.")


def test_a_space_without_its_own_outline_is_a_neighbouring_room():
    f = _fact([WINDOW, DOOR], [_opening("vidus", 0.64), _opening("laukas", 1.0, x=0.2)])
    assert "į gretimą patalpą (0,64 m)" in f["sentence"]


def test_a_roof_window_is_not_looked_for_in_the_walls():
    skylight = {"tipas": "stoglangis", "kiekis": 1, "plotis_mm": 780, "aukstis_mm": 1400}
    f = _fact([skylight, DOOR], [_opening("03", 0.8)])
    assert f["status"] == "read" and f["value"] == 2
    assert f["sentence"].startswith("1 stoglangis, 1 durys. Sienose tiek pat angų: į patalpą 03 (0,80 m)")


def test_sizes_from_the_schedule_are_still_credited():
    anchored = {**DOOR, "_schedule_anchored": True, "_schedule_page": 9}
    f = _fact([anchored], [_opening("03", 0.9)])
    assert f["sentence"] == ("1 durys. Matmenys — iš žiniaraščio, psl. 9. Sienose tiek pat angų: į patalpą 03 (0,90 m) — "
                             "pažymėtos brėžinyje.")


def test_without_wall_openings_the_fact_is_what_it_was():
    f = _fact([WINDOW, DOOR], None)
    assert f["status"] == "read" and f["source"]["page"] == 2 and f["source"]["kind"] == "planas"
    assert f["openings"] is None and f["suggestions"] == []
    assert f["sentence"].startswith("1 langas, 1 durys. Durys ir langai suskaičiuoti plane.")
    empty = _fact([WINDOW], [])                                   # an outlined room whose walls show no gap at all
    assert empty["openings"] is None and empty["status"] == "read"


def test_the_plural_of_anga():
    many = [_opening(f"{n:02d}", 0.8) for n in range(1, 11)]
    f = _fact([DOOR] * 10, many)
    assert "Sienose tiek pat angų" in f["sentence"]
    five = _fact([DOOR], [_opening("03", 0.8), _opening("04", 0.8), _opening("05", 0.8), _opening("07", 0.8), _opening("08", 0.8)])
    assert "Sienose angų daugiau — 5:" in five["sentence"]


# ── 2026-10-06: a listed unit no opening took holds back the leftover openings of its kind ───────────────
# objektas_a on production: „Sienose matau 7 angas, kurių nėra durų ir langų sąraše", every one pre-ticked —
# four of them in rooms whose listed windows stood in no opening: most likely those windows, read at another
# width. Only what is OFFERED and SAID changes here; the walls pass and every quantity stay as they were.


def _el(tipas: str, w: int, h: int, n: int = 1) -> dict:
    return {"tipas": tipas, "kiekis": n, "plotis_mm": w, "aukstis_mm": h}


def _stood(nr: str, elementai: list[dict], angos: list[tuple], **room) -> dict:
    """A room as production stores it: walls read, doors and windows stood in their openings by the pass."""
    r = {"nr": nr, "puslapio_nr": 2, "paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0,
         "lubu_aukstis_m": 2.7, "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai",
         "_konturas": {"page": 1}, "elementai": elementai,
         "_angos_sienose": {"page": 1, "angos": [_opening(i, w, x=round(0.2 + 0.05 * k, 2)) for k, (i, w) in enumerate(angos)]},
         **room}
    ur.prepare_rooms_for_calc([r])
    return r


def _angos(room: dict) -> dict:
    return next(f for f in build_room_facts({"patalpos": [room]}, room["nr"])["facts"] if f["key"] == "angos")


def test_listed_windows_no_opening_took_hold_back_the_openings_left_to_the_outside():
    """objektas_a 102 (production): the pass stood the 2,11 m window and the 1,73 m door, and found no opening for
    the two 3,00 m windows; the 3,90 and 0,96 m openings it left are those windows at another width. Offered as
    new windows, pre-ticked, they were counted twice — the project's seven offers would have taken the reveals
    from 82,93 to ~112 m (true 89,39)."""
    room = _stood("102", [_el("langas", 3000, 2600, n=2), _el("langas", 2110, 2600), _el("duris", 1730, 2400)],
                  [("laukas", 2.11), ("laukas", 1.73), ("laukas", 3.9), ("laukas", 0.96)])
    f = _angos(room)
    held = ("Sąraše langai 3,00 m (2 vnt.) neįstatyti į angas, o sienose liko angos 3,90 ir 0,96 m — tikriausiai "
            "tai tie patys langai, tik kito pločio. Patikrinkite brėžinyje; jei langas kitas — spustelėkite jo angą brėžinyje "
            "ir įrašykite plotį.")
    assert f["suggestions"] == [] and f["status"] == "assumed"      # named for a look, not offered — still asks
    assert f["sentence"] == ("3 langai, 1 durys. Sienose 4 angos: į lauką (2,11 m), į lauką (1,73 m), į lauką (3,90 m), "
                             "į lauką (0,96 m). " + held)
    assert f["withheld"] == [{"tipas": "langas", "sentence": held, "listed": [{"plotis_m": 3.0, "kiekis": 2}],
                              "openings": [{"plotis_m": 3.9, "i": "laukas", "line_pct": [[0.3, 0.25], [0.3, 0.29]]},
                                           {"plotis_m": 0.96, "i": "laukas", "line_pct": [[0.35, 0.25], [0.35, 0.29]]}]}]
    assert f["value"] == 4                                          # the list is what it was: nothing added or taken


def test_one_listed_window_and_two_openings_left_names_both_widths():
    """objektas_a 104: a 1,80 m window listed, 1,00 and 2,30 m openings to the outside left — one is that window,
    the other maybe one the list lacks; which is his to see. Once the window stands (he corrects its width), the
    opening still left is offered again."""
    room = _stood("104", [_el("langas", 1800, 2000), _el("duris", 1150, 2100)],
                  [("103", 1.15), ("laukas", 1.0), ("laukas", 2.3)])
    f = _angos(room)
    assert f["suggestions"] == [] and f["status"] == "assumed"
    assert f["sentence"].endswith(
        "Sąraše langas 1,80 m neįstatytas į angą, o sienose liko angos 1,00 ir 2,30 m — tikriausiai viena iš jų ir yra "
        "tas langas, tik kito pločio. Patikrinkite brėžinyje; jei langas kitas — spustelėkite jo angą brėžinyje ir įrašykite plotį.")
    room["elementai"][0].update({"plotis_mm": 2300, "_dydis_user": True})
    ur.prepare_rooms_for_calc([room])
    f = _angos(room)
    assert [(s["tipas"], s["plotis_m"]) for s in f["suggestions"]] == [("langas", 1.0)] and f["withheld"] == []


def test_a_room_whose_listed_windows_all_stand_is_still_offered_the_opening_left():
    """objektas_a 101 and 103 list no window: an opening to the outside nothing stands in can only be one the
    list lacks — offered as before. So it is where every listed window stands in its own opening."""
    hall = _stood("101", [_el("duris", 1440, 2100)], [("laukas", 1.44), ("laukas", 1.3)], paskirtis="tamburas")
    f = _angos(hall)
    assert [(s["tipas"], s["plotis_m"]) for s in f["suggestions"]] == [("langas", 1.3)] and f["withheld"] == []
    assert "1 angoje niekas nestovi — patikrinkite brėžinyje ir pridėkite." in f["sentence"]
    bedroom = _stood("108", [_el("langas", 2060, 1500)], [("laukas", 2.06), ("laukas", 1.2)])
    f = _angos(bedroom)
    assert [(s["tipas"], s["plotis_m"]) for s in f["suggestions"]] == [("langas", 1.2)] and f["withheld"] == []


def test_more_listed_windows_than_openings_left_says_one_of_them():
    room = _stood("05", [_el("langas", 3000, 2600, n=2), _el("duris", 900, 2100)], [("03", 0.9), ("laukas", 3.9)])
    f = _angos(room)
    assert f["suggestions"] == []
    assert f["withheld"][0]["sentence"].startswith(
        "Sąraše langai 3,00 m (2 vnt.) neįstatyti į angas, o sienose liko anga 3,90 m — tikriausiai tai vienas iš tų "
        "langų, tik kito pločio.")


def test_a_listed_door_no_opening_backs_holds_back_the_door_openings_left():
    """The same for doors: a 1,20 m door the pass stood in no opening, and a 0,70 m opening to the space beside
    that nothing stands in — named with both widths in place of the bare count, not offered as a second door."""
    room = _stood("03", [_el("duris", 800, 2100), _el("duris", 1200, 2100)], [("07", 0.8), ("vidus", 0.7)],
                  paskirtis="koridorius")
    f = _angos(room)
    assert f["suggestions"] == [] and f["status"] == "assumed"
    assert f["sentence"] == (
        "2 durys. Sienose 2 angos: į patalpą 07 (0,80 m), į gretimą patalpą (0,70 m). Sąraše durys 1,20 m neįstatytos "
        "į angą, o sienose liko anga į gretimą patalpą (0,70 m) — tikriausiai tai tos pačios durys, tik kito pločio. "
        "Patikrinkite brėžinyje; jei durys kitos — spustelėkite jų angą brėžinyje ir įrašykite plotį.")
    assert [(w["tipas"], w["listed"]) for w in f["withheld"]] == [("duris", [{"plotis_m": 1.2, "kiekis": 1}])]
    # a door no opening backs and no opening left: the plain count, as before
    alone = _stood("01", [_el("duris", 800, 2100), _el("duris", 1200, 2100)], [("07", 0.8)], paskirtis="koridorius")
    f = _angos(alone)
    assert f["withheld"] == [] and "1 durys sąraše, kurioms angos sienose nematau — jei jų nėra, sumažinkite durų skaičių." in f["sentence"]


# ── 2026-10-06: a door the room beyond lists, standing in the opening toward this room, is that opening's ──
# objektas_a (local fixture): the garage was offered the laundry's door (the pass calls it a door to the
# outside — a garage is outside for the finisher — and the claim skipped every such door), and the bathroom
# was offered the bedroom's 0,57 m door (it claimed the FIRST opening toward the bathroom, the 1,57 m one).


def _beside(*rooms: tuple[str, list[dict], list[tuple], dict]) -> dict:
    """Rooms of one project as production stores them, the walls pass run over all of them together."""
    project = {"patalpos": [
        {"nr": nr, "puslapio_nr": 2, "plotas_m2": 15.0, "perimetras_m": 16.0, "lubu_aukstis_m": 2.7,
         "polygon_pct": OUTLINE, "polygon_source": "vektoriniai_konturai", "_konturas": {"page": 1},
         "elementai": elementai,
         "_angos_sienose": {"page": 1, "angos": [_opening(i, w, x=round(0.2 + 0.05 * k, 2)) for k, (i, w) in enumerate(angos)]},
         **room}
        for nr, elementai, angos, room in rooms]}
    ur.prepare_rooms_for_calc(project["patalpos"])
    return project


def _angos_of(project: dict, nr: str) -> dict:
    return next(f for f in build_room_facts(project, nr)["facts"] if f["key"] == "angos")


def test_the_garage_is_not_offered_the_door_the_laundry_lists_toward_it():
    project = _beside(
        ("103", [_el("duris", 780, 2100)], [("106", 0.78)], {"paskirtis": "koridorius"}),
        ("105", [_el("duris", 1910, 2100)], [("106", 0.86), ("laukas", 1.91)], {"paskirtis": "garazas"}),
        ("106", [], [("103", 0.78), ("105", 0.86)], {"paskirtis": "skalbykla"}))
    laundry = project["patalpos"][2]["elementai"]
    # the laundry's door stands in its opening toward the garage, a door to the outside for the finisher
    assert [(e.get(ur.OPENING_SIDE_KEY), e.get(ur.EXTERIOR_KEY)) for e in laundry] == [("105", True)]
    f = _angos_of(project, "105")
    assert f["suggestions"] == [] and f["status"] == "read"
    assert f["sentence"].endswith("Durys į patalpą 106 (0,86 m) įrašytos prie tos patalpos.")
    # a door to the outside the room beyond lists in ITS opening to the outside claims nothing here
    lone = _beside(("105", [_el("duris", 1910, 2100)], [("106", 0.86), ("laukas", 1.91)], {"paskirtis": "garazas"}),
                   ("106", [{**_el("duris", 860, 2100), "_exterior": True}], [("laukas", 0.86)], {"paskirtis": "skalbykla"}))
    assert lone["patalpos"][1]["elementai"][0][ur.OPENING_SIDE_KEY] == "laukas"
    assert [(s["tipas"], s["plotis_m"], s["i"]) for s in _angos_of(lone, "105")["suggestions"]] == [("duris", 0.86, "106")]


def test_the_bedrooms_door_claims_the_bathrooms_opening_of_its_width_and_the_wide_one_is_offered_once():
    project = _beside(
        ("110", [_el("duris", 600, 2100), _el("langas", 960, 1500)], [("111", 1.57), ("111", 0.57), ("laukas", 0.96)],
         {"paskirtis": "miegamoji"}),
        ("111", [_el("langas", 1440, 1500)], [("110", 1.57), ("110", 0.57), ("laukas", 1.44)], {"paskirtis": "vonia"}))
    door = project["patalpos"][0]["elementai"][0]
    assert (door[ur.OPENING_SIDE_KEY], door["plotis_mm"]) == ("111", 570)
    bath = _angos_of(project, "111")
    # the 0,57 m opening is the bedroom's door — said, not offered; the 1,57 m one nothing stands in is offered
    assert [(s["tipas"], s["plotis_m"], s["i"]) for s in bath["suggestions"]] == [("duris", 1.57, "110")]
    assert bath["sentence"].endswith("Durys į patalpą 110 (0,57 m) įrašytos prie tos patalpos.")
    bedroom = _angos_of(project, "110")
    assert [(s["tipas"], s["plotis_m"], s["i"]) for s in bedroom["suggestions"]] == [("duris", 1.57, "111")]
    # one hole, one tick: the question offers the opening between them once, from the room asked first
    q = next(x for x in build_questions(project)["questions"] if x["kind"] == "angos")
    assert [(it["room_nr"], it["tipas"], it["plotis_m"], it["i"]) for it in q["items"]] == [("110", "duris", 1.57, "111")]
    assert q["manual"] == []
