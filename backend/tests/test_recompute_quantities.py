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
    """100 m² of paintable surface at class 2 → exactly 20.0 L.

    2026-09-02: this used to assert 22.5 L — this endpoint ran its own formula
    (paint_coverage["plastered_q2_q3"] = 8 m²/L × first_coat_factor 1.8) while
    the extraction pipeline used the class profile (9 m²/L × 1.8) for the same
    room. Both numbers sit inside CLAUDE.md §1.10's 7-9 m²/L band, but a project
    cannot have two answers: the litres shifted ~11% the first time a user
    touched Prielaidos. Since materials became a priced section of their own the
    endpoint delegates to the canonical `_calc_dazai_liters`, so a Prielaidos
    edit reproduces the extraction's own figure.
    """
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200
    body = r.json()
    # 100 m² × 1.8 absorption / 9 m²/L (class-2 profile) = 20.0 L
    assert body["rooms"][0]["dazai_l"] == 20.0
    # …and that is exactly what the extraction pipeline computes for it.
    from extractor.vision_call import _calc_dazai_liters
    assert body["rooms"][0]["dazai_l"] == _calc_dazai_liters(100.0, paint_class=2)


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


def test_merge_carries_price_across_tier_boundary():
    """2026-06-19 bug-hunt: a priced '(virš 3m)' line whose label flips to
    '(iki 3m)' when the ceiling drops below 3 m must keep its unit price (and
    recompute suma from the new quantity)."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)",
              "kiekis": 100, "kaina": 5.0, "suma": 500.0}]
    rebuilt = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 120}]
    out = _merge_user_edits(rebuilt, prior)
    assert out[0]["kaina"] == 5.0
    assert out[0]["suma"] == 600.0  # 120 × 5, from the rebuilt kiekis


def test_merge_does_not_cross_contaminate_mixed_tier_pair():
    """Mixed-height project: both tier lines present with DIFFERENT prices →
    exact match keeps each price on its own line (no cross-assignment)."""
    from api.recompute_quantities import _merge_user_edits
    prior = [
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 80, "kaina": 3.0},
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)", "kiekis": 40, "kaina": 5.0},
    ]
    rebuilt = [
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 80},
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)", "kiekis": 40},
    ]
    out = {p["aprasymas"]: p for p in _merge_user_edits(rebuilt, prior)}
    assert out["Sienų, lubų glaistymas/dažymas (iki 3m aukščio)"]["kaina"] == 3.0
    assert out["Sienų, lubų glaistymas/dažymas (virš 3m aukščio)"]["kaina"] == 5.0


def test_merge_ambiguous_tier_fallback_is_skipped():
    """One priced prior line, but two rebuilt lines share the normalized base →
    ambiguous → the fallback must NOT guess (no mis-assigned price).

    2026-07-27 (audit fix 1): the price is no longer DELETED either — the prior
    line is carried as `_orphaned_after_rebuild`. The invariant under test is
    unchanged: no REBUILT line may inherit a price it can't be proven to own."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)", "kiekis": 40, "kaina": 5.0}]
    rebuilt = [
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 80},
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (standartinis aukštis)", "kiekis": 30},
    ]
    out = _merge_user_edits(rebuilt, prior)
    assert all(p.get("kaina") in (None, 0)
               for p in out if not p.get("_orphaned_after_rebuild"))
    carried = [p for p in out if p.get("_orphaned_after_rebuild")]
    assert len(carried) == 1 and carried[0]["kaina"] == 5.0, out


def test_q4_level_edit_emits_q4_sanding_line():
    """2026-06-19 bug-hunt: a glaistimo_lygis=Q4 edit must reach the canonical
    builder (which reads glaistas_q_lygis) so the Q4 sanding-labor line is emitted,
    not silently dropped to the Q2 default. (Production rooms carry computed
    geometry; a glaistimo_lygis edit doesn't re-run calc, so pre-compute here.)"""
    from extractor.universal_rules import calc_room_quantities
    room = _living_room(h=2.8)
    room.update(calc_room_quantities(room))
    payload = {
        "rooms": [room],
        "edits": [{"field": "glaistimo_lygis", "new_value": "Q4"}],
        "current_assumptions": {},
        "context": {"detected_symbols_summary": {}},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    poz = r.json()["pozicijos"]
    has_q4 = any("q4" in (p.get("aprasymas") or "").lower() for p in poz)
    assert has_q4, [p.get("aprasymas") for p in poz]


def test_recompute_emits_darbu_sarasas_in_sync_with_pozicijos():
    """2026-06-19 workspace hunt: the Kiekiai table, totals and export read
    darbu_sarasas (a v8 reshape of pozicijos), NOT pozicijos. The recompute must
    emit darbu_sarasas so a Prielaidos edit actually reaches the customer doc."""
    from extractor.universal_rules import calc_room_quantities
    room = _living_room(h=2.8)
    room.update(calc_room_quantities(room))
    payload = {
        "rooms": [room],
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": 3.4}}],
        "current_assumptions": {},
        "context": {"detected_symbols_summary": {}},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    poz, ds = body["pozicijos"], body["darbu_sarasas"]
    assert ds, "darbu_sarasas must be emitted"
    assert len(ds) == len(poz)
    poz_by = {p["aprasymas"]: p["kiekis"] for p in poz}
    for row in ds:  # same quantity per matching line
        assert row["kiekis"] == poz_by.get(row["aprasymas"])


def test_recompute_interior_tolerates_malformed_room():
    """2026-06-19 hunt: one malformed room (e.g. a comma-decimal/non-numeric
    plotas_m2 from a corrupted/legacy project) must NOT 500 the whole recompute
    and lose every other room — it should degrade to the un-recomputed room."""
    payload = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Bloga", "paskirtis": "gyvenamoji",
             "plotas_m2": "12,5", "perimetras_m": 14, "lubu_aukstis_m": 2.8},  # comma-decimal → calc raises
            {"nr": "2", "pavadinimas": "Gera", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.8},
        ],
    }
    r = client.post("/recompute-interior", json=payload)
    assert r.status_code == 200, r.text          # NOT a 500
    body = r.json()
    assert body.get("status") != "error", body
    rooms = body.get("patalpos") or body.get("v8_rooms") or []
    assert len(rooms) == 2                        # both rooms survive


def test_recompute_invalid_field_returns_400():
    payload = {
        "rooms": [],
        "edits": [{"field": "definitely_not_a_field", "new_value": 99}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400
    assert "definitely_not_a_field" in r.json()["detail"]


# ── Per-room finishing override (walls_paint) — 2026-07-05 ────────────────────
# Beржų garage: some garages/tambūrai are finished (painted walls) though they
# default to raw. The AssumptionsPanel toggle flips walls_paint per room and
# recomputes the paint geometry through the same live path as ceiling height.

def test_walls_paint_override_paints_raw_garage():
    from api.recompute_quantities import _apply_assumption_edits
    room = {"nr": "105", "pavadinimas": "Garažas", "paskirtis": "garazas",
            "plotas_m2": 10.67, "perimetras_m": 13.5, "lubu_aukstis_m": 3.4,
            "walls_paintable_m2": 0.0}
    out = _apply_assumption_edits([dict(room)], {"walls_paint_override": {"105": 1.0}})[0]
    assert out.get("walls_paintable_m2", 0) > 20, out.get("walls_paintable_m2")
    assert out.get("_walls_paint_override") == 1.0


def test_walls_paint_override_unpaints_living_room():
    from api.recompute_quantities import _apply_assumption_edits
    room = {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
            "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
            "walls_paintable_m2": 45.0}
    out = _apply_assumption_edits([dict(room)], {"walls_paint_override": {"1": 0.0}})[0]
    assert out.get("walls_paintable_m2", 99) == 0.0, out.get("walls_paintable_m2")
    assert out.get("_walls_paint_override") == 0.0


def test_walls_paint_override_absent_leaves_room_untouched():
    from api.recompute_quantities import _apply_assumption_edits
    room = {"nr": "1", "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
            "perimetras_m": 18.0, "lubu_aukstis_m": 2.7, "walls_paintable_m2": 45.0}
    out = _apply_assumption_edits([dict(room)], {})[0]
    assert out.get("walls_paintable_m2") == 45.0
    assert "_walls_paint_override" not in out


def test_walls_paint_override_valid_field():
    from api.recompute_quantities import _ASSUMPTION_FIELDS, _VALID_FIELDS
    assert "walls_paint_override" in _ASSUMPTION_FIELDS
    assert "walls_paint_override" in _VALID_FIELDS


# ── B3 (2026-07-28 audit): darbu_sarasas / pozicijos length mismatch ──────────
# OLD: `if len(darbu_sarasas) == len(pozicijos):` had NO else. When the compat
# emit returned a different number of rows (a reshape change, a merged/dropped
# line), the response's darbu_sarasas came back with kaina/suma/override flags
# STRIPPED — and the frontend writes that straight onto the project, so the
# user's entered prices silently vanished with HTTP 200 and no warning.

def _mismatch_payload():
    """A recompute whose pozicijos carry real money."""
    return {
        "rooms": [_living_room()],
        "pozicijos": [
            {"aprasymas": "Sienų dažymas", "kiekis": 50.0, "mato_vnt": "m2",
             "kaina": 7.5, "suma": 375.0},
            {"aprasymas": "Lubų dažymas", "kiekis": 30.0, "mato_vnt": "m2",
             "kaina": 6.0, "suma": 180.0},
        ],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    }


def test_compat_emit_mismatch_is_disclosed_and_prices_survive(monkeypatch):
    import extractor.vision_call as _vc

    def _short_emit(parsed):
        # One row fewer than pozicijos — the invariant break this guards.
        rows = [{"aprasymas": p["aprasymas"], "kiekis": p["kiekis"],
                 "mato_vnt": p.get("mato_vnt", "")}
                for p in parsed["pozicijos"][:1]]
        return {"darbu_sarasas": rows}
    monkeypatch.setattr(_vc, "_emit_v8_compat_fields", _short_emit)

    r = client.post("/api/recompute-quantities", json=_mismatch_payload())
    assert r.status_code == 200, r.text
    body = r.json()

    # 1. The prices survive on the rows whose labels still line up.
    ds = body["darbu_sarasas"]
    assert len(ds) == 1
    assert ds[0]["aprasymas"] == "Sienų dažymas"
    assert ds[0]["kaina"] == 7.5
    assert ds[0]["suma"] == 375.0

    # 2. And the divergence is DISCLOSED, machine-readably, in LT.
    deg = [d for d in body["_degradations"]
           if isinstance(d, dict) and d.get("reason") == "compat_emit_mismatch"]
    assert len(deg) == 1, body["_degradations"]
    assert deg[0]["rows"] == 1 and deg[0]["pozicijos"] == 2
    assert deg[0]["recovered"] == 1
    assert "Kiekių lentelė nesutapo" in deg[0]["message"]


def test_compat_emit_mismatch_does_not_guess_on_duplicate_labels(monkeypatch):
    """EXACT label match only. A duplicated aprasymas is ambiguous, so no price
    is carried for it — a wrong price is worse than a missing one."""
    import extractor.vision_call as _vc

    payload = _mismatch_payload()
    payload["pozicijos"] = [
        {"aprasymas": "Dažymas", "kiekis": 10.0, "kaina": 5.0, "suma": 50.0},
        {"aprasymas": "Dažymas", "kiekis": 20.0, "kaina": 9.0, "suma": 180.0},
        {"aprasymas": "Grindjuostės", "kiekis": 12.0, "kaina": 4.0, "suma": 48.0},
    ]
    monkeypatch.setattr(_vc, "_emit_v8_compat_fields", lambda parsed: {
        "darbu_sarasas": [{"aprasymas": p["aprasymas"], "kiekis": p["kiekis"]}
                          for p in parsed["pozicijos"][:2]]})

    body = client.post("/api/recompute-quantities", json=payload).json()
    by_label = {r["aprasymas"]: r for r in body["darbu_sarasas"]}
    assert "kaina" not in by_label["Dažymas"], "ambiguous label must not be priced"


def test_degradations_are_objects_not_bare_strings(monkeypatch):
    """B2 — the frontend filters _degradations on `d.reason`; plain strings were
    invisible, so a failed rebuild told the user nothing."""
    import extractor.vision_call as _vc
    monkeypatch.setattr(_vc, "_emit_v8_compat_fields",
                        lambda parsed: (_ for _ in ()).throw(RuntimeError("boom")))

    body = client.post("/api/recompute-quantities", json=_mismatch_payload()).json()
    degs = body["_degradations"]
    assert degs, "a failed compat emit must be disclosed"
    assert all(isinstance(d, dict) for d in degs), degs
    stale = [d for d in degs if d.get("reason") == "stale_quantities"]
    assert len(stale) == 1
    assert "seni kiekiai" in stale[0]["message"]
