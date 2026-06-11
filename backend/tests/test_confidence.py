"""Confidence post-pass tests (2026-06-11 false-green follow-up)."""
from extractor.confidence import apply_confidence
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _parsed(rooms, **top):
    for r in rooms:
        r.update(calc_room_quantities(r))
    p = {"patalpos": rooms, "santrauka": {}}
    p.update(top)
    return _build_pozicijos_from_rooms(p)


def _room(**kw):
    r = {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
         "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
         "elementai": [{"tipas": "pasleptos_duris", "kiekis": 1,
                        "plotis_mm": 900, "aukstis_mm": 2400}]}
    r.update(kw)
    return r


def _find(out, needle):
    return next(p for p in out["pozicijos"] if needle.lower() in p["aprasymas"].lower())


def test_calibrated_class_is_geltona():
    out = _parsed([_room()])
    durys = _find(out, "beapvadinėms durims")
    assert durys["confidence"] == "geltona"
    assert "−61%" in durys["_confidence_reason"] or "-61%" in durys["_confidence_reason"]


def test_unlisted_class_defaults_zalia():
    out = _parsed([_room()])
    line = _find(out, "dangos pamušalas")  # no class rule, no flags → žalia
    assert line["confidence"] == "zalia"


def test_apdailos_low_demotes_finish_lines():
    room = _room()
    room["_apdailos_confidence"] = "low"
    room["sienu_apdailos_breakdown"] = {"dazymas_share": 1.0}
    out = _parsed([room])
    paint = _find(out, "glaistymas/dažymas")
    assert paint["confidence"] == "geltona"
    assert "low confidence" in paint["_confidence_reason"]


def test_voting_flags_demote_geometry_lines():
    out = _parsed([_room()], _voting={"low_confidence_fields": [
        {"room": "Svetainė", "field": "perimetras_m"}]})
    paint = _find(out, "glaistymas/dažymas")
    assert paint["confidence"] == "geltona"


def test_kampai_raudona_when_adjacency_empty():
    # npw == 0 everywhere → kampai missing pusiniai → raudona
    out = _parsed([_room()])
    kampai = _find(out, "kampų montavimas")
    assert kampai["confidence"] == "raudona"


def test_kampai_geltona_when_adjacency_present():
    out = _parsed([_room(n_partition_walls=3)])
    kampai = _find(out, "kampų montavimas")
    assert kampai["confidence"] == "geltona"  # class rule (±17%), not raudona


def test_existing_medium_normalized_not_upgraded():
    p = {"pozicijos": [{"aprasymas": "X", "confidence": "medium"}], "patalpos": []}
    apply_confidence(p)
    assert p["pozicijos"][0]["confidence"] == "geltona"
