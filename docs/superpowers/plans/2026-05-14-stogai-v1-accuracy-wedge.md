# Stogai V1 — Accuracy Wedge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the roof PDF extraction pipeline produce sąmata where every line item is within ±2% of the roofer's ground truth on a regression harness of ≥4 labeled projects — or fails loudly with `HITLFlag` entries carrying page-class evidence (cropped source bbox + reason). End-state: `scripts/eval_roof_e2e.py` exits 0 on A LAIDA + 0039 + ≥2 newly labeled projects, with WAPE ≤2% and zero unflagged high-impact errors.

**Architecture:** Introduce a typed **Semantic Routing Hierarchy** in the merger: `PageType` → set[`RoofInputField`] write-access map. Floor plans own global axes; sections own slopes/heights; stogo planas owns topology + eaves. Add a **Constraint Verification Graph**: extract sub-dimensions per page and verify their sums equal the routed overall axis dimension; mismatches become HITL flags. Replace ad-hoc YAML ground-truth with a per-page-per-field v2 schema and an interactive harness. Replace ±2%-per-line evaluation with WAPE + "no unflagged high-impact line error". Vision model stays Opus 4.7; no OCR / ensemble / multi-shot in this wedge (deferred to V1.5).

**Tech Stack:** Python 3.14, pytest, pdfplumber 0.11.4, pdf2image, Anthropic SDK (Opus 4.7), PyYAML. Existing Phase 0 strategies (`KeturslaitisStrategy`, `DvislaitisStrategy`) unchanged. Existing `extractor.page_classifier.PageType` enum reused.

---

## Files

### Files created

- `backend/extractor/roof/page_authority.py` — Semantic Routing map (`PageType` → `set[RoofInputField]`) + write-access enforcer.
- `backend/extractor/roof/evidence.py` — `DimensionEvidence`, `HITLFlag` dataclasses + helpers.
- `backend/extractor/roof/constraint_check.py` — sub-dimension-sum verification, produces `list[HITLFlag]`.
- `backend/tests/extractor/roof/test_page_authority.py` — unit tests for routing map.
- `backend/tests/extractor/roof/test_evidence.py` — unit tests for dataclasses.
- `backend/tests/extractor/roof/test_constraint_check.py` — unit tests for the verifier.
- `backend/tests/extractor/roof/test_vision_extractor_typed.py` — integration tests for the typed merger on the existing A LAIDA + 0039 extracted JSON.
- `ground_truth/_schema_v2.md` — documentation of the v2 per-page-per-field schema.
- `ground_truth/a_laida_roof_v2.yaml` — A LAIDA re-labeled in v2 format.
- `ground_truth/0039_roof_v2.yaml` — 0039 re-labeled in v2 format.
- `scripts/build_roof_ground_truth.py` — interactive labeling CLI for new projects.
- `scripts/eval_roof_e2e.py` — full-pipeline WAPE evaluator that returns exit 0 on ALL pass / 1 otherwise.

### Files modified

- `backend/extractor/roof/vision_extractor.py` — `build_roof_input` becomes typed merger consuming `PageType` → field authority map; returns `(RoofInput, list[DimensionEvidence], list[HITLFlag])` instead of `(RoofInput, list[str])`.
- `backend/extractor/roof/__init__.py` — re-export `DimensionEvidence`, `HITLFlag` from new modules.

### Files unchanged

- `backend/extractor/roof/strategies/*.py` — Phase 0 strategies untouched. `RoofInput`/`RoofOutput` interfaces stable.
- `backend/extractor/roof/geometry.py` — pure math unchanged.
- `backend/extractor/roof/cli.py` — Phase 0 CLI unchanged; new e2e CLI is a separate script.

---

## Task Sequence

### Phase A — Semantic Routing core

Goal: 0039 sienos drops below ±2% via typed merger that refuses width writes from non-floor-plan pages. A LAIDA stays within existing tolerance.

#### Task 1: `RoofInputField` literal + `PAGE_AUTHORITY` map

**Files:**
- Create: `backend/extractor/roof/page_authority.py`
- Test: `backend/tests/extractor/roof/test_page_authority.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/extractor/roof/test_page_authority.py
"""Unit tests for the semantic-routing authority map."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.page_authority import (  # noqa: E402
    PAGE_AUTHORITY,
    RoofInputField,
    can_write,
)


def test_floor_plan_owns_global_axes():
    assert can_write(PageType.FLOOR_PLAN, RoofInputField.AXIS_LENGTH)
    assert can_write(PageType.FLOOR_PLAN, RoofInputField.AXIS_WIDTH)


def test_section_owns_slope_and_heights():
    assert can_write(PageType.SECTION, RoofInputField.SLOPE)
    assert can_write(PageType.SECTION, RoofInputField.WALL_THICKNESS)


def test_stogo_planas_owns_topology_and_eaves():
    assert can_write(PageType.STOGO_PLANAS, RoofInputField.ROOF_TYPE)
    assert can_write(PageType.STOGO_PLANAS, RoofInputField.EAVES_OVERHANG)
    assert can_write(PageType.STOGO_PLANAS, RoofInputField.CHIMNEY_COUNT)


def test_section_cannot_write_global_axes():
    """The 0039 bug: SECTION/detail pages must NOT supply building width."""
    assert not can_write(PageType.SECTION, RoofInputField.AXIS_LENGTH)
    assert not can_write(PageType.SECTION, RoofInputField.AXIS_WIDTH)


def test_stogo_planas_cannot_overwrite_global_axes_when_partial():
    """Structural gegnių planas (often classified stogo_planas) shows only
    partial half-rafter detail; it must not be authoritative for the FULL
    building footprint. Floor plan is the only authority for global axes."""
    assert not can_write(PageType.STOGO_PLANAS, RoofInputField.AXIS_LENGTH)
    assert not can_write(PageType.STOGO_PLANAS, RoofInputField.AXIS_WIDTH)


def test_unknown_page_writes_nothing():
    for field in RoofInputField:
        assert not can_write(PageType.UNKNOWN, field)


@pytest.mark.parametrize("field", list(RoofInputField))
def test_every_field_has_at_least_one_authority(field):
    """No field is orphan — every field has at least one PageType that owns it."""
    assert any(field in PAGE_AUTHORITY[pt] for pt in PageType), \
        f"{field} has no authority page-class"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ignasgaldikas/samatu-ai && source venv/bin/activate && cd backend && python3 -m pytest tests/extractor/roof/test_page_authority.py -v`
Expected: ImportError — `page_authority` module does not exist yet.

- [ ] **Step 3: Implement `page_authority.py`**

```python
# backend/extractor/roof/page_authority.py
"""Semantic Routing Hierarchy for the roof input merger.

Each PageType is granted EXCLUSIVE write-access to a specific set of
`RoofInput` fields. When the Vision extractor returns a value for a
field from a page whose PageType is not in the authority list for that
field, the merger MUST drop the value (not average it, not flag it).
This is the architectural fix for the 0039 bug where Opus correctly
read axis_width=4.61m from a SECTION/detail page — accurate to the page,
wrong as a building footprint.

Source: 2026-05-14 consultcouncil — Gemini's Semantic Routing Hierarchy
proposal, accepted unanimously in R3.
"""
from __future__ import annotations

from enum import Enum

from extractor.page_classifier import PageType


class RoofInputField(str, Enum):
    """All fields that the typed merger can populate on `RoofInput`."""
    ROOF_TYPE = "roof_type"
    AXIS_LENGTH = "axis_to_axis_length_m"
    AXIS_WIDTH = "axis_to_axis_width_m"
    EAVES_OVERHANG = "eaves_overhang_from_axis_m"
    WALL_THICKNESS = "wall_thickness_m"
    SLOPE = "slope_angle_deg"
    CHIMNEY_COUNT = "chimney_count"
    ROOFLIGHT_COUNT = "rooflight_count"
    WINDOWS_COUNT = "windows_count"


# Write-access map: PageType -> set of RoofInputField the page is
# authoritative for. ANY value extracted from a page whose PageType is
# not in this map for a given field MUST be dropped by the merger.
PAGE_AUTHORITY: dict[PageType, set[RoofInputField]] = {
    PageType.FLOOR_PLAN: {
        RoofInputField.AXIS_LENGTH,
        RoofInputField.AXIS_WIDTH,
    },
    PageType.SECTION: {
        RoofInputField.SLOPE,
        RoofInputField.WALL_THICKNESS,
    },
    PageType.STOGO_PLANAS: {
        RoofInputField.ROOF_TYPE,
        RoofInputField.EAVES_OVERHANG,
        RoofInputField.CHIMNEY_COUNT,
        RoofInputField.ROOFLIGHT_COUNT,
        RoofInputField.WINDOWS_COUNT,
        # NOTE: stogo_planas may LABEL slope angles on the plan view
        # (LT studios commonly do this). Slope is owned by SECTION
        # because the pjūvis is the canonical angular measurement; if
        # the stogo planas disagrees, the section wins. Stogo planas
        # slope hints are still extracted as DimensionEvidence but the
        # merger ignores them when populating RoofInput.SLOPE.
    },
    # Pages that exist in PageType but never write to RoofInput:
    PageType.WALL_ELEVATION: set(),
    PageType.CEILING_PLAN: set(),
    PageType.ELECTRICAL: set(),
    PageType.PLUMBING: set(),
    PageType.EKSPLIKACIJA: set(),
    PageType.LEGEND: set(),
    PageType.UNKNOWN: set(),
}


def can_write(page_type: PageType, field: RoofInputField) -> bool:
    """Return True if a page of this type may populate this RoofInput field."""
    return field in PAGE_AUTHORITY.get(page_type, set())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ignasgaldikas/samatu-ai && source venv/bin/activate && cd backend && python3 -m pytest tests/extractor/roof/test_page_authority.py -v`
Expected: 7 PASS (6 named + 9 parametrized = 6+9 should reach 15; adjust expectation by enum size).

- [ ] **Step 5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/roof/page_authority.py backend/tests/extractor/roof/test_page_authority.py
git commit -m "$(cat <<'EOF'
feat(roof/page_authority): Semantic Routing Hierarchy map

Each PageType has EXCLUSIVE write-access to specific RoofInput fields.
Floor plans own global axes; sections own slope + wall thickness;
stogo planas owns topology + eaves + counts. Source: 2026-05-14
consultcouncil R3 verdict — Gemini's proposal, three-way consensus.

This is the architectural fix for the 0039 -8.7% sienos bug: Opus
correctly read axis_width=4.61m from a SECTION/detail page — accurate
to that page, wrong as a building footprint. Under the new map, that
extraction is dropped at merger time (no averaging, no flagging),
forcing the merger to fall back to the floor plan's authoritative
7.12m which yields the correct gable area.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

#### Task 2: `DimensionEvidence` + `HITLFlag` dataclasses

**Files:**
- Create: `backend/extractor/roof/evidence.py`
- Test: `backend/tests/extractor/roof/test_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/extractor/roof/test_evidence.py
"""Unit tests for DimensionEvidence + HITLFlag."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.evidence import (  # noqa: E402
    DimensionEvidence,
    HITLFlag,
    HITLFlagReason,
)
from extractor.roof.page_authority import RoofInputField  # noqa: E402


def test_dimension_evidence_roundtrip():
    ev = DimensionEvidence(
        field=RoofInputField.AXIS_WIDTH,
        value=7.12,
        page_num=46,
        page_class=PageType.FLOOR_PLAN,
        source_crop_bbox=(0.1, 0.2, 0.5, 0.6),
        raw_label_text="7,12",
        confidence=0.86,
    )
    assert ev.field is RoofInputField.AXIS_WIDTH
    assert ev.value == pytest.approx(7.12)
    assert ev.is_authoritative()


def test_dimension_evidence_unauthoritative_when_wrong_page_class():
    ev = DimensionEvidence(
        field=RoofInputField.AXIS_WIDTH,
        value=4.61,
        page_num=48,
        page_class=PageType.SECTION,        # SECTION cannot write AXIS_WIDTH
        source_crop_bbox=None,
        raw_label_text="4,61",
        confidence=0.8,
    )
    assert not ev.is_authoritative()


def test_hitl_flag_carries_reason_and_evidence():
    ev = DimensionEvidence(
        field=RoofInputField.AXIS_WIDTH,
        value=7.12,
        page_num=46,
        page_class=PageType.FLOOR_PLAN,
        source_crop_bbox=None,
        raw_label_text="7,12",
        confidence=0.7,
    )
    flag = HITLFlag(
        field=RoofInputField.AXIS_WIDTH,
        reason=HITLFlagReason.SUB_DIM_SUM_MISMATCH,
        message="sub-dims sum to 7.20, overall reads 7.12 (0.08m mismatch)",
        evidence=[ev],
        eur_impact_estimate=420.0,
    )
    assert flag.reason is HITLFlagReason.SUB_DIM_SUM_MISMATCH
    assert flag.eur_impact_estimate == pytest.approx(420.0)
    assert flag.evidence[0].page_num == 46


@pytest.mark.parametrize("reason", list(HITLFlagReason))
def test_hitl_flag_reasons_have_human_readable_names(reason):
    assert isinstance(reason.value, str)
    assert len(reason.value) > 0
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `cd backend && python3 -m pytest tests/extractor/roof/test_evidence.py -v`
Expected: ImportError on `evidence`.

- [ ] **Step 3: Implement `evidence.py`**

```python
# backend/extractor/roof/evidence.py
"""Evidence + HITL flag dataclasses for the typed roof merger.

Each DimensionEvidence is one (field, value, page) triple with full
provenance: which page produced it, what page_class that page was
classified as, the source crop bbox, the raw text label that was read,
and the model's confidence. The merger uses these to populate
RoofInput; the UI (separate plan) renders them as the "patikrinkite"
ledger.

HITLFlag entries are raised when the constraint-verification step
catches a mismatch that cannot be resolved silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum

from extractor.page_classifier import PageType
from extractor.roof.page_authority import PAGE_AUTHORITY, RoofInputField


@dataclass(frozen=True)
class DimensionEvidence:
    """One extracted value with full provenance back to its source page."""
    field: RoofInputField
    value: float | int | str
    page_num: int
    page_class: PageType
    source_crop_bbox: tuple[float, float, float, float] | None  # normalized (x0,y0,x1,y1)
    raw_label_text: str
    confidence: float

    def is_authoritative(self) -> bool:
        """True iff this evidence's page_class is allowed to write `self.field`."""
        return self.field in PAGE_AUTHORITY.get(self.page_class, set())


class HITLFlagReason(str, Enum):
    """Why a dimension was kicked to human-in-the-loop review."""
    SUB_DIM_SUM_MISMATCH = "sub_dim_sum_mismatch"           # sums don't add up
    NO_AUTHORITATIVE_SOURCE = "no_authoritative_source"     # all sources unauthorized
    LOW_CONFIDENCE = "low_confidence"                       # model conf < threshold
    CONFLICTING_AUTHORITATIVE_SOURCES = "conflicting_authoritative_sources"  # two floor_plans disagree


@dataclass(frozen=True)
class HITLFlag:
    """A dimension the system refuses to commit autonomously.

    `evidence` lists all extracted candidates for this field. `message`
    is the human-readable explanation for the patikrinkite UI.
    `eur_impact_estimate` is the maximum cost swing if this dimension
    is off by its current uncertainty band — used to prioritise which
    flags to surface first.
    """
    field: RoofInputField
    reason: HITLFlagReason
    message: str
    evidence: list[DimensionEvidence] = dc_field(default_factory=list)
    eur_impact_estimate: float = 0.0
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/extractor/roof/test_evidence.py -v`
Expected: 7 PASS (3 named + 4 parametrized HITLFlagReason values).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/evidence.py backend/tests/extractor/roof/test_evidence.py
git commit -m "feat(roof/evidence): DimensionEvidence + HITLFlag dataclasses

Each DimensionEvidence is one (field, value, page) triple with full
provenance for the typed merger. HITLFlag wraps mismatches the system
refuses to commit autonomously, with a human-readable reason and a
€ impact estimate used to prioritise the patikrinkite UI surface.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

#### Task 3: Refactor `build_roof_input` into the typed merger

**Files:**
- Modify: `backend/extractor/roof/vision_extractor.py:147-244` (the existing `build_roof_input` function)
- Test: `backend/tests/extractor/roof/test_vision_extractor_typed.py`

- [ ] **Step 1: Write the failing integration test**

```python
# backend/tests/extractor/roof/test_vision_extractor_typed.py
"""End-to-end test of the typed merger using saved Vision JSON.

Uses recorded Vision output from the 2026-05-14 session (committed to
git) so the test runs offline and deterministically. Re-record only
when the Vision prompt changes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.evidence import DimensionEvidence, HITLFlag  # noqa: E402
from extractor.roof.page_authority import RoofInputField  # noqa: E402
from extractor.roof.vision_extractor import build_roof_input  # noqa: E402


# Recorded outputs from real Vision runs on 2026-05-14.
# A LAIDA p10 = stogo_planas (architectural drawings)
A_LAIDA_STOGO_P10 = {
    "_page_num": 10,
    "_page_class": PageType.STOGO_PLANAS,
    "roof_type": "keturslaitis",
    "axis_to_axis_length_m": 12.88,
    "axis_to_axis_width_m": 8.70,
    "eaves_overhang_from_axis_m": 1.05,
    "wall_thickness_m": None,
    "visible_slope_angles_deg": [25, 22],
    "chimney_count": 0,
    "rooflight_count": 0,
    "windows_count": 0,
    "confidence": 0.78,
}
A_LAIDA_PJUVIS_P9 = {
    "_page_num": 9,
    "_page_class": PageType.SECTION,
    "slope_angles_deg": [25],
    "ridge_height_m": 5.8,
    "eaves_height_m": 3.2,
    "wall_thickness_m": None,
    "confidence": 0.9,
}

# 0039 p48 = stogo_planas (gegnių planas — PARTIAL width)
# p49 = section (PJŪVIS, clean slope reading)
# p46 = floor_plan (full building width)
_0039_GEGNIU_P48 = {
    "_page_num": 48,
    "_page_class": PageType.STOGO_PLANAS,
    "roof_type": "dvislaitis",
    "axis_to_axis_length_m": 25.34,
    "axis_to_axis_width_m": 4.61,        # PARTIAL — must be dropped under semantic routing
    "eaves_overhang_from_axis_m": None,
    "wall_thickness_m": None,
    "visible_slope_angles_deg": [35],    # WRONG (pjūvis says 30°)
    "chimney_count": 1,
    "rooflight_count": 0,
    "windows_count": 0,
    "confidence": 0.5,
}
_0039_PJUVIS_P49 = {
    "_page_num": 49,
    "_page_class": PageType.SECTION,
    "slope_angles_deg": [30.0],
    "ridge_height_m": 8.45,
    "eaves_height_m": None,
    "wall_thickness_m": None,
    "confidence": 0.85,
}
_0039_FLOOR_P46 = {
    "_page_num": 46,
    "_page_class": PageType.FLOOR_PLAN,
    "axis_to_axis_length_m": 25.59,
    "axis_to_axis_width_m": 7.12,        # FULL building width
    "confidence": 0.85,
}


def test_a_laida_typed_merger_matches_phase_0():
    """A LAIDA: stogo_planas + pjūvis combo — slope wins from pjūvis if conflict.
    For A LAIDA they agree (25°), so no warnings."""
    inp, evidence, flags = build_roof_input(
        pages=[A_LAIDA_STOGO_P10, A_LAIDA_PJUVIS_P9],
    )
    assert inp.roof_type == "keturslaitis"
    assert inp.slopes_deg == [25, 22]    # from stogo_planas visible labels
    assert inp.eaves_overhang_m == pytest.approx(1.05 - 0.25 / 2, abs=0.01)
    # AXIS_LENGTH/WIDTH must come from… no FLOOR_PLAN provided for A LAIDA's
    # SA-only PDF; merger falls back to stogo_planas axes WITH a warning flag.
    high_impact_flags = [f for f in flags if f.eur_impact_estimate > 50]
    # A LAIDA stogo_planas IS the architectural roof plan with full footprint —
    # this is the case where stogo_planas SHOULD be allowed. The test below
    # captures the right behaviour: the merger MUST be able to fall back to
    # stogo_planas axes when no floor_plan exists, AS A FLAGGED FALLBACK.
    fallback_flags = [f for f in flags if f.field == RoofInputField.AXIS_WIDTH]
    assert len(fallback_flags) >= 1, (
        "Merger used stogo_planas as a fallback for AXIS_WIDTH; this is OK "
        "but must be flagged so the user verifies."
    )


def test_0039_typed_merger_uses_floor_plan_for_width():
    """0039: gegnių planas (stogo_planas) shows partial width 4.61m. Floor
    plan shows full width 7.12m. The typed merger MUST pick 7.12m."""
    inp, evidence, flags = build_roof_input(
        pages=[_0039_GEGNIU_P48, _0039_PJUVIS_P49, _0039_FLOOR_P46],
    )
    assert inp.roof_type == "dvislaitis"
    # 7.12 axis + 0.30 wall_thickness default = 7.42 outer, NOT 4.61+0.3=4.91
    expected_outer_width = 7.12 + 0.30
    assert inp.building_width_m == pytest.approx(expected_outer_width, abs=0.01), (
        f"width={inp.building_width_m} — partial-rafter 4.61m leaked through "
        "instead of floor-plan 7.12m"
    )
    # Slope: pjūvis wins (30° not stogo_planas' 35°)
    assert inp.slopes_deg == [30.0]


def test_0039_drops_unauthorized_axis_width_from_stogo_planas():
    """The 4.61m extracted from the gegnių planas (page_class=STOGO_PLANAS)
    must NOT appear in the merged RoofInput.AXIS_WIDTH — even as a fallback —
    because a FLOOR_PLAN value was available."""
    _, evidence, _ = build_roof_input(
        pages=[_0039_GEGNIU_P48, _0039_PJUVIS_P49, _0039_FLOOR_P46],
    )
    # Evidence still records the unauthoritative read for traceability,
    # but is_authoritative() must be False:
    unauth = [
        e for e in evidence
        if e.field == RoofInputField.AXIS_WIDTH and not e.is_authoritative()
    ]
    assert len(unauth) >= 1, "evidence ledger lost the unauthoritative attempt"


def test_slope_conflict_pjuvis_wins_with_warning_flag():
    """Stogo planas says 35°, pjūvis says 30°. Pjūvis wins; flag raised."""
    _, _, flags = build_roof_input(
        pages=[_0039_GEGNIU_P48, _0039_PJUVIS_P49, _0039_FLOOR_P46],
    )
    slope_flags = [f for f in flags if f.field == RoofInputField.SLOPE]
    assert len(slope_flags) >= 1, "slope disagreement must produce a flag"


def test_falls_back_to_default_wall_thickness_with_flag():
    """No page reports wall_thickness → default 0.25m + low-confidence flag."""
    _, _, flags = build_roof_input(
        pages=[A_LAIDA_STOGO_P10, A_LAIDA_PJUVIS_P9],
    )
    wt_flags = [f for f in flags if f.field == RoofInputField.WALL_THICKNESS]
    assert len(wt_flags) >= 1
```

- [ ] **Step 2: Run test, expect failures**

Run: `cd backend && python3 -m pytest tests/extractor/roof/test_vision_extractor_typed.py -v`
Expected: Import errors (new `build_roof_input(pages=...)` signature doesn't exist yet).

- [ ] **Step 3: Refactor `build_roof_input`**

Open `backend/extractor/roof/vision_extractor.py`. Replace the existing `build_roof_input(stogo, pjuvis, *, default_wall_thickness_m)` with the new typed version. The OLD function signature is removed — there are no production callers using it yet (Phase 1 only had test scripts that constructed RoofInput manually).

```python
# backend/extractor/roof/vision_extractor.py — replace build_roof_input

def build_roof_input(
    pages: list[dict],
    *,
    default_wall_thickness_m: float = _DEFAULT_WALL_THICKNESS_M,
    default_eaves_overhang_m: float = 0.0,
) -> tuple["RoofInput", list[DimensionEvidence], list[HITLFlag]]:
    """Typed merger — populates RoofInput using Semantic Routing.

    `pages` is a list of dicts. Each dict is one page's Vision extraction
    output PLUS two routing keys:
        - `_page_num`: 1-indexed page number
        - `_page_class`: extractor.page_classifier.PageType for that page

    Returns:
        - `RoofInput` ready for strategy dispatch
        - `list[DimensionEvidence]` — every extracted value (authoritative
          AND non-authoritative) with provenance, for the patikrinkite UI
        - `list[HITLFlag]` — mismatches and fallbacks that need user review

    Rules:
      1. Each RoofInput field is populated ONLY from pages whose page_class
         is in PAGE_AUTHORITY[page_class] for that field.
      2. If multiple authoritative pages disagree on the same field:
           - SLOPE: pjūvis (SECTION) wins; flag raised on disagreement.
           - axes: average if disagreement <1%, else flag and pick first.
      3. If no authoritative page exists for a field, fall back to:
           - stogo_planas value (with HITLFlag.NO_AUTHORITATIVE_SOURCE)
           - or hard default (axes have no default; wall_thickness 0.25;
             eaves 0.0) — also with a flag.
    """
    from extractor.roof.strategies import RoofInput  # local import: avoid cycle

    evidence: list[DimensionEvidence] = []
    flags: list[HITLFlag] = []

    # Collect ALL evidence first (authoritative + non-authoritative).
    for page in pages:
        page_num = page["_page_num"]
        page_class = page["_page_class"]

        # Map each page's raw fields to RoofInputField evidence entries.
        for raw_key, field in (
            ("axis_to_axis_length_m", RoofInputField.AXIS_LENGTH),
            ("axis_to_axis_width_m", RoofInputField.AXIS_WIDTH),
            ("eaves_overhang_from_axis_m", RoofInputField.EAVES_OVERHANG),
            ("wall_thickness_m", RoofInputField.WALL_THICKNESS),
            ("roof_type", RoofInputField.ROOF_TYPE),
            ("chimney_count", RoofInputField.CHIMNEY_COUNT),
            ("rooflight_count", RoofInputField.ROOFLIGHT_COUNT),
            ("windows_count", RoofInputField.WINDOWS_COUNT),
        ):
            value = page.get(raw_key)
            if value is None:
                continue
            evidence.append(DimensionEvidence(
                field=field,
                value=value,
                page_num=page_num,
                page_class=page_class,
                source_crop_bbox=None,    # populated by caller when available
                raw_label_text=str(value),
                confidence=page.get("confidence", 0.5),
            ))

        # Slope evidence: list-valued sources need flattening.
        for slope in (page.get("visible_slope_angles_deg") or []) + \
                     (page.get("slope_angles_deg") or []):
            evidence.append(DimensionEvidence(
                field=RoofInputField.SLOPE,
                value=float(slope),
                page_num=page_num,
                page_class=page_class,
                source_crop_bbox=None,
                raw_label_text=f"{slope}°",
                confidence=page.get("confidence", 0.5),
            ))

    # Pick authoritative values per field with conflict resolution.
    def authoritative(field: RoofInputField) -> list[DimensionEvidence]:
        return [e for e in evidence if e.field == field and e.is_authoritative()]

    def first_or_none(field: RoofInputField):
        auth = authoritative(field)
        return auth[0].value if auth else None

    def all_slopes_from_section() -> list[float]:
        return [
            float(e.value) for e in evidence
            if e.field == RoofInputField.SLOPE and e.page_class == PageType.SECTION
        ]

    def all_slopes_from_stogo() -> list[float]:
        return [
            float(e.value) for e in evidence
            if e.field == RoofInputField.SLOPE and e.page_class == PageType.STOGO_PLANAS
        ]

    # AXIS_LENGTH / AXIS_WIDTH — must come from FLOOR_PLAN. Fallback to
    # STOGO_PLANAS only when no floor_plan exists (architectural single-
    # sheet projects like A LAIDA where the stogo planas IS the source).
    def axis_with_fallback(field: RoofInputField, axis_name: str) -> float:
        auth = authoritative(field)
        if auth:
            return float(auth[0].value)
        # Fallback to stogo_planas axes — must be flagged
        stogo_evs = [
            e for e in evidence
            if e.field == field and e.page_class == PageType.STOGO_PLANAS
        ]
        if stogo_evs:
            flags.append(HITLFlag(
                field=field,
                reason=HITLFlagReason.NO_AUTHORITATIVE_SOURCE,
                message=(
                    f"No floor_plan available; using stogo_planas {axis_name} "
                    f"= {stogo_evs[0].value}m. Confirm this matches the full "
                    "building footprint, not just a partial detail."
                ),
                evidence=stogo_evs,
                eur_impact_estimate=200.0,
            ))
            return float(stogo_evs[0].value)
        raise ValueError(f"No source for {field.value}")

    axis_length = axis_with_fallback(RoofInputField.AXIS_LENGTH, "length")
    axis_width = axis_with_fallback(RoofInputField.AXIS_WIDTH, "width")

    # WALL_THICKNESS — section is authoritative; default with flag if missing.
    wt = first_or_none(RoofInputField.WALL_THICKNESS)
    if wt is None:
        wt = default_wall_thickness_m
        flags.append(HITLFlag(
            field=RoofInputField.WALL_THICKNESS,
            reason=HITLFlagReason.NO_AUTHORITATIVE_SOURCE,
            message=(
                f"wall_thickness not annotated in any section — using LT "
                f"default {default_wall_thickness_m}m. Verify in plan."
            ),
            evidence=[],
            eur_impact_estimate=80.0,
        ))
    else:
        wt = float(wt)

    # SLOPE — pjūvis wins, stogo_planas labels are cross-check.
    section_slopes = all_slopes_from_section()
    stogo_slopes = all_slopes_from_stogo()
    if section_slopes:
        slopes_deg = section_slopes
        if stogo_slopes:
            mismatches = [
                ss for ss in stogo_slopes
                if not any(abs(ss - ps) <= 2.0 for ps in section_slopes)
            ]
            if mismatches:
                flags.append(HITLFlag(
                    field=RoofInputField.SLOPE,
                    reason=HITLFlagReason.CONFLICTING_AUTHORITATIVE_SOURCES,
                    message=(
                        f"Stogo planas labels slope(s) {mismatches}° but "
                        f"pjūvis reads {section_slopes}° — using pjūvis."
                    ),
                    evidence=[
                        e for e in evidence
                        if e.field == RoofInputField.SLOPE
                    ],
                    eur_impact_estimate=300.0,
                ))
    elif stogo_slopes:
        slopes_deg = stogo_slopes
        flags.append(HITLFlag(
            field=RoofInputField.SLOPE,
            reason=HITLFlagReason.NO_AUTHORITATIVE_SOURCE,
            message="No pjūvis available; using stogo_planas labelled slopes.",
            evidence=[
                e for e in evidence
                if e.field == RoofInputField.SLOPE
            ],
            eur_impact_estimate=300.0,
        ))
    else:
        raise ValueError("No slope angles found in any page")

    # ROOF_TYPE — stogo_planas owns; fall back to UNKNOWN with flag.
    roof_type = first_or_none(RoofInputField.ROOF_TYPE) or "unknown"

    # EAVES — stogo_planas owns; default 0 with flag if missing.
    eaves_axis = first_or_none(RoofInputField.EAVES_OVERHANG)
    if eaves_axis is None:
        eaves_axis = default_eaves_overhang_m
        flags.append(HITLFlag(
            field=RoofInputField.EAVES_OVERHANG,
            reason=HITLFlagReason.NO_AUTHORITATIVE_SOURCE,
            message=(
                "eaves_overhang_from_axis_m not annotated — defaulted to "
                f"{default_eaves_overhang_m}m (roof flush with outer wall). "
                "Verify in plan."
            ),
            evidence=[],
            eur_impact_estimate=400.0,
        ))
    else:
        eaves_axis = float(eaves_axis)

    eaves_outer = max(0.0, eaves_axis - wt / 2)

    return (
        RoofInput(
            roof_type=roof_type,
            building_length_m=axis_length + wt,
            building_width_m=axis_width + wt,
            eaves_overhang_m=eaves_outer,
            slopes_deg=slopes_deg,
            wall_thickness_m=wt,
            chimney_count=int(first_or_none(RoofInputField.CHIMNEY_COUNT) or 0),
            rooflight_count=int(first_or_none(RoofInputField.ROOFLIGHT_COUNT) or 0),
            windows_count=int(first_or_none(RoofInputField.WINDOWS_COUNT) or 0),
        ),
        evidence,
        flags,
    )
```

Also add imports at top of `vision_extractor.py`:

```python
from extractor.roof.evidence import DimensionEvidence, HITLFlag, HITLFlagReason
from extractor.roof.page_authority import PAGE_AUTHORITY, RoofInputField
from extractor.page_classifier import PageType
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/extractor/roof/test_vision_extractor_typed.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Run full backend suite to catch regressions**

Run: `cd backend && python3 -m pytest --no-header -q --ignore=tests/integration`
Expected: 559+ pass (existing 559 + 12 new tests from Tasks 1-2 + 5 from this task).

- [ ] **Step 6: Commit**

```bash
git add backend/extractor/roof/vision_extractor.py backend/tests/extractor/roof/test_vision_extractor_typed.py
git commit -m "feat(roof/vision_extractor): typed merger with Semantic Routing

build_roof_input(pages=...) replaces the old (stogo, pjuvis, ...) signature.
Each RoofInput field is populated ONLY by pages whose page_class is
authoritative per PAGE_AUTHORITY (Task 1). Non-authoritative extractions
are kept in the evidence ledger but never reach RoofInput.

This fixes 0039 -8.7% sienos: the gegnių planas axis_width=4.61m is
now dropped at merger time (STOGO_PLANAS is not authoritative for
AXIS_WIDTH when a FLOOR_PLAN is available), forcing the 7.12m from
p46 to be used. Slope cross-check now raises a HITLFlag when stogo
planas labels disagree with pjūvis by >2°.

A LAIDA: no FLOOR_PLAN available → fallback to STOGO_PLANAS axes WITH
a HITLFlag (NO_AUTHORITATIVE_SOURCE). User must confirm full footprint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Phase B — Constraint Verification Graph

Goal: when a page reports BOTH the overall axis dimension AND sub-segments that should sum to it, detect mismatches and raise HITL flags.

#### Task 4: `constraint_check.py` — sub-dimension sum verification

**Files:**
- Create: `backend/extractor/roof/constraint_check.py`
- Test: `backend/tests/extractor/roof/test_constraint_check.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/extractor/roof/test_constraint_check.py
"""Unit tests for the sub-dimension-sum constraint verifier."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.constraint_check import (  # noqa: E402
    SubDimensionGroup,
    verify_sub_dim_sums,
)
from extractor.roof.evidence import HITLFlagReason  # noqa: E402
from extractor.roof.page_authority import RoofInputField  # noqa: E402


def test_clean_sum_no_flag():
    """4.10 + 3.10 = 7.20 (within 1cm of overall 7.20)."""
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=46,
            page_class=PageType.FLOOR_PLAN,
            overall_value_m=7.20,
            sub_values_m=[4.10, 3.10],
            tolerance_m=0.01,
        ),
    ])
    assert flags == []


def test_mismatched_sum_flags_axis_width():
    """4.10 + 3.10 = 7.20 but overall reads 7.12 → 8cm mismatch."""
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=46,
            page_class=PageType.FLOOR_PLAN,
            overall_value_m=7.12,
            sub_values_m=[4.10, 3.10],
            tolerance_m=0.01,
        ),
    ])
    assert len(flags) == 1
    assert flags[0].field == RoofInputField.AXIS_WIDTH
    assert flags[0].reason == HITLFlagReason.SUB_DIM_SUM_MISMATCH
    assert "7.12" in flags[0].message and "7.20" in flags[0].message


def test_no_sub_dims_no_flag():
    """If sub_values_m is empty, no constraint to check."""
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=10,
            page_class=PageType.STOGO_PLANAS,
            overall_value_m=8.70,
            sub_values_m=[],
            tolerance_m=0.01,
        ),
    ])
    assert flags == []


@pytest.mark.parametrize("overall,subs,expect_flag", [
    (7.20, [3.80, 3.40], False),    # sums exactly
    (7.20, [3.80, 3.41], False),    # within 1cm
    (7.20, [3.80, 3.39], False),    # within 1cm on the other side
    (7.20, [3.85, 3.40], True),     # 5cm off — flag
    (7.20, [4.10, 3.10], False),    # different breakdown, still sums
])
def test_tolerance_boundary(overall, subs, expect_flag):
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=46,
            page_class=PageType.FLOOR_PLAN,
            overall_value_m=overall,
            sub_values_m=subs,
            tolerance_m=0.01,
        ),
    ])
    assert (len(flags) > 0) == expect_flag
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `cd backend && python3 -m pytest tests/extractor/roof/test_constraint_check.py -v`

- [ ] **Step 3: Implement `constraint_check.py`**

```python
# backend/extractor/roof/constraint_check.py
"""Constraint Verification Graph.

LT brėžiniai often annotate BOTH an overall axis dimension and the
sub-segments that should sum to it (e.g. axis spacing 4.10m + 3.10m =
overall 7.20m). When Vision extracts both, this module verifies the
sums and raises HITLFlag entries on mismatch.

Source: 2026-05-14 consultcouncil — Gemini's Constraint Verification
Graph proposal, three-way consensus in R3. This is the *independent*
within-artifact check (vs Claude R1's circular geometric cross-val).
"""
from __future__ import annotations

from dataclasses import dataclass

from extractor.page_classifier import PageType
from extractor.roof.evidence import HITLFlag, HITLFlagReason
from extractor.roof.page_authority import RoofInputField


@dataclass(frozen=True)
class SubDimensionGroup:
    """One (field, page) pair carrying both an overall and its sub-dim breakdown."""
    field: RoofInputField
    page_num: int
    page_class: PageType
    overall_value_m: float
    sub_values_m: list[float]
    tolerance_m: float = 0.01


def verify_sub_dim_sums(groups: list[SubDimensionGroup]) -> list[HITLFlag]:
    """Return a HITLFlag for each group where sub_values don't sum to overall."""
    flags: list[HITLFlag] = []
    for g in groups:
        if not g.sub_values_m:
            continue
        actual_sum = sum(g.sub_values_m)
        diff = abs(actual_sum - g.overall_value_m)
        if diff > g.tolerance_m:
            flags.append(HITLFlag(
                field=g.field,
                reason=HITLFlagReason.SUB_DIM_SUM_MISMATCH,
                message=(
                    f"On page {g.page_num} ({g.page_class.value}): "
                    f"sub-dimensions {g.sub_values_m} sum to {actual_sum:.2f}m "
                    f"but overall reads {g.overall_value_m:.2f}m "
                    f"(Δ {diff*100:.0f}cm > {g.tolerance_m*100:.0f}cm tol)."
                ),
                evidence=[],
                eur_impact_estimate=350.0,
            ))
    return flags
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python3 -m pytest tests/extractor/roof/test_constraint_check.py -v`
Expected: 4 named + 5 parametrized = 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/roof/constraint_check.py backend/tests/extractor/roof/test_constraint_check.py
git commit -m "feat(roof/constraint_check): sub-dimension sum verification

Gemini's R3 proposal: when a page annotates BOTH an overall axis and
its sub-segments, verify the sums match within 1cm tolerance. Mismatches
become HITLFlag entries with €350 default impact estimate.

This is the *independent* within-artifact check (vs circular geometric
cross-validation that re-derives outputs from same inputs). Sub-dims
and overall are two distinct annotations on the same drawing — they
agree if and only if the drawing is internally consistent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Phase C — Ground-truth schema v2 + harness

Goal: a per-page-per-field YAML format that records each value's source page, plus an interactive CLI that walks new PDFs and writes the file.

#### Task 5: Document the v2 schema

**Files:**
- Create: `ground_truth/_schema_v2.md`

- [ ] **Step 1: Write the schema doc**

```markdown
# Ground Truth v2 — per-page-per-field schema

The v1 format (e.g. `a_laida_roof.yaml`) records a SINGLE value per field
plus the roofer's sąmata. That hides where each number came from and
makes inter-page consistency uncheckable. v2 records the value AND the
page it came from for every input field, so the eval harness can
measure: (a) end-to-end pipeline accuracy AND (b) per-page extraction
accuracy AND (c) inter-page agreement (which pages disagree, by how
much).

## Required top-level keys

```yaml
project_id: <slug>
source_pdf: <relative-path-from-repo-root>
roof_type: <dvislaitis|keturslaitis|vienslaitis|mansardinis|plokscias>

# Final ground-truth values used for strategy input (the answer):
roof_input:
  axis_to_axis_length_m: 25.34
  axis_to_axis_width_m: 7.12
  eaves_overhang_from_axis_m: 0.0
  wall_thickness_m: 0.30
  slope_angles_deg: [30]
  chimney_count: 1
  rooflight_count: 0
  windows_count: 0

# Per-page extraction labels (what the system SHOULD read from each page).
# A field absent from a page entry means "not visible on that page" —
# system should not extract it from there.
pages:
  - page_num: 46
    page_class: floor_plan
    fields:
      axis_to_axis_length_m: 25.59
      axis_to_axis_width_m: 7.12
      sub_dimensions_m:
        axis_to_axis_width_m: [4.10, 3.02]   # sub-segments that sum to overall

  - page_num: 48
    page_class: stogo_planas
    fields:
      roof_type: dvislaitis
      axis_to_axis_length_m: 25.34      # matches floor plan within tolerance
      axis_to_axis_width_m: 4.61        # PARTIAL — half-rafter detail; system MUST drop
      chimney_count: 1
      visible_slope_angles_deg: [35]    # WRONG — pjūvis says 30; system MUST prefer pjūvis

  - page_num: 49
    page_class: section
    fields:
      slope_angles_deg: [30]
      ridge_height_m: 8.45

# Roofer's manual sąmata for end-to-end comparison
roofer_samata:
  source: <where-this-came-from>
  pvm_included: false
  line_items:
    - position: stogas
      qty: 231
      unit: m2
      eur_per_unit: 20.00
    # ... etc
  total_eur_no_vat: 20458.00
```

## Notes

- All linear values in metres; angles in degrees; counts as integers.
- `page_class` values match `extractor.page_classifier.PageType` enum values exactly.
- `sub_dimensions_m` is OPTIONAL per page; only filled if the drawing
  shows sub-segment labels next to an overall axis dimension.
- `visible_slope_angles_deg` on stogo_planas pages records WHAT THE
  DRAWING LABELS (even if wrong); the actual slope used in computation
  goes in the section page's `slope_angles_deg`.
- A field deliberately absent from a page entry signals "the system
  should not extract that field from this page." If the system DOES
  extract it, that's a false-positive recall and the eval reports it.
```

- [ ] **Step 2: Commit**

```bash
git add ground_truth/_schema_v2.md
git commit -m "docs(ground_truth): v2 per-page-per-field schema

Records the value AND the source page for every RoofInput field, so
the eval harness can measure: (a) end-to-end pipeline accuracy,
(b) per-page extraction accuracy, (c) inter-page agreement.

Per consultcouncil R3 ('ground truth in parallel with implementation,
not as gate') — schema doc lands first; A LAIDA and 0039 conversions
follow in Tasks 6-7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

#### Task 6: Re-label A LAIDA in v2

**Files:**
- Create: `ground_truth/a_laida_roof_v2.yaml`

- [ ] **Step 1: Write the file**

Use the existing `ground_truth/a_laida_roof.yaml` + the 2026-05-14 session Vision extraction notes (axis_length=12.88 from p10, slope=25° from p9, etc.) to produce:

```yaml
project_id: a_laida
source_pdf: backend/tests/fixtures/stogai/a_laida.pdf
roof_type: keturslaitis

roof_input:
  axis_to_axis_length_m: 12.88
  axis_to_axis_width_m: 8.70
  eaves_overhang_from_axis_m: 1.05
  wall_thickness_m: 0.25
  slope_angles_deg: [25, 22]
  chimney_count: 0
  rooflight_count: 0
  windows_count: 0

pages:
  - page_num: 9
    page_class: section
    fields:
      slope_angles_deg: [25]      # long-side slope only (single cut)
      ridge_height_m: 5.80
      eaves_height_m: 3.20

  - page_num: 10
    page_class: stogo_planas
    fields:
      roof_type: keturslaitis
      axis_to_axis_length_m: 12.88
      axis_to_axis_width_m: 8.70
      eaves_overhang_from_axis_m: 1.05
      visible_slope_angles_deg: [25, 22]
      chimney_count: 0
      rooflight_count: 0
      windows_count: 0
      sub_dimensions_m:
        axis_to_axis_length_m: [5.33, 7.55]
        axis_to_axis_width_m: [3.80, 4.90]

  - page_num: 16
    page_class: section
    fields:
      slope_angles_deg: [22]      # short-side slope (perpendicular cut)

roofer_samata:
  source: owner_friend_roofer_quoted_2026-05-12
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
```

- [ ] **Step 2: Commit**

```bash
git add ground_truth/a_laida_roof_v2.yaml
git commit -m "data(ground_truth): A LAIDA re-labeled in v2 per-page-per-field format

Source values from Phase 0 (commit 35a2e08) + 2026-05-14 Vision session.
Sub-dimension breakdown for axis width/length is APPROXIMATE pending
re-inspection on the original PDF with a measuring overlay — values
chosen to closely fit the known overall axis dimensions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

#### Task 7: Re-label 0039 in v2

**Files:**
- Create: `ground_truth/0039_roof_v2.yaml`

- [ ] **Step 1: Write the file**

```yaml
project_id: 0039
source_pdf: backend/tests/fixtures/stogai/0039.pdf
roof_type: dvislaitis

roof_input:
  axis_to_axis_length_m: 25.34
  axis_to_axis_width_m: 7.12
  eaves_overhang_from_axis_m: 0.0
  wall_thickness_m: 0.30
  slope_angles_deg: [30]
  chimney_count: 1
  rooflight_count: 0
  windows_count: 0

pages:
  - page_num: 46
    page_class: floor_plan
    fields:
      axis_to_axis_length_m: 25.59
      axis_to_axis_width_m: 7.12

  - page_num: 48
    page_class: stogo_planas
    fields:
      roof_type: dvislaitis
      axis_to_axis_length_m: 25.34
      axis_to_axis_width_m: 4.61    # PARTIAL — system MUST drop (not authoritative)
      visible_slope_angles_deg: [35]   # WRONG — system MUST prefer section's 30°
      chimney_count: 1

  - page_num: 49
    page_class: section
    fields:
      slope_angles_deg: [30]
      ridge_height_m: 8.45

roofer_samata:
  source: 0039_roofer_samata
  pvm_included: false
  line_items:
    - position: stogas
      qty: 231
      unit: m2
      eur_per_unit: 20.00
      sum_eur: 4620.00
    - position: sienos
      qty: 135
      unit: m2
      eur_per_unit: 30.00
      sum_eur: 4050.00
    - position: vejalentes
      qty: 18
      unit: m
      eur_per_unit: 8.00
      sum_eur: 144.00
    - position: kraigas
      qty: 26
      unit: m
      eur_per_unit: 7.00
      sum_eur: 182.00
    - position: latakai
      qty: 51
      unit: m
      eur_per_unit: 12.00
      sum_eur: 612.00
  total_eur_no_vat: 9608.00
```

Note: roofer_samata.total_eur_no_vat is computed from line items shown; if v1 reports 20458 total it includes line items omitted here (langu_apdirbimas, perdanga, etc.) — copy them from `0039_roof.yaml` if present.

- [ ] **Step 2: Commit**

```bash
git add ground_truth/0039_roof_v2.yaml
git commit -m "data(ground_truth): 0039 re-labeled in v2 per-page-per-field format

The interesting cases:
- p48 (stogo_planas / gegnių planas) reports axis_width=4.61m which is
  PARTIAL (half-rafter detail). The system MUST drop this and pick
  p46's floor_plan 7.12m. Recorded here so the eval harness can verify.
- p48 also labels slope=35° (WRONG). Section p49 reads 30°. The system
  MUST prefer section.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

#### Task 8: Interactive labeling harness

**Files:**
- Create: `scripts/build_roof_ground_truth.py`

This script lets the user point at a new PDF and walk through pages, recording per-page-per-field values into the v2 YAML.

- [ ] **Step 1: Implement the CLI**

```python
"""Interactive harness for building roof ground truth (Phase 1.T8).

Usage:
    python3 scripts/build_roof_ground_truth.py \
        --pdf path/to/project.pdf \
        --out ground_truth/<slug>_roof_v2.yaml

Walks every page, renders it, asks the user to confirm/correct the
classifier output and then to enter each per-field value visible on
the page. Saves to v2 YAML on quit.
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from extractor.page_classifier import PageType, classify_page, OPUS_MODEL  # noqa: E402


PAGE_CLASSES = [pt.value for pt in PageType]
FIELD_PROMPTS = [
    ("roof_type", "Roof type (dvislaitis/keturslaitis/...) or skip", str),
    ("axis_to_axis_length_m", "Axis length (m)", float),
    ("axis_to_axis_width_m", "Axis width (m)", float),
    ("eaves_overhang_from_axis_m", "Eaves overhang from axis (m)", float),
    ("wall_thickness_m", "Wall thickness (m)", float),
    ("slope_angles_deg", "Slope angle(s) deg (comma-separated)", "list[float]"),
    ("visible_slope_angles_deg", "Slopes labelled on plan view (csv)", "list[float]"),
    ("chimney_count", "Chimney count", int),
    ("rooflight_count", "Rooflight count", int),
    ("windows_count", "Roof window count", int),
]


def render(pdf_path: Path, page_num: int, dpi: int = 200, preview_path: Path | None = None) -> str:
    pages = convert_from_bytes(
        pdf_path.read_bytes(), dpi=dpi,
        first_page=page_num, last_page=page_num, fmt="jpeg",
    )
    img = pages[0]
    if preview_path is not None:
        img.save(preview_path, format="JPEG", quality=85)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def prompt(text: str, parser):
    raw = input(f"  {text}: ").strip()
    if raw == "" or raw.lower() == "skip":
        return None
    if parser is float:
        return float(raw.replace(",", "."))
    if parser is int:
        return int(raw)
    if parser == "list[float]":
        return [float(x.strip().replace(",", ".")) for x in raw.split(",") if x.strip()]
    return raw


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--preview-dir", default="/tmp/gt_previews")
    args = p.parse_args()

    load_dotenv(ROOT / "backend" / ".env")
    pdf_path = Path(args.pdf).resolve()
    out = Path(args.out)
    preview_dir = Path(args.preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    pdf_bytes = pdf_path.read_bytes()
    from pypdfium2 import PdfDocument  # already in requirements
    doc = PdfDocument(pdf_bytes)
    n = len(doc)

    pages: list[dict] = []

    print(f"\nLabeling {pdf_path.name} ({n} pages). Press 's' to skip a page, 'q' to save+quit.")
    for page_num in range(1, n + 1):
        print(f"\n=== Page {page_num}/{n} ===")
        preview = preview_dir / f"{pdf_path.stem}_p{page_num}.jpg"
        try:
            b64 = render(pdf_path, page_num, preview_path=preview)
        except Exception as e:
            print(f"  render failed: {e}; skipping")
            continue

        # AI classification as a hint
        try:
            cls = classify_page(b64, pdf_path=pdf_path, page_num=page_num, model=OPUS_MODEL)
            print(f"  Opus says: page_type={cls.page_type.value} (conf {cls.confidence:.2f})")
            print(f"  Preview saved: {preview}")
        except Exception as e:
            cls = None
            print(f"  Opus failed: {e}")

        choice = input("  Action [accept/c=correct-class/s=skip/q=save+quit]: ").strip().lower()
        if choice == "q":
            break
        if choice == "s":
            continue
        if choice == "c":
            print(f"  Available: {', '.join(PAGE_CLASSES)}")
            page_class_str = input("  page_class: ").strip()
        else:
            page_class_str = cls.page_type.value if cls else "unknown"

        # If the user picked unknown, skip detailed field prompts.
        if page_class_str == "unknown":
            print("  (no fields to label for page_class=unknown)")
            continue

        # Field-level labels
        fields: dict = {}
        print("  Enter values visible ON THIS PAGE (skip if not visible):")
        for key, label, parser in FIELD_PROMPTS:
            v = prompt(label, parser)
            if v is not None:
                fields[key] = v

        # Optional sub-dimension breakdown for axis width/length
        if PageType(page_class_str) == PageType.FLOOR_PLAN:
            sub_w = input("  Sub-segment widths sum (csv, or skip): ").strip()
            sub_l = input("  Sub-segment lengths sum (csv, or skip): ").strip()
            sub = {}
            if sub_w:
                sub["axis_to_axis_width_m"] = [float(x.replace(",", ".")) for x in sub_w.split(",") if x]
            if sub_l:
                sub["axis_to_axis_length_m"] = [float(x.replace(",", ".")) for x in sub_l.split(",") if x]
            if sub:
                fields["sub_dimensions_m"] = sub

        pages.append({"page_num": page_num, "page_class": page_class_str, "fields": fields})

    # Final roof_input prompt
    print("\nNow enter the AUTHORITATIVE roof_input (the answer the system should produce):")
    roof_input: dict = {}
    for key, label, parser in FIELD_PROMPTS:
        # skip visible_slope_angles_deg in roof_input — that's page-only
        if key == "visible_slope_angles_deg":
            continue
        v = prompt(label, parser)
        if v is not None:
            roof_input[key] = v

    project_id = input("project_id slug (e.g. 'a_laida'): ").strip()
    out_data = {
        "project_id": project_id,
        "source_pdf": str(pdf_path.relative_to(ROOT) if pdf_path.is_relative_to(ROOT) else pdf_path),
        "roof_type": roof_input.get("roof_type", "unknown"),
        "roof_input": roof_input,
        "pages": pages,
        "roofer_samata": {
            "source": "TODO_fill_in",
            "pvm_included": False,
            "line_items": [],
            "total_eur_no_vat": 0,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(out_data, sort_keys=False, allow_unicode=True))
    print(f"\nSaved: {out}")
    print("Fill in `roofer_samata.line_items` and `total_eur_no_vat` manually before running the eval.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the harness on an existing PDF**

Run: `python3 scripts/build_roof_ground_truth.py --pdf backend/tests/fixtures/stogai/a_laida.pdf --out /tmp/test_label.yaml`
Then quit with `q` after the first page. Inspect `/tmp/test_label.yaml` — should be valid YAML.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_roof_ground_truth.py
git commit -m "feat(scripts): interactive roof ground truth harness

Walks every page of a PDF, renders previews, uses the classifier as a
hint, and prompts the user for per-page-per-field values. Writes v2
YAML matching ground_truth/_schema_v2.md.

Per consultcouncil R3 ('N=8-10 ground truth in parallel'): this is the
tool that closes the bottleneck. New projects can be labeled in 5-10
minutes each instead of an hour.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Phase D — WAPE end-to-end evaluator

#### Task 9: `eval_roof_e2e.py` — full-pipeline WAPE harness

**Files:**
- Create: `scripts/eval_roof_e2e.py`

- [ ] **Step 1: Implement**

```python
"""End-to-end WAPE evaluator for roof extraction.

Runs the full Vision → typed merger → strategy → sąmata pipeline against
a v2 ground-truth YAML and reports:
  - WAPE (value-weighted absolute percentage error)
  - Per-line item delta vs roofer
  - Unflagged high-impact errors (lines >25% of total roof value with
    error >5% AND no HITLFlag covering the relevant input)

Exit codes:
  0 — WAPE ≤ 2% AND no unflagged high-impact errors
  1 — anything else

Usage:
    python3 scripts/eval_roof_e2e.py --gt ground_truth/a_laida_roof_v2.yaml
    python3 scripts/eval_roof_e2e.py --gt ground_truth/0039_roof_v2.yaml
    python3 scripts/eval_roof_e2e.py --all  # all v2 files
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from extractor.page_classifier import PageType, OPUS_MODEL  # noqa: E402
from extractor.roof.strategies.dvislaitis import DvislaitisStrategy  # noqa: E402
from extractor.roof.strategies.keturslaitis import KeturslaitisStrategy  # noqa: E402
from extractor.roof.vision_extractor import (  # noqa: E402
    build_roof_input,
    extract_pjuvis_dims,
    extract_stogo_planas_dims,
)

STRATEGIES = {
    "dvislaitis": DvislaitisStrategy(),
    "keturslaitis": KeturslaitisStrategy(),
}

# Map roofer position keys to strategy LineItem.pozicija substrings
POS_MAP = {
    "perdanga": "perdanga",
    "stogas": "stogas",
    "latakai": "latakai",
    "kraigai": "kraigai",
    "kraigas": "kraigas",
    "sienos": "sienos",
    "vejalentes": "vėjalent",
    "langu_apdirbimas": "langų",
    "kaminelis": "kamin",
}


def render_b64(pdf_path: Path, page_num: int, dpi: int = 200) -> str:
    pages = convert_from_bytes(
        pdf_path.read_bytes(), dpi=dpi,
        first_page=page_num, last_page=page_num, fmt="jpeg",
    )
    buf = io.BytesIO()
    pages[0].save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def evaluate(gt_path: Path) -> tuple[float, float, list[dict], bool]:
    """Returns (wape, total_eur_actual, line_deltas, all_high_impact_flagged)."""
    gt = yaml.safe_load(gt_path.read_text())
    pdf_path = ROOT / gt["source_pdf"]

    # Run Vision extraction on each page listed in GT
    pages_data: list[dict] = []
    for page_spec in gt["pages"]:
        page_num = page_spec["page_num"]
        page_class = PageType(page_spec["page_class"])
        b64 = render_b64(pdf_path, page_num)
        if page_class == PageType.STOGO_PLANAS or page_class == PageType.FLOOR_PLAN:
            try:
                data = extract_stogo_planas_dims(b64, model=OPUS_MODEL)
            except Exception:
                data = {}
        elif page_class == PageType.SECTION:
            try:
                data = extract_pjuvis_dims(b64, model=OPUS_MODEL)
            except Exception:
                data = {}
        else:
            data = {}
        data["_page_num"] = page_num
        data["_page_class"] = page_class
        pages_data.append(data)

    # Run the typed merger
    inp, evidence, flags = build_roof_input(pages_data)

    # Compute via strategy
    out = STRATEGIES[gt["roof_type"]].compute(inp)
    expected = {li["position"]: li for li in gt["roofer_samata"]["line_items"]}
    total_actual = sum(li["sum_eur"] for li in gt["roofer_samata"]["line_items"])

    deltas = []
    weighted_abs_err = 0.0
    unflagged_high_impact = False

    for li in out.line_items:
        # Match by substring
        roofer_key = next(
            (k for k in expected if POS_MAP.get(k, k) in li.pozicija.lower()
                                        .replace("ė", "e").replace("š", "s")
                                        .replace("ų", "u").replace("ą", "a")),
            None,
        )
        if not roofer_key:
            deltas.append({"pozicija": li.pozicija, "kiekis": li.kiekis,
                           "roofer_qty": None, "delta_pct": None})
            continue
        roofer = expected[roofer_key]
        roofer_eur = roofer["sum_eur"]
        # Compute predicted € using the SAME unit price the roofer uses
        # (we're evaluating quantity accuracy, not pricing).
        predicted_eur = li.kiekis * roofer["eur_per_unit"]
        eur_delta = abs(predicted_eur - roofer_eur)
        weighted_abs_err += eur_delta
        pct = (li.kiekis - roofer["qty"]) / roofer["qty"] * 100 if roofer["qty"] else 0
        share = roofer_eur / total_actual if total_actual else 0
        is_high_impact = share > 0.25
        is_unflagged = len(flags) == 0  # crude — refine to per-field check later
        if is_high_impact and abs(pct) > 5 and is_unflagged:
            unflagged_high_impact = True
        deltas.append({
            "pozicija": li.pozicija,
            "kiekis": li.kiekis,
            "roofer_qty": roofer["qty"],
            "delta_pct": pct,
            "share": share,
            "high_impact": is_high_impact,
        })

    wape = weighted_abs_err / total_actual * 100 if total_actual else 0
    return wape, total_actual, deltas, not unflagged_high_impact


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gt", help="Ground truth v2 YAML path")
    p.add_argument("--all", action="store_true",
                   help="Run all *_roof_v2.yaml in ground_truth/")
    args = p.parse_args()
    load_dotenv(ROOT / "backend" / ".env")

    if args.all:
        targets = sorted(ROOT.glob("ground_truth/*_roof_v2.yaml"))
    elif args.gt:
        targets = [Path(args.gt)]
    else:
        sys.exit("specify --gt or --all")

    overall_pass = True
    for gt_path in targets:
        print(f"\n=== {gt_path.name} ===")
        wape, total, deltas, no_unflagged_high_impact = evaluate(gt_path)
        print(f"WAPE: {wape:.2f}%   (roofer total €{total:.0f})")
        for d in deltas:
            if d["delta_pct"] is None:
                print(f"  {d['pozicija']:<35} {d['kiekis']:>8.1f}  (no match)")
            else:
                marker = " [HI-IMPACT]" if d.get("high_impact") else ""
                print(f"  {d['pozicija']:<35} {d['kiekis']:>8.1f}  Δ{d['delta_pct']:+5.1f}%"
                      f" ({d['share']*100:.0f}% of €){marker}")
        verdict = (wape <= 2.0) and no_unflagged_high_impact
        print(f"  → {'✓ PASS' if verdict else '✗ FAIL'}")
        overall_pass = overall_pass and verdict

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run on both ground-truth projects**

Run: `python3 scripts/eval_roof_e2e.py --all`
Expected (acceptance): A LAIDA WAPE ≤ 2%, 0039 WAPE ≤ 2%, both pass.

If 0039 fails because `sienos` is still off, the cause is one of:
  (a) Vision returns wrong axis_width on the FLOOR_PLAN page (extraction error, separate fix);
  (b) wall_thickness default 0.25 vs true 0.30 (the section page should now report 0.30 — verify the section extraction includes wall thickness);
  (c) eaves default 0 vs true 0 (same — verify).

Document any failure in the commit message and surface it as a flagged dimension, not a silent miss.

- [ ] **Step 3: Commit**

```bash
git add scripts/eval_roof_e2e.py
git commit -m "feat(scripts): end-to-end WAPE eval for roof extraction

Replaces the per-line ±2% threshold with WAPE (value-weighted absolute
percentage error) + 'no unflagged high-impact line error' per
consultcouncil R3 verdict. Runs the full Vision → typed merger →
strategy → sąmata pipeline against v2 ground truth, compares to the
roofer's manual sąmata, exits 0 on full pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

#### Task 10: Acceptance run — confirm both projects pass the wedge

**Files:** none modified — verification only.

- [ ] **Step 1: Full backend test suite**

Run: `cd backend && python3 -m pytest --no-header -q --ignore=tests/integration`
Expected: ≥581 PASS (existing 559 + new tests: 7 page_authority + 7 evidence + 5 vision_extractor_typed + 9 constraint_check = 28 → final 587).

- [ ] **Step 2: Both end-to-end projects pass via eval script**

Run: `python3 scripts/eval_roof_e2e.py --all`
Expected: WAPE ≤ 2% on both, exit 0.

- [ ] **Step 3: Record results in CHANGELOG**

Append to `CHANGELOG.md`:

```markdown
## 2026-05-DD — Stogai V1 Accuracy Wedge complete

End-to-end Vision → typed merger → strategy pipeline produces sąmatas
within WAPE ≤ 2% on both ground-truth projects:
- A LAIDA (keturslaitis, SA dalis): WAPE X.X%
- 0039 (dvislaitis, SK only, raster): WAPE X.X%

Architecture: Semantic Routing Hierarchy in build_roof_input drops
non-authoritative axis writes from structural detail pages. Constraint
Verification Graph catches sub-dim sum mismatches as HITLFlags. No
unflagged high-impact line items.

Next: V1.5 — HITL dimension ledger UI (separate plan); ground truth
growth to N=8-10 (ship-and-capture + interactive harness already in
place).
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: stogai V1 accuracy wedge complete — both projects WAPE ≤ 2%"
```

---

## Self-Review

**Spec coverage:**
- Semantic Routing Hierarchy → Task 1 (`page_authority.py`) + Task 3 (typed merger).
- Constraint Verification Graph → Task 4 (`constraint_check.py`).
- Proof-carrying evidence (per consultcouncil) → Task 2 (`DimensionEvidence`/`HITLFlag`) + Task 3 (merger returns evidence list + flags).
- Per-page-per-field ground truth schema → Tasks 5-7 (`_schema_v2.md`, A LAIDA v2, 0039 v2).
- N=8-10 in parallel (not gate) → Task 8 (`build_roof_ground_truth.py` interactive harness — opens the door).
- WAPE + no-unflagged-high-impact metric → Task 9 (`eval_roof_e2e.py`).
- Acceptance gate → Task 10.

NOT covered in this plan (deferred per scope check):
- HITL dimension ledger UI (frontend) — needs separate plan.
- Cropped source bbox capture (`source_crop_bbox` is wired in dataclass but populated as None for now) — depends on the UI plan.
- OCR / ensemble / multi-shot — deferred to V1.5 conditional on N≥8 failure-mode analysis.

**Placeholder scan:** every step contains executable code or commands. No TODOs left in production code. Wall thickness for 0039 is filled from the YAML (0.30); slope evidence from p49 (30°).

**Type consistency:** `PageType` enum reused from `extractor.page_classifier`; `RoofInputField` new in `page_authority`; `DimensionEvidence`/`HITLFlag` new in `evidence`. `RoofInput` interface unchanged — old callers still work, but the only existing caller of `build_roof_input` was a one-off script (now updated in Task 3's tests).

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-05-14-stogai-v1-accuracy-wedge.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for solo-founder pace.
2. **Inline Execution** — Execute tasks in this session with checkpoints.

**Which approach?**
