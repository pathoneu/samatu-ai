"""2026-07-27 pre-handoff audit — /api/recompute-quantities findings 1-4.

  1. _merge_user_edits DELETED priced / manually-corrected prior lines whose
     label no longer exists after the canonical rebuild (real project: the two
     priced 'LED nišų glaistymas' + 'LED nišų dažymas' lines vanish because the
     rebuild emits the consolidated 'LED nišų glaistymas/dažymas').
  2. Out-of-range / unparseable per-room ceiling heights were dropped silently
     with HTTP 200 — the user saw "saved" and nothing changed.
  3. Non-numeric assumptions (lubu_aukstis='abc', paint_class=None) 500'd on the
     bare int()/float() calls.
  4. The inner `except Exception: pass` blocks hid every partial failure.

Every fix is observable in the response: carried lines are flagged
`_orphaned_after_rebuild`, everything else lands in `_degradations`.
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from main import app  # noqa: E402

client = TestClient(app)


def _room(nr="1", h=2.8, **extra):
    r = {
        "nr": nr, "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": h,
        "elementai": [{"tipas": "duris", "kiekis": 1,
                       "plotis_mm": 900, "aukstis_mm": 2100}],
    }
    r.update(extra)
    return r


def _post(payload):
    r = client.post("/api/recompute-quantities", json=payload)
    return r


def _degradations(body):
    return body.get("_degradations") or []


# ── Fix 1: no priced / manually-corrected line may be deleted ────────────────

def test_led_pair_consolidation_keeps_both_priced_lines():
    """The exact production scenario: two priced LED lines, one consolidated
    rebuilt line. Neither price may disappear."""
    from api.recompute_quantities import _merge_user_edits
    prior = [
        {"aprasymas": "LED nišų glaistymas", "vnt": "m",
         "kiekis": 42.3, "kaina": 4.0, "suma": 169.2},
        {"aprasymas": "LED nišų dažymas", "vnt": "m",
         "kiekis": 42.3, "kaina": 3.0, "suma": 126.9},
    ]
    rebuilt = [{"aprasymas": "LED nišų glaistymas/dažymas", "vnt": "m",
                "kiekis": 42.3}]
    out = _merge_user_edits(rebuilt, prior)

    # The first priced line reunites with the consolidated rebuilt line…
    consolidated = [p for p in out
                    if p["aprasymas"] == "LED nišų glaistymas/dažymas"]
    assert len(consolidated) == 1, out
    assert consolidated[0]["kaina"] == 4.0
    assert consolidated[0]["suma"] == 169.2          # 42.3 × 4.0, from rebuilt kiekis

    # …and the second is CARRIED, flagged, never silently dropped.
    carried = [p for p in out if p.get("_orphaned_after_rebuild")]
    assert len(carried) == 1, out
    assert carried[0]["aprasymas"] == "LED nišų dažymas"
    assert carried[0]["kaina"] == 3.0

    # No money vanished.
    assert round(sum(float(p.get("suma") or 0) for p in out), 2) == 296.1


def test_manual_override_line_always_survives_rebuild():
    """A manual count override on a line the rebuild no longer emits must be
    carried, not destroyed (the audit's second reproduced loss)."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Rozetės (rankinis skaičius)", "vnt": "vnt.",
              "kiekis": 50, "manual_override": True, "ai_kiekis_original": 52}]
    rebuilt = [{"aprasymas": "Sienų dažymas", "kiekis": 10}]
    out = _merge_user_edits(rebuilt, prior)
    carried = [p for p in out if p.get("_orphaned_after_rebuild")]
    assert len(carried) == 1, out
    assert carried[0]["kiekis"] == 50
    assert carried[0]["manual_override"] is True


def test_unedited_lines_are_carried_too():
    """POLICY CHANGE 2026-07-28 (P0). This test previously asserted the OPPOSITE
    — that an un-edited vanished line is 'supposed to disappear'. Production
    proved that wrong: prices live in `darbu_sarasas`, so from `pozicijos` alone
    almost every priced line looks un-edited, and a ceiling round-trip deleted
    12-15 fully-priced rows (−5 281,85 €) with HTTP 200 and no degradations.
    Nothing may be dropped just because this endpoint can't see the money."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Senas AI kiekis", "kiekis": 7}]      # no visible edit
    rebuilt = [{"aprasymas": "Sienų dažymas", "kiekis": 10}]
    out = _merge_user_edits(rebuilt, prior)
    assert len(out) == 2, out
    carried = [p for p in out if p.get("_orphaned_after_rebuild")]
    assert len(carried) == 1 and carried[0]["aprasymas"] == "Senas AI kiekis"
    assert carried[0]["kiekis"] == 7


def test_retiered_unedited_line_is_still_dropped():
    """The ONE legitimate removal survives the policy change: an un-edited line
    whose work is still listed under a sibling TIER label was re-tiered by the
    rebuild (… (virš 3m) → … (iki 3m)), not deleted — carrying it would pin a
    stale duplicate of a quantity that legitimately moved."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)",
              "kiekis": 40}]                                     # no price, no override
    rebuilt = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
                "kiekis": 120}]
    notes: list = []
    out = _merge_user_edits(rebuilt, prior, notes)
    assert len(out) == 1 and out[0]["aprasymas"].endswith("(iki 3m aukščio)")
    assert [n["reason"] for n in notes] == ["superseded_by_tier"]


def test_retiered_line_dropped_when_its_sibling_was_already_matched():
    """Same idea, the shape that actually occurs on a height revert: the '(iki
    3m)' line exists in BOTH lists (so pass 2 has no candidate left) and the
    '(virš 3m)' line simply has no work behind it any more. Un-edited → dropped,
    with the reason recorded."""
    from api.recompute_quantities import _merge_user_edits
    prior = [
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 80},
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)", "kiekis": 40},
    ]
    rebuilt = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
                "kiekis": 120}]
    notes: list = []
    out = _merge_user_edits(rebuilt, prior, notes)
    assert len(out) == 1, out
    assert [n["reason"] for n in notes] == ["superseded_by_tier"]


def test_retiered_PRICED_line_is_carried_not_dropped():
    """…but the moment real money rides on it, the tier heuristic stops being
    allowed to delete it. Obsolete-or-not is the user's call, not ours."""
    from api.recompute_quantities import _merge_user_edits
    prior = [
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
         "kiekis": 120, "kaina": 3.0, "suma": 360.0},
        {"aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)",
         "kiekis": 40, "kaina": 5.0, "suma": 200.0},
    ]
    rebuilt = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
                "kiekis": 120}]
    out = _merge_user_edits(rebuilt, prior)
    carried = [p for p in out if p.get("_orphaned_after_rebuild")]
    assert len(carried) == 1 and carried[0]["kaina"] == 5.0, out
    assert round(sum(float(p.get("suma") or 0) for p in out), 2) == 560.0


def test_norm_label_collapses_led_pair():
    from api.recompute_quantities import _norm_label
    assert (_norm_label("LED nišų glaistymas")
            == _norm_label("LED nišų dažymas")
            == _norm_label("LED nišų glaistymas/dažymas"))


def test_end_to_end_priced_lines_survive_ceiling_edit():
    """Through the HTTP endpoint: a ceiling-height edit rebuilds the pozicijos;
    every priced prior line must still be present afterwards."""
    prior = [
        {"aprasymas": "LED nišų glaistymas", "vnt": "m",
         "kiekis": 42.3, "kaina": 4.0, "suma": 169.2},
        {"aprasymas": "LED nišų dažymas", "vnt": "m",
         "kiekis": 42.3, "kaina": 3.0, "suma": 126.9},
    ]
    r = _post({
        "rooms": [_room(h=2.8)],
        "pozicijos": prior,
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": 3.2}}],
        "current_assumptions": {},
        "context": {"detected_symbols_summary": {}},
    })
    assert r.status_code == 200, r.text
    poz = r.json()["pozicijos"]
    priced = {p["aprasymas"]: p for p in poz if p.get("kaina")}
    assert priced, [p.get("aprasymas") for p in poz]
    # Both prior prices are still reachable (either on a rebuilt line or carried).
    assert round(sum(float(p.get("kaina") or 0) for p in priced.values()), 2) == 7.0


# ── Fix 2: rejected height overrides are reported ────────────────────────────

def test_out_of_range_height_is_reported_not_silent():
    r = _post({
        "rooms": [_room(nr="101")],
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": 100}}],
        "current_assumptions": {},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    degs = _degradations(body)
    hit = [d for d in degs if isinstance(d, dict)
           and d.get("room") == "101" and d.get("reason") == "out_of_range"]
    assert hit, degs
    assert hit[0]["field"] == "lubu_aukstis"
    # …and the bogus height was NOT applied.
    assert body["rooms"][0]["lubu_aukstis_m"] == 2.8


def test_unparseable_height_is_reported():
    r = _post({
        "rooms": [_room(nr="101")],
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": "trys metrai"}}],
        "current_assumptions": {},
    })
    assert r.status_code == 200, r.text
    degs = _degradations(r.json())
    assert [d for d in degs if isinstance(d, dict)
            and d.get("room") == "101" and d.get("reason") == "not_numeric"], degs


def test_valid_height_applies_with_no_degradation():
    r = _post({
        "rooms": [_room(nr="101")],
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": 3.0}}],
        "current_assumptions": {},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rooms"][0]["lubu_aukstis_m"] == 3.0
    assert body["rooms"][0]["lubu_aukstis_saltinis"] == "user_override"
    assert _degradations(body) == []


# ── Fix 3: non-numeric assumptions degrade instead of 500 ────────────────────

def test_non_numeric_assumptions_do_not_500():
    r = _post({
        "rooms": [_room()],
        "edits": [{"field": "lubu_aukstis", "new_value": "abc"},
                  {"field": "paint_class", "new_value": None}],
        "current_assumptions": {},
    })
    assert r.status_code == 200, r.text          # was a 500 before the fix
    body = r.json()
    fields = {d.get("field") for d in _degradations(body) if isinstance(d, dict)}
    assert {"lubu_aukstis", "paint_class"} <= fields, _degradations(body)
    # Defaults applied → paint still computed off class 1.
    assert body["rooms"][0]["dazai_l"] >= 0


def test_non_numeric_wall_thickness_does_not_500():
    r = _post({
        "rooms": [_room()],
        "edits": [{"field": "sienos_storis_m", "new_value": "storoka"}],
        "current_assumptions": {},
    })
    assert r.status_code == 200, r.text
    fields = {d.get("field") for d in _degradations(r.json()) if isinstance(d, dict)}
    assert "sienos_storis_m" in fields


# ── Fix 4: swallowed per-room failures surface ───────────────────────────────

def test_garbage_room_area_is_reported_not_swallowed():
    r = _post({
        "rooms": [_room(nr="7", dazomas_plotas_m2="n/a")],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {},
    })
    assert r.status_code == 200, r.text          # was a 500 before the fix
    degs = _degradations(r.json())
    assert [d for d in degs if isinstance(d, dict) and d.get("room") == "7"], degs


def test_clean_recompute_reports_no_degradations():
    """Guard against a noisy false-positive: a normal edit must stay silent."""
    r = _post({
        "rooms": [_room()],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    })
    assert r.status_code == 200, r.text
    assert _degradations(r.json()) == []
