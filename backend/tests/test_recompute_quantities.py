from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_recompute_paint_class_change_uses_backend_formula():
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "rooms" in body
    assert "pozicijos" in body
    assert body["rooms"][0]["dazai_l"] > 0


def test_recompute_paint_formula_class_2_walls_100m2():
    """Regression test: 100 m² walls at class 2 (8 m²/L coverage) with
    1.8× first-coat absorption → exactly 22.5 L of wall paint."""
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200
    body = r.json()
    # 100 m² * 1.8 / 8 m²/L = 22.5 L
    assert body["rooms"][0]["dazai_l"] == 22.5


def _living_room(nr="1", h=2.8):
    return {
        "nr": nr, "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": h,
        "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}],
    }


def _ceiling_recompute(height):
    """POST a per-room ceiling-height edit WITH reader context — the 2026-06-17
    fix path that rebuilds canonical pozicijos via _build_pozicijos_from_rooms."""
    payload = {
        "rooms": [_living_room(h=2.8)],
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": height}}],
        "current_assumptions": {},
        # context carries reader-derived data so the rebuild keeps non-geometry lines
        "context": {"detected_symbols_summary": {"rozetes": 7}},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _paint_total(body):
    return round(sum(
        float(p.get("kiekis") or 0) for p in body["pozicijos"]
        if "glaistymas/dažymas" in (p.get("aprasymas") or "").lower()
    ), 2)


def test_ceiling_height_change_rebuilds_paint_pozicijos():
    """2026-06-17 fix: a ceiling-height edit must REBUILD the canonical pozicijos
    so paint scales with height. Before the fix, _apply_assumption_edits updated
    room geometry but the aggregated paint pozicija stayed stale."""
    low = _ceiling_recompute(2.6)
    high = _ceiling_recompute(3.6)
    paint_low = _paint_total(low)
    paint_high = _paint_total(high)
    assert paint_low > 0 and paint_high > 0, (paint_low, paint_high)
    # Taller walls → strictly more paintable area (perimeter × Δh = 22 × 1.0 = 22 m²).
    assert paint_high > paint_low + 15, (paint_low, paint_high)


def test_ceiling_height_change_preserves_reader_lines():
    """The canonical rebuild must NOT drop reader/symbol-derived lines that the
    plain geometry recompute can't reproduce (rozetės from detected_symbols)."""
    body = _ceiling_recompute(3.0)
    has_rozetes = any(
        "rozet" in (p.get("aprasymas") or "").lower() for p in body["pozicijos"]
    )
    assert has_rozetes, [p.get("aprasymas") for p in body["pozicijos"]]


def test_ceiling_change_preserves_manual_count_override_and_price():
    """2026-06-17 regression: a ceiling-height edit rebuilds the canonical
    pozicijos, but it must NOT wipe user edits made on the prior pozicijos —
    manual count overrides (rozetės 52→50) and entered prices (kaina). The
    rebuild sources counts from detected_symbols_summary; without a merge it
    would silently revert the user's correction."""
    prior_pozicijos = [
        {"aprasymas": "Rozetės / jungiklio pajungimas", "vnt": "vnt",
         "kiekis": 50, "kaina": 12.5, "manual_override": True,
         "ai_kiekis_original": 52},
    ]
    payload = {
        "rooms": [_living_room(h=2.8)],
        "pozicijos": prior_pozicijos,
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": 3.2}}],
        "current_assumptions": {},
        "context": {"detected_symbols_summary": {"rozetes": 52}},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    poz = r.json()["pozicijos"]
    roz = next((p for p in poz if "rozet" in (p.get("aprasymas") or "").lower()), None)
    assert roz is not None, [p.get("aprasymas") for p in poz]
    # User's corrected count (50) must survive — NOT revert to detected 52.
    assert roz.get("kiekis") == 50, roz
    # User's entered price must survive the rebuild.
    assert roz.get("kaina") == 12.5, roz


def test_recompute_invalid_field_returns_400():
    payload = {
        "rooms": [],
        "edits": [{"field": "definitely_not_a_field", "new_value": 99}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400
    assert "definitely_not_a_field" in r.json()["detail"]
