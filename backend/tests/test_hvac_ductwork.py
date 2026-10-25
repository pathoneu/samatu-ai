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
              "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
              "elementai": [], "confidence": "high"}]
    out = _build_pozicijos_from_rooms(_build_parsed(rooms))
    assert len(_ortakiu_lines(out)) == 0










