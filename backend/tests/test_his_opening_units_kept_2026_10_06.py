"""2026-10-06 — the walls pass never cuts a door or window count HE set on the room sheet.

universal_rules.reconcile_openings_with_walls stands each listed unit in a wall opening, and step 5 set every
piece's `kiekis` to the units that stood: a listed element whose units could not all stand lost the rest.
His „+" on a window that stands was undone on the next recompute (no free opening to the outside within the
tolerance), and a width he typed on a 2-unit row (objektas_a 102: 3000 ×2 → 3900) dropped the second window
until he accepted the leftover 0,96 m opening as a new one. Now the units left keep their element as a piece of
their own — a door no opening backs (`_be_angos`), a window standing in no opening (no `_anga_ks`) — and the
room sheet names them instead of losing them.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from extractor import universal_rules as ur  # noqa: E402
from extractor.project_questions import build_questions  # noqa: E402
from extractor.room_facts import build_room_facts  # noqa: E402

OUTLINE = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]]
HIS = "2026-10-06T10:00:00Z"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _room(nr, elementai, angos, **more):
    return {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": "virtuve", "puslapio_nr": 2, "plotas_m2": 14.0,
            "perimetras_m": 15.0, "lubu_aukstis_m": 2.7, "polygon_pct": OUTLINE,
            "polygon_source": "vektoriniai_konturai", "_konturas": {"page": 1}, "elementai": elementai,
            "_angos_sienose": {"page": 1, "angos": [
                {"i": i, "plotis_m": w, "storis_m": 0.3, "line_pct": [[0.2 + 0.05 * k, 0.1], [0.24 + 0.05 * k, 0.1]],
                 **({"nupiesta": n} if n else {})}
                for k, (i, w, n) in enumerate(angos)]},
            **more}


def _units(room, tipas):
    return sum(ur._el_units(e) for e in room["elementai"] if (e.get("tipas") or "") == tipas)


def _pieces(room, tipas):
    return sorted((ur._el_units(e), e.get("plotis_mm"), tuple(e.get(ur.OPENING_INDEX_KEY) or ()), bool(e.get(ur.UNBACKED_KEY)))
                  for e in room["elementai"] if (e.get("tipas") or "") == tipas)


def _angos(room):
    return next(f for f in build_room_facts({"patalpos": [room]}, room["nr"])["facts"] if f["key"] == "angos")


def _kitchen():
    """Two windows in two glazed openings, the door in the opening to the corridor — the list agrees."""
    return _room("04", [{"tipas": "langas", "kiekis": 2, "plotis_mm": 1350, "aukstis_mm": 1400},
                        {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}],
                 [("laukas", 1.36, "langas"), ("laukas", 1.35, "langas"), ("03", 0.9, None)])


def _pressed(room, tipas, delta=+1, **size):
    """What the room sheet saves (lib/roomSheet.js adjustOpeningCount / setOpeningSize + openingsPatch): the
    first element of that kind moved, the room marked as his."""
    room = copy.deepcopy(room)
    el = next(e for e in room["elementai"] if (e.get("tipas") or "") == tipas)
    el["kiekis"] = max(0, int(el.get("kiekis") or 0) + delta)
    if size:
        el.update(size, _dydis_user=True)
    room[ur.USER_OPENINGS_KEY] = HIS
    return room


def test_his_plus_on_a_window_that_stands_survives_two_recomputes():
    room = _kitchen()
    ur.reconcile_openings_with_walls([room])
    assert _pieces(room, "langas") == [(2, 1350, (1, 0), False)]
    room = _pressed(room, "langas")
    for _ in range(2):
        ur.reconcile_openings_with_walls([room])
        assert _units(room, "langas") == 3
        # the two that stand keep their openings; his third is a window standing in no opening
        assert _pieces(room, "langas") == [(1, 1350, (), False), (2, 1350, (1, 0), False)]
    f = _angos(room)
    assert f["value"] == 4 and f["status"] == "assumed"                # 3 windows and the door
    assert "1 langas sąraše, kuriam angos sienose nematau — patikrinkite patalpoje." in f["sentence"]
    assert "tiek pat angų" not in f["sentence"]


def test_a_width_he_typed_on_a_two_unit_row_keeps_both_windows():
    """objektas_a 102: two 3,00 m windows the walls could not stand, a 3,90 and a 0,96 m opening left; he
    follows the sheet's advice and types 3900 on the row."""
    room = _room("102", [{"tipas": "langas", "kiekis": 2, "plotis_mm": 3000, "aukstis_mm": 2600}],
                 [("laukas", 3.9, None), ("laukas", 0.96, None)], paskirtis="valgomasis")
    ur.reconcile_openings_with_walls([room])
    assert _pieces(room, "langas") == [(2, 3000, (), False)]           # nothing stands: kept whole, as before
    room = _pressed(room, "langas", delta=0, plotis_mm=3900)
    for _ in range(2):
        ur.reconcile_openings_with_walls([room])
        assert _pieces(room, "langas") == [(1, 3900, (), False), (1, 3900, (0,), False)]
    f = _angos(room)
    assert f["suggestions"] == []
    assert ("Sąraše langas 3,90 m neįstatytas į angą, o sienose liko anga 0,96 m — tikriausiai tai tas pats langas, "
            "tik kito pločio.") in f["sentence"]
    # he corrects „its" width on the sheet — which moves the first row of that size (lib/roomSheet.js); the
    # two rows are the same window, so both stand either way
    room = _pressed(room, "langas", delta=0, plotis_mm=960)
    ur.reconcile_openings_with_walls([room])
    assert _pieces(room, "langas") == [(1, 960, (1,), False), (1, 3900, (0,), False)]
    assert _angos(room)["withheld"] == [] and "neįstatyt" not in _angos(room)["sentence"]


def test_his_plus_on_a_door_he_added_from_an_opening_stays_as_a_door_no_opening_backs():
    room = _room("06", [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100,
                         "_is_sienu_angos": "03", "_dydis_user": True}],
                 [("03", 0.8, None), ("laukas", 1.2, "langas")], paskirtis="miegamoji")
    ur.reconcile_openings_with_walls([room])
    room = _pressed(room, "duris")
    for _ in range(2):
        ur.reconcile_openings_with_walls([room])
        assert _units(room, "duris") == 2
        assert _pieces(room, "duris") == [(1, 800, (), True), (1, 800, (0,), False)]
    assert "1 durys sąraše, kurioms angos sienose nematau — patikrinkite patalpoje." in _angos(room)["sentence"]


def test_his_removal_still_holds_and_a_plus_still_releases_it():
    """The removals he makes stay his (audit calc-engine-4) — the kept units do not bring an emptied opening back."""
    room = _kitchen()
    ur.reconcile_openings_with_walls([room])
    room = _pressed(room, "langas", delta=-1)
    for _ in range(2):
        ur.reconcile_openings_with_walls([room])
        assert _units(room, "langas") == 1
    room = _pressed(room, "langas", delta=+1)
    ur.reconcile_openings_with_walls([room])
    assert _pieces(room, "langas") == [(2, 1350, (1, 0), False)]


def test_the_room_sheet_recompute_keeps_his_plus(client):
    room = _kitchen()
    first = client.post("/recompute-interior", json={"patalpos": [room], "rules_override": {}}).json()["patalpos"][0]
    assert first["_n_windows"] == 2
    second = client.post("/recompute-interior", json={"patalpos": [_pressed(first, "langas")],
                                                      "rules_override": {}}).json()["patalpos"][0]
    third = client.post("/recompute-interior", json={"patalpos": [second], "rules_override": {}}).json()["patalpos"][0]
    for r in (second, third):
        assert _units(r, "langas") == 3 and r["_n_windows"] == 3


def test_the_question_says_which_windows_no_opening_takes():
    room = _pressed(_kitchen(), "langas")
    ur.reconcile_openings_with_walls([room])
    q = next(x for x in build_questions({"patalpos": [room]})["questions"] if x["kind"] == "angos")
    assert q["items"] == []
    assert q["manual"][0]["sentence"] == "Sąraše 3 langai, o sienose — tik 2 angos langams: 1 lango sienose neradau."
    assert q["manual"][0]["langai"]["sienose"] == 2 and q["manual"][0]["proposed"]["langai"] == 2


def test_without_his_mark_a_listed_count_the_walls_cannot_all_stand_is_cut_as_before():
    """The same for the reader's own list was MEASURED and left out (2026-10-06): objektas_h 05 lists
    „langas 1500 ×2", its walls show one glazed opening (1,36 m) and a 5,07 m one the terrace door stands in.
    Keeping the second window as a window with no opening, with production's drawing lanes replayed
    (eval_harness --replay-geometry), took objektas_h's billed lines from 19,28 to 21,20 % (reveals +21,6 →
    +29,7 %) and the corpus headline from 22,88 to 23,19 %. Only a count HE set is kept."""
    room = _room("05", [{"tipas": "langas", "kiekis": 2, "plotis_mm": 1500, "aukstis_mm": 1800, "_exterior": True},
                        {"tipas": "duris", "kiekis": 1, "plotis_mm": 1800, "aukstis_mm": 2200, "_exterior": True}],
                 [("03", 1.56, None), ("laukas", 1.36, "langas"), ("laukas", 5.07, None)], paskirtis="gyvenamoji")
    for _ in range(2):
        ur.reconcile_openings_with_walls([room])
        assert _pieces(room, "langas") == [(1, 1360, (1,), False)]
        assert _pieces(room, "duris") == [(1, 5070, (2,), False)]
