"""v3 W5-E E2 — wallpaper rolls behind SAMATU_WALLPAPER_ROLLS (default off), CLAUDE.md §1.9 + §3."""
import json
import math

from extractor import wallpaper_flag as wf
from extractor.universal_rules import UNIVERSAL_RULES, calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _parsed(share=0.5):
    room = {"nr": "3", "pavadinimas": "Vaiko kambarys", "paskirtis": "miegamasis", "plotas_m2": 12.0,
            "perimetras_m": 14.0, "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 1,
            "sienu_apdailos_breakdown": {"dazymas_share": 1 - share, "tapetai_share": share}}
    room.update(calc_room_quantities(room))
    return json.loads(json.dumps({"patalpos": [room], "santrauka": {}}))


def _rows(monkeypatch, flag, share=0.5):
    if flag is None:
        monkeypatch.delenv(wf.FLAG_ENV, raising=False)
    else:
        monkeypatch.setenv(wf.FLAG_ENV, flag)
    return _build_pozicijos_from_rooms(_parsed(share))["pozicijos"]


def test_rolls_formula():
    usable = UNIVERSAL_RULES["wallpaper_roll_usable_area_m2"]
    assert wf.rolls(0) == 0
    assert wf.rolls(usable / 1.10) == 1
    assert wf.rolls(20.0) == math.ceil(20.0 * 1.10 / usable)


def test_room_area_from_the_read_share():
    room = {"sienu_apdailos_breakdown": {"tapetai_share": 0.5}, "walls_gross_m2": 40.0, "doors_deducted_m2": 2.0}
    assert wf.room_wallpaper_m2(room) == 19.0
    assert wf.room_wallpaper_m2({"walls_gross_m2": 40.0}) == 0.0
    assert wf.room_wallpaper_m2({"sienu_apdailos_breakdown": {"tapetai_share": 0.005}, "walls_gross_m2": 40}) == 0.0


def test_flag_off_identical(monkeypatch):
    a = _rows(monkeypatch, None)
    b = _rows(monkeypatch, "0")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert not any(p.get("aprasymas") == wf.ROW for p in a)


def test_flag_on_adds_the_row_and_its_rolls(monkeypatch):
    off = _rows(monkeypatch, None)
    on = _rows(monkeypatch, "1")
    row = next(p for p in on if p.get("aprasymas") == wf.ROW)
    room = _parsed()["patalpos"][0]
    area = wf.room_wallpaper_m2(room)
    assert area > 0 and row["kiekis"] == area and row["vnt"] == "m2"
    mat = next(p for p in on if str(p.get("aprasymas", "")).startswith("Tapetai (ritiniai"))
    assert mat["kiekis"] == wf.rolls(area) and mat["vnt"] == "vnt"
    assert "Vaiko kambarys" in row["_confidence_reason"]
    # every other row is untouched (the walls stay in the skim base)
    strip = lambda poz: [p for p in poz if p.get("aprasymas") != wf.ROW and not str(p.get("aprasymas", "")).startswith("Tapetai")]
    assert json.dumps(strip(on), sort_keys=True) == json.dumps(off, sort_keys=True)


def test_no_wallpaper_no_row(monkeypatch):
    assert not any(p.get("aprasymas") == wf.ROW for p in _rows(monkeypatch, "1", share=0.0))
