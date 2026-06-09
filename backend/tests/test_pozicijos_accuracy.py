"""Pozicijos accuracy fixes — Phase 1 (deterministic, no Vision change).

From the Beržų line-by-line audit (docs/berzas_audit_notes.md):
  RC3 — angokraščiai use the calibrated angokrasciu_gkp_m field, not the inline
        Σ(2H+W) recompute (which over-quoted +54.8% by counting exterior reveals).
  RC1 — basin count from detected_symbols.praustuves, not the toilet count.
  RC8 — emit kampai as ONE line (stop the vidiniai+išoriniai+montavimas triple
        that double-bills the same metrai).
Tests assert BEHAVIOUR (uses-the-field / uses-the-symbol / single-line), not
brittle magic numbers, so they survive future extract changes.
"""
from extractor.vision_call import _build_pozicijos_from_rooms
from extractor.universal_rules import calc_room_quantities


def _parsed(rooms):
    return {"patalpos": rooms, "santrauka": {}}


def _room(elementai, **kw):
    r = {"paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0,
         "lubu_aukstis_m": 2.7, "elementai": elementai}
    r.update(kw)
    r.update(calc_room_quantities(r))
    return r


# ── RC3 ────────────────────────────────────────────────────────────────
def test_angokrasciai_uses_calibrated_field_not_inline():
    # interior door (counted) + EXTERIOR window (the calibrated field excludes it
    # per is_exterior; the old inline recompute wrongly counted it). This is the
    # case where field != inline, so it actually exercises the fix.
    rooms = [_room([{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2050},
                    {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500,
                     "_exterior": True}])]
    out = _build_pozicijos_from_rooms(_parsed(rooms))
    expected = round(sum(r.get("angokrasciu_gkp_m") or 0 for r in rooms), 2)
    glaist = [p for p in out["pozicijos"] if p["aprasymas"] == "Angokraščių glaistymas-dažymas"]
    gkp = [p for p in out["pozicijos"] if p["aprasymas"].startswith("Angokraščių apdirbimas GKP")]
    assert len(glaist) == 1 and len(gkp) == 1, [p["aprasymas"] for p in out["pozicijos"]]
    assert abs(glaist[0]["kiekis"] - expected) < 0.01, f"{glaist[0]['kiekis']} vs field {expected}"
    assert abs(gkp[0]["kiekis"] - expected) < 0.01, f"{gkp[0]['kiekis']} vs field {expected}"


# ── RC1 ────────────────────────────────────────────────────────────────
def test_basin_count_uses_praustuves_symbol():
    rooms = [_room([], paskirtis="vonia", plotas_m2=5.0),
             _room([], paskirtis="san", plotas_m2=4.0)]
    parsed = _parsed(rooms)
    parsed["detected_symbols_summary"] = {"praustuves": 3}
    out = _build_pozicijos_from_rooms(parsed)
    basin = [p for p in out["pozicijos"] if p["aprasymas"] == "Praustuvės maišytuvo montavimas"]
    assert len(basin) == 1 and basin[0]["kiekis"] == 3, basin  # not 2 (n_wet_with_klozetas)


# ── RC8 ────────────────────────────────────────────────────────────────
def test_kampai_emitted_as_single_line():
    rooms = [_room([], perimetras_m=20.0)]
    out = _build_pozicijos_from_rooms(_parsed(rooms))
    kampai_lines = [p for p in out["pozicijos"] if "kamp" in p["aprasymas"].lower()
                    and p.get("skyrius") == "Sienų lubų glaistymas dažymas"]
    labels = [p["aprasymas"] for p in kampai_lines]
    assert "Glaistymo kampai vidiniai" not in labels, labels
    assert "Glaistymo kampai išoriniai" not in labels, labels
    assert labels.count("Dažymo kampų montavimas") == 1, labels
