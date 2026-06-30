"""HVAC ductwork (ortakiai) tests (Sprint §40, 2026-04-29).

Rangovas audit v2 identified ductwork as #1 gap (40% premium projects, 0 coverage).
Now backend emits per-diameter ortakių line items + izoliacija + tvirtinimas
when symbols.detected_symbols_summary.ortakiai_d{100,125,160}_m > 0.
"""

from extractor.vision_call import _build_pozicijos_from_rooms


def _build_parsed(rooms, symbols=None):
    parsed = {"patalpos": rooms, "santrauka": {}}
    if symbols:
        parsed["detected_symbols_summary"] = symbols
    return parsed


def _ortakiu_lines(out):
    return [p for p in out.get("pozicijos", []) if p.get("skyrius") == "Ventiliacijos darbai"]


def test_no_symbols_no_diffusers_no_ductwork():
    """Empty symbols → no ductwork emitted."""
    rooms = [{"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
              "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
              "elementai": [], "confidence": "high"}]
    out = _build_pozicijos_from_rooms(_build_parsed(rooms))
    assert len(_ortakiu_lines(out)) == 0


def test_explicit_d125_emits_one_line():
    """Vision detected 12 m of D125 ducts → emit 1 line + izoliacija + tvirtinimas."""
    rooms = [{"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
              "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
              "elementai": [], "confidence": "high"}]
    out = _build_pozicijos_from_rooms(_build_parsed(rooms, {"ortakiai_d125_m": 12.0}))
    lines = _ortakiu_lines(out)
    # Expect: D125 montavimas + izoliacija + tvirtinimas = 3 lines
    assert len(lines) == 3
    d125 = next(l for l in lines if "D125" in l.get("aprasymas", ""))
    assert d125["kiekis"] == 12.0
    assert d125["medziagos_kiekis"] == 12.6  # 12 × 1.05 atliekos


def test_all_three_diameters():
    """Mixed ductwork: D100 + D125 + D160 → 3 montavimas lines + izoliacija + tvirtinimas."""
    rooms = [{"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
              "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.7,
              "elementai": [], "confidence": "high"}]
    out = _build_pozicijos_from_rooms(_build_parsed(rooms, {
        "ortakiai_d100_m": 5.0,
        "ortakiai_d125_m": 10.0,
        "ortakiai_d160_m": 4.0,
    }))
    lines = _ortakiu_lines(out)
    montavimas = [l for l in lines if "montavimas" in l.get("aprasymas", "").lower()]
    assert len(montavimas) == 3, f"Expected 3 ductwork lines, got {[l['aprasymas'] for l in lines]}"
    izol = [l for l in lines if "izoliacija" in l.get("aprasymas", "").lower()]
    assert len(izol) == 1
    # Total length 19 m, izoliacija ~70% = 13.3 m
    assert izol[0]["kiekis"] == 13.3


def test_difuzoriai_fallback_emits_d125_estimate():
    """When difuzoriai detected but ortakiai NOT — fallback heuristic
    estimates ~5 m D125 per diffuser."""
    rooms = [{"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia",
              "plotas_m2": 5.0, "perimetras_m": 9.0, "lubu_aukstis_m": 2.5,
              "lubu_tipas": "pakabinamos",
              "plyteles_sienos_aukstis_m": 2.0, "elementai": [], "confidence": "high"}]
    # 4 diffusers, no explicit ortakių length → fallback emits ~20 m D125
    out = _build_pozicijos_from_rooms(_build_parsed(rooms, {"difuzoriai": 4}))
    lines = _ortakiu_lines(out)
    d125 = next((l for l in lines if "D125" in l.get("aprasymas", "")), None)
    assert d125 is not None, "Fallback should emit D125 ductwork from difuzoriai"
    assert d125["kiekis"] == 20.0  # 4 × 5.0 m


def test_d100_only_no_fallback():
    """Explicit D100 quantity → use exactly that, no D125 fallback."""
    rooms = [{"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
              "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
              "elementai": [], "confidence": "high"}]
    out = _build_pozicijos_from_rooms(_build_parsed(rooms, {
        "ortakiai_d100_m": 8.0,
        "difuzoriai": 3,  # would otherwise trigger fallback
    }))
    lines = _ortakiu_lines(out)
    d125_lines = [l for l in lines if "D125" in l.get("aprasymas", "")]
    d100_lines = [l for l in lines if "D100" in l.get("aprasymas", "")]
    assert len(d100_lines) == 1
    assert len(d125_lines) == 0  # no fallback when explicit data present


def test_tvirtinimas_count_one_per_1_5m():
    """Tvirtinimas (kabykės) ≈ 1 fix per 1.5 m of ductwork."""
    rooms = [{"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
              "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
              "elementai": [], "confidence": "high"}]
    out = _build_pozicijos_from_rooms(_build_parsed(rooms, {"ortakiai_d125_m": 15.0}))
    tvirt = next((l for l in _ortakiu_lines(out) if "tvirtinimas" in l.get("aprasymas", "").lower()), None)
    assert tvirt is not None
    assert tvirt["kiekis"] == round(15 / 1.5)  # = 10
