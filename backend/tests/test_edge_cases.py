"""Edge case coverage (Sprint §38, 2026-04-29).

Cases:
  - Empty patalpos array
  - Single garazas only (no painting expected)
  - Single-room project (one kambarys, all calcs work)
  - NRM2 + Q4 + paint_class=3 combo
  - All rooms wet (vonia/wc/san only)
  - Cellar floor (paskirtis recognized as floor 0 via room_aukstas_from_nr)
"""

from extractor.vision_call import _build_pozicijos_from_rooms
from extractor.universal_rules import (
    calc_room_quantities, room_aukstas_from_nr, group_rooms_by_floor,
    translate_user_prefs_to_room_rules, ROOM_TYPE_RULES,
)


def _build_parsed(rooms, overrides=None):
    parsed = {"patalpos": rooms, "santrauka": {}}
    if overrides is not None:
        parsed["_overrides"] = overrides
    return parsed


# ── Edge: empty rooms ──────────────────────────────────────────────────

def test_empty_rooms_pozicijos_is_empty():
    out = _build_pozicijos_from_rooms(_build_parsed([]))
    assert out.get("pozicijos") == [], f"Expected empty, got {out.get('pozicijos')}"


def test_empty_rooms_calc_totals():
    from extractor.universal_rules import calc_totals
    t = calc_totals([])
    assert t["dazymo_plotas_total_m2"] == 0
    assert t["plyteles_grindys_m2_total"] == 0
    assert t["hidroizoliacijos_vnt"] == 0


# ── Edge: single garazas (no painting, no plytelės) ────────────────────

def test_single_garazas_walls_unpainted_ceiling_painted():
    """Garažas (betonas lubos, no apdailos): WALLS stay unpainted, CEILING is painted.

    Spec changed 2026-05-31 (commit c91dd3b, "close calculator coverage gaps —
    Beržų MAE 3.25%→1.15%"). calc_room_quantities now sets
    base_ceiling_area = plotas for ALL ceiling types (universal_rules.py:778-788):
    betonas garažas/tambūras ceilings are plastered + painted in LT residential
    builds. The contractor-validated Beržų ground truth confirms it — garažas
    room 105 (lubu_tipas=betonas) carries ceiling_paintable_m2=10.67 and IS
    included in the primary dazymo_plotas_total_m2 (607.11; the excl-garažas
    figure 557.06 is only a secondary total). So a betonas garažas ceiling is
    painted; the pre-calibration "no painting at all" assertion (written
    2026-04-29) is stale and reverting it would regress the Beržų benchmark.

    Walls stay unpainted HERE only because this room has no
    sienu_apdailos_breakdown → it falls through the legacy paskirtis path where
    garazas walls_paint=0. (Beržų's garažas walls ARE painted, but solely
    because its truth file supplies dazymas_share=1.0, routing it through the
    apdailos path.) This test still guards that: a bare garažas paints the
    ceiling but never the walls.
    """
    rooms = [{
        "nr": "1", "pavadinimas": "Garažas", "paskirtis": "garazas",
        "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.7,
        "lubu_tipas": "betonas", "elementai": [],
        "confidence": "high",
    }]
    parsed = _build_parsed(rooms)
    # Apply calc to each room first
    for r in rooms:
        r.update(calc_room_quantities(r))
    out = _build_pozicijos_from_rooms(parsed)
    pozicijos = out.get("pozicijos", [])
    paint_lines = [p for p in pozicijos if "dažymas" in p.get("aprasymas", "").lower()
                   or "glaistymas" in p.get("aprasymas", "").lower()]
    # The ONLY glaistymas/dažymas in a bare garažas is the ceiling — never walls.
    assert paint_lines, "betonas garažas ceiling should be painted (Beržų calibration)"
    assert all(p["aprasymas"].lower().startswith("lubų") for p in paint_lines), \
        f"Only the ceiling should be painted in a bare garažas, got {paint_lines}"
    assert all(p["kiekis"] == 30.0 for p in paint_lines), \
        f"Ceiling paint area should equal floor area (30.0), got {paint_lines}"


# ── Edge: single-room project ─────────────────────────────────────────

def test_single_living_room_full_pipeline():
    rooms = [{
        "nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 25.0, "perimetras_m": 20.0, "lubu_aukstis_m": 2.7,
        "lubu_tipas": "gkp",
        "elementai": [
            {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2050},
            {"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500},
        ],
        "confidence": "high",
    }]
    for r in rooms:
        r.update(calc_room_quantities(r))
    out = _build_pozicijos_from_rooms(_build_parsed(rooms))
    pozicijos = out.get("pozicijos", [])
    assert len(pozicijos) > 5, f"Single room project should have multiple pozicijos, got {len(pozicijos)}"
    # Specifically expect painting + GKP + grindys lines
    skyriai = {p.get("skyrius") for p in pozicijos}
    assert "Sienų lubų glaistymas dažymas" in skyriai
    assert "GKP montavimas" in skyriai


# ── Edge: NRM2 + Q4 + paint_class=3 combo ─────────────────────────────

def test_nrm2_q4_class3_combined():
    """All accuracy parameters at their non-default extreme — verify pipeline
    handles aggressively, no crash, results sane."""
    rooms = [{
        "nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia",
        "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.65,
        # Tile to 1.5m only — full-height 2.4m tiles + default 1 door +
        # 1 window deductions take walls_net below zero (clamped) → no
        # šlifavimas pozicija fires. Pre-2026-05-10 calc ignored
        # plyteles_sienos_aukstis_m so this was an accidental pass.
        "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 1.5,
        "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000}],
        "confidence": "high",
    }]
    rules_override = {
        "paint_deduction_standard": "NRM2",
        "glaistas_q_lygis": "Q4",
        "paint_class": 3,
    }
    rules = translate_user_prefs_to_room_rules(rules_override)
    for r in rooms:
        r.update(calc_room_quantities(r, rules=rules))
    parsed = _build_parsed(rooms, overrides=rules_override)
    out = _build_pozicijos_from_rooms(parsed)
    pozicijos = out.get("pozicijos", [])
    assert len(pozicijos) > 0
    # Q4 šlifavimas should appear with darbo_norma
    sand_lines = [p for p in pozicijos if "šlifavimas" in p.get("aprasymas", "")]
    assert len(sand_lines) > 0
    q4_sand = [p for p in sand_lines if p.get("_q_lygis") == "Q4"]
    assert len(q4_sand) > 0, f"Expected Q4 sanding lines, got {sand_lines}"


# ── Edge: all rooms wet ──────────────────────────────────────────────

def test_all_wet_rooms_emits_hydroinsulation():
    """Hidroizoliacija is computed in _recompute_per_room_via_python (full
    pipeline) not just calc_room_quantities. Use _calc_hidroizoliacija_m2
    directly + verify pozicija emitted."""
    from extractor.vision_call import _calc_hidroizoliacija_m2
    rooms = [
        {"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia",
         "plotas_m2": 5.0, "perimetras_m": 9.0, "lubu_aukstis_m": 2.5,
         "lubu_tipas": "pakabinamos",
         "plyteles_sienos_aukstis_m": 2.0, "elementai": [], "confidence": "high"},
        {"nr": "2", "pavadinimas": "WC", "paskirtis": "wc",
         "plotas_m2": 2.5, "perimetras_m": 6.0, "lubu_aukstis_m": 2.5,
         "lubu_tipas": "pakabinamos",
         "plyteles_sienos_aukstis_m": 2.0, "elementai": [], "confidence": "high"},
    ]
    for r in rooms:
        r.update(calc_room_quantities(r))
        # Manually inject hidroizoliacija like recompute pipeline does
        r["hidroizoliacija_m2"] = _calc_hidroizoliacija_m2(r, r.get("perimetras_m", 0))
    out = _build_pozicijos_from_rooms(_build_parsed(rooms))
    pozicijos = out.get("pozicijos", [])
    hydro = [p for p in pozicijos if "hidroizoliacija" in p.get("aprasymas", "").lower()
             or p.get("skyrius") == "Hidroizoliacija"]
    assert len(hydro) > 0, "Wet rooms project must emit hidroizoliacija line"


# ── Edge: cellar floor ───────────────────────────────────────────────

def test_cellar_floor_recognized():
    """Room nr starting with "0" or "P-" is parter/cellar (floor 0)."""
    assert room_aukstas_from_nr("0F-01") == 0
    assert room_aukstas_from_nr("P-12") == 0
    rooms = [
        {"nr": "0F-01", "pavadinimas": "Rūsys"},
        {"nr": "1F-01", "pavadinimas": "Holas"},
    ]
    grouped = group_rooms_by_floor(rooms)
    assert 0 in grouped
    assert 1 in grouped
    assert len(grouped[0]) == 1
    assert len(grouped[1]) == 1


# ── Edge: high ceiling >3m → emits separate GKP virš 3m ──────────────

def test_high_ceiling_emits_separate_gkp_line():
    rooms = [{
        "nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 3.5,  # >3m!
        "lubu_tipas": "gkp", "elementai": [], "confidence": "high",
    }]
    for r in rooms:
        r.update(calc_room_quantities(r))
    out = _build_pozicijos_from_rooms(_build_parsed(rooms))
    pozicijos = out.get("pozicijos", [])
    gkp_high = [p for p in pozicijos if "virš 3" in p.get("aprasymas", "").lower()
                or "virš 3 m" in p.get("aprasymas", "").lower()]
    assert len(gkp_high) >= 1, f"High ceiling should emit `virš 3m` GKP line, got {[p.get('aprasymas') for p in pozicijos if 'GKP' in p.get('skyrius', '')]}"


# ── Edge: paskirtis with unusual chars ───────────────────────────────

def test_paskirtis_unicode_normalize():
    """LT diacritics should normalize correctly."""
    from extractor.universal_rules import normalize_paskirtis
    assert normalize_paskirtis("Drabužinė") == "drabuzine"
    assert normalize_paskirtis("Sandėliukas") == "sandeliukas"
    assert normalize_paskirtis("VONIA") == "vonia"
    assert normalize_paskirtis("svetainė") == "gyvenamoji"
