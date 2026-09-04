# Objektas A pozicijos accuracy — Phase 1 (clean line-level fixes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the three highest-leverage, lowest-risk line-level inaccuracies found in the Objektas A audit (RC3 angokraščiai duplicate formula, RC1 basin count, RC8/RC5 redundant kampai emission) — globally, validated against the Rangovas A samata.

**Architecture:** All three are localized edits in `backend/extractor/vision_call.py::_build_pozicijos_from_rooms`. Each consumes data the pipeline already computes (the calibrated `angokrasciu_gkp_m` field; `detected_symbols_summary`; `kampu_metrai`). No data-model changes. Each is independently testable + committable. Verified numbers in `docs/objektas_a_audit_notes.md`.

**Tech Stack:** Python 3.14, pytest, `venv/bin/python`.

**Honest scope note:** These are *improvements*, not perfect matches (RC3 → −12.7%, RC1 → −40% residual from symbol recall). The deeper issues are deferred to Phase 2 (see end): kampai run-to-run instability (fresh 325 — a Vision extraction-stability problem, not a formula tweak), RC4 Rotband recalibration (needs block-wall-area data), RC2 symbol-path debug, RC6 partial-zone splits, RC7 missing categories.

---

## File Structure
- `backend/extractor/vision_call.py` — the only production file modified (3 edits in `_build_pozicijos_from_rooms`).
- `backend/tests/test_pozicijos_accuracy.py` — NEW test file for the three fixes.

---

### Task 1: RC3 — Angokraščiai use the calibrated field (not the inline recompute)

**Files:**
- Modify: `backend/extractor/vision_call.py:1257-1287`
- Test: `backend/tests/test_pozicijos_accuracy.py`

**Why:** The bill recomputes `angokrasciai_m = Σ(2H+W)` inline (counts exterior openings → 138.42 m on objektas_a, +54.8%) and emits it on TWO lines (`SK_GD` glaistymas + `SK_GKP` apdirbimas). The pipeline already computes a per-room `angokrasciu_gkp_m` (excludes exterior); `_sum("angokrasciu_gkp_m")` = 78.05 m (−12.7% vs contractor 89.39 — far better than +54.8%). Use it.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pozicijos_accuracy.py
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


def test_angokrasciai_uses_calibrated_field_not_inline():
    # one interior door + one window
    rooms = [_room([{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2050},
                    {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500}])]
    out = _build_pozicijos_from_rooms(_parsed(rooms))
    expected = round(sum(r.get("angokrasciu_gkp_m") or 0 for r in rooms), 2)
    glaist = [p for p in out["pozicijos"] if p["aprasymas"] == "Angokraščių glaistymas-dažymas"]
    gkp = [p for p in out["pozicijos"] if p["aprasymas"].startswith("Angokraščių apdirbimas GKP")]
    assert len(glaist) == 1 and len(gkp) == 1, out["pozicijos"]
    assert abs(glaist[0]["kiekis"] - expected) < 0.01, f"{glaist[0]['kiekis']} vs field {expected}"
    assert abs(gkp[0]["kiekis"] - expected) < 0.01, f"{gkp[0]['kiekis']} vs field {expected}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest backend/tests/test_pozicijos_accuracy.py::test_angokrasciai_uses_calibrated_field_not_inline -v`
Expected: FAIL (kiekis is the inline Σ(2H+W), not `angokrasciu_gkp_m`).

- [ ] **Step 3: Replace the inline recompute with the field**

In `backend/extractor/vision_call.py`, replace lines 1257-1287 (the `angokrasciai_m = 0` block through `pasleptu_duru_staktu_m = round(...)`):

```python
    # 2026-06-06 (RC3): use the calibrated per-room angokrasciu_gkp_m field
    # (universal_rules.calc_room_quantities; excludes exterior reveals) instead of
    # recomputing Σ(2H+W) inline. The inline version counted exterior openings and
    # over-quoted +54.8% on BOTH the glaistymas (SK_GD) and apdirbimas (SK_GKP) lines.
    angokrasciai_m = _sum("angokrasciu_gkp_m")
    pasleptu_duru_staktu_m = 0.0
    for r in rooms:
        for el in (r.get("elementai") or []):
            if (el.get("tipas") or "").lower() == "pasleptos_duris":
                W = (el.get("plotis_mm") or 0) / 1000
                H = (el.get("aukstis_mm") or 0) / 1000
                if W > 0 and H > 0:
                    pasleptu_duru_staktu_m += (2 * H + W) * int(el.get("kiekis") or 1)
    pasleptu_duru_staktu_m = round(pasleptu_duru_staktu_m, 2)
```

Then delete the now-unused import line 1254 (`from extractor.universal_rules import _opening_adds_reveal, _resolve_deduction_standard`) and line 1256 (`deduction_standard = ...`) — they were only used by the removed inline reveal gate. (Verify with grep that `deduction_standard` / `_opening_adds_reveal` are not used elsewhere in the function before deleting.)

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest backend/tests/test_pozicijos_accuracy.py::test_angokrasciai_uses_calibrated_field_not_inline -v`
Expected: PASS.

- [ ] **Step 5: Verify on objektas_a + no regression**

Run: `venv/bin/python3 -c "import json,sys; sys.path.insert(0,'backend'); from extractor.vision_call import _build_pozicijos_from_rooms; a=json.load(open('ground_truth/objektas_a/ai_extract.json')); o=_build_pozicijos_from_rooms({'patalpos':a['patalpos'],'santrauka':{}}); print([p['kiekis'] for p in o['pozicijos'] if 'Angokraščių' in p['aprasymas']])"`
Expected: `[78.05, 78.05]` (was `[138.42, 138.42]`).
Run: `venv/bin/python -m pytest backend/tests/ -q -k "not vision and not api and not integration and not endpoint"` → all pass (re-baseline any test asserting old 138.42).

- [ ] **Step 6: Commit**

```bash
git add backend/extractor/vision_call.py backend/tests/test_pozicijos_accuracy.py
git commit -m "fix(pozicijos): angokraščiai use calibrated field, not inline recompute (RC3)"
```

---

### Task 2: RC1 — Basin count from detected symbols, not toilet count

**Files:**
- Modify: `backend/extractor/vision_call.py:1755-1758`
- Test: `backend/tests/test_pozicijos_accuracy.py`

**Why:** `Praustuvės maišytuvo montavimas` and `Praustuvės montavimas` use `n_wet_with_klozetas` (=2 on objektas_a), chaining basins to toilets. `detected_symbols_summary.praustuves` (=3) is the real basin count. Use `max(n_wet_with_klozetas, sym.praustuves)` so basins decouple from toilets (2→3; contractor 5 — residual is symbol recall).

- [ ] **Step 1: Write the failing test**

```python
def test_basin_count_uses_praustuves_symbol():
    rooms = [_room([], paskirtis="vonia", plotas_m2=5.0),
             _room([], paskirtis="san", plotas_m2=4.0)]
    parsed = _parsed(rooms)
    parsed["detected_symbols_summary"] = {"praustuves": 3}
    out = _build_pozicijos_from_rooms(parsed)
    basin = [p for p in out["pozicijos"] if p["aprasymas"] == "Praustuvės maišytuvo montavimas"]
    assert len(basin) == 1 and basin[0]["kiekis"] == 3, basin  # not 2 (n_wet_with_klozetas)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest backend/tests/test_pozicijos_accuracy.py::test_basin_count_uses_praustuves_symbol -v`
Expected: FAIL (kiekis == 2).

- [ ] **Step 3: Wire the symbol count**

In `backend/extractor/vision_call.py`, immediately before the `if n_wet_with_klozetas > 0:` block (line 1747), add:

```python
        # 2026-06-06 (RC1): basins are not 1-per-wet-room — decouple from toilets.
        _sym = (parsed.get("detected_symbols_summary") or {})
        n_praustuves = max(n_wet_with_klozetas, int(_sym.get("praustuves") or 0))
```

Then change the two basin lines (1755-1758) to use `n_praustuves`:

```python
                {"skyrius": SK_SAN, "aprasymas": "Praustuvės maišytuvo montavimas",
                 "vnt": "vnt", "kiekis": n_praustuves, "saltinis": "paskirtis_default"},
                {"skyrius": SK_SAN, "aprasymas": "Praustuvės montavimas",
                 "vnt": "vnt", "kiekis": n_praustuves, "saltinis": "paskirtis_default"},
```

(Leave WC rėmas / Klozetas on `n_wet_with_klozetas` — those are correctly toilet-driven.)

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest backend/tests/test_pozicijos_accuracy.py::test_basin_count_uses_praustuves_symbol -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/vision_call.py backend/tests/test_pozicijos_accuracy.py
git commit -m "fix(pozicijos): basin count from detected_symbols.praustuves, not toilet count (RC1)"
```

---

### Task 3: RC8 — Emit kampai as ONE line (stop the triple-emission)

**Files:**
- Modify: `backend/extractor/vision_call.py:1234-1250`
- Test: `backend/tests/test_pozicijos_accuracy.py`

**Why:** The app emits the same `kampu_metrai` (501.3 m) THREE times: `Glaistymo kampai vidiniai` (×0.7) + `Glaistymo kampai išoriniai` (×0.3) [= the full total] AND `Dažymo kampų montavimas` (= the full total). If priced, the corner length bills ~2×. Contractor has ONE line (item 19). Collapse to one labour line + one material sub-field. **Does not change `kampu_metrai`.** (The fresh-extraction *value* instability — 325 vs 501 — is a separate Vision-stability issue, Phase 2.)

- [ ] **Step 1: Write the failing test**

```python
def test_kampai_emitted_as_single_line():
    rooms = [_room([], perimetras_m=20.0)]
    out = _build_pozicijos_from_rooms(_parsed(rooms))
    kampai_lines = [p for p in out["pozicijos"] if "kamp" in p["aprasymas"].lower()
                    and p.get("skyrius") == "Sienų lubų glaistymas dažymas"]
    labels = [p["aprasymas"] for p in kampai_lines]
    assert "Glaistymo kampai vidiniai" not in labels, labels
    assert "Glaistymo kampai išoriniai" not in labels, labels
    assert labels.count("Dažymo kampų montavimas") == 1, labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest backend/tests/test_pozicijos_accuracy.py::test_kampai_emitted_as_single_line -v`
Expected: FAIL (vidiniai/išoriniai present).

- [ ] **Step 3: Collapse the triple-emission**

In `backend/extractor/vision_call.py`, replace lines 1234-1250 with:

```python
    kampai_total = _sum("kampu_metrai")
    if kampai_total > 0:
        # 2026-06-06 (RC8): ONE corner line (= contractor item 19 "Dažymo kampų
        # montavimas"). Previously the same metrai were emitted as vidiniai+išoriniai
        # AND as montavimas → double-billable. Outer-corner kampuotės (~30%) as material.
        pozicijos.append({
            "skyrius": SK_GD, "aprasymas": "Dažymo kampų montavimas",
            "vnt": "m", "kiekis": kampai_total, "saltinis": SAL,
            "medziagos_aprasymas": "PVC kampuotės (išoriniai kampai)",
            "medziagos_kiekis": round(kampai_total * 0.3, 2), "medziagos_vnt": "m",
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest backend/tests/test_pozicijos_accuracy.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Full regression sweep**

Run: `venv/bin/python -m pytest backend/tests/ -q -k "not vision and not api and not integration and not endpoint"`
Expected: all pass (re-baseline any test asserting "Glaistymo kampai vidiniai/išoriniai").
Run: `venv/bin/python eval_harness.py --totals-only` → average MAE unchanged (these fixes don't touch scored santrauka totals).

- [ ] **Step 6: Commit**

```bash
git add backend/extractor/vision_call.py backend/tests/test_pozicijos_accuracy.py
git commit -m "fix(pozicijos): emit kampai as one line, stop triple-emission double-count (RC8)"
```

---

## Deferred to Phase 2 (need investigation/data, NOT clean fixes)
- **RC5 kampai run-to-run instability (fresh 325 vs cached 501).** Root cause is Vision extraction variance (perimeters + `wall_adjacency` adjacency bailing → `pusiniai` collapses), not a formula tweak. Removing the legacy `+perim` term *regresses* (verified earlier: it's load-bearing). Needs the adjacency/perimeter extraction stabilized — its own debugging task.
- **RC4 Rotband +59%.** `walls_paint × 0.50` over-scales because `walls_paint` grew (277→441). Correct fix needs a block/concrete-wall-area input the data model doesn't track; interim recalibration risks overfitting one contractor.
- **RC2 symbol-path debug** (skylių gręžimas 4 vs 56 — why `detected_symbols` doesn't reach the branch).
- **RC6 partial-zone splits** (paint/GKP iki-virš-3m binary), **RC7 missing categories** (wall GKP, TRACK, bidė, large-format tile, tile skirting), **RC9 line-level eval**.

---

## Self-Review
- **Spec coverage:** Tasks 1-3 map to RC3, RC1, RC8 from the audit; deferred section names RC2/RC4/RC5/RC6/RC7/RC9. ✓
- **Placeholder scan:** every step has exact code/commands/expected output. ✓
- **Type consistency:** `_sum`, `parsed`, `kampai_total`, `n_praustuves` used consistently; `_sum("angokrasciu_gkp_m")` matches the field name verified to sum 78.05. ✓
- **Numbers verified empirically** (angokraščiai field 78.05, praustuves symbol 3) — tests assert behavior (uses-the-field / uses-the-symbol), not brittle magic constants, so they hold even if a future extract changes the values. ✓
