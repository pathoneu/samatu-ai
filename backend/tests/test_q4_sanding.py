"""Q4 sanding labor uplift tests (Sprint §2A.4 Phase 2).

2026-06-06: paint lines are consolidated (ENABLE_CONSOLIDATE_PAINT_LINES). Q4
emits ONE combined "Sienų, lubų šlifavimas Q4 (80–120 grit, 100% paviršius)"
line with darbo_norma_h_m2 = 0.30 and _q_lygis = "Q4". Lower Q levels have NO
separate šlifavimas line — sanding is folded into the consolidated
glaistymas/dažymas line (matches the contractor's m² rate).
"""

from extractor.vision_call import _build_pozicijos_from_rooms, _Q4_SANDING_HOURS_PER_M2


def _build_minimal_parsed(q_lygis: str | None = None) -> dict:
    """Minimal parsed dict for the pozicijos generator."""
    parsed = {
        "patalpos": [
            {
                "nr": 1,
                "pavadinimas": "Svetainė",
                "paskirtis": "gyvenamoji",
                "plotas_m2": 20.0,
                "perimetras_m": 18.0,
                "lubu_aukstis_m": 2.82,
                "dazymo_plotas_m2": 50.0,
                "walls_paintable_m2": 35.0,
                "ceiling_paintable_m2": 20.0,
                "gkp_lubu_standart_m2": 20.0,
                "kampu_metrai": 5.0,
                "elementai": [],
                "lubu_tipas": "gkp",
            }
        ],
        "santrauka": {},
    }
    if q_lygis is not None:
        parsed["_overrides"] = {"glaistas_q_lygis": q_lygis}
    return parsed


def _find_lines(pozicijos: list, needle: str) -> list:
    return [p for p in pozicijos if needle.lower() in (p.get("aprasymas") or "").lower()]


def test_q4_walls_sanding_has_uplift():
    parsed = _build_minimal_parsed(q_lygis="Q4")
    out = _build_pozicijos_from_rooms(parsed)
    matches = _find_lines(out["pozicijos"], "šlifavimas Q4")
    assert len(matches) >= 1
    line = matches[0]
    assert "Q4" in line["aprasymas"]
    assert "80–120 grit" in line["aprasymas"] or "80-120 grit" in line["aprasymas"]
    assert line.get("darbo_norma_h_m2") == _Q4_SANDING_HOURS_PER_M2
    assert line.get("_q_lygis") == "Q4"


def test_q4_lubos_sanding_has_uplift():
    parsed = _build_minimal_parsed(q_lygis="Q4")
    out = _build_pozicijos_from_rooms(parsed)
    matches = _find_lines(out["pozicijos"], "Lubų šlifavimas")
    assert len(matches) >= 1
    line = matches[0]
    assert "Q4" in line["aprasymas"]
    assert line.get("darbo_norma_h_m2") == _Q4_SANDING_HOURS_PER_M2


def test_q2_default_no_separate_sanding_line():
    # Q2 (default): sanding is folded into the consolidated glaistymas/dažymas
    # line — no separate šlifavimas line (matches the contractor). Only Q4 keeps
    # a standalone šlifavimas line (premium full-surface sanding).
    parsed = _build_minimal_parsed(q_lygis="Q2")
    out = _build_pozicijos_from_rooms(parsed)
    matches = _find_lines(out["pozicijos"], "šlifavimas")
    assert matches == [], \
        f"Q2 should have no separate sanding line, got {[m['aprasymas'] for m in matches]}"


def test_no_overrides_defaults_to_q2():
    parsed = _build_minimal_parsed(q_lygis=None)
    out = _build_pozicijos_from_rooms(parsed)
    matches = _find_lines(out["pozicijos"], "šlifavimas")
    for line in matches:
        assert "Q4" not in line["aprasymas"]


def test_q4_sanding_norm_constant():
    # Sanity check on the published norm — research source: Merkblatt Nr.2.
    assert _Q4_SANDING_HOURS_PER_M2 == 0.30
