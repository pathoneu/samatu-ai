# Interior-Finishing Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the accuracy, trust, and compounding-learning of the interior-finishing (vidaus apdaila) pipeline by closing concrete gaps surfaced in the 2026-06-30 takeoff-research scan — without touching electrical/sanitary scope.

**Architecture:** Additive. Every Phase-1–3 change is a new pure module or a new function registered into an existing dispatcher (`sanity_checks._ALL_CHECKS`, `scale_validator`, `db._init`/`_migrate_schema`, `vision_call._build_pozicijos_from_rooms`). No existing accuracy-bearing formula is rewritten. Confidence demotion and "learned rules" only *flag and surface* — they never silently mutate a `kiekis`. The current numbers stay reproducible; new signal is layered on top.

**Tech Stack:** Python 3 / FastAPI / pytest (backend), React + Vite + Zustand (frontend), SQLite (`backend/db.py`), Anthropic Claude (vision + price-suggestion). Tests import `from extractor.X import ...`; `backend/conftest.py` puts `backend/` on `sys.path`, so run from `backend/`.

---

## How this plan is organized

The research produced ~15 candidate improvements across four tiers plus two net-new items. They are **not** one subsystem, so per the writing-plans scope rule this plan is layered by execution-readiness:

| Phase | Theme | Status |
|-------|-------|--------|
| **Phase 1** | Trust & correctness quick-wins (units, magnitude guard, reconciliation, reference-object scale) | **Execution-ready — full TDD** |
| **Phase 2** | Measurement-expression transparency (item B) | **Execution-ready — full TDD** |
| **Phase 3** | Learned-rule store (item A — the compounding moat) | **Execution-ready — full TDD** |
| **Phase 4** | Pricing intelligence (pricebook + LLM suggestion + composite recipes) | Concrete spec; pricebook table is full TDD, the rest specified |
| **Phase 5** | Geometry & routing (vector/raster routing, linear topology, legend-first confidence, gap-band heal→opening) | Concrete spec — **each needs its own dedicated plan before execution** |
| **Phase 6** | Large subsystems (declarative metric config, agentic/RAG, Bluebeam import/export, version compare, void-relation model) | Concrete spec — **each is its own multi-week project; do NOT execute from this doc** |

Execute Phases 1→3 in order; they are independent of 4–6 and each leaves the app green. Stop and write a dedicated plan before starting any Phase-5/6 item.

**Sequencing rationale (highest leverage first):** Phase 1 catches the worst-class errors (10×/decimal slips) for almost no code; Phase 2 makes every number defensible to a skeptical estimator (directly serves CLAUDE.md "every calculation must show its assumptions"); Phase 3 is the only change that *compounds* — corrections start improving future extractions instead of dying in an audit table.

---

## File Structure

**New files (Phases 1–3):**
- `backend/extractor/units.py` — single source of truth for mm/cm/m → m. Replaces the scattered `_to_metres` / `_opening_dims` ad-hoc conversions.
- `backend/extractor/matavimai.py` — pure builder of human-readable measurement expressions per room ("perim 18.0 m × h 2.7 m − angos 1.8 m² = 46.8 m²").
- `backend/extractor/learned_rules.py` — pure aggregation of the `corrections` audit log into apply-able rules (class-bias / override-frequency), plus the gated `apply_learned_rules`.
- `backend/tests/test_units.py`, `test_quantity_magnitude.py`, `test_scale_reference_objects.py`, `test_matavimai.py`, `test_learned_rules.py`, `test_learned_rules_db.py` — one test file per new unit.

**Modified files (Phases 1–3):**
- `backend/extractor/sanity_checks.py` — add `check_quantity_magnitude` + `check_putty_consumption`; register both in `_ALL_CHECKS`.
- `backend/extractor/scale_validator.py` — add `REFERENCE_OBJECTS`, `validate_scale_by_reference_objects`, `solve_px_per_m_from_references`.
- `backend/extractor/vision_call.py` — call `matavimai.build_room_expressions` while assembling room aggregates; attach `_matavimai` to contributing pozicijos.
- `backend/db.py` — add `learned_rules` table to `_init`, append-only `_migrate_schema` guard, `upsert_learned_rule` / `get_learned_rules` helpers.
- `backend/extractor/confidence.py` — call `apply_learned_rules` (flag-gated) after the static `CLASS_RULES` pass.
- `frontend/src/components/project/ProjectMainView.jsx` — render the `matavimai` expression in the line-item detail.

**Each new backend unit is a pure function tested in isolation** before it is wired into the big dispatchers — that is what keeps the TDD steps small and the existing pipeline untouched until the last wiring step.

---

# PHASE 1 — Trust & correctness quick-wins

## Task 1.1: Centralized units normalizer

**Why:** mm/cm/m conversion is currently re-implemented in `height_markers._to_metres`, `line_items._opening_dims`, etc. Divergence here is a silent class of magnitude bugs. One tested module removes the duplication and gives Phase-1.2 a trustworthy primitive.

**Files:**
- Create: `backend/extractor/units.py`
- Test: `backend/tests/test_units.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_units.py
import math
import pytest
from extractor.units import to_metres, pick_length_m


def test_to_metres_explicit_units():
    assert to_metres(2400, "mm") == pytest.approx(2.4)
    assert to_metres(240, "cm") == pytest.approx(2.4)
    assert to_metres(2.4, "m") == pytest.approx(2.4)
    # Lithuanian unit words and case/whitespace are tolerated
    assert to_metres(900, " MM ") == pytest.approx(0.9)
    assert to_metres(90, "centimetras") == pytest.approx(0.9)


def test_to_metres_bad_input_returns_none():
    assert to_metres(None, "mm") is None
    assert to_metres("abc", "mm") is None
    assert to_metres(100, "furlong") is None


def test_pick_length_m_prefers_metre_field_then_mm():
    # explicit *_m wins
    assert pick_length_m({"plotis_m": 0.9, "plotis_mm": 5}, "plotis") == pytest.approx(0.9)
    # falls back to *_mm / 1000
    assert pick_length_m({"plotis_mm": 900}, "plotis") == pytest.approx(0.9)
    # English alias field name
    assert pick_length_m({"width_mm": 900}, "width") == pytest.approx(0.9)
    # nothing usable
    assert pick_length_m({"foo": 1}, "plotis") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_units.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'extractor.units'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/extractor/units.py
"""Single source of truth for length-unit normalization in the extractor.

Vision returns dimensions in mixed units across fields/projects (mm, cm, m).
Previously each call site re-implemented the conversion (height_markers._to_metres,
line_items._opening_dims, ...). Consolidate here so a unit bug is fixed once.
"""
from __future__ import annotations

_M_PER_UNIT = {
    "m": 1.0, "metre": 1.0, "metras": 1.0, "metrai": 1.0,
    "cm": 0.01, "centimetras": 0.01, "centimetrai": 0.01,
    "mm": 0.001, "milimetras": 0.001, "milimetrai": 0.001,
}


def to_metres(value, unit: str = "m"):
    """Convert an explicit (value, unit) pair to metres. None on bad input."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    factor = _M_PER_UNIT.get((unit or "m").strip().lower())
    if factor is None:
        return None
    return v * factor


def pick_length_m(d: dict, *names: str):
    """Read a length from a dict that may store it as `<name>_m` or `<name>_mm`.

    Tries each name in order; for each, prefers the metre field, then the mm
    field (÷1000). Returns metres, or None when no recognized field is present.
    """
    for name in names:
        if d.get(f"{name}_m") is not None:
            m = to_metres(d.get(f"{name}_m"), "m")
            if m is not None:
                return m
        if d.get(f"{name}_mm") is not None:
            m = to_metres(d.get(f"{name}_mm"), "mm")
            if m is not None:
                return m
        if d.get(f"{name}_cm") is not None:
            m = to_metres(d.get(f"{name}_cm"), "cm")
            if m is not None:
                return m
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_units.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/units.py backend/tests/test_units.py
git commit -m "feat(extractor): centralized units normalizer (mm/cm/m → m)"
```

> **Note (deliberately deferred):** wholesale migration of `height_markers._to_metres` and `line_items._opening_dims` to call `units` is intentionally NOT in this task — it would touch accuracy-bearing code with no behavior change to show for it. Do it opportunistically when next editing those files, with their existing tests as the regression guard. This task only lands the trustworthy primitive that Task 1.2 depends on.

---

## Task 1.2: Magnitude / decimal-slip sanity check

**Why:** The single worst extraction failure is an order-of-magnitude error (a `mm²` read as `m²`, a `×1000` slip, a misplaced decimal). None of the six existing checks catch it. The bands below are generous — a normal interior project never trips them — but a 10×+ slip lights up red.

**Files:**
- Modify: `backend/extractor/sanity_checks.py` (add function after `check_window_reveals`, register in `_ALL_CHECKS`)
- Test: `backend/tests/test_quantity_magnitude.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_quantity_magnitude.py
from extractor.sanity_checks import check_quantity_magnitude, run_all_checks


def _vr(floor_m2, pozicijos):
    return {"patalpos": [{"plotas_m2": floor_m2}], "pozicijos": pozicijos}


def test_normal_project_passes():
    vr = _vr(100, [
        {"aprasymas": "Sienų dažymas", "vnt": "m2", "kiekis": 320},   # 3.2× floor — fine
        {"aprasymas": "Grindjuostės", "vnt": "m", "kiekis": 180},      # 1.8× floor — fine
        {"aprasymas": "Dažai", "vnt": "l", "kiekis": 70},              # 0.7 l/m² floor — fine
    ])
    assert check_quantity_magnitude([{"plotas_m2": 100}], vr) == []


def test_area_decimal_slip_flagged():
    # 320 m² mistakenly ×1000 → 320000 on a 100 m² project
    vr = _vr(100, [{"aprasymas": "Sienų dažymas", "vnt": "m2", "kiekis": 320000}])
    warns = check_quantity_magnitude([{"plotas_m2": 100}], vr)
    assert len(warns) == 1
    assert warns[0].code == "quantity_magnitude"
    assert warns[0].severity == "high"
    assert "Sienų dažymas" in warns[0].message


def test_litres_slip_flagged():
    vr = _vr(100, [{"aprasymas": "Dažai", "vnt": "l", "kiekis": 5000}])  # 50 l/m² floor
    warns = check_quantity_magnitude([{"plotas_m2": 100}], vr)
    assert len(warns) == 1
    assert warns[0].code == "quantity_magnitude"


def test_no_floor_area_is_noop():
    vr = _vr(0, [{"aprasymas": "X", "vnt": "m2", "kiekis": 999999}])
    assert check_quantity_magnitude([{"plotas_m2": 0}], vr) == []


def test_registered_in_run_all_checks():
    vr = _vr(100, [{"aprasymas": "Sienų dažymas", "vnt": "m2", "kiekis": 320000}])
    out = run_all_checks(vr)
    assert any(w["code"] == "quantity_magnitude" for w in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_quantity_magnitude.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_quantity_magnitude'`

- [ ] **Step 3: Write minimal implementation**

Add after `check_window_reveals` (around line 215), and add to `_ALL_CHECKS`:

```python
# Per-unit plausibility ceilings, expressed as a multiple of total floor area.
# Generous on purpose: real interior projects sit well under these. Crossing
# one means an order-of-magnitude error, not "a big project".
_MAGNITUDE_CEILINGS = {
    "m2": 12.0,   # paintable walls ~4× + ceiling ~1× + tiles/floors → ~8× realistic
    "m": 8.0,     # baseboard + cornice + reveals + corners
    "l": 2.0,     # paint+primer litres per m² of FLOOR
    "kg": 40.0,   # putty/adhesive kg per m² of FLOOR
}


def check_quantity_magnitude(rooms, vision_result=None):
    """Magnitude / decimal-slip guard: flags the FIRST pozicija whose kiekis
    exceeds a generous per-unit multiple of total floor area. Catches ×10/×100/
    ×1000 errors and stray-decimal mistakes that the ratio checks miss.

    Returns a single Warning (the worst offender) or None.
    """
    floor = _sum_field(rooms, "plotas_m2")
    if floor < 1:
        return None
    pozicijos = (vision_result or {}).get("pozicijos") or []
    worst = None
    worst_ratio = 0.0
    for p in pozicijos:
        vnt = (p.get("vnt") or "").strip().lower()
        ceiling = _MAGNITUDE_CEILINGS.get(vnt)
        if ceiling is None:
            continue
        try:
            kiekis = float(p.get("kiekis") or 0)
        except (TypeError, ValueError):
            continue
        if kiekis <= 0:
            continue
        ratio = kiekis / (floor * ceiling)
        if ratio > 1.0 and ratio > worst_ratio:
            worst_ratio = ratio
            worst = (p, vnt, kiekis, ceiling)
    if worst is None:
        return None
    p, vnt, kiekis, ceiling = worst
    return Warning(
        code="quantity_magnitude",
        message=(f"„{p.get('aprasymas', '?')}“ = {kiekis:g} {vnt} — "
                 f"{kiekis / floor:.0f}× grindų ploto ({floor:.0f} m²)"),
        hint=("Tikėtina dešimtainio kablelio / mato vieneto klaida (pvz. mm² kaip m², "
              "arba ×1000). Patikrink šios eilutės kiekį."),
        severity="high",
        expected=f"≤ {ceiling:g}× grindų ploto",
        actual=f"{kiekis / floor:.0f}×",
    )
```

Then extend `_ALL_CHECKS`:

```python
_ALL_CHECKS = [
    check_paintable_wall_to_floor,
    check_ceiling_to_floor,
    check_baseboard_perimeter,
    check_paint_quantity,
    check_gk_sheets_math,
    check_window_reveals,
    check_quantity_magnitude,
]
```

And in `run_all_checks`, route the pozicijos-needing checks (it already special-cases `check_gk_sheets_math`):

```python
            if check_fn in (check_gk_sheets_math, check_quantity_magnitude):
                w = check_fn(rooms, vision_result)
            else:
                w = check_fn(rooms)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_quantity_magnitude.py tests/test_sanity_checks.py -v`
Expected: PASS (new file + existing sanity tests still green)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/sanity_checks.py backend/tests/test_quantity_magnitude.py
git commit -m "feat(sanity): magnitude/decimal-slip guard on pozicijos"
```

---

## Task 1.3: Putty-consumption reconciliation check

**Why:** Material-vs-work cross-checks are the cheapest way to catch a `medziagos_kiekis` that drifted from its work area. `check_paint_quantity` already does this for paint; glaistas (putty) is the next-biggest material line and has a tight kg/m² band across Q1–Q4 (0.8–1.5 kg/m²/mm × 0.5–3 mm thickness → ~0.4–4.5 kg/m²).

**Files:**
- Modify: `backend/extractor/sanity_checks.py`
- Test: `backend/tests/test_putty_consumption.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_putty_consumption.py
from extractor.sanity_checks import check_putty_consumption


def test_in_band_passes():
    # 200 kg putty over 100 m² glaistymas = 2.0 kg/m² — within Q1..Q4
    rooms = [{"glaistas_kg": 200, "walls_paintable_m2": 80, "ceiling_paintable_m2": 20}]
    assert check_putty_consumption(rooms) is None


def test_too_high_flagged():
    rooms = [{"glaistas_kg": 900, "walls_paintable_m2": 80, "ceiling_paintable_m2": 20}]  # 9 kg/m²
    w = check_putty_consumption(rooms)
    assert w is not None
    assert w.code == "putty_consumption_rate"


def test_no_putty_is_noop():
    rooms = [{"glaistas_kg": 0, "walls_paintable_m2": 80}]
    assert check_putty_consumption(rooms) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_putty_consumption.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_putty_consumption'`

- [ ] **Step 3: Write minimal implementation**

Add after `check_quantity_magnitude`, register in `_ALL_CHECKS` (rooms-only signature, so no `run_all_checks` change needed):

```python
def check_putty_consumption(rooms):
    """Reconciliation: glaistas kg per m² of glaistymas area must sit in the
    Q1..Q4 band (~0.4–4.5 kg/m²). Catches a putty material qty that drifted
    from its work area."""
    putty_kg = _sum_field(rooms, "glaistas_kg")
    area = (_sum_field(rooms, "walls_paintable_m2")
            + _sum_field(rooms, "ceiling_paintable_m2"))
    if putty_kg < 1 or area < 1:
        return None
    rate = putty_kg / area
    if 0.4 <= rate <= 4.5:
        return None
    return Warning(
        code="putty_consumption_rate",
        message=f"Glaisto sąnaudos {rate:.2f} kg/m² ({putty_kg:.0f} kg / {area:.0f} m²)",
        hint=("Turi būti ~0.4–4.5 kg/m² (Q1 plonas → Q4 storas). Patikrink glaisto "
              "kiekį arba Q lygį."),
        severity="low",
        expected="0.4-4.5 kg/m²",
        actual=f"{rate:.2f} kg/m²",
    )
```

Add to `_ALL_CHECKS` (before `check_quantity_magnitude`):

```python
    check_window_reveals,
    check_putty_consumption,
    check_quantity_magnitude,
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_putty_consumption.py tests/test_sanity_checks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/sanity_checks.py backend/tests/test_putty_consumption.py
git commit -m "feat(sanity): putty kg/m² reconciliation check"
```

---

## Task 1.4: Reference-object scale back-solve

**Why:** `scale_validator.validate_scale_by_doors` already cross-checks scale against doors as a 0.9 m ruler — but (a) it only uses doors, and (b) it only *validates*, it can't *set* scale when the title block has no `M 1:xx`. Generalize to a small library of standard LT objects and add a back-solver that returns a `px_per_m` estimate so a scale-less drawing is still measurable.

**Files:**
- Modify: `backend/extractor/scale_validator.py`
- Test: `backend/tests/test_scale_reference_objects.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scale_reference_objects.py
import pytest
from extractor.scale_validator import (
    REFERENCE_OBJECTS,
    validate_scale_by_reference_objects,
    solve_px_per_m_from_references,
)


def test_reference_library_has_core_objects():
    assert "durys" in REFERENCE_OBJECTS
    assert REFERENCE_OBJECTS["durys"] == pytest.approx(0.9)
    assert "unitazas" in REFERENCE_OBJECTS   # toilet bowl length ~0.7 m
    assert "vonia" in REFERENCE_OBJECTS      # bathtub ~1.7 m


def test_validate_multi_object_green():
    # at 100 px/m: a 0.9 m door = 90 px, a 0.7 m toilet = 70 px
    dets = [
        {"type": "durys", "pixel_size": 90},
        {"type": "unitazas", "pixel_size": 70},
    ]
    r = validate_scale_by_reference_objects(dets, claimed_px_per_m=100.0)
    assert r.valid is True
    assert r.severity == "green"


def test_validate_multi_object_red_on_4x():
    dets = [{"type": "durys", "pixel_size": 360}]  # implies 3.6 m door @ 100 px/m
    r = validate_scale_by_reference_objects(dets, claimed_px_per_m=100.0)
    assert r.valid is False
    assert r.severity == "red"


def test_back_solve_returns_px_per_m():
    dets = [
        {"type": "durys", "pixel_size": 90},     # 90 / 0.9 = 100
        {"type": "unitazas", "pixel_size": 70},  # 70 / 0.7 = 100
    ]
    px_per_m = solve_px_per_m_from_references(dets)
    assert px_per_m == pytest.approx(100.0, rel=0.02)


def test_back_solve_none_without_known_objects():
    assert solve_px_per_m_from_references([{"type": "spinta", "pixel_size": 200}]) is None
    assert solve_px_per_m_from_references([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scale_reference_objects.py -v`
Expected: FAIL — `ImportError: cannot import name 'REFERENCE_OBJECTS'`

- [ ] **Step 3: Write minimal implementation**

Append to `scale_validator.py`:

```python
# Standard LT interior reference objects, longest plan dimension in metres.
# Used as "rulers" when a drawing lacks a parseable M 1:xx title block.
REFERENCE_OBJECTS = {
    "durys": 0.9,       # interior door leaf
    "unitazas": 0.7,    # toilet bowl length
    "vonia": 1.7,       # standard bathtub length
    "dušas": 0.9,       # shower tray side
    "praustuvas": 0.6,  # washbasin width
}


def validate_scale_by_reference_objects(
    detections: list[dict],
    claimed_px_per_m: float,
) -> ScaleValidationResult:
    """Generalized door-ruler check across multiple known objects.

    `detections`: list of {"type": <key in REFERENCE_OBJECTS>, "pixel_size": px}.
    Computes the implied scale factor for each known object and aggregates by
    median, so one mis-detection can't swing the verdict.
    """
    factors = []
    for d in detections:
        real_m = REFERENCE_OBJECTS.get((d.get("type") or "").strip().lower())
        px = d.get("pixel_size")
        if real_m and px and claimed_px_per_m > 0:
            implied_m = float(px) / claimed_px_per_m
            factors.append(implied_m / real_m)
    if not factors:
        return ScaleValidationResult(
            valid=False, severity="yellow", factor=None,
            message="No reference objects available — scale cannot be cross-checked.",
        )
    factor = median(factors)
    if 0.85 <= factor <= 1.15:
        return ScaleValidationResult(
            valid=True, severity="green", factor=factor,
            message=f"Scale matches {len(factors)} reference object(s) (factor {factor:.2f}).",
        )
    severity = "red" if (factor < 0.5 or factor > 2.0) else "yellow"
    return ScaleValidationResult(
        valid=False, severity=severity, factor=factor,
        message=(f"Scale mismatch across {len(factors)} reference object(s): "
                 f"factor {factor:.2f}. Patikrink mastelį."),
    )


def solve_px_per_m_from_references(detections: list[dict]) -> float | None:
    """Back-solve pixels-per-metre from detected reference objects when no
    title-block scale exists. Returns the median px/m, or None if no detection
    matches a known object."""
    estimates = []
    for d in detections:
        real_m = REFERENCE_OBJECTS.get((d.get("type") or "").strip().lower())
        px = d.get("pixel_size")
        if real_m and px and real_m > 0:
            estimates.append(float(px) / real_m)
    if not estimates:
        return None
    return median(estimates)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_scale_reference_objects.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/scale_validator.py backend/tests/test_scale_reference_objects.py
git commit -m "feat(scale): reference-object scale validation + back-solve"
```

> **Wiring note:** routing detected fixture pixel-sizes into `solve_px_per_m_from_references` requires the Vision pass to emit `pixel_size` for sanitary fixtures — that is a Vision-prompt change tracked separately (same dormancy as `validate_scale`'s `diagonal_px`). This task lands the tested math so the wiring is a one-line call when those detections exist.

---

# PHASE 2 — Measurement-expression transparency (item B)

**Goal:** every quantity shows the arithmetic that produced it, the way Bluebeam/CostX show a "measurement" behind each takeoff number. Directly serves CLAUDE.md: *"Every calculation must show its assumptions to the user."*

## Task 2.1: Pure per-room measurement-expression builder

**Files:**
- Create: `backend/extractor/matavimai.py`
- Test: `backend/tests/test_matavimai.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_matavimai.py
from extractor.matavimai import build_room_expressions


def test_paintable_walls_expression():
    room = {
        "pavadinimas": "Svetainė",
        "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.7,
        "walls_paintable_m2": 46.8,
        "elementai": [{"type": "durys", "plotis_m": 0.9, "aukstis_m": 2.0}],
    }
    exprs = build_room_expressions(room)
    assert "dazomos_sienos" in exprs
    # perimeter × height − openings = area
    assert "18.0" in exprs["dazomos_sienos"]
    assert "2.7" in exprs["dazomos_sienos"]
    assert "46.8" in exprs["dazomos_sienos"]
    assert "=" in exprs["dazomos_sienos"]


def test_ceiling_expression_uses_floor_area():
    room = {"pavadinimas": "WC", "plotas_m2": 4.2, "ceiling_paintable_m2": 4.2}
    exprs = build_room_expressions(room)
    assert "lubos" in exprs
    assert "4.2" in exprs["lubos"]


def test_missing_fields_skipped_not_crashed():
    exprs = build_room_expressions({"pavadinimas": "X"})
    assert isinstance(exprs, dict)
    assert "dazomos_sienos" not in exprs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_matavimai.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'extractor.matavimai'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/extractor/matavimai.py
"""Human-readable measurement expressions per room.

Each derived quantity gets a one-line expression showing the arithmetic that
produced it, e.g. "perim 18.0 m × h 2.7 m − angos 1.8 m² = 46.8 m²". Pure and
side-effect free; the caller attaches the strings to rooms/pozicijos.
"""
from __future__ import annotations


def _n(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _openings_area_m2(room: dict) -> float:
    total = 0.0
    for e in (room.get("elementai") or []):
        w = _n(e.get("plotis_m"))
        if w is None and e.get("plotis_mm") is not None:
            w = (_n(e.get("plotis_mm")) or 0) / 1000.0
        h = _n(e.get("aukstis_m"))
        if h is None and e.get("aukstis_mm") is not None:
            h = (_n(e.get("aukstis_mm")) or 0) / 1000.0
        kiekis = _n(e.get("kiekis")) or 1
        if w and h:
            total += w * h * kiekis
    return round(total, 2)


def build_room_expressions(room: dict) -> dict:
    """Return {quantity_key: 'expression string'} for a single room."""
    exprs: dict[str, str] = {}

    perim = _n(room.get("perimetras_m"))
    h = _n(room.get("lubu_aukstis_m"))
    walls = _n(room.get("walls_paintable_m2"))
    if perim and h and walls is not None:
        angos = _openings_area_m2(room)
        if angos > 0:
            exprs["dazomos_sienos"] = (
                f"perim {perim:.1f} m × h {h:.2f} m − angos {angos:.1f} m² = {walls:.1f} m²"
            )
        else:
            exprs["dazomos_sienos"] = f"perim {perim:.1f} m × h {h:.2f} m = {walls:.1f} m²"

    ceiling = _n(room.get("ceiling_paintable_m2"))
    floor = _n(room.get("plotas_m2"))
    if ceiling is not None and floor is not None:
        exprs["lubos"] = f"grindų plotas {floor:.1f} m² = lubos {ceiling:.1f} m²"

    grind = _n((room.get("derived") or room).get("grindjuostes_m"))
    if grind is not None and perim:
        exprs["grindjuostes"] = f"perim {perim:.1f} m − durų pločiai = {grind:.1f} m"

    return exprs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_matavimai.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/matavimai.py backend/tests/test_matavimai.py
git commit -m "feat(extractor): per-room measurement-expression builder"
```

---

## Task 2.2: Attach expressions to room aggregates in the pipeline

**Files:**
- Modify: `backend/extractor/vision_call.py` (`_build_pozicijos_from_rooms`, near line 1093 where `rooms` is read)
- Test: `backend/tests/test_confidence.py` already builds pozicijos via `_build_pozicijos_from_rooms`; add a focused assertion in a new test file to avoid disturbing it.
- Test: `backend/tests/test_matavimai_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_matavimai_wiring.py
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _room(**kw):
    r = {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
         "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
         "elementai": [{"type": "durys", "plotis_mm": 900, "aukstis_mm": 2000}]}
    r.update(kw)
    return r


def test_rooms_get_matavimai_attached():
    rooms = [_room()]
    for r in rooms:
        r.update(calc_room_quantities(r))
    parsed = {"patalpos": rooms, "santrauka": {}}
    out = _build_pozicijos_from_rooms(parsed)
    # the room now carries a _matavimai dict
    assert "_matavimai" in out["patalpos"][0]
    assert "dazomos_sienos" in out["patalpos"][0]["_matavimai"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_matavimai_wiring.py -v`
Expected: FAIL — `KeyError: '_matavimai'`

- [ ] **Step 3: Write minimal implementation**

In `vision_call.py`, add the import near the other `extractor` imports at the top of the module:

```python
from extractor.matavimai import build_room_expressions
```

Then in `_build_pozicijos_from_rooms`, immediately after `rooms = parsed.get("patalpos") or []` and the empty guard (around line 1096), attach expressions:

```python
    # Transparency: attach a per-room measurement expression dict so the UI can
    # show the arithmetic behind each quantity (item B, 2026-06-30).
    for r in rooms:
        try:
            r["_matavimai"] = build_room_expressions(r)
        except Exception:
            r["_matavimai"] = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_matavimai_wiring.py tests/test_confidence.py -v`
Expected: PASS (new test + existing confidence tests still green)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/vision_call.py backend/tests/test_matavimai_wiring.py
git commit -m "feat(extractor): attach per-room measurement expressions to output"
```

---

## Task 2.3: Render the measurement expression in the line-item UI (concrete spec)

> **Status: concrete spec.** UI work needs a running browser to verify (per CLAUDE.md "for UI changes, open a browser") — keep it a small follow-up rather than a blind code paste.

**Files:** `frontend/src/components/project/ProjectMainView.jsx` (line-item detail, near the qty/price inputs at lines ~87–160).

**Approach:**
- The room objects in the project payload now carry `_matavimai`. Surface the relevant string under the line description as muted helper text, or in a popover on a small `ⓘ` affordance next to the `kiekis` cell (matches the existing provenance-popover pattern from Phase C-2).
- Map pozicija → expression by `skyrius`/`aprasymas` keyword (e.g. "dažymas" rows → `dazomos_sienos`, "lubų" rows → `lubos`, "grindjuostės" → `grindjuostes`). For aggregate lines spanning multiple rooms, show "Σ N patalpų" and list each room's expression in the popover.
- Lithuanian label: **"Matavimas"**. Example rendered: `Matavimas: perim 18.0 m × h 2.7 m − angos 1.8 m² = 46.8 m²`.

**Test strategy:** Vite component render test if one exists for `ProjectMainView`; otherwise manual browser verification on the contractor fixture (Objektas A) — confirm a paint row shows its expression and the numbers match the displayed `kiekis`. Document the screenshot check in the commit message.

---

# PHASE 3 — Learned-rule store (item A: the compounding moat)

**Goal:** stop letting corrections die in an audit table. Aggregate them into rules that *demote confidence* (and later *suggest values*) for classes the user repeatedly overrides — so the app gets measurably better the more it's used. This is the highest strategic-value item in the research: it converts every correction into compounding accuracy.

**Guardrail (non-negotiable):** learned rules NEVER silently rewrite a `kiekis`. They only (a) lower a line's confidence and (b) attach a `_confidence_reason` referencing the user's own history. A future opt-in "apply suggestion" button is Phase-4 territory. This keeps the change reversible and honest (CLAUDE.md: "Honest disclosure beats clever fixes").

## Task 3.1: `learned_rules` table + DB helpers

**Files:**
- Modify: `backend/db.py` (add table to `_init` schema block ending ~line 134; add `_migrate_schema` guard ~line 542; add helpers near `corrections_summary` ~line 539)
- Test: `backend/tests/test_learned_rules_db.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_learned_rules_db.py
import importlib
import db as dbmod


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path / "t.db"))
    importlib.reload(dbmod)
    dbmod.init_db()
    return dbmod


def test_upsert_and_get_learned_rule(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    db.upsert_learned_rule(
        rule_key="class:beapvadinės durys",
        field_path="kiekis",
        adjustment="demote",
        support=5,
        projects=3,
        detail="users raise count 4/5 times",
    )
    rules = db.get_learned_rules()
    assert len(rules) == 1
    assert rules[0]["rule_key"] == "class:beapvadinės durys"
    assert rules[0]["support"] == 5

    # upsert again with same key updates in place, not duplicates
    db.upsert_learned_rule(
        rule_key="class:beapvadinės durys", field_path="kiekis",
        adjustment="demote", support=8, projects=4, detail="updated",
    )
    rules = db.get_learned_rules()
    assert len(rules) == 1
    assert rules[0]["support"] == 8


def test_get_learned_rules_min_support_filter(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    db.upsert_learned_rule(rule_key="a", field_path="kiekis", adjustment="demote",
                           support=2, projects=1, detail="")
    db.upsert_learned_rule(rule_key="b", field_path="kiekis", adjustment="demote",
                           support=6, projects=3, detail="")
    assert {r["rule_key"] for r in db.get_learned_rules(min_support=3)} == {"b"}
```

> Confirm the test harness's DB-reset idiom against `backend/tests/conftest.py` / existing `test_*_db.py` files before running; if the suite uses an in-memory fixture rather than `SAMATU_DB_PATH` reload, mirror that idiom here instead. The two test bodies above are the contract; the setup adapts to the established pattern.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_learned_rules_db.py -v`
Expected: FAIL — `AttributeError: module 'db' has no attribute 'upsert_learned_rule'`

- [ ] **Step 3: Write minimal implementation**

In `_init` schema block (after the `corrections` indexes, before the closing `"""`):

```sql
            CREATE TABLE IF NOT EXISTS learned_rules (
                rule_key     TEXT PRIMARY KEY,
                field_path   TEXT NOT NULL,
                adjustment   TEXT NOT NULL,   -- 'demote' | 'suggest'
                support      INTEGER NOT NULL,
                projects     INTEGER NOT NULL,
                detail       TEXT,
                updated_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lr_support ON learned_rules(support);
```

Add `_migrate_schema` guard (append-only, mirrors the existing pattern) inside `_migrate_schema`:

```python
        lr = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_rules'").fetchone()
        if not lr:
            c.execute("""
                CREATE TABLE learned_rules (
                    rule_key TEXT PRIMARY KEY, field_path TEXT NOT NULL,
                    adjustment TEXT NOT NULL, support INTEGER NOT NULL,
                    projects INTEGER NOT NULL, detail TEXT, updated_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_lr_support ON learned_rules(support)")
```

Add helpers near `corrections_summary`:

```python
def upsert_learned_rule(rule_key: str, field_path: str, adjustment: str,
                        support: int, projects: int, detail: str = "") -> None:
    """Insert or replace a derived learning rule (idempotent on rule_key)."""
    with _conn() as c:
        c.execute("""
            INSERT INTO learned_rules
                (rule_key, field_path, adjustment, support, projects, detail, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rule_key) DO UPDATE SET
                field_path=excluded.field_path, adjustment=excluded.adjustment,
                support=excluded.support, projects=excluded.projects,
                detail=excluded.detail, updated_at=excluded.updated_at
        """, (rule_key, field_path, adjustment, int(support), int(projects),
              detail, _now_iso()))


def get_learned_rules(min_support: int = 1) -> list[dict]:
    """All learned rules at or above a support threshold, strongest first."""
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM learned_rules WHERE support >= ?
            ORDER BY support DESC
        """, (int(min_support),)).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_learned_rules_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/test_learned_rules_db.py
git commit -m "feat(db): learned_rules table + upsert/get helpers"
```

---

## Task 3.2: Pure rule-derivation from the corrections log

**Files:**
- Create: `backend/extractor/learned_rules.py`
- Test: `backend/tests/test_learned_rules.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_learned_rules.py
from extractor.learned_rules import derive_rules_from_corrections


def _corr(project_id, field_path, aprasymas, old, new):
    return {"project_id": project_id, "field_path": field_path,
            "new_value": {"aprasymas": aprasymas, "kiekis": new},
            "old_value": {"aprasymas": aprasymas, "kiekis": old}}


def test_derives_rule_above_min_support():
    # same class overridden upward across 3 projects
    corrs = [
        _corr("p1", "kiekis", "Beapvadinės durys", 4, 6),
        _corr("p2", "kiekis", "Beapvadinės durys", 3, 5),
        _corr("p3", "kiekis", "Beapvadinės durys", 2, 4),
    ]
    rules = derive_rules_from_corrections(corrs, min_support=3, min_projects=2)
    assert len(rules) == 1
    r = rules[0]
    assert r["adjustment"] == "demote"
    assert r["support"] == 3
    assert r["projects"] == 3
    assert "durys" in r["rule_key"].lower()


def test_below_support_threshold_yields_nothing():
    corrs = [_corr("p1", "kiekis", "Silikonavimas", 10, 12)]
    assert derive_rules_from_corrections(corrs, min_support=3, min_projects=2) == []


def test_single_project_repeats_dont_qualify():
    corrs = [
        _corr("p1", "kiekis", "Plytelės", 10, 12),
        _corr("p1", "kiekis", "Plytelės", 11, 13),
        _corr("p1", "kiekis", "Plytelės", 9, 11),
    ]
    # support 3 but only 1 project → fails min_projects
    assert derive_rules_from_corrections(corrs, min_support=3, min_projects=2) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_learned_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'extractor.learned_rules'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/extractor/learned_rules.py
"""Aggregate the corrections audit log into apply-able learning rules.

A rule fires only with real support: a class must be overridden in the same
direction across at least `min_projects` distinct projects and `min_support`
total corrections. This avoids learning from a single noisy project.

Pure: takes a list of correction dicts (db.list_corrections shape), returns a
list of rule dicts ready for db.upsert_learned_rule.
"""
from __future__ import annotations
import collections


def _class_of(aprasymas: str) -> str:
    """Coarse class key from a line description (lowercased, first 4 words)."""
    return " ".join((aprasymas or "").lower().split()[:4]).strip()


def _aprasymas(corr: dict, side: str) -> str:
    val = corr.get(side)
    if isinstance(val, dict):
        return val.get("aprasymas") or ""
    return ""


def derive_rules_from_corrections(
    corrections: list[dict],
    min_support: int = 3,
    min_projects: int = 2,
) -> list[dict]:
    """Return [{rule_key, field_path, adjustment, support, projects, detail}]."""
    # group by (field_path, class)
    buckets: dict[tuple, list[dict]] = collections.defaultdict(list)
    for corr in corrections:
        fp = corr.get("field_path")
        if fp != "kiekis":
            continue  # quantity overrides are the learnable signal for now
        klass = _class_of(_aprasymas(corr, "new_value") or _aprasymas(corr, "old_value"))
        if not klass:
            continue
        buckets[(fp, klass)].append(corr)

    rules = []
    for (fp, klass), items in buckets.items():
        support = len(items)
        projects = len({c.get("project_id") for c in items})
        if support < min_support or projects < min_projects:
            continue
        rules.append({
            "rule_key": f"class:{klass}",
            "field_path": fp,
            "adjustment": "demote",
            "support": support,
            "projects": projects,
            "detail": f"Naudotojas taisė šią klasę {support}× per {projects} projektus.",
        })
    rules.sort(key=lambda r: -r["support"])
    return rules
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_learned_rules.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/learned_rules.py backend/tests/test_learned_rules.py
git commit -m "feat(learning): derive demote-rules from corrections log"
```

---

## Task 3.3: Gated apply — demote confidence on learned classes

**Files:**
- Modify: `backend/extractor/learned_rules.py` (add `apply_learned_rules`)
- Modify: `backend/extractor/confidence.py` (call it after the static `CLASS_RULES` pass, behind an env flag)
- Test: `backend/tests/test_learned_rules.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_learned_rules.py
from extractor.learned_rules import apply_learned_rules


def test_apply_demotes_matching_pozicija():
    rules = [{"rule_key": "class:beapvadinės durys", "field_path": "kiekis",
              "adjustment": "demote", "support": 5, "projects": 3,
              "detail": "Naudotojas taisė šią klasę 5× per 3 projektus."}]
    parsed = {"pozicijos": [
        {"aprasymas": "Beapvadinės durys montavimas", "confidence": "zalia"},
        {"aprasymas": "Sienų dažymas", "confidence": "zalia"},
    ]}
    out = apply_learned_rules(parsed, rules)
    durys = next(p for p in out["pozicijos"] if "durys" in p["aprasymas"].lower())
    paint = next(p for p in out["pozicijos"] if "dažymas" in p["aprasymas"].lower())
    assert durys["confidence"] == "geltona"          # demoted
    assert "taisė" in durys.get("_confidence_reason", "")
    assert paint["confidence"] == "zalia"            # untouched


def test_apply_never_promotes():
    rules = [{"rule_key": "class:sienų dažymas", "field_path": "kiekis",
              "adjustment": "demote", "support": 5, "projects": 3, "detail": "x"}]
    parsed = {"pozicijos": [{"aprasymas": "Sienų dažymas", "confidence": "raudona"}]}
    out = apply_learned_rules(parsed, rules)
    assert out["pozicijos"][0]["confidence"] == "raudona"  # stays worst, not promoted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_learned_rules.py::test_apply_demotes_matching_pozicija -v`
Expected: FAIL — `ImportError: cannot import name 'apply_learned_rules'`

- [ ] **Step 3: Write minimal implementation**

Append to `learned_rules.py`:

```python
_RANK = {"zalia": 0, "geltona": 1, "raudona": 2}
_RANK_INV = {0: "zalia", 1: "geltona", 2: "raudona"}


def apply_learned_rules(parsed: dict, rules: list[dict]) -> dict:
    """Flag-only application: demote (never promote) the confidence of any
    pozicija whose class matches a 'demote' rule, and append a reason citing
    the user's own correction history. Mutates and returns `parsed`."""
    if not rules:
        return parsed
    demote_keys = [r for r in rules if r.get("adjustment") == "demote"]
    for p in parsed.get("pozicijos") or []:
        label = (p.get("aprasymas") or "").lower()
        for r in demote_keys:
            klass = r["rule_key"].split("class:", 1)[-1]
            if klass and klass in label:
                cur = _RANK.get((p.get("confidence") or "zalia"), 0)
                new = max(cur, _RANK["geltona"])   # demote toward geltona, never below cur
                p["confidence"] = _RANK_INV[new]
                reason = r.get("detail") or "Naudotojas dažnai taiso šią klasę."
                prev = p.get("_confidence_reason")
                p["_confidence_reason"] = f"{prev}; {reason}" if prev else reason
                break
    return parsed
```

In `confidence.py`, after the static rules loop in `apply_confidence` (before `return parsed`), add the gated hook:

```python
    import os
    if os.getenv("SAMATU_LEARNED_RULES") == "1":
        try:
            import db
            from extractor.learned_rules import apply_learned_rules
            rules = db.get_learned_rules(min_support=3)
            apply_learned_rules(parsed, rules)
        except Exception:
            pass  # learning is best-effort; never break extraction
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_learned_rules.py tests/test_confidence.py -v`
Expected: PASS (learned-rules tests green; existing confidence tests unaffected because the flag is off by default)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/learned_rules.py backend/extractor/confidence.py backend/tests/test_learned_rules.py
git commit -m "feat(learning): gated confidence-demotion from learned rules"
```

---

## Task 3.4: Refresh job + admin surface (concrete spec)

> **Status: concrete spec** — small, but touches the admin surface, so verify in-app.

- **Refresh entrypoint:** a function `refresh_learned_rules()` (in `learned_rules.py`) that reads `db.list_corrections(None, limit=5000)`, runs `derive_rules_from_corrections`, and `db.upsert_learned_rule` for each. Call it (a) from a lightweight admin endpoint `POST /api/admin/refresh-learned-rules` (mirror the existing `/api/admin/corrections-summary` auth guard) and (b) optionally nightly alongside `backup_scheduler`. TDD the refresh function with a temp DB (seed corrections → refresh → `get_learned_rules` non-empty).
- **Admin view:** extend the existing corrections-summary admin surface to list active learned rules (rule_key, support, projects, last updated) so the operator can see what the system has learned before flipping `SAMATU_LEARNED_RULES=1`.
- **Rollout:** ship with the flag OFF. Turn on only after eyeballing the derived rules against the corrections corpus on a real account — per the "council needs real-PDF test" memory, validate empirically before trusting the aggregation.

---

# PHASE 4 — Pricing intelligence (concrete spec)

> **Status:** the persistent pricebook table is execution-ready (TDD sketch below); LLM price-suggestion and composite recipes are specified and each warrant a short dedicated plan.

**Today (from the corrections+pricing map):** prices are typed inline per project (`projects.data.darbu_sarasas[i].kaina`); a localStorage-only `samatu_price_lists` exists but isn't synced; `assembly_library.json` holds **consumption ratios, not prices**. So a contractor re-enters every unit rate on every project.

**4.1 Persistent pricebook (TDD-ready).**
- New table `pricebook (user_id, skyrius, aprasymas, vnt, kaina, updated_at)` in `db.py` with helpers `upsert_price`, `get_pricebook(user_id)`, and a fuzzy `lookup_price(user_id, aprasymas, vnt)` (normalize description → match). Follow the exact TDD shape of Task 3.1.
- Endpoints `GET/PUT /api/pricebook` (user-scoped, reuse the auth dependency from existing user endpoints).
- On extraction, pre-fill each pozicija's `kaina` from the user's pricebook when a confident match exists; mark `kaina_saltinis="pricebook"` so the UI shows it's a remembered rate, not a guess. This is the single biggest day-2 retention lever for a real estimator.

**4.2 LLM price-suggestion.**
- For pozicijos with no pricebook match, batch them into one Claude call returning a suggested €/unit + a one-line basis, tagged `kaina_saltinis="ai_suggestion"` and rendered 🟡 (never silently authoritative). Retry/backoff per the project's "max 3 retries" rule. Needs its own plan (prompt design + cost guard + eval against the contractor fixture's known rates).

**4.3 Composite recipe unit-rates.**
- Extend `assembly_library.json` entries with an optional priced build-up (`{labour_h_per_unit, material_qty_per_unit, material_unit}`) so a line like "Sienų glaistymas+dažymas" can resolve to a composite €/m² from component rates × the user's pricebook. Keep ratios and prices in separate files (ratios are universal; prices are per-user). Own plan: schema design + migration of the existing ratio entries + calc wiring + validation against §6 checks.

---

# PHASE 5 — Geometry & routing enhancements (concrete spec — each needs its own plan)

From the geometry map, the flood-fill (`cv_polygon.py`), shoelace area (`plan_assembler.py`/`takeoffStore.js`), opening deductions (`universal_rules.py`), and polygon editor (`PolygonEditor.jsx`) already exist and are tested. The research gaps are:

**5.1 Vector/raster page routing.** `page_classifier.py` classifies by drawing *type*, never by substrate. A new pre-step (PyMuPDF path-count vs image-area ratio) would route true-vector PDFs to a precise vector-geometry extractor and raster PDFs to the current Vision path. High accuracy ceiling, but a genuinely new module + a vector extractor — its own plan. (Note the existing CLAUDE.md finding: all current LT test PDFs are flattened raster, so validate that vector inputs actually occur before building this.)

**5.2 Linear-quantity topology.** Baseboard/LED/cornice currently come from a simple perimeter sum. A skeleton→graph model (dedup shared runs, handle open vs closed runs, subtract door openings topologically) would tighten linear quantities. Geometry-heavy; own plan with synthetic-fixture tests like `test_cv_polygon.py`.

**5.3 Legend-first source-tagged confidence.** Extend `confidence.py` so a quantity derived from a legend-matched symbol carries a distinct, higher-trust source tag than a vision-estimated one. Smaller; could fold into a Phase-3 follow-up.

**5.4 Gap-band heal → opening.** `gap_fill_doors` bridges door gaps so the flood doesn't leak, but discards where it bridged. Recording each healed gap as a candidate opening would feed door/window counts for free. Medium; own plan, extends `cv_polygon.py` + its tests.

---

# PHASE 6 — Large subsystems (concrete spec — do NOT execute from this doc)

Each of these is a multi-week project. Listed for the roadmap; **each requires its own brainstorming + dedicated plan** before any code.

- **Declarative metric config.** Interior formulas are hard-coded across `interiorCalc.js` / `universal_rules.py` / `line_items.py`. Extracting them into a declarative config (per construction type) is the enabler for facade/roof/earthworks modules — but it's a refactor of accuracy-bearing code, so it ships only behind a full regression suite proving identical numbers on the fixtures first (CLAUDE.md: "refactoring allowed only when at least as accurate").
- **Agentic / RAG layer.** A retrieval layer over the knowledge base (CLAUDE.md formulas, LT standards, the corrections corpus) to ground extraction and answer estimator questions. New subsystem.
- **Bluebeam markup import/export.** Interop with the dominant US takeoff tool's markup format — checkbox feature, not hero (per the "no add-on positioning" memory). Defer until a customer asks.
- **Drawing version comparison.** Diff revisions of the same drawing → changed quantities. Valuable for renovation rounds; own data model + UI.
- **Void-relation data model.** First-class model of openings/voids and their parent surfaces (instead of per-line deductions) — unlocks correct propagation when a wall or opening is edited. Foundational refactor; sequence after declarative config.

---

## Self-Review

**Spec coverage** (against the research task list):

| Research item | Tier | Covered by |
|---|---|---|
| Units normalizer | 1 | Task 1.1 ✓ |
| Magnitude/decimal sanity | 1 | Task 1.2 ✓ |
| Quantity reconciliation | 1 | Task 1.3 ✓ |
| Reference-object scale back-solve | 1 | Task 1.4 ✓ |
| Measurement-expression capture (B) | new | Tasks 2.1–2.3 ✓ |
| Learned-rule store (A) | new | Tasks 3.1–3.4 ✓ |
| Pricebook + LLM price suggestion | 3 | Phase 4.1 (TDD-ready) / 4.2 ✓ |
| Composite recipe unit-rates | 3 | Phase 4.3 ✓ |
| Deterministic click-to-fill + gap-band heal | 2 | Phase 5.4 ✓ (exists; heal is the delta) |
| Linear-quantity topology | 2 | Phase 5.2 ✓ |
| Vector/raster routing | 2 | Phase 5.1 ✓ |
| Legend-first source-tagged confidence | 2 | Phase 5.3 ✓ |
| Declarative metric config | 4 | Phase 6 ✓ |
| Agentic/RAG layer | 4 | Phase 6 ✓ |
| Bluebeam import/export | 4 | Phase 6 ✓ |
| Drawing version comparison | 4 | Phase 6 ✓ |
| Void-relation data model | 4 | Phase 6 ✓ |

No gaps. Electrical/sanitary explicitly out of scope (per user instruction).

**Placeholder scan:** Phases 1–3 contain complete test + implementation code for every TDD step. Phases 4–6 are deliberately specs (flagged as such) — they are roadmap entries that each need their own plan, not half-written tasks pretending to be executable. The one UI task (2.3) is a spec because it needs browser verification.

**Type consistency:** `to_metres`/`pick_length_m` (1.1) reused conceptually by 2.1's opening helper; `Warning` dataclass (1.2/1.3) matches the existing `sanity_checks` signature exactly; `ScaleValidationResult` (1.4) reuses the existing dataclass; confidence strings `zalia|geltona|raudona` (3.3) match `confidence.py`'s enum; `upsert_learned_rule`/`get_learned_rules` (3.1) signatures match the calls in 3.3/3.4. Consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-30-interior-finishing-upgrades.md`.**

Per your instruction — **not executing yet.** When you're ready, two options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks. Best for the 14 TDD tasks in Phases 1–3.
2. **Inline Execution** — I work the tasks in this session with checkpoints.

Either way I'd suggest doing Phase 1 first (highest leverage, ~4 small tasks, lands green), then Phase 2, then Phase 3 — and writing a dedicated plan before any Phase 4–6 item.
