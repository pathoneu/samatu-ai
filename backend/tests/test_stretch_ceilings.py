"""Įtempiamos lubos per kambarį (2026-09-02, contractor ask F1).

A room the user marks as ĮTEMPIAMOS gets NO ceiling skim / prime / paint /
sanding — a stretch membrane is a separate trade stretched under a raw slab, so
every one of those m² would be work nobody performs. Everything else the ceiling
carries — lubų karnizas, LED nišos, GKP lubos, grindjuostės — is untouched: the
founder scoped this to "išimti lubų dažymą" only.

Wired as the assumption `stretch_ceiling_override: {room nr: 1|0}`, absent =
dažomos, so a project whose owner never opens the toggle is byte-identical to
before the feature.
"""
import os

import pytest

from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import (
    _build_pozicijos_from_rooms,
    _calc_dazai_liters,
    _calc_glaistas_kg,
    _ceiling_paint_m2,
    _stretch_ceiling_nrs,
)


def _room(nr, **kw):
    r = {"nr": nr, "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
         "perimetras_m": 18.0, "lubu_aukstis_m": 2.7, "elementai": []}
    r.update(kw)
    r.update(calc_room_quantities(r))
    # The per-room material fields the extraction pipeline computes on top of
    # calc_room_quantities (`_recompute_per_room_via_python` §4.1-4.3). Without
    # them every material quantity is 0 and the material assertions below pass
    # vacuously — which is exactly what they did before 2026-09-02.
    dazymo = float(r.get("dazymo_plotas_m2") or 0)
    r["glaistas_kg"] = _calc_glaistas_kg(dazymo)
    r["dazai_l"] = _calc_dazai_liters(dazymo, paint_class=2)
    r["gruntas_l"] = round(dazymo / 7.0, 2) if dazymo > 0 else 0.0
    return r


def _parsed(rooms, overrides=None):
    p = {"patalpos": rooms, "santrauka": {}}
    if overrides is not None:
        p["_overrides"] = overrides
    return p


def _by_label(poz):
    return {p["aprasymas"]: p for p in poz}


def _paint_kiekis(poz):
    """Total m² across the consolidated glaistymas/dažymas work lines."""
    return round(sum(
        float(p.get("kiekis") or 0) for p in poz
        if "glaistymas/dažymas" in (p.get("aprasymas") or "")
        and (p.get("vnt") or "") in ("m2", "m²")
        and "Q4" not in (p.get("aprasymas") or "")
    ), 2)


# ── The override reader ─────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ({"101": 1}, {"101"}),
    ({"101": 1.0, "102": 0}, {"101"}),
    ({"101": "1"}, {"101"}),
    ({101: True}, {"101"}),
    ({"101": 0, "102": 0}, set()),
    ({}, set()),
    (None, set()),
    ("not a dict", set()),
    ({"101": "taip"}, set()),        # unparseable → ignored, never raises
    ({"": 1}, set()),                # blank nr can't identify a room
])
def test_override_reader(raw, expected):
    assert _stretch_ceiling_nrs({"_overrides": {"stretch_ceiling_override": raw}}) == expected


def test_ceiling_paint_m2_zeroes_only_the_flagged_room():
    a, b = _room("101"), _room("102")
    assert _ceiling_paint_m2(a, {"101"}) == 0.0
    assert _ceiling_paint_m2(b, {"101"}) == b["ceiling_paintable_m2"]
    assert _ceiling_paint_m2(a, set()) == a["ceiling_paintable_m2"]


# ── The billed quantities ───────────────────────────────────────────────────

def test_flagged_rooms_drop_their_ceiling_paint_and_leave_walls_alone():
    rooms = [_room("101"), _room("102"), _room("103")]
    base = _build_pozicijos_from_rooms(_parsed([dict(r) for r in rooms]))["pozicijos"]
    out = _build_pozicijos_from_rooms(_parsed(
        [dict(r) for r in rooms],
        {"stretch_ceiling_override": {"101": 1, "102": 1}},
    ))["pozicijos"]

    dropped = sum(r["ceiling_paintable_m2"] for r in rooms[:2])
    assert _paint_kiekis(base) - _paint_kiekis(out) == pytest.approx(dropped, abs=0.02)

    # Walls are untouched — Rotband is billed off walls_paint alone.
    assert (_by_label(base)["Sienų lyginimas Knauf Rotband"]["kiekis"]
            == _by_label(out)["Sienų lyginimas Knauf Rotband"]["kiekis"])


def test_untouched_lines_stay_untouched():
    """Karnizas, LED nišos, GKP lubos, grindjuostės — explicitly out of scope."""
    rooms = [_room("101", nisu_metrai=6.0), _room("102")]
    # calc_room_quantities gives `gyvenamoji` no cornice; force one so the
    # assertion below is about the stretch flag, not about the fixture.
    for r in rooms:
        r["lubu_karnizo_m"] = 18.9
    keep = ("Lubų karnizo sumontavimas", "Lubų karnizo dažymas",
            "LED nišų glaistymas/dažymas", "Grindjuosčių sumontavimas",
            "Grindjuosčių dažymas", "GKP lubų montavimas (standartinis aukštis)",
            "GKP lapai luboms (9.5 mm)")
    base = _by_label(_build_pozicijos_from_rooms(
        _parsed([dict(r) for r in rooms]))["pozicijos"])
    out = _by_label(_build_pozicijos_from_rooms(_parsed(
        [dict(r) for r in rooms],
        {"stretch_ceiling_override": {"101": 1}},
    ))["pozicijos"])
    for label in keep:
        assert label in base, f"fixture never produced {label!r}"
        assert label in out, f"{label!r} vanished when a ceiling went stretch"
        assert base[label]["kiekis"] == out[label]["kiekis"], label


def test_all_rooms_stretch_leaves_no_zero_quantity_ghost_rows():
    rooms = [_room("101"), _room("102")]
    out = _build_pozicijos_from_rooms(_parsed(
        rooms, {"stretch_ceiling_override": {"101": 1, "102": 1}},
    ))["pozicijos"]
    ceiling_rows = [p for p in out
                    if (p.get("aprasymas") or "").startswith("Lubų glaistymas")
                    or (p.get("aprasymas") or "").startswith("Lubų pirminis")
                    or (p.get("aprasymas") or "").startswith("Lubų antrinis")
                    or (p.get("aprasymas") or "").startswith("Lubų gruntavimas")
                    or (p.get("aprasymas") or "").startswith("Lubų dažymas")
                    or (p.get("aprasymas") or "").startswith("Lubų šlifavimas")]
    assert ceiling_rows == [], f"zero-quantity ghost rows survived: {ceiling_rows}"
    # And no row anywhere is a 0 m² paint line.
    zero = [p for p in out if "glaistymas/dažymas" in (p.get("aprasymas") or "")
            and float(p.get("kiekis") or 0) == 0]
    assert zero == [], zero


def test_absent_override_is_byte_identical_to_before():
    rooms = [_room("101"), _room("102", lubu_aukstis_m=3.4)]
    a = _build_pozicijos_from_rooms(_parsed([dict(r) for r in rooms]))["pozicijos"]
    b = _build_pozicijos_from_rooms(_parsed(
        [dict(r) for r in rooms], {"stretch_ceiling_override": {}}))["pozicijos"]
    c = _build_pozicijos_from_rooms(_parsed(
        [dict(r) for r in rooms], {"stretch_ceiling_override": {"101": 0}}))["pozicijos"]
    assert a == b == c


def test_high_ceiling_tier_also_loses_the_flagged_room():
    """The virš-3m tier must drop the ceiling too, not only the iki-3m one."""
    rooms = [_room("101", lubu_aukstis_m=3.6), _room("102")]
    base = _build_pozicijos_from_rooms(_parsed([dict(r) for r in rooms]))["pozicijos"]
    out = _build_pozicijos_from_rooms(_parsed(
        [dict(r) for r in rooms], {"stretch_ceiling_override": {"101": 1}},
    ))["pozicijos"]

    def _virs(poz):
        return round(sum(float(p.get("kiekis") or 0) for p in poz
                         if "virš 3m" in (p.get("aprasymas") or "")), 2)

    assert _virs(base) > 0, "fixture produced no virš-3m line"
    assert _virs(base) - _virs(out) == pytest.approx(
        rooms[0]["ceiling_paintable_m2"], abs=0.02)


def test_material_leaves_with_the_work_instead_of_moving_to_the_walls():
    """A stretch ceiling must not INFLATE the wall putty/primer/paint.

    The share denominator is the FULL paintable area on purpose: dividing by the
    shrunken billed total would push walls_share toward 1.0 and hand the ceiling's
    material to the walls."""
    os.environ["ENABLE_CONSOLIDATE_PAINT_LINES"] = "0"
    try:
        rooms = [_room("101"), _room("102")]
        base = _by_label(_build_pozicijos_from_rooms(
            _parsed([dict(r) for r in rooms]))["pozicijos"])
        out = _by_label(_build_pozicijos_from_rooms(_parsed(
            [dict(r) for r in rooms], {"stretch_ceiling_override": {"101": 1}},
        ))["pozicijos"])
        # 2026-09-02: the materials live in the global "Medžiagos" section now,
        # each linked back to its work line by `susijes_darbas`.
        for label in ("Pradinis glaistas sienoms", "Gruntas sienoms",
                      "Dažai sienoms (2 sluoksniai)"):
            assert base[label]["kiekis"] == out[label]["kiekis"], label
        # The ceiling half shrank by exactly one of the two identical rooms.
        assert out["Gruntas luboms"]["kiekis"] == pytest.approx(
            base["Gruntas luboms"]["kiekis"] / 2, abs=0.05)
    finally:
        os.environ.pop("ENABLE_CONSOLIDATE_PAINT_LINES", None)


def test_per_coat_ceiling_rows_also_honour_the_flag():
    os.environ["ENABLE_CONSOLIDATE_PAINT_LINES"] = "0"
    try:
        rooms = [_room("101"), _room("102")]
        out = _by_label(_build_pozicijos_from_rooms(_parsed(
            [dict(r) for r in rooms], {"stretch_ceiling_override": {"101": 1}},
        ))["pozicijos"])
        for label in ("Lubų pirminis glaistymas Q1", "Lubų antrinis glaistymas Q2",
                      "Lubų šlifavimas", "Lubų gruntavimas (1 sluoksnis)",
                      "Lubų dažymas (2 sluoksniai)"):
            assert out[label]["kiekis"] == pytest.approx(
                rooms[1]["ceiling_paintable_m2"], abs=0.02), label
    finally:
        os.environ.pop("ENABLE_CONSOLIDATE_PAINT_LINES", None)


# ── The live recompute endpoint ─────────────────────────────────────────────

def test_the_field_is_accepted_by_the_recompute_endpoint():
    from api.recompute_quantities import _ASSUMPTION_FIELDS, _VALID_FIELDS
    assert "stretch_ceiling_override" in _ASSUMPTION_FIELDS
    assert "stretch_ceiling_override" in _VALID_FIELDS


def test_a_priced_ceiling_row_keeps_its_price_when_the_quantity_shrinks():
    """Merge invariant: the toggle changes a quantity, never a price."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
              "kiekis": 200.0, "kaina": 7.5, "suma": 1500.0}]
    rebuilt = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
                "kiekis": 160.0}]
    out = _merge_user_edits(rebuilt, prior)
    assert len(out) == 1
    assert out[0]["kaina"] == 7.5
    assert out[0]["kiekis"] == 160.0
    assert out[0]["suma"] == 1200.0
