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
         "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
         "elementai": [{"tipas": "pasleptos_duris", "kiekis": 1,
                        "plotis_mm": 900, "aukstis_mm": 2400}]}
    r.update(kw)
    return r


def _find(out, needle):
    return next(p for p in out["pozicijos"] if needle.lower() in p["aprasymas"].lower())


def test_calibrated_class_is_geltona():
    # v4 3b: a frame type read in the drawing's text (the door-type reader) keeps the row; symbols alone do not
    out = _parsed([_room()], _door_types={"count": 1, "reader_beapvadines": 1})
    durys = _find(out, "beapvadinėms durims")
    assert durys["confidence"] == "geltona"
    # 2026-08-31: reasons guide, never confess — the old string quoted
    # benchmark error pairs; the new one tells the user what to compare.
    assert "specifikacija" in durys["_confidence_reason"]
    assert "%" not in durys["_confidence_reason"]


def test_unlisted_class_defaults_zalia():
    # A line that matches NO class rule and carries no flags stays žalia.
    p = {"pozicijos": [{"aprasymas": "Sienų gruntavimas prieš dažymą", "confidence": "high"}],
         "patalpos": []}
    apply_confidence(p)
    assert p["pozicijos"][0]["confidence"] == "zalia"


def test_apdailos_low_demotes_finish_lines():
    room = _room()
    room["_apdailos_confidence"] = "low"
    room["sienu_apdailos_breakdown"] = {"dazymas_share": 1.0}
    out = _parsed([room])
    paint = _find(out, "glaistymas/dažymas")
    assert paint["confidence"] == "geltona"
    assert "prielaidomis" in paint["_confidence_reason"], paint["_confidence_reason"]


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


def test_kampai_reason_discloses_calibration():
    # The kampai reason must honestly disclose it's calibrated to 1 contractor
    # (the formula is fitted to Objektas A 493.35 m with a +perim double-count), not
    # imply a clean validated geometric sum.
    out = _parsed([_room(n_partition_walls=3)])
    kampai = _find(out, "kampų montavimas")
    assert kampai["confidence"] == "geltona"
    # The calibration confession ("kalibruota pagal 1 rangovo samatą (Objektas A)")
    # leaked a client name and our methodology — the string now explains the
    # formula and the check instead.
    assert "kampus plane" in kampai["_confidence_reason"]
    assert "Objektas A" not in kampai["_confidence_reason"]


def test_angokrasciai_flags_unread_opening_dims():
    # A room whose window has no readable dims → its reveal is SILENTLY skipped
    # in calc_room_quantities. The angokraščiai line must surface that gap.
    room = _room(elementai=[
        {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2400},
        {"tipas": "langas", "kiekis": 1, "plotis_mm": 0, "aukstis_mm": 0},
    ])
    out = _parsed([room])
    ang = _find(out, "angokrašči")
    assert ang["confidence"] in ("geltona", "raudona")
    assert "matmen" in ang["_confidence_reason"].lower()


def test_angokrasciai_no_unread_flag_when_dims_present():
    # All openings have dims → no unread-dims reason on the reveal line.
    # (2026-09-23: the reveal line is the windows' and the exterior doors' — a hidden door is prepared on its own row)
    out = _parsed([_room(elementai=[
        {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2400},
        {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500},
    ])])
    ang = _find(out, "angokrašči")
    assert "be nuskaitytų matmenų" not in (ang.get("_confidence_reason") or "")


def test_existing_medium_normalized_not_upgraded():
    p = {"pozicijos": [{"aprasymas": "X", "confidence": "medium"}], "patalpos": []}
    apply_confidence(p)
    assert p["pozicijos"][0]["confidence"] == "geltona"


def test_confidence_survives_v8_compat_darbu_sarasas():
    # The UI may render darbu_sarasas (V8-compat shape); confidence + reason must
    # carry through, not get dropped.
    from extractor.vision_call import _emit_v8_compat_fields
    parsed = {"pozicijos": [
        {"aprasymas": "Dažymo kampų montavimas", "vnt": "m", "kiekis": 100.0,
         "skyrius": "Sienų lubų glaistymas dažymas",
         "confidence": "raudona", "_confidence_reason": "Gretimybės analizė nerado pertvarų"},
    ]}
    _emit_v8_compat_fields(parsed)
    row = parsed["darbu_sarasas"][0]
    assert row["confidence"] == "raudona"
    assert "pertvar" in row["_confidence_reason"]
