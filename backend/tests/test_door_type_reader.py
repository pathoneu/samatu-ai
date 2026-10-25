"""Door-type reader + reconcile-and-surface (2026-06-14).

Frameless door type is structurally NOT in the plan glyph (a frameless and a
standard door draw identically) — it lives in TEXT (tags LD-1/D-2, annotations
"skirta beapvadinėms durims", notes). We read that text (~90% regime) and
reconcile against the glyph-detected count, SURFACING disagreement as a
confidence flag — never silently overwriting. Council 5/5 + research.
"""
from extractor.door_type_reader import (
    reconcile_frameless, _find_door_pages,
    _safe_count, _mode_int, read_door_types,
)


# ── safe coercion: a non-numeric Vision count must not crash the read ─────
# (audit 2026-07-06: door_type_reader was the one reader missing the
#  _safe_count wrapper that sanitary_fixture_reader/doors_reader already had.)
def test_safe_count_coerces_or_defaults():
    assert _safe_count(3) == 3
    assert _safe_count("3") == 3
    assert _safe_count("3+") == 0          # non-numeric → default, no ValueError
    assert _safe_count("3 durys") == 0
    assert _safe_count(None) == 0
    assert _safe_count(2.9) == 2
    assert _safe_count("nėra", default=1) == 1


def test_mode_int_survives_non_numeric_reads():
    # a hallucinated "3+" among numeric reads is dropped, not crash-inducing
    assert _mode_int([3, 3, "3+"]) == 3


# ── reconcile-and-surface (the merge discipline) ─────────────────────────
def test_agree_is_green():
    r = reconcile_frameless(plan_frameless=8, reader_frameless=8,
                            bendras_tipas=None, n_interior_doors=10, archetipas="premium")
    assert r["count"] == 8 and r["confidence"] == "zalia"


def test_reader_higher_raises_and_flags_yellow():
    # The Objektas A case: glyph tagged 2, text annotations/tags say ~8 → raise + flag.
    r = reconcile_frameless(plan_frameless=2, reader_frameless=8,
                            bendras_tipas=None, n_interior_doors=10, archetipas="premium")
    assert r["count"] == 8                      # raised to the text count
    assert r["confidence"] == "geltona"
    assert "8" in r["reason"] and "2" in r["reason"]


def test_governing_narrative_applies_to_interior_doors_flagged():
    # "visos vidaus durys — beapvadinės" + premium → all interior doors, flagged.
    r = reconcile_frameless(plan_frameless=2, reader_frameless=3,
                            bendras_tipas="beapvadines", n_interior_doors=9, archetipas="premium")
    assert r["count"] == 9                       # raised to interior-door count
    assert r["confidence"] == "geltona"
    assert "beapvad" in r["reason"].lower()


def test_conflict_keeps_plan_and_surfaces_both_never_lowers():
    # reader < plan (e.g. value-engineered) → don't silently lower; surface both.
    r = reconcile_frameless(plan_frameless=6, reader_frameless=3,
                            bendras_tipas=None, n_interior_doors=10, archetipas="standard")
    assert r["count"] == 6                        # never lowered below the plan symbol
    assert r["confidence"] == "geltona"
    assert "6" in r["reason"] and "3" in r["reason"]


def test_narrative_default_not_applied_without_premium():
    # narrative-gated: only premium archetype auto-applies the governing note.
    r = reconcile_frameless(plan_frameless=2, reader_frameless=2,
                            bendras_tipas="beapvadines", n_interior_doors=9, archetipas="standard")
    assert r["count"] == 2                        # not auto-expanded on non-premium
    assert r["confidence"] == "geltona"           # but still flag the governing note


# ── page finding (text-first: prefer pages with door tags/annotations) ───
def test_find_door_pages_prefers_tag_and_annotation_pages(monkeypatch):
    import extractor.door_type_reader as m

    class _Page:
        def __init__(self, t): self._t = t
        def extract_text(self): return self._t

    class _Pdf:
        def __init__(self, pages): self.pages = pages
        def __enter__(self): return self
        def __exit__(self, *a): return False

    pages = [_Page("TITULINIS LAPAS"),
             _Page("AUKŠTO PLANAS ... skirta beapvadinėms durims"),  # annotation
             _Page("PERTVARŲ PLANAS D-1 D-1 D-2 D-3"),               # door tags
             _Page("LUBŲ PLANAS LD-1 LD-1 LD-2 LD-3 +2800")]         # curtain-niche details — NOT door tags (2026-09-23)
    # Seam moved 2026-08-03: _find_door_pages reads the shared parse in
    # extractor.pdf_page_cache instead of opening its own document (it used to
    # re-parse the whole PDF once per voting round). Same texts in, same
    # assertion below.
    monkeypatch.setattr("extractor.pdf_page_cache.page_texts",
                        lambda *_a, **_k: [p.extract_text() for p in pages])
    pp = _find_door_pages(b"x")
    assert 2 in pp and 3 in pp and 1 not in pp and 4 not in pp


# ── wiring: reconciled count flows into the durų angų pozicija ────────────
def test_door_types_raises_and_flags_pozicija():
    from extractor.universal_rules import calc_room_quantities
    from extractor.vision_call import _build_pozicijos_from_rooms
    # one room with 2 tagged frameless doors (900×2400 → 5.7m reveal each)
    room = {"nr": "1", "pavadinimas": "Koridorius", "paskirtis": "koridorius",
            "plotas_m2": 12.0, "perimetras_m": 14.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas",
            "elementai": [{"tipas": "pasleptos_duris", "kiekis": 2,
                           "plotis_mm": 900, "aukstis_mm": 2400}]}
    room.update(calc_room_quantities(room))
    # reader/reconciliation says 7 frameless → durų angų should scale 2→7
    parsed = {"patalpos": [room], "santrauka": {},
              # the count is one the reader READ in the text (2026-09-23: a count made of the plan's own
              # symbols, reader 0, no longer raises anything)
              "_door_types": {"count": 7, "reader_beapvadines": 7, "confidence": "geltona", "saltinis": "tekstas",
                              "reason": "Anotacijose rasta 7, pradinis rado 2 — patikrink"}}
    out = _build_pozicijos_from_rooms(parsed)
    line = [p for p in out["pozicijos"] if "beapvadinėms durims" in p["aprasymas"]]
    assert len(line) == 1
    # 7 doors × 5.7m avg reveal ≈ 39.9m (was 2×5.7=11.4)
    assert line[0]["kiekis"] > 35.0, line[0]["kiekis"]
    assert line[0]["confidence"] == "geltona"
    assert "7" in line[0]["_confidence_reason"]
