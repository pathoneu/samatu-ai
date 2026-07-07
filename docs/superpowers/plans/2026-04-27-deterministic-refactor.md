# Sprint B — Deterministic Refactor

> **Goal:** Vision returns ONLY primitives (plotas_m2, perimetras_m, lubu_aukstis_m, elementai, paskirtis). Python computes EVERYTHING ELSE deterministically. Result: 3× same project = bit-identical output.

**Why:** Vision is non-deterministic (Phase 6.5.2: CV 5-22%). Mixing extraction with computation amplifies variance. The math is simple — should be pure Python. Vision should only OCR. (User: "kiekvieną kartą skirtingai" frustration.)

**Tech Stack:** Python 3.11, Anthropic SDK (Opus 4.7), pdfplumber/pdf2image, FastAPI. Same as current.

**Migration policy (B per user):** Old projects in DB stay snapshot. Only NEW extracts go through new pipeline.

---

## Critical Files

- `backend/extractor/prompt.py` — `OUTPUT_SCHEMA` (strip computed fields), `SYSTEM_TEXT` (forbid math)
- `backend/extractor/vision_call.py` — `extract_interior()` Step 3 (`_recompute_santrauka`) → expand to ALWAYS call `calc_room_quantities` from universal_rules
- `backend/extractor/universal_rules.py` — `calc_room_quantities()` and `calc_totals()` are the truth source
- `backend/extractor/lt_rules.py` — sanity warnings (untouched)
- `backend/extractor/eksplikacija_reader.py` — primitives source priority #1 (untouched, just feeds primitives in)

---

## Tasks

### Task B1 — Audit & strip Vision schema

**Files:** `backend/extractor/prompt.py:67-170` (`OUTPUT_SCHEMA.patalpos.items`)

Current `patalpos[].items.properties` has ~30 fields. Bucket them:

**KEEP (primitives Vision OCRs):**
- `nr`, `pavadinimas`, `paskirtis`
- `puslapio_nr`, `bbox_pct` (zoom anchor)
- `plotas_m2`, `plotas_saltinis`, `plotas_m2_raw`, `eksplikacija_row_idx`
- `perimetras_m`, `perimetras_m_raw`
- `lubu_aukstis_m`, `lubu_aukstis_saltinis`, `lubu_aukstis_m_raw`
- `lubu_tipas`
- `elementai[]` (langai/durys/nišos with mm dimensions)
- `confidence`, `pastabos`

**STRIP (computed by Python from primitives):**
- `dazymo_plotas_m2`, `dazymo_plotas_gross_m2` ❌
- `deductions[]` ❌
- `kampu_metrai`, `angokrasciu_gkp_m`, `pasleptu_duru_staktu_m`, `nisu_metrai` ❌
- `pvc_grindys_m2`, `plyteles_grindys_m2`, `plyteles_sienos_m2`, `plyteles_sienos_aukstis_m` ❌
- `isliginamasis_m2`, `grindjuosciu_m`, `hidroizoliacija_m2` ❌
- `calculation_trace` ❌ (Python regenerates)

Top-level: keep `archetipas`, `bendras_plotas_m2`, `puslapiai[]`, `patalpos[]`, `pastabos`, `warnings[]`, `_eksplikacija`. **DROP `santrauka` and `pozicijos`** from Vision output — Python rebuilds them from per-room calc.

`required` lists: trim to keep only required primitives. `additionalProperties: False` ensures Vision can't sneak in computed fields.

### Task B2 — Update prompt text

**Files:** `backend/extractor/prompt.py` (`SYSTEM_TEXT` and user-content prompt section ~line 770-810)

Add a clear directive at top of system prompt:

```
**KRITIŠKAI SVARBU — TU NESKAIČIUOJI, TU SKAITAI:**

Tu esi OCR + spatial parser, ne kalkuliatorius.
- Tu PERSKAITAI iš brėžinio: patalpos pavadinimas, plotas (iš eksplikacijos), perimetras, lubų aukštis, langai/durys mm.
- Tu NESKAIČIUOJI: dažomo ploto, glaisto kg, plytelių zonų, GK lapų, grindjuosčių, hidroizoliacijos.
- Šitas matematika daroma DETERMINISTIŠKAI Python kodu po tavęs.
- Tavo darbas: GAUTI TIKSLIUS PRIMITYVUS. Visa kita — ne tavo problema.
```

Strip current sections that ask Vision to compute. The user-facing prompt around `bbox_pct` and per-room CO2 stays. Eksplikacija + schedule sections stay (those are primitive sources).

### Task B3 — Wire Python math as single source of truth

**Files:** `backend/extractor/vision_call.py` (lines ~492-520, post-parse step)

Current flow:
```
parse JSON → eksplikacija merge → schedule anchor → zoom pass
→ _recompute_santrauka(parsed)  # uses Vision per-room values
→ apply_lt_sanity → emit_v8_compat
```

New flow:
```
parse JSON → eksplikacija merge → schedule anchor → zoom pass
→ _recompute_per_room_via_python(parsed)   # NEW: calc_room_quantities for every patalpa
→ _recompute_santrauka(parsed)             # Now sums Python-computed values
→ apply_lt_sanity → emit_v8_compat
```

Implement `_recompute_per_room_via_python`:
```python
from .universal_rules import calc_room_quantities, translate_user_prefs_to_room_rules
def _recompute_per_room_via_python(parsed: dict, rules_override: dict | None) -> dict:
    rules = translate_user_prefs_to_room_rules(rules_override or {})
    for room in parsed.get("patalpos", []):
        # primitives flow in: plotas_m2, perimetras_m, lubu_aukstis_m, elementai
        # calc adds: dazymo_plotas_m2, kampu_metrai, plyteles_*, grindjuostes_m, etc.
        recomputed = calc_room_quantities(room, rules=rules)
        # Merge — keep primitives, override computed
        room.update(recomputed)
        # Add audit field showing this came from Python
        room["_computed_by"] = "python_deterministic"
    return parsed
```

`calc_room_quantities` already exists in universal_rules.py. It takes a room dict and rules, returns computed values.

### Task B4 — Audit & strengthen universal_rules formulas

**Files:** `backend/extractor/universal_rules.py:205-330` (`calc_room_quantities`)

Verify against CLAUDE.md §1 formulas:
1. Sienų dažomas plotas: `perim × H − Σ(angos > 0.5m²) + lubos`
2. Angokraščiai: `(2H + W) × sienos_storis` per opening
3. Grindjuostės: `perim − Σ(durų pločių) + 10%`
4. Lubų karnizas: `perim + 5%` (no door deduction)
5. GK lapai: `⌈sienų_plotas / 3.0⌉ × 1.10`
6. Plytelės sienose: `tiled_wall_length × tile_height`
7. Hidroizoliacija (vonia): `floor_area + perim × 0.30 + dušas`
8. Glaistas: `area × storis_mm × Q_koef`

**If any formula missing or simplified — add it now.** Apply findings from research subagent (Task #50) when it lands.

### Task B5 — Determinism validation

**Files:** `backend/tests/test_deterministic.py` (NEW)

Two-tier test:

**Tier 1 — pure-math determinism (no API call):**
```python
def test_calc_room_quantities_deterministic():
    room = {"plotas_m2": 6.45, "perimetras_m": 10.30, "lubu_aukstis_m": 2.65,
            "paskirtis": "vonia", "elementai": [{"tipas": "duris", "plotis_mm": 700, "aukstis_mm": 2000, "kiekis": 1}]}
    a = calc_room_quantities(room)
    b = calc_room_quantities(room)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
```

**Tier 2 — full pipeline with mocked Vision:**
```python
def test_extract_interior_deterministic_with_mocked_vision():
    # Stub anthropic client to return fixed primitives
    # Run extract_interior 3× → assert santrauka identical
```

Run after every change. Block merge if not green.

### Task B6 — Live validation against P1

After tests pass, restart backend and run real extract on P1 (when user authorizes credit spend). Capture santrauka. Re-run. Compare. Should be identical (modulo Vision input variance — same primitives → same computed totals).

---

## Verification Plan

1. **Unit-level (Tier 1):** `pytest backend/tests/test_deterministic.py::test_calc_room_quantities_deterministic`
2. **Pipeline-level (Tier 2):** mocked-Vision extract 3× → bit-identical
3. **Integration:** real Vision call on P1 → compare santrauka to ground truth (Rangovas, when applicable)
4. **No-regression:** existing P1 project re-extracted under new code → spot-check 5 random kambariai's dazymo_plotas. Should differ from old value (because Python now does math) but should be deterministic across runs.

---

## Out of Scope (future sprints)

- pdfplumber primitive override layer (Sprint A — after B is shipped + user-tested)
- Single-canvas UI default (UI consolidation sprint, deferred per user)
- Edit cascade wiring (depends on this — recompute-interior already calls calc_room_quantities, just needs frontend trigger)

---

## Risk Mitigation

- **Schema change breaks frontend:** the v8_compat emit step (`_emit_v8_compat_fields`) maps internal schema → frontend-expected fields. Keep that intact, just feed it Python-computed values. Frontend won't notice.
- **Per-paskirtis defaults differ from old Vision intuition:** universal_rules has the defaults. If any rule produces nonsense (e.g., garage walls painted), the LT sanity check catches it. Add new check if needed.
- **calc_room_quantities crashes on missing primitives:** ensure it has safe defaults for missing perimeter (skip dazymo, mark confidence:low) and missing ceiling height (use paskirtis-based default).
