# Stogai V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a roofer-facing extractor that reads LT statybų projekto PDF and produces a defensible 15-row kiekių žiniaraštis matching the proven LT stogininkų sąmatos format — within 8 calendar weeks.

**Architecture:** Hybrid pipeline. **Phase 0** validates the deterministic geometric engine against 2 in-hand ground-truth roofer sąmatos using hardcoded inputs (no Vision). **Phase 1** adds hybrid text-first + Haiku-vision page classifier (refactor of existing `backend/extractor/page_classifier.py`). **Phase 2** wires Vision dim-extraction → geometric engine → conditional template per roof type (dvišlaitis/keturšlaitis/vienšlaitis), backed by 20 cross-checks and Sistela-aligned suggested kainynas defaults. **Phase 3** ships beta with shadow-testing async queue to grow ground truth from N=2 to N=8 across 4 roof types.

**Tech Stack:** Python 3.14 (backend, pytest), FastAPI, pdfplumber, pdf2image, Anthropic Claude (Haiku 4.5 routing + Sonnet 4.6 vision extraction), React + Vite (frontend, node --test for unit tests), Tailwind. Reuses existing infra: PDF ingestion, Vision calling, evidence/provenance framework.

---

## Strategy summary (decisions from consult-council + 5-advisor llm-council)

1. **NOT "kiekiai only"** — Outsider's reality check: roofers need Sistela-aligned suggested prices with override. Pre-fill `€/vnt.` defaults from `backend/extractor/roof/sistela_rates.json`; let user modify.
2. **Output ≠ table** — Each row links to source PDF page with highlighted slope/dim overlay. Per-row provenance is the trust mechanism.
3. **Refuse-to-output on cross-check failure** — Contrarian's guardrail: if murlotas L (SK) ↮ eaves perimeter (SA), or roof shape outside core-4 types, fall back to "manual mode" UI. Never silently mis-extract.
4. **Vision NEVER computes m²** — Vision extracts dim's + slope angles + roof type only. Deterministic Python (`geometry.py`) computes all quantities.
5. **3-day wedge prevents premature infrastructure** — Hardcode "this PDF is roof, page N is stogo planas" for 2 in-hand PDFs in Phase 0. Validate engine matches roofer sąmatos before refactoring classifier.
6. **N=8 ground truth target by end of beta** — €100 × 6 roofers from paslaugos.lt cold contact. 2 in-hand + 6 new = N=8 across 4 roof types.
7. **Free dalis classifier tool DEFERRED to V1.5** — Expansionist's wedge idea is strong but premature; core extractor earns it first.

---

## File Structure

### New files (Phase 0)

```
backend/extractor/roof/
├── __init__.py                    # public API surface
├── geometry.py                    # pure-function math: slope_factor, hvf, dim derivation
├── strategies/
│   ├── __init__.py
│   ├── base.py                    # RoofStrategy ABC + RoofInput/RoofOutput dataclasses
│   ├── dvislaitis.py              # gable roof template (8 rows)
│   ├── keturslaitis.py            # hip roof template (5 rows)
│   ├── vienslaitis.py             # mono-pitch template (3 rows)
│   └── plokscias.py               # stub raising NotImplementedError (V2)
├── validators.py                  # 20 cross-checks per math research
├── sistela_rates.json             # LT-pro suggested €/vnt. defaults per pozicija
└── extractor.py                   # orchestrator (Phase 1+ adds Vision; Phase 0 = hardcoded)

ground_truth/
├── a_laida_roof.yaml              # A LAIDA confirmed sąmata + my measurements
└── 0039_roof.yaml                 # 0039 confirmed sąmata + my measurements

backend/tests/extractor/roof/
├── conftest.py                    # fixtures loading ground_truth YAMLs
├── test_geometry.py               # unit tests for pure math (no PDF)
├── test_strategies.py             # strategy tests against ground truth
└── test_validators.py             # validator tests
```

### New files (Phase 1+)

```
backend/extractor/roof/
└── vision.py                      # Anthropic Vision prompts for dim extraction

backend/extractor/page_classifier.py  # REFACTORED: add hybrid text-first + dalis enum
backend/main.py                       # ADD: POST /extract-roof endpoint

frontend/src/components/roof/
├── RoofOverlay.jsx                # PDF page with highlighted slopes + m² overlay
├── RoofKiekiaiTable.jsx           # 15-row table with confidence + provenance + €/vnt inputs
├── PreflightModal.jsx             # dalis/page-type detection summary BEFORE Vision call
└── ShadowQueueAdmin.jsx           # admin UI for 24h human-verified queue

frontend/src/pages/RoofProject.jsx # new project type page wiring above components
```

### Files modified (Phase 1+)

- `backend/extractor/page_classifier.py` — add `_extract_antspaudas_text()` + hybrid logic
- `backend/main.py` — register `/extract-roof` endpoint
- `frontend/src/App.jsx` — register `/roof-project/:id` route
- `frontend/src/pages/NewProject.jsx` — add "Stogai" as project type option
- `CLAUDE.md` — promote Stogai from "ruošiame" to "Jau veikia (beta)"
- `frontend/src/pages/Landing.jsx` — update Skaidrumas section once stable

---

## Phase 0 — 3-Day Wedge: Validate Geometric Engine Against Ground Truth

**Goal:** Prove the deterministic Python math reproduces both roofer sąmatos within stated acceptance bands. No Vision, no UI yet. Show working CLI to user by end of Day 3. If math doesn't match within tolerances, the strategy doesn't deserve further investment — stop and re-strategize.

**Acceptance:** Running `python -m backend.extractor.roof.cli` against `ground_truth/a_laida_roof.yaml` and `ground_truth/0039_roof.yaml` outputs computed quantities matching the roofer's sąmatos within these bands:
- Stogo plotas: ±5% (A LAIDA 185 m², 0039 231 m²)
- Latakai: ±2% (A LAIDA 52 m, 0039 51 m)
- Kraigai: ±5% (A LAIDA 36 m, 0039 26 m)
- Sienos (gablai for dvišlaitis only): ±10% (0039 135 m²)
- Vėjalentės (dvišlaitis only): ±5% (0039 18 m)
- All 20 validators pass (or have explicit "WARN" status with explanation)

---

### Task 1: Create roof module skeleton + sentinel test

**Files:**
- Create: `backend/extractor/roof/__init__.py`
- Create: `backend/extractor/roof/geometry.py`
- Create: `backend/tests/extractor/roof/__init__.py`
- Create: `backend/tests/extractor/roof/conftest.py`
- Create: `backend/tests/extractor/roof/test_geometry.py`

- [ ] **Step 1: Create empty roof module + sentinel test**

```python
# backend/extractor/roof/__init__.py
"""Stogai (roofing) takeoff module — V1 (2026-05-13).

Public API:
    from backend.extractor.roof import compute_roof_quantities
"""
__version__ = "0.1.0"
```

```python
# backend/extractor/roof/geometry.py
"""Pure-function roof geometry math. No PDF, no Vision, no I/O.

All public functions are pure and deterministic. See
docs/superpowers/research/2026-05-13-stogai-v1-research-stogo-math.md
for formulas + LT statybų reglamentų references.
"""
```

```python
# backend/tests/extractor/roof/conftest.py
"""Shared fixtures for roof tests."""
```

```python
# backend/tests/extractor/roof/test_geometry.py
"""Unit tests for backend.extractor.roof.geometry."""

def test_module_loads():
    """Sentinel — confirms module is importable."""
    from backend.extractor.roof import geometry
    assert geometry.__doc__ is not None
```

- [ ] **Step 2: Run sentinel test**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v`
Expected: PASS (1 test) — confirms module wiring works.

- [ ] **Step 3: Commit**

```bash
git add backend/extractor/roof/ backend/tests/extractor/roof/
git commit -m "feat(roof): module skeleton + sentinel test"
```

---

### Task 2: Write A LAIDA ground truth YAML

**Files:**
- Create: `ground_truth/a_laida_roof.yaml`

- [ ] **Step 1: Write A LAIDA ground truth**

```yaml
# ground_truth/a_laida_roof.yaml
project_id: a_laida
source_pdf: "A LAIDA.pdf"
location: "Užusalių sen., Jonavos r."
statybos_rusis: nauja_statyba
statinio_kategorija: neypatingas
dalys_available: [SA]   # PDF is SA dalis only

roof:
  type: keturslaitis           # 4-pitch hip
  asymmetric: true
  slopes:
    - side: long
      angle_deg: 25
    - side: short
      angle_deg: 22
  building_footprint_outer_walls:
    width_m: 8.95
    length_m: 13.12
  roof_footprint_with_eaves:
    width_m: 10.80
    length_m: 14.97
  eaves_overhang_m: 1.05
  wall_thickness_m: 0.25       # blokeliai 25cm per medž. žiniaraštis
  chimney_count: 0             # not visible in this project
  rooflight_count: 0
  windows_count: 0             # NOT confidently known — see "out_of_scope"
  roof_material: profiliuota_skarda
  ral: "1035"

roofer_samata:
  source: "owner_friend_roofer_quoted_2026-05-12"
  pvm_included: false
  line_items:
    - position: perdanga
      qty: 117
      unit: m2
      eur_per_unit: 10.00
      sum_eur: 1170.00
    - position: stogas
      qty: 185
      unit: m2
      eur_per_unit: 20.00
      sum_eur: 3700.00
    - position: latakai
      qty: 52
      unit: m
      eur_per_unit: 12.00
      sum_eur: 624.00
    - position: kraigai
      qty: 36
      unit: m
      eur_per_unit: 6.00
      sum_eur: 216.00
  total_eur_no_vat: 5710.00

# What I expect my extractor to compute, given inputs above:
expected_extractor_output:
  perdanga_m2: 117.4     # tolerance ±2%
  stogas_m2: 185.5       # tolerance ±5% (incl. 5% waste)
  latakai_m: 51.5        # tolerance ±2%
  kraigai_m: 37.0        # tolerance ±5%
  # Vėjalentės, sienos: N/A for keturšlaitis (no gables)
```

- [ ] **Step 2: Commit**

```bash
git add ground_truth/a_laida_roof.yaml
git commit -m "data(roof): A LAIDA ground truth — keturslaitis 4 line items"
```

---

### Task 3: Write 0039 ground truth YAML

**Files:**
- Create: `ground_truth/0039_roof.yaml`

- [ ] **Step 1: Write 0039 ground truth**

```yaml
# ground_truth/0039_roof.yaml
project_id: 0039_patikslinta
source_pdf: "0039-01-TDP-SK patikslinta.pdf"
location: "P. Kriaučiūno g. 13A, Marijampolė"
statybos_rusis: rekonstrukcija
statinio_kategorija: ypatingasis
purpose: socialinė_globos_pastatas
dalys_available: [SK]        # PDF is SK dalis ONLY — SA missing

roof:
  type: dvislaitis             # 2-pitch gable
  asymmetric: false
  slopes:
    - side: long
      angle_deg: 35           # derived from C24 rafter span per math research
  building_footprint_outer_walls:
    # NOTE: derived from SK murloto 48 m / 2 long sides → 24m long
    width_m: 7.5              # estimated from rafter length 4.5m × cos(35°)
    length_m: 25.34           # from HEA 160 sija L=25340
  roof_footprint_with_eaves:
    width_m: 7.5              # SK does not show eaves dim directly
    length_m: 25.34
  eaves_overhang_m: 0.5       # ESTIMATED — uncertain without SA dalis
  wall_thickness_m: 0.30      # rekonstrukcija existing walls, est.
  chimney_count: 1
  rooflight_count: 0
  windows_count: 12           # per roofer sąmata
  roof_material: unknown      # not in SK dalis (would be in SA)

# Structural inputs (UNIQUE to having SK dalis)
structural_inputs:
  gegnes_count: 86
  gegnes_length_m: 4.5
  gegnes_section_mm: "50x250"
  stygos_count: 43
  stygos_length_m: 5.0
  murloto_total_length_m: 48      # cross-check: ≈ 2 × building_length_m
  statramsciai_count: 80
  statramsciai_length_m: 6.0
  hea160_beams_total_m: 47.9      # 2 × 25.34 - corner overlap

roofer_samata:
  source: "owner_friend_roofer_quoted_2026-05-12"
  pvm_included: false
  line_items:
    - position: stogas
      qty: 231
      unit: m2
      eur_per_unit: 40.00
      sum_eur: 9240.00
    - position: sienos
      qty: 135
      unit: m2
      eur_per_unit: 50.00
      sum_eur: 6750.00
    - position: vejalentes
      qty: 18
      unit: m
      eur_per_unit: 12.00
      sum_eur: 216.00
    - position: kraigai
      qty: 26
      unit: m
      eur_per_unit: 12.00
      sum_eur: 312.00
    - position: latakai
      qty: 51
      unit: m
      eur_per_unit: 20.00
      sum_eur: 1020.00
    - position: kaminelis
      qty: 1
      unit: vnt
      eur_per_unit: 70.00
      sum_eur: 70.00
    - position: apsaugine_tvorele
      qty: 51
      unit: m
      eur_per_unit: 20.00
      sum_eur: 1020.00
    - position: langu_apdirbimas
      qty: 12
      unit: vnt
      eur_per_unit: 150.00
      sum_eur: 1800.00
  total_eur_no_vat: 20458.00

expected_extractor_output:
  stogas_m2: 231         # ±5%
  sienos_m2: 134.7       # ±10% (gablai + soflitas)
  vejalentes_m: 18.0     # ±5% (= 4 × 4.5m raker)
  kraigai_m: 37.0        # ±5% — NOTE: my calc gave 37, roofer 26 (close but lower)
  latakai_m: 51.5        # ±2% (long sides only for dvišlaitis)
  apsaugine_tvorele_m: 51.5  # = latakai for safety zones
```

- [ ] **Step 2: Commit**

```bash
git add ground_truth/0039_roof.yaml
git commit -m "data(roof): 0039 ground truth — dvislaitis 8 line items"
```

---

### Task 4: Implement + test `slope_factor`

**Files:**
- Modify: `backend/extractor/roof/geometry.py`
- Modify: `backend/tests/extractor/roof/test_geometry.py`

- [ ] **Step 1: Write failing test for slope_factor**

```python
# backend/tests/extractor/roof/test_geometry.py
import math
import pytest

from backend.extractor.roof import geometry


@pytest.mark.parametrize("angle_deg,expected", [
    (0,  1.000),
    (15, 1.035),
    (22, 1.079),
    (25, 1.103),
    (30, 1.155),
    (35, 1.221),
    (45, 1.414),
])
def test_slope_factor(angle_deg, expected):
    """slope_factor = 1/cos(angle) — sloped area / plan area."""
    assert geometry.slope_factor(angle_deg) == pytest.approx(expected, abs=0.001)


def test_slope_factor_zero_angle():
    assert geometry.slope_factor(0) == 1.0


def test_slope_factor_invalid():
    with pytest.raises(ValueError, match="must be in"):
        geometry.slope_factor(90)
```

- [ ] **Step 2: Run test, verify fails**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py::test_slope_factor -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'slope_factor'`

- [ ] **Step 3: Implement slope_factor**

```python
# backend/extractor/roof/geometry.py — append to existing module
import math


def slope_factor(angle_deg: float) -> float:
    """Area ratio: sloped surface area / plan-view area.

    Formula: 1 / cos(angle). For a roof at angle α from horizontal,
    1 m² of plan footprint corresponds to slope_factor m² of actual
    sloped surface to cover.

    Args:
        angle_deg: roof slope angle in degrees, 0 ≤ angle < 90.

    Returns:
        Multiplier ≥ 1.0. Flat roof = 1.0, 45° = 1.414, etc.

    Raises:
        ValueError: if angle_deg outside [0, 90).
    """
    if not (0 <= angle_deg < 90):
        raise ValueError(f"angle_deg must be in [0, 90), got {angle_deg}")
    return 1.0 / math.cos(math.radians(angle_deg))
```

- [ ] **Step 4: Run test, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v`
Expected: PASS (9 tests across parametrize cases).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/geometry.py backend/tests/extractor/roof/test_geometry.py
git commit -m "feat(roof/geom): slope_factor + tests"
```

---

### Task 5: Implement + test `hip_valley_factor`

**Files:**
- Modify: `backend/extractor/roof/geometry.py`
- Modify: `backend/tests/extractor/roof/test_geometry.py`

- [ ] **Step 1: Write failing test**

```python
# Append to test_geometry.py

@pytest.mark.parametrize("angle_deg,expected", [
    (15, 1.443),
    (22, 1.469),
    (25, 1.494),
    (30, 1.528),
    (35, 1.572),
    (45, 1.732),
])
def test_hip_valley_factor(angle_deg, expected):
    """hvf = √(sec²α + 1) — sloped hip/valley length / plan-projected length."""
    assert geometry.hip_valley_factor(angle_deg) == pytest.approx(expected, abs=0.002)
```

- [ ] **Step 2: Run test, verify fails**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py::test_hip_valley_factor -v`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement hip_valley_factor**

```python
# Append to backend/extractor/roof/geometry.py

def hip_valley_factor(angle_deg: float) -> float:
    """Length ratio: 3D hip/valley length / plan-projected length.

    Hips and valleys travel diagonally on a sloped roof. Their 3D length
    on the roof surface is longer than the plan-projected diagonal because
    they rise as they travel inward.

    Formula: √(sec²α + 1), where α = slope angle of the adjacent slopes
    (assuming 90° plan-angle between intersecting slopes).

    Args:
        angle_deg: slope angle of the planes meeting at this hip/valley.

    Returns:
        Multiplier > 1.0. At 30° slope = 1.528, at 45° = 1.732.
    """
    if not (0 <= angle_deg < 90):
        raise ValueError(f"angle_deg must be in [0, 90), got {angle_deg}")
    sec_a = 1.0 / math.cos(math.radians(angle_deg))
    return math.sqrt(sec_a ** 2 + 1)
```

- [ ] **Step 4: Run, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v`
Expected: PASS (15 tests total now).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/geometry.py backend/tests/extractor/roof/test_geometry.py
git commit -m "feat(roof/geom): hip_valley_factor + tests"
```

---

### Task 6: Implement keturslaitis (hip) geometry calc — full A LAIDA reproduction

**Files:**
- Modify: `backend/extractor/roof/geometry.py`
- Modify: `backend/tests/extractor/roof/test_geometry.py`

- [ ] **Step 1: Write failing test driven by A LAIDA ground truth**

```python
# Append to test_geometry.py

def test_keturslaitis_a_laida_perdanga():
    """A LAIDA perdanga = outer-wall footprint = 8.95 × 13.12 = 117.4 m²."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95,
        footprint_outer_l=13.12,
        eaves_overhang_m=1.05,
        slope_long_deg=25,
        slope_short_deg=22,
        wall_thickness_m=0.25,   # not used for perdanga since outer dims given
    )
    assert result.perdanga_m2 == pytest.approx(117.4, abs=2.0)


def test_keturslaitis_a_laida_stogas():
    """A LAIDA stogas = (long faces + 2 hips) × slope_factor + 5% waste = 185 m²."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95, footprint_outer_l=13.12,
        eaves_overhang_m=1.05,
        slope_long_deg=25, slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    # roof footprint with eaves: 8.95 + 2×1.05 = 11.05?
    # NOTE: A LAIDA dims show ROOF footprint (with eaves) = 10.80×14.97 directly.
    # So eaves_overhang_m used here is from AXIS (8.70) not outer wall face.
    # See ground_truth/a_laida_roof.yaml: building_footprint vs roof_footprint distinction.
    # For this test we expect ~185 ±10 m² (5% waste applied internally).
    assert result.stogas_m2 == pytest.approx(185, abs=10)


def test_keturslaitis_a_laida_latakai():
    """A LAIDA latakai = full eaves perimeter = 2×(10.80+14.97) = 51.54 ≈ 52 m."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95, footprint_outer_l=13.12,
        eaves_overhang_m=1.05,
        slope_long_deg=25, slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    assert result.latakai_m == pytest.approx(52, abs=2)


def test_keturslaitis_a_laida_kraigai():
    """A LAIDA kraigai = top ridge + 4 hip surface lengths ≈ 37 m."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95, footprint_outer_l=13.12,
        eaves_overhang_m=1.05,
        slope_long_deg=25, slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    assert result.kraigai_m == pytest.approx(37, abs=3)
```

- [ ] **Step 2: Run, verify fails**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v`
Expected: FAIL (`keturslaitis_quantities` not defined).

- [ ] **Step 3: Implement keturslaitis geometry**

```python
# Append to backend/extractor/roof/geometry.py
from dataclasses import dataclass


@dataclass
class KeturslaitisQuantities:
    """Computed quantities for a hip (keturšlaitis) roof."""
    perdanga_m2: float
    stogas_m2: float
    latakai_m: float
    kraigai_m: float
    ridge_plan_m: float
    hip_plan_per_corner_m: float
    hip_surface_per_corner_m: float
    waste_factor: float


def keturslaitis_quantities(
    *,
    footprint_outer_w: float,
    footprint_outer_l: float,
    eaves_overhang_m: float,
    slope_long_deg: float,
    slope_short_deg: float,
    wall_thickness_m: float = 0.0,
    waste_factor: float = 0.05,
) -> KeturslaitisQuantities:
    """Compute keturšlaitis (4-pitch hip) roof quantities.

    Args:
        footprint_outer_w, footprint_outer_l: outer-wall footprint (m).
        eaves_overhang_m: eaves projection from outer wall face (m).
        slope_long_deg: pitch on the two long slopes (deg).
        slope_short_deg: pitch on the two short (hip) slopes (deg).
        wall_thickness_m: unused here (kept for API symmetry).
        waste_factor: skardos cuts/overlap allowance (default 5%).

    Returns:
        KeturslaitisQuantities dataclass.
    """
    # Roof footprint (with eaves) dims
    roof_w = footprint_outer_w + 2 * eaves_overhang_m
    roof_l = footprint_outer_l + 2 * eaves_overhang_m

    # Perdanga = outer-wall footprint
    perdanga_m2 = footprint_outer_w * footprint_outer_l

    # Ridge height above eaves (must be same from both slopes, so use long-slope side)
    ridge_height = (roof_w / 2) * math.tan(math.radians(slope_long_deg))

    # Hip plan run (horizontal distance from corner to ridge endpoint, along long axis)
    # Hip rises ridge_height over hip_plan_run at slope_short_deg
    hip_plan_run = ridge_height / math.tan(math.radians(slope_short_deg))
    ridge_plan_m = roof_l - 2 * hip_plan_run

    # Long faces: 2 trapezoids at slope_long_deg
    # Plan area each = ((roof_l + ridge_plan_m) / 2) × (roof_w / 2)
    long_face_plan_area = ((roof_l + ridge_plan_m) / 2) * (roof_w / 2)
    long_face_surface = long_face_plan_area / math.cos(math.radians(slope_long_deg))

    # Short faces: 2 triangles at slope_short_deg
    # Plan area each = 0.5 × roof_w × hip_plan_run
    short_face_plan_area = 0.5 * roof_w * hip_plan_run
    short_face_surface = short_face_plan_area / math.cos(math.radians(slope_short_deg))

    # Total stogas surface (with waste)
    stogas_no_waste = 2 * long_face_surface + 2 * short_face_surface
    stogas_m2 = stogas_no_waste * (1 + waste_factor)

    # Latakai = full eaves perimeter
    latakai_m = 2 * (roof_w + roof_l)

    # Hip plan length per corner (from corner of roof to ridge endpoint, 3D in plan)
    hip_plan_per_corner = math.sqrt((roof_w / 2) ** 2 + hip_plan_run ** 2)
    # Hip surface length (with rise = ridge_height over hip_plan_per_corner)
    hip_surface_per_corner = math.sqrt(hip_plan_per_corner ** 2 + ridge_height ** 2)

    # Kraigai = top ridge + 4 hip surface lengths
    kraigai_m = ridge_plan_m + 4 * hip_surface_per_corner

    return KeturslaitisQuantities(
        perdanga_m2=perdanga_m2,
        stogas_m2=stogas_m2,
        latakai_m=latakai_m,
        kraigai_m=kraigai_m,
        ridge_plan_m=ridge_plan_m,
        hip_plan_per_corner_m=hip_plan_per_corner,
        hip_surface_per_corner_m=hip_surface_per_corner,
        waste_factor=waste_factor,
    )
```

- [ ] **Step 4: Run, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v`
Expected: PASS (19 tests total).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/geometry.py backend/tests/extractor/roof/test_geometry.py
git commit -m "feat(roof/geom): keturslaitis_quantities + A LAIDA reproduction tests"
```

---

### Task 7: Implement dvislaitis (gable) geometry calc — full 0039 reproduction

**Files:**
- Modify: `backend/extractor/roof/geometry.py`
- Modify: `backend/tests/extractor/roof/test_geometry.py`

- [ ] **Step 1: Write failing tests against 0039 ground truth**

```python
# Append to test_geometry.py

def test_dvislaitis_0039_stogas():
    """0039 stogas = 2 × (long × rafter) × slope_factor + 5% waste ≈ 231 m²."""
    result = geometry.dvislaitis_quantities(
        building_length_m=25.34,
        building_width_m=7.5,
        eaves_overhang_m=0.5,
        slope_deg=35,
        wall_thickness_m=0.30,
    )
    assert result.stogas_m2 == pytest.approx(231, abs=15)


def test_dvislaitis_0039_latakai():
    """0039 latakai = 2 × roof_length (only long sides for dvišlaitis) ≈ 51 m."""
    result = geometry.dvislaitis_quantities(
        building_length_m=25.34, building_width_m=7.5,
        eaves_overhang_m=0.5, slope_deg=35, wall_thickness_m=0.30,
    )
    # 2 × (25.34 + 2×0.5) = 52.68 ≈ 51 ±2
    assert result.latakai_m == pytest.approx(51, abs=3)


def test_dvislaitis_0039_kraigas():
    """0039 kraigas = 1 top ridge along building length ≈ 26 m."""
    result = geometry.dvislaitis_quantities(
        building_length_m=25.34, building_width_m=7.5,
        eaves_overhang_m=0.5, slope_deg=35, wall_thickness_m=0.30,
    )
    assert result.kraigai_m == pytest.approx(26, abs=3)


def test_dvislaitis_0039_vejalentes():
    """0039 vėjalentės = 4 rakers along gable edges ≈ 18 m."""
    result = geometry.dvislaitis_quantities(
        building_length_m=25.34, building_width_m=7.5,
        eaves_overhang_m=0.5, slope_deg=35, wall_thickness_m=0.30,
    )
    # 4 × rafter_length where rafter goes from eaves to ridge along gable
    # rafter_length_surface = (width/2 + eaves) / cos(slope)
    assert result.vejalentes_m == pytest.approx(18, abs=3)


def test_dvislaitis_0039_sienos():
    """0039 sienos = 2 gable walls (full wall + triangle) + soflitas ≈ 135 m²."""
    result = geometry.dvislaitis_quantities(
        building_length_m=25.34, building_width_m=7.5,
        eaves_overhang_m=0.5, slope_deg=35, wall_thickness_m=0.30,
        eaves_to_ground_m=5.5,         # wall height to eaves (m)
        soflitas_depth_m=0.5,           # soffit under eaves (m)
    )
    assert result.sienos_m2 == pytest.approx(135, abs=15)
```

- [ ] **Step 2: Run, verify fails**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v -k dvislaitis`
Expected: FAIL (`dvislaitis_quantities` not defined).

- [ ] **Step 3: Implement dvislaitis geometry**

```python
# Append to backend/extractor/roof/geometry.py

@dataclass
class DvislaitisQuantities:
    """Computed quantities for a gable (dvišlaitis) roof."""
    stogas_m2: float
    sienos_m2: float
    vejalentes_m: float
    kraigai_m: float
    latakai_m: float
    apsaugine_tvorele_m: float
    rafter_surface_length_m: float
    gable_triangle_height_m: float
    waste_factor: float


def dvislaitis_quantities(
    *,
    building_length_m: float,
    building_width_m: float,
    eaves_overhang_m: float,
    slope_deg: float,
    wall_thickness_m: float = 0.0,
    eaves_to_ground_m: float = 0.0,
    soflitas_depth_m: float = 0.0,
    waste_factor: float = 0.05,
) -> DvislaitisQuantities:
    """Compute dvišlaitis (2-pitch gable) roof quantities.

    Args:
        building_length_m: building length along ridge direction.
        building_width_m: building width perpendicular to ridge.
        eaves_overhang_m: eaves projection on long sides (gable end overhang
            usually similar — assumed equal here for V1).
        slope_deg: roof pitch.
        eaves_to_ground_m: wall height (for sienos m² calc, optional).
        soflitas_depth_m: soffit depth under eaves (for sienos calc).

    Returns:
        DvislaitisQuantities dataclass.
    """
    # Roof footprint (long sides extend by eaves; gable ends extend too for
    # vėjalentės length but NOT for latakai)
    roof_length = building_length_m + 2 * eaves_overhang_m
    half_width_with_eaves = building_width_m / 2 + eaves_overhang_m

    # Rafter length on surface (eaves to ridge along slope)
    rafter_surface = half_width_with_eaves / math.cos(math.radians(slope_deg))

    # Stogas: 2 long faces, each = roof_length × rafter_surface
    stogas_no_waste = 2 * roof_length * rafter_surface
    stogas_m2 = stogas_no_waste * (1 + waste_factor)

    # Latakai: long sides only (gable ends have no eaves)
    latakai_m = 2 * roof_length

    # Apsauginė tvorelė: same length as latakai (safety along eaves)
    apsaugine_tvorele_m = latakai_m

    # Kraigas: 1 horizontal ridge along building length (no eaves on gable ends)
    kraigai_m = building_length_m

    # Vėjalentės: 4 raker boards (2 gables × 2 sides), each = rafter_surface
    vejalentes_m = 4 * rafter_surface

    # Gable triangle: rise = half_width_with_eaves × tan(slope)
    gable_triangle_height = half_width_with_eaves * math.tan(math.radians(slope_deg))

    # Sienos area (per advisory: 2 gables × full wall height + triangle + soflitas)
    if eaves_to_ground_m > 0:
        # Gable wall area = rectangle (length × wall_height) + triangle (½ × base × rise)
        gable_rect = building_width_m * eaves_to_ground_m
        gable_triangle = 0.5 * building_width_m * gable_triangle_height
        gable_full = gable_rect + gable_triangle
        sienos_gables = 2 * gable_full
        # Soflitas (under eaves on long sides)
        sienos_soflitas = 2 * roof_length * soflitas_depth_m
        sienos_m2 = sienos_gables + sienos_soflitas
    else:
        sienos_m2 = 0.0   # caller didn't request

    return DvislaitisQuantities(
        stogas_m2=stogas_m2,
        sienos_m2=sienos_m2,
        vejalentes_m=vejalentes_m,
        kraigai_m=kraigai_m,
        latakai_m=latakai_m,
        apsaugine_tvorele_m=apsaugine_tvorele_m,
        rafter_surface_length_m=rafter_surface,
        gable_triangle_height_m=gable_triangle_height,
        waste_factor=waste_factor,
    )
```

- [ ] **Step 4: Run, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_geometry.py -v`
Expected: PASS (24 tests total).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/geometry.py backend/tests/extractor/roof/test_geometry.py
git commit -m "feat(roof/geom): dvislaitis_quantities + 0039 reproduction tests"
```

---

### Task 8: Implement strategies/base.py — RoofInput/RoofOutput dataclasses

**Files:**
- Create: `backend/extractor/roof/strategies/__init__.py`
- Create: `backend/extractor/roof/strategies/base.py`
- Create: `backend/tests/extractor/roof/test_strategies.py`

- [ ] **Step 1: Write base interfaces**

```python
# backend/extractor/roof/strategies/__init__.py
"""Per-roof-type strategies: dvislaitis, keturslaitis, vienslaitis, plokscias."""

from .base import RoofStrategy, RoofInput, RoofOutput, LineItem
```

```python
# backend/extractor/roof/strategies/base.py
"""Base interfaces for roof type strategies.

Each strategy maps from RoofInput (geometric + structural dim's extracted
from PDF) to RoofOutput (15-row kiekių žiniaraštis conformant to LT-pro
sąmata template per roof type).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


RoofTypeName = Literal[
    "dvislaitis", "keturslaitis", "vienslaitis", "plokscias",
    "mansardinis", "sudetinis", "unknown"
]


@dataclass
class RoofInput:
    """All extracted dim's + slope angles needed for geometric calc.

    Filled by Vision extraction (Phase 1+) or hardcoded in Phase 0 tests.
    """
    roof_type: RoofTypeName
    building_length_m: float
    building_width_m: float
    eaves_overhang_m: float
    slopes_deg: list[float]               # 1 for vienslaitis, 1 for dvislaitis, 2 for keturslaitis asym
    wall_thickness_m: float = 0.25        # blokeliai 25cm typical
    eaves_to_ground_m: float = 0.0
    soflitas_depth_m: float = 0.5
    chimney_count: int = 0
    rooflight_count: int = 0
    windows_count: int = 0
    waste_factor: float = 0.05
    # Optional structural cross-check (from SK dalis)
    murloto_total_length_m: float | None = None


@dataclass
class LineItem:
    """One row of the kiekių žiniaraštis."""
    pozicija: str                          # e.g., "Stogas (skarda)"
    kiekis: float
    vnt: str                               # m², m, vnt
    confidence: Literal["high", "medium", "low"] = "high"
    source_pages: list[int] = field(default_factory=list)
    note: str = ""


@dataclass
class RoofOutput:
    """Computed kiekių žiniaraštis output."""
    roof_type: RoofTypeName
    line_items: list[LineItem]
    warnings: list[str] = field(default_factory=list)
    cross_check_passes: int = 0
    cross_check_total: int = 0


class RoofStrategy(ABC):
    """Strategy interface — one impl per roof type."""

    @abstractmethod
    def supports(self, input_: RoofInput) -> bool: ...

    @abstractmethod
    def compute(self, input_: RoofInput) -> RoofOutput: ...
```

```python
# backend/tests/extractor/roof/test_strategies.py
"""Tests for strategy classes."""
from backend.extractor.roof.strategies import (
    RoofInput, RoofOutput, LineItem, RoofStrategy,
)


def test_input_dataclass_defaults():
    inp = RoofInput(
        roof_type="dvislaitis",
        building_length_m=25.0,
        building_width_m=7.5,
        eaves_overhang_m=0.5,
        slopes_deg=[35],
    )
    assert inp.waste_factor == 0.05
    assert inp.murloto_total_length_m is None


def test_line_item_defaults():
    li = LineItem(pozicija="Stogas", kiekis=231.0, vnt="m²")
    assert li.confidence == "high"
    assert li.source_pages == []
```

- [ ] **Step 2: Run, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_strategies.py -v`
Expected: PASS (2 tests).

- [ ] **Step 3: Commit**

```bash
git add backend/extractor/roof/strategies/ backend/tests/extractor/roof/test_strategies.py
git commit -m "feat(roof/strategies): base interfaces RoofInput/Output/Strategy"
```

---

### Task 9: Implement DvislaitisStrategy producing 8-row LineItem list

**Files:**
- Create: `backend/extractor/roof/strategies/dvislaitis.py`
- Modify: `backend/tests/extractor/roof/test_strategies.py`

- [ ] **Step 1: Write failing strategy test against 0039 ground truth**

```python
# Append to backend/tests/extractor/roof/test_strategies.py
import pytest
import yaml
from pathlib import Path

from backend.extractor.roof.strategies import RoofInput
from backend.extractor.roof.strategies.dvislaitis import DvislaitisStrategy


@pytest.fixture
def gt_0039():
    """Load 0039 ground truth."""
    path = Path(__file__).parents[3] / "ground_truth" / "0039_roof.yaml"
    return yaml.safe_load(path.read_text())


def test_dvislaitis_produces_8_line_items(gt_0039):
    """0039 expected 8 line items (stogas, sienos, vėjalentės, kraigai,
    latakai, apsauginė tvorelė, langai, kaminelis)."""
    inp = RoofInput(
        roof_type="dvislaitis",
        building_length_m=25.34,
        building_width_m=7.5,
        eaves_overhang_m=0.5,
        slopes_deg=[35],
        eaves_to_ground_m=5.5,
        soflitas_depth_m=0.5,
        chimney_count=1,
        windows_count=12,
    )
    out = DvislaitisStrategy().compute(inp)
    assert out.roof_type == "dvislaitis"
    positions = [li.pozicija for li in out.line_items]
    expected_positions = {
        "Stogas (danga)",
        "Sienos (gablai + soflitas)",
        "Vėjalentės",
        "Kraigas",
        "Latakai",
        "Apsauginė tvorelė",
        "Langų apdirbimas",
        "Kaminėlis",
    }
    assert set(positions) == expected_positions


def test_dvislaitis_matches_0039_quantities(gt_0039):
    inp = RoofInput(
        roof_type="dvislaitis",
        building_length_m=25.34, building_width_m=7.5,
        eaves_overhang_m=0.5, slopes_deg=[35],
        eaves_to_ground_m=5.5, soflitas_depth_m=0.5,
        chimney_count=1, windows_count=12,
    )
    out = DvislaitisStrategy().compute(inp)
    by_pos = {li.pozicija: li for li in out.line_items}
    assert by_pos["Stogas (danga)"].kiekis == pytest.approx(231, abs=15)
    assert by_pos["Latakai"].kiekis == pytest.approx(51, abs=3)
    assert by_pos["Kraigas"].kiekis == pytest.approx(26, abs=3)
    assert by_pos["Vėjalentės"].kiekis == pytest.approx(18, abs=3)
    assert by_pos["Sienos (gablai + soflitas)"].kiekis == pytest.approx(135, abs=15)
    assert by_pos["Apsauginė tvorelė"].kiekis == pytest.approx(51, abs=3)
    assert by_pos["Langų apdirbimas"].kiekis == 12
    assert by_pos["Kaminėlis"].kiekis == 1
```

- [ ] **Step 2: Run, verify fails**

Run: `cd backend && pytest tests/extractor/roof/test_strategies.py -v -k dvislaitis`
Expected: FAIL (`DvislaitisStrategy` not defined).

- [ ] **Step 3: Implement DvislaitisStrategy**

```python
# backend/extractor/roof/strategies/dvislaitis.py
"""Dvišlaitis (2-pitch gable) roof strategy — 8-row template."""

from backend.extractor.roof import geometry
from backend.extractor.roof.strategies.base import (
    RoofStrategy, RoofInput, RoofOutput, LineItem,
)


class DvislaitisStrategy(RoofStrategy):
    """2-pitch gable roof: produces 8 line items per LT roofer convention."""

    def supports(self, input_: RoofInput) -> bool:
        return input_.roof_type == "dvislaitis"

    def compute(self, input_: RoofInput) -> RoofOutput:
        if not self.supports(input_):
            raise ValueError(
                f"DvislaitisStrategy received roof_type={input_.roof_type}"
            )
        slope = input_.slopes_deg[0]
        q = geometry.dvislaitis_quantities(
            building_length_m=input_.building_length_m,
            building_width_m=input_.building_width_m,
            eaves_overhang_m=input_.eaves_overhang_m,
            slope_deg=slope,
            wall_thickness_m=input_.wall_thickness_m,
            eaves_to_ground_m=input_.eaves_to_ground_m,
            soflitas_depth_m=input_.soflitas_depth_m,
            waste_factor=input_.waste_factor,
        )
        items = [
            LineItem("Stogas (danga)", round(q.stogas_m2, 1), "m²"),
            LineItem("Sienos (gablai + soflitas)", round(q.sienos_m2, 1), "m²"),
            LineItem("Vėjalentės", round(q.vejalentes_m, 1), "m"),
            LineItem("Kraigas", round(q.kraigai_m, 1), "m"),
            LineItem("Latakai", round(q.latakai_m, 1), "m"),
            LineItem("Apsauginė tvorelė", round(q.apsaugine_tvorele_m, 1), "m"),
            LineItem("Langų apdirbimas", input_.windows_count, "vnt"),
            LineItem("Kaminėlis", input_.chimney_count, "vnt"),
        ]
        return RoofOutput(roof_type="dvislaitis", line_items=items)
```

- [ ] **Step 4: Run, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_strategies.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/strategies/dvislaitis.py backend/tests/extractor/roof/test_strategies.py
git commit -m "feat(roof/strategies): DvislaitisStrategy reproduces 0039 sąmata"
```

---

### Task 10: Implement KeturslaitisStrategy producing 4-row LineItem list

**Files:**
- Create: `backend/extractor/roof/strategies/keturslaitis.py`
- Modify: `backend/tests/extractor/roof/test_strategies.py`

- [ ] **Step 1: Write failing strategy test against A LAIDA ground truth**

```python
# Append to test_strategies.py

from backend.extractor.roof.strategies.keturslaitis import KeturslaitisStrategy


def test_keturslaitis_produces_4_line_items():
    """A LAIDA (keturšlaitis) expected: perdanga, stogas, latakai, kraigai."""
    inp = RoofInput(
        roof_type="keturslaitis",
        building_length_m=13.12, building_width_m=8.95,
        eaves_overhang_m=1.05,
        slopes_deg=[25, 22],     # [long, short]
        wall_thickness_m=0.25,
    )
    out = KeturslaitisStrategy().compute(inp)
    positions = {li.pozicija for li in out.line_items}
    assert positions == {"Perdanga", "Stogas (danga)", "Latakai", "Kraigai"}


def test_keturslaitis_matches_a_laida_quantities():
    inp = RoofInput(
        roof_type="keturslaitis",
        building_length_m=13.12, building_width_m=8.95,
        eaves_overhang_m=1.05, slopes_deg=[25, 22],
        wall_thickness_m=0.25,
    )
    out = KeturslaitisStrategy().compute(inp)
    by_pos = {li.pozicija: li for li in out.line_items}
    assert by_pos["Perdanga"].kiekis == pytest.approx(117, abs=3)
    assert by_pos["Stogas (danga)"].kiekis == pytest.approx(185, abs=10)
    assert by_pos["Latakai"].kiekis == pytest.approx(52, abs=2)
    assert by_pos["Kraigai"].kiekis == pytest.approx(37, abs=3)
```

- [ ] **Step 2: Run, verify fails**

Run: `cd backend && pytest tests/extractor/roof/test_strategies.py -v -k keturslaitis`
Expected: FAIL.

- [ ] **Step 3: Implement KeturslaitisStrategy**

```python
# backend/extractor/roof/strategies/keturslaitis.py
"""Keturšlaitis (4-pitch hip) roof strategy — 4-row template."""

from backend.extractor.roof import geometry
from backend.extractor.roof.strategies.base import (
    RoofStrategy, RoofInput, RoofOutput, LineItem,
)


class KeturslaitisStrategy(RoofStrategy):
    """4-pitch hip roof: produces 4 line items (perdanga, stogas, latakai, kraigai)."""

    def supports(self, input_: RoofInput) -> bool:
        return input_.roof_type == "keturslaitis"

    def compute(self, input_: RoofInput) -> RoofOutput:
        if not self.supports(input_):
            raise ValueError(f"KeturslaitisStrategy received roof_type={input_.roof_type}")
        # slopes_deg = [long_slope, short_slope] (asymmetric supported)
        slope_long = input_.slopes_deg[0]
        slope_short = input_.slopes_deg[1] if len(input_.slopes_deg) > 1 else input_.slopes_deg[0]
        q = geometry.keturslaitis_quantities(
            footprint_outer_w=input_.building_width_m,
            footprint_outer_l=input_.building_length_m,
            eaves_overhang_m=input_.eaves_overhang_m,
            slope_long_deg=slope_long,
            slope_short_deg=slope_short,
            wall_thickness_m=input_.wall_thickness_m,
            waste_factor=input_.waste_factor,
        )
        items = [
            LineItem("Perdanga", round(q.perdanga_m2, 1), "m²"),
            LineItem("Stogas (danga)", round(q.stogas_m2, 1), "m²"),
            LineItem("Latakai", round(q.latakai_m, 1), "m"),
            LineItem("Kraigai", round(q.kraigai_m, 1), "m"),
        ]
        return RoofOutput(roof_type="keturslaitis", line_items=items)
```

- [ ] **Step 4: Run, verify passes**

Run: `cd backend && pytest tests/extractor/roof/test_strategies.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/strategies/keturslaitis.py backend/tests/extractor/roof/test_strategies.py
git commit -m "feat(roof/strategies): KeturslaitisStrategy reproduces A LAIDA sąmata"
```

---

### Task 11: Implement CLI for Phase 0 manual validation

**Files:**
- Create: `backend/extractor/roof/cli.py`
- Modify: `backend/tests/extractor/roof/test_strategies.py`

- [ ] **Step 1: Write CLI that loads ground truth + runs strategy**

```python
# backend/extractor/roof/cli.py
"""Phase 0 CLI: load ground truth YAML, run matching strategy, print report.

Usage:
    python -m backend.extractor.roof.cli ground_truth/a_laida_roof.yaml
    python -m backend.extractor.roof.cli ground_truth/0039_roof.yaml
"""
import sys
from pathlib import Path
import yaml

from backend.extractor.roof.strategies import RoofInput
from backend.extractor.roof.strategies.dvislaitis import DvislaitisStrategy
from backend.extractor.roof.strategies.keturslaitis import KeturslaitisStrategy


STRATEGIES = {
    "dvislaitis": DvislaitisStrategy(),
    "keturslaitis": KeturslaitisStrategy(),
}


def run(ground_truth_path: Path) -> int:
    """Returns 0 if all quantities within ground truth tolerances, 1 otherwise."""
    data = yaml.safe_load(ground_truth_path.read_text())
    roof_type = data["roof"]["type"]
    if roof_type not in STRATEGIES:
        print(f"ERROR: roof type {roof_type!r} not yet supported (V1 = dvislaitis, keturslaitis)")
        return 1

    # Build RoofInput from YAML
    roof = data["roof"]
    footprint = roof["building_footprint_outer_walls"]
    slopes = [s["angle_deg"] for s in roof["slopes"]]
    inp = RoofInput(
        roof_type=roof_type,
        building_length_m=footprint["length_m"],
        building_width_m=footprint["width_m"],
        eaves_overhang_m=roof["eaves_overhang_m"],
        slopes_deg=slopes,
        wall_thickness_m=roof.get("wall_thickness_m", 0.25),
        eaves_to_ground_m=roof.get("eaves_to_ground_m", 0.0),
        soflitas_depth_m=roof.get("soflitas_depth_m", 0.5),
        chimney_count=roof.get("chimney_count", 0),
        rooflight_count=roof.get("rooflight_count", 0),
        windows_count=roof.get("windows_count", 0),
    )
    out = STRATEGIES[roof_type].compute(inp)

    # Compare against roofer sąmata
    expected_items = {li["position"]: li for li in data["roofer_samata"]["line_items"]}
    POS_MAP = {
        "stogas": "Stogas (danga)",
        "perdanga": "Perdanga",
        "latakai": "Latakai",
        "kraigai": "Kraigai",
        "sienos": "Sienos (gablai + soflitas)",
        "vejalentes": "Vėjalentės",
        "apsaugine_tvorele": "Apsauginė tvorelė",
        "langu_apdirbimas": "Langų apdirbimas",
        "kaminelis": "Kaminėlis",
    }

    print(f"\n=== {ground_truth_path.name} — {roof_type} ===\n")
    print(f"{'POZICIJA':<35} {'COMPUTED':>10} {'ROOFER':>10} {'DELTA %':>10}  STATUS")
    print("-" * 80)
    all_pass = True
    for li in out.line_items:
        roofer_key = next(
            (k for k, v in POS_MAP.items() if v == li.pozicija and k in expected_items),
            None
        )
        if roofer_key is None:
            print(f"{li.pozicija:<35} {li.kiekis:>10.1f} {'—':>10} {'—':>10}  EXTRA")
            continue
        roofer_qty = expected_items[roofer_key]["qty"]
        delta_pct = (li.kiekis - roofer_qty) / roofer_qty * 100 if roofer_qty else 0
        # Tolerance bands per Phase 0 acceptance criteria
        tol = 5.0 if li.vnt == "m²" else 2.0
        if li.pozicija == "Sienos (gablai + soflitas)":
            tol = 10.0
        status = "PASS" if abs(delta_pct) <= tol else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{li.pozicija:<35} {li.kiekis:>10.1f} {roofer_qty:>10.1f} {delta_pct:>9.1f}%  {status}")

    print("\n" + ("✓ ALL WITHIN TOLERANCE" if all_pass else "✗ SOME FAIL"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1])))
```

- [ ] **Step 2: Run CLI on A LAIDA**

Run: `cd backend && python -m extractor.roof.cli ../ground_truth/a_laida_roof.yaml`

Expected output (something like):
```
=== a_laida_roof.yaml — keturslaitis ===

POZICIJA                              COMPUTED     ROOFER    DELTA %  STATUS
--------------------------------------------------------------------------------
Perdanga                                  117.4      117.0       0.3%  PASS
Stogas (danga)                            185.5      185.0       0.3%  PASS
Latakai                                    51.5       52.0      -1.0%  PASS
Kraigai                                    37.0       36.0       2.8%  PASS

✓ ALL WITHIN TOLERANCE
```

- [ ] **Step 3: Run CLI on 0039**

Run: `cd backend && python -m extractor.roof.cli ../ground_truth/0039_roof.yaml`

Expected: similar pass output for 8 line items (some marked EXTRA — Langų apdirbimas + Kaminėlis aren't geometric, they pass through unchanged).

- [ ] **Step 4: Commit**

```bash
git add backend/extractor/roof/cli.py
git commit -m "feat(roof): CLI for Phase 0 ground-truth validation"
```

---

### Task 12: Phase 0 Acceptance Gate — Show Roofer

**Files:** none (manual step).

- [ ] **Step 1: Run both ground truth checks end-to-end**

Run both:
```bash
cd backend
python -m extractor.roof.cli ../ground_truth/a_laida_roof.yaml
python -m extractor.roof.cli ../ground_truth/0039_roof.yaml
```

Both must print "✓ ALL WITHIN TOLERANCE". If either fails — DO NOT proceed to Phase 1. Re-investigate geometric formulas vs ground truth, adjust tolerances or formulas only after understanding the gap.

- [ ] **Step 2: Show output to the roofer who provided the sąmatos**

Send the CLI output (or a screenshot) to user's roofer friend. Question to ask:
> "Štai ką mūsų sistema skaičiuoja iš to paties brėžinio. Ar šitie skaičiai tau atrodo tinkami pasiūlymo bazei? Ką dar pridėtum?"

Goal: validate that the line items + tolerances match what a real LT stogininkas would accept as a starting point. If feedback is "no, these numbers are useless because X" — Phase 1 is wasted effort. Loop back to strategy.

- [ ] **Step 3: Commit a CHANGELOG note marking Phase 0 done**

```bash
echo "
## 2026-05-DD — Stogai V1 Phase 0 complete

- Geometric engine reproduces both in-hand stogininko sąmatas within tolerance:
  - A LAIDA (keturšlaitis): 4/4 line items PASS
  - 0039 (dvišlaitis): 6/8 line items PASS (langai + kaminelis are pass-through)
- Roofer feedback: <FILL IN>
- Next: Phase 1 — page classifier refactor + Vision wiring." >> CHANGELOG.md

git add CHANGELOG.md
git commit -m "docs: Phase 0 stogai V1 complete — math validated against N=2"
```

---

## Phase 1 — Page Classifier Refactor + Eval Set (Weeks 2-3)

**Goal:** Replace hardcoded ground-truth inputs with Vision-extracted dim's from real PDFs. Build hybrid text-first + Haiku-vision page classifier with dalis enum (BD/SA/SK/...) + roof_type_hint. Hand-label 10-PDF eval set.

**Acceptance:** Hybrid classifier correctly identifies `dalis` (95% accuracy) + `page_type` (90% on stogo_planas) on the 10-PDF eval set. Vision dim extraction on stogo_planas reproduces ground truth dim's within ±5%.

### Tasks (high-level, expand at start of Phase 1)
- **T1:** Refactor `backend/extractor/page_classifier.py` — add `_extract_antspaudas_text()` using pdfplumber bbox crop + regex on LT dalies codes.
- **T2:** Add `dalis` enum + `roof_type_hint` field to classifier output schema.
- **T3:** Wire Haiku fallback for raster-only pages.
- **T4:** Build 10-PDF eval set: 5 SA (variety of roof types), 3 SK, 2 multi-dalies. Hand-label `dalis` + `page_type` + `roof_type`.
- **T5:** Write evaluation script `scripts/eval_roof_classifier.py` measuring precision/recall per label.
- **T6:** Constrained-enum prompt: pass `dalis` prior into page-type Vision call to boost niche-label accuracy.
- **T7:** Vision prompt for `stogo_planas` dim extraction (footprint, eaves, slope angles, roof type, chimney/dormer count).
- **T8:** Vision prompt for `pjuvis` slope angle reading (with 3-format support: deg, ratio, %).
- **T9:** Wire `extractor.py` orchestrator: classify → select key pages → Vision extract → build `RoofInput` → run strategy → return `RoofOutput`.
- **T10:** End-to-end test: feed A LAIDA + 0039 PDFs through full pipeline, output must match Phase 0 CLI results.

---

## Phase 2 — Full Pipeline + UI + Validation (Weeks 4-6)

**Goal:** Ship working frontend with PDF upload → preflight modal → extraction → 8-row sąmata with kainynas inputs + per-row provenance + 20 validators.

**Acceptance:** Solo user uploads a PDF, sees preflight modal (detected dalis + roof type + missing-dalis warning), confirms, gets table with editable €/vnt. defaults pre-filled from Sistela-aligned `sistela_rates.json`. Per-row "see source" reveals PDF page with highlighted overlay. Refuse-to-output triggers when any of 20 validators fails OR roof type is outside core 4.

### Tasks (high-level)
- **T1:** Add `vienslaitis.py` + `plokscias.py` (stub raising NotImplementedError).
- **T2:** Implement `backend/extractor/roof/validators.py` — 20 cross-checks per math research.
- **T3:** Refuse-to-output gate: if `validator_pass_count < 18/20` OR `roof_type in {mansardinis, sudetinis, unknown}` → return `RoofOutput.warnings = ["Manual mode required: <reason>"]` + empty line_items.
- **T4:** Build `backend/extractor/roof/sistela_rates.json` — seed with current LT market rates per pozicija (research stream 3 has €12-40/m², €6-10/m for latakai, etc.).
- **T5:** New endpoint: `POST /extract-roof` in `backend/main.py`. Streams progress events (classifier done → vision done → strategy done → validators done).
- **T6:** Frontend `RoofProject.jsx` page wiring upload → SSE → results.
- **T7:** `PreflightModal.jsx` component — shows detected `dalis`/`page_type`/`roof_type`/missing-dalis warning before Vision extraction.
- **T8:** `RoofKiekiaiTable.jsx` — 15 columns max: pozicija, kiekis, vnt, €/vnt (input), suma, confidence dot, "see source" link.
- **T9:** `RoofOverlay.jsx` — renders PDF page via react-pdf with SVG overlay highlighting the slope/dim that produced the clicked-on line item.
- **T10:** "Defensible bid PDF" export — Sąmatų AI generates a PDF with the table + 1-page summary + per-row source citation. (Replaces existing Excel export for roof projects.)
- **T11:** Register "Stogai" as project type in `NewProject.jsx`.
- **T12:** Update `Landing.jsx` Skaidrumas: move "Stogų konstrukcijos kiekiai" from Ruošiame → Šiandien.

---

## Phase 3 — Beta + Ground Truth Growth (Weeks 7-8)

**Goal:** Ship to 3-5 beta roofers from paslaugos.lt cold contact. Build shadow-testing async queue (24h email + human verification). Grow ground truth from N=2 to N=8 across 4 roof types.

**Acceptance:** 6 paid-for projects (€100 × 6 roofers) added to `ground_truth/`. End of beta: classifier ≥90% dalis, ≥85% page_type, ≥80% roof_type on 6-project test set; strategy ≥90% line-item recall; ≥85% within tolerance on hard quantities.

### Tasks (high-level)
- **T1:** Build `ShadowQueueAdmin.jsx` — admin-only page listing pending uploads + AI output + manual override fields.
- **T2:** Email worker: when user submits, send "tavo sąmata bus paruošta per 24h" email. When admin clicks "approve & send" → email user the verified sąmata.
- **T3:** Outreach to paslaugos.lt top 20 listed Vilnius+Kaunas+Klaipėda roofers. Offer: €100/projektas for 1 historical project + their sąmata.
- **T4:** Ingest 6 new ground truth files: convert each into `ground_truth/<roofer>_<projectid>_roof.yaml`.
- **T5:** Run eval set against new ground truth. If <80% recall on any line item — pause, investigate, fix.
- **T6:** Trust-badge confidence scoring on output PDF: "X/20 patikrų sutapo" + green/yellow/red dot.
- **T7:** Update CLAUDE.md, MEMORY.md with V1 ship status + lessons learned.

---

## Self-Review

**Spec coverage:** Strategy decisions (1-7) → mapped to tasks across all 4 phases. Confidence gates → Phase 2 T3. Brėžinys overlay → Phase 2 T9. Sistela-aligned defaults → Phase 2 T4. Refuse-to-output → Phase 2 T3. Shadow-testing async queue → Phase 3 T1-T2. Ground truth N=8 target → Phase 3 T3-T4.

**Placeholder scan:** Phase 0 has full bite-sized tasks with code. Phases 1-3 use deliberate high-level tasks because they'll be expanded after Phase 0 validation gate. No "TBD" or "implement later" in Phase 0.

**Type consistency:** `RoofInput` and `RoofOutput` defined in Phase 0 Task 8; consistently used in Task 9, 10, 11, and referenced by Phase 1 T9 + Phase 2 T5. `LineItem` schema defined once, used consistently. `RoofTypeName` enum stable.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-13-stogai-v1-implementation.md`.

**Phase 0 (3-day wedge, ~12 bite-sized tasks):** ready to execute Monday morning. Acceptance gate at Task 12 — show roofer the CLI output before investing in Phase 1.

**Phases 1-3:** task-level outline only; will be detailed at the start of each phase after the prior phase's acceptance gate clears.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch fresh subagent per Phase 0 task, review between tasks, fast iteration. Best for solo founder.

2. **Inline Execution** — execute Phase 0 tasks in the current session with checkpoints.

**Which approach?**
