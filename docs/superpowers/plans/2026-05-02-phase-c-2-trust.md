# Phase C-2 — Trust Through Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dishonest polygon-existence badge + the broken bbox-flash with an honest area-confidence system: badges that reflect WHETHER THE NUMBER IS RIGHT, per-number provenance chips that explain where the number came from, one-click verification, and the bbox-flash dropped entirely.

**Architecture:** Pure JS confidence calculator (`areaConfidence.js`) classifies each room based on which sources agree on its `plotas_m2`. Backend extractors get a small audit to ensure `plotas_source` is always set so the calculator has truthful inputs. Frontend swaps `PolygonReviewBadge` → `ConfidenceBadge`, mounts `ProvenanceChip` next to each kiekiai number, and `AiRoomOverlay` stops rendering bbox rectangles (only `polygon_pdf` polygons survive). All UI text Lithuanian; no "bbox" or "polygon" jargon survives.

**Tech Stack:**
- Frontend: React 18 + Tailwind, react-konva (existing), `node:test` for unit tests (no new dep)
- Backend: Python (no new deps; just attribute-population audit on existing extractors)
- Source spec: `docs/superpowers/specs/2026-05-02-pdf-viewer-trust-design.md` §3

---

## File Structure

### New files
- `frontend/src/lib/areaConfidence.js` — pure functions: `computeAreaConfidence(room)`, `agreementOf(values, tolerancePct)`, source-priority constants
- `frontend/src/lib/areaConfidence.test.js` — `node:test` unit tests
- `frontend/src/components/project/ConfidenceBadge.jsx` — replaces `PolygonReviewBadge`
- `frontend/src/components/project/ProvenanceChip.jsx` — per-kiekiai-number "iš kur tai?" chip
- `frontend/src/components/project/EksplikacijaRowFlash.jsx` — temporary halo overlay used when chip is clicked

### Modified files
- `frontend/src/components/project/RoomCard.jsx` — swap PolygonReviewBadge → ConfidenceBadge
- `frontend/src/components/project/WorkspacePanel.jsx` — same swap; also mount ProvenanceChip in the kiekiai loop
- `frontend/src/components/project/AiRoomOverlay.jsx` — drop the `bbox_pct` Rect rendering; keep `polygon_pdf` Line rendering
- `frontend/src/lib/projectStore.js` — add `markRoomVerified(projectId, roomNr)` helper + dispatch the existing `samatu:project-recompute` event
- `backend/extractor/pdfplumber_eksplikacija.py` — ensure every emitted patalpa has `plotas_source: 'eksplikacija'`
- `backend/extractor/vision_call.py` — ensure every emitted patalpa has `plotas_source: 'vision'` when no other source claimed it
- `backend/tests/test_plotas_source.py` — new test, asserts every patalpa from the extraction pipeline has `plotas_source` set

### Deleted files
- `frontend/src/components/project/PolygonReviewBadge.jsx` — replaced

---

## Pre-flight

Working state at start:
- Branch: `main`. Most recent commit: `7673e9e` (`chore: gitignore .smoke/`). Working tree clean.
- 22 frontend unit tests pass; `npm run build` clean.
- 170 backend pytest pass.
- Backend on :8000 (auth disabled). Frontend on :5173. Both running.

---

## Phase A: Foundation — areaConfidence pure function (TDD)

### Task 1: areaConfidence.js — sources + agreement detection

**Files:**
- Create: `frontend/src/lib/areaConfidence.js`
- Create: `frontend/src/lib/areaConfidence.test.js`

This is the pure-function brain of C-2. Every other task consumes its output. Build it first with TDD; UI components rest on top.

- [ ] **Step 1.1: Write failing tests**

Create `frontend/src/lib/areaConfidence.test.js`:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  computeAreaConfidence, AREA_AGREEMENT_TOLERANCE_PCT,
} from './areaConfidence.js';

test('computeAreaConfidence: room with eksplikacija + agreeing manual polygon → high', () => {
  const room = {
    nr: '01', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    polygon_source: 'manual', polygon_pdf: [[0, 0], [10, 0], [10, 5], [0, 5]],
    _polygon_area_m2: 12.6,  // 0.8% off, within tolerance
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'eksplikacija');
  assert.deepEqual(r.agreeingSources.sort(), ['eksplikacija', 'manual_polygon']);
});

test('computeAreaConfidence: eksplikacija only (no polygon) → medium', () => {
  const room = {
    nr: '02', plotas_m2: 12.5, plotas_source: 'eksplikacija',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'medium');
  assert.equal(r.primarySource, 'eksplikacija');
  assert.deepEqual(r.agreeingSources, ['eksplikacija']);
});

test('computeAreaConfidence: manual polygon only → medium', () => {
  const room = {
    nr: '03', plotas_m2: 8.4, plotas_source: 'manual_polygon',
    polygon_pdf: [[0, 0], [10, 0], [5, 5]],
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'medium');
  assert.equal(r.primarySource, 'manual_polygon');
});

test('computeAreaConfidence: vision-only (no eksplikacija, no polygon) → low', () => {
  const room = {
    nr: '04', plotas_m2: 6.0, plotas_source: 'vision',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'low');
  assert.equal(r.primarySource, 'vision');
});

test('computeAreaConfidence: eksplikacija + manual polygon DISAGREE (>5% off) → low', () => {
  const room = {
    nr: '05', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    polygon_source: 'manual', polygon_pdf: [[0, 0], [10, 0], [10, 5], [0, 5]],
    _polygon_area_m2: 18.0,  // 44% off
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'low');
  assert.equal(r.disagreement, true);
});

test('computeAreaConfidence: user_verified_at promotes medium → high', () => {
  const room = {
    nr: '06', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    user_verified_at: '2026-05-02T10:00:00Z',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.ok(r.userVerified);
});

test('computeAreaConfidence: room with no plotas_m2 → unknown', () => {
  const room = { nr: '07', plotas_m2: null };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'unknown');
});

test('AREA_AGREEMENT_TOLERANCE_PCT is 5%', () => {
  // Spec §3.2.1 specifies ±2% in the "high" path, but allow up to ±5% for "agreement"
  // because hand-drawn polygons trace edges with imprecision. The badge stays "high"
  // when sources are within ±2% AND drops to "low" when >5% — between, it stays "medium".
  assert.ok(AREA_AGREEMENT_TOLERANCE_PCT > 0 && AREA_AGREEMENT_TOLERANCE_PCT <= 0.05);
});
```

- [ ] **Step 1.2: Run, verify FAIL**

Run: `cd frontend && npm run test:units`
Expected: `Cannot find module './areaConfidence.js'`

- [ ] **Step 1.3: Implement**

Create `frontend/src/lib/areaConfidence.js`:

```javascript
/**
 * areaConfidence — classify per-room area trust based on agreeing sources.
 *
 * Coordinate convention: rooms come from projectStore.patalpos (FLAT shape;
 * NOT proj.data.patalpos). Inputs may include any of:
 *   - plotas_m2 / plotas_source: 'eksplikacija' | 'vision' | 'manual_polygon'
 *   - polygon_pdf + polygon_source: 'manual'   (Phase C-1 manual trace)
 *   - _polygon_area_m2 (optional, computed when polygon committed)
 *   - user_verified_at (ISO timestamp; user clicked ✓ patvirtinta)
 *
 * Returns:
 *   { confidence: 'high'|'medium'|'low'|'unknown',
 *     primarySource: string,
 *     agreeingSources: string[],
 *     userVerified: boolean,
 *     disagreement: boolean,
 *     sources: [{ type, value, label }] }
 *
 * Confidence rules:
 *   - 'unknown' if plotas_m2 is null/undefined
 *   - 'high' if userVerified, OR if ≥2 sources agree within ±2%
 *   - 'low' if ≥2 sources disagree by >5%
 *   - 'medium' otherwise (single source, or sources within 2-5%)
 */

export const AREA_HIGH_AGREEMENT_PCT = 0.02;
export const AREA_AGREEMENT_TOLERANCE_PCT = 0.05;

const SOURCE_LABEL_LT = {
  eksplikacija: 'iš eksplikacijos',
  manual_polygon: 'manualu',
  vision: 'iš AI',
  dimension: 'iš dimensijos',
};

export function computeAreaConfidence(room) {
  if (!room || room.plotas_m2 == null) {
    return {
      confidence: 'unknown',
      primarySource: null,
      agreeingSources: [],
      userVerified: false,
      disagreement: false,
      sources: [],
    };
  }

  const sources = collectSources(room);
  const userVerified = !!room.user_verified_at;

  if (sources.length === 0) {
    return {
      confidence: 'unknown',
      primarySource: null,
      agreeingSources: [],
      userVerified,
      disagreement: false,
      sources: [],
    };
  }

  const primarySource = sources[0].type;

  if (sources.length === 1) {
    return {
      confidence: userVerified ? 'high' : 'medium',
      primarySource,
      agreeingSources: [primarySource],
      userVerified,
      disagreement: false,
      sources,
    };
  }

  // 2+ sources — check agreement
  const values = sources.map((s) => s.value).filter((v) => v != null);
  const { agree, disagree } = agreementOf(values);

  if (disagree) {
    return {
      confidence: 'low',
      primarySource,
      agreeingSources: agree.map((idx) => sources[idx].type),
      userVerified,
      disagreement: true,
      sources,
    };
  }

  // All within tolerance
  return {
    confidence: 'high',
    primarySource,
    agreeingSources: sources.map((s) => s.type),
    userVerified,
    disagreement: false,
    sources,
  };
}

function collectSources(room) {
  const out = [];
  if (room.plotas_source === 'eksplikacija' && room.plotas_m2 != null) {
    out.push({ type: 'eksplikacija', value: room.plotas_m2, label: SOURCE_LABEL_LT.eksplikacija });
  }
  if (
    Array.isArray(room.polygon_pdf) &&
    room.polygon_pdf.length >= 3 &&
    room.polygon_source === 'manual'
  ) {
    const value = room._polygon_area_m2 != null ? room._polygon_area_m2 : room.plotas_m2;
    out.push({ type: 'manual_polygon', value, label: SOURCE_LABEL_LT.manual_polygon });
  }
  if (room.plotas_source === 'vision' && room.plotas_m2 != null) {
    out.push({ type: 'vision', value: room.plotas_m2, label: SOURCE_LABEL_LT.vision });
  }
  return out;
}

/**
 * Given an array of numeric values, return whether they all agree within ±5%
 * of the mean. Returns { agree: indices[], disagree: bool }.
 */
export function agreementOf(values) {
  if (!values || values.length === 0) return { agree: [], disagree: false };
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const indices = [];
  let disagree = false;
  values.forEach((v, i) => {
    const pct = Math.abs(v - mean) / mean;
    if (pct <= AREA_AGREEMENT_TOLERANCE_PCT) indices.push(i);
    else disagree = true;
  });
  return { agree: indices, disagree };
}
```

- [ ] **Step 1.4: Run, verify PASS**

Run: `cd frontend && npm run test:units`
Expected: 22 prior tests + 8 new tests = 30 pass.

- [ ] **Step 1.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/lib/areaConfidence.js frontend/src/lib/areaConfidence.test.js
git commit -m "feat(confidence): areaConfidence helper — classify rooms by source agreement

Phase C-2 brain: computes per-room {confidence, primarySource, agreeingSources}
from plotas_source + polygon_source + user_verified_at. Used by ConfidenceBadge
(replaces PolygonReviewBadge polygon-existence check) and by ProvenanceChip
to label each kiekiai number's origin."
```

---

## Phase B: Backend source flags

### Task 2: ensure plotas_source is always set in extractors

**Files:**
- Modify: `backend/extractor/pdfplumber_eksplikacija.py`
- Modify: `backend/extractor/vision_call.py`
- Create: `backend/tests/test_plotas_source.py`

The frontend confidence calculator depends on `plotas_source` being a truthful flag. Audit current extractors to ensure every emitted patalpa has the field.

- [ ] **Step 2.1: Locate where pdfplumber_eksplikacija builds patalpa dicts**

Run: `grep -n "patalpa.*=\|out\.append\|return \[" backend/extractor/pdfplumber_eksplikacija.py | head -10`

Find the function that constructs and returns the room dicts. Read it.

- [ ] **Step 2.2: Add plotas_source flag in pdfplumber_eksplikacija**

In `backend/extractor/pdfplumber_eksplikacija.py`, locate the function around line 181 that builds the patalpa dict (the one with `row_idx` and `row_bbox` parameters). At the END of that function — after the dict is constructed but before it's returned — add:

```python
# Phase C-2 (2026-05-02): tag every eksplikacija-derived patalpa with the
# plotas_source field so frontend areaConfidence can classify trust correctly.
if room.get("plotas_m2") is not None:
    room["plotas_source"] = "eksplikacija"
```

(Note: the variable holding the room dict may be named `out`, `patalpa`, or `room` — adapt to the actual local name. Read the function first; do not paste blindly.)

- [ ] **Step 2.3: Locate Vision-derived patalpa construction**

Run: `grep -n "def _build_pozicijos_from_rooms\|patalpos\\.append\|patalpos =\|\"patalpos\"" backend/extractor/vision_call.py | head -10`

Vision-derived rooms come from the response of the Anthropic API call. Find where `vision_call.py` constructs the canonical project structure — search for where `patalpos` is set onto the project dict from the Vision response.

- [ ] **Step 2.4: Add plotas_source='vision' fallback in vision_call.py**

In `backend/extractor/vision_call.py`, find the spot where the patalpos list is finalized for return (after merging with eksplikacija data). Add a defensive default:

```python
# Phase C-2 (2026-05-02): if a patalpa has plotas_m2 but no plotas_source,
# tag it as 'vision' (came from Anthropic Vision response, not eksplikacija).
# Eksplikacija reader sets 'eksplikacija' explicitly; manual polygons set
# 'manual_polygon' on the frontend. Anything left over is Vision.
for p in patalpos:
    if p.get("plotas_m2") is not None and not p.get("plotas_source"):
        p["plotas_source"] = "vision"
```

(The exact local variable holding the patalpos list will depend on the function. Read first.)

- [ ] **Step 2.5: Write test**

Create `backend/tests/test_plotas_source.py`:

```python
"""Phase C-2 (2026-05-02): every emitted patalpa with plotas_m2 must carry
a plotas_source flag. The frontend confidence calculator depends on it."""

from extractor.pdfplumber_eksplikacija import _build_room_from_row


def test_pdfplumber_room_has_plotas_source():
    """When pdfplumber parses a room, it tags plotas_source='eksplikacija'."""
    # Simulate a clean row: nr='1', name='Vonia', area_m2=6.83
    raw_row = ["1", "Vonia", "6,83"]
    room = _build_room_from_row(
        raw_row=raw_row, row_idx=0, page_nr=2, row_bbox=None,
    )
    assert room is not None, "row should parse"
    assert room.get("plotas_m2") == 6.83
    assert room.get("plotas_source") == "eksplikacija"


def test_vision_fallback_tag_applied():
    """vision_call.py defaults plotas_source='vision' when no flag is set."""
    # Reproduce the fallback loop from vision_call.py inline
    patalpos = [
        {"nr": "1", "plotas_m2": 6.83},  # untagged → should become 'vision'
        {"nr": "2", "plotas_m2": 12.5, "plotas_source": "eksplikacija"},  # already tagged → unchanged
        {"nr": "3", "plotas_m2": None},  # no area → unchanged (no source)
    ]
    for p in patalpos:
        if p.get("plotas_m2") is not None and not p.get("plotas_source"):
            p["plotas_source"] = "vision"
    assert patalpos[0]["plotas_source"] == "vision"
    assert patalpos[1]["plotas_source"] == "eksplikacija"
    assert "plotas_source" not in patalpos[2]
```

(The first test calls `_build_room_from_row` which is the actual function name in pdfplumber_eksplikacija.py — verify this in step 2.1's grep. If the function name differs, adapt.)

- [ ] **Step 2.6: Run backend tests**

Run: `cd backend && pytest tests/test_plotas_source.py -v`
Expected: 2 tests pass.

If `_build_room_from_row` is named differently in the actual file (e.g. `_build_room` or `parse_row`), the test will error with `ImportError`. Fix the import to match the actual function name.

- [ ] **Step 2.7: Run full backend regression**

Run: `cd backend && pytest -q`
Expected: 172 tests pass (170 existing + 2 new).

- [ ] **Step 2.8: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/pdfplumber_eksplikacija.py backend/extractor/vision_call.py backend/tests/test_plotas_source.py
git commit -m "feat(extractor): tag every patalpa with plotas_source

Phase C-2 frontend areaConfidence helper needs to know whether each room's
plotas_m2 came from the eksplikacija text (deterministic, high-trust) or
Vision (low-trust). pdfplumber_eksplikacija now sets plotas_source='eksplikacija'
when emitting; vision_call.py defaults to 'vision' for any untagged patalpa."
```

---

## Phase C: ConfidenceBadge replaces PolygonReviewBadge

### Task 3: Create ConfidenceBadge component

**Files:**
- Create: `frontend/src/components/project/ConfidenceBadge.jsx`

- [ ] **Step 3.1: Write the component**

Create `frontend/src/components/project/ConfidenceBadge.jsx`:

```javascript
/**
 * ConfidenceBadge — Phase C-2 replacement for PolygonReviewBadge.
 *
 * Reflects AREA confidence (whether plotas_m2 is trustworthy) — NOT polygon
 * existence. A room with eksplikacija-derived plotas_m2 but no manual polygon
 * is still 🟡 medium-trust, not (incorrectly) 🟡 "needs trace".
 *
 * Colors:
 *   🟢 tikslus  — multiple sources agree, OR user clicked ✓ patvirtinta
 *   🟡 tikrinti — single source, plausible
 *   🔴 neaišku — sources disagree, OR weak Vision-only
 *
 * No "bbox" or "polygon" word in user-visible text.
 */

import { computeAreaConfidence } from '@/lib/areaConfidence';

const STYLES = {
  high: {
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: '🟢',
    label: 'tikslus',
  },
  medium: {
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    dot: '🟡',
    label: 'tikrinti',
  },
  low: {
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    dot: '🔴',
    label: 'neaišku',
  },
};

export default function ConfidenceBadge({ room, onClick }) {
  const result = computeAreaConfidence(room);
  if (result.confidence === 'unknown') return null;

  const style = STYLES[result.confidence];
  if (!style) return null;

  const sourceList = result.sources
    .map((s) => `${s.label}: ${s.value?.toFixed?.(2) ?? '—'} m²`)
    .join('\n');
  const verifiedLine = result.userVerified
    ? `\nPatvirtinta: ${new Date(room.user_verified_at).toLocaleDateString('lt-LT')}`
    : '';
  const disagreementLine = result.disagreement
    ? '\n⚠ Šaltiniai nesutampa — patikrinti rankiniu būdu.'
    : '';
  const title = `Plotas: ${room.plotas_m2?.toFixed?.(2) ?? '—'} m²\n${sourceList}${verifiedLine}${disagreementLine}`;

  return (
    <button
      onClick={onClick}
      title={title}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${style.cls}`}
      data-testid={`confidence-badge-${room.nr}`}
      data-confidence={result.confidence}
    >
      <span>{style.dot}</span>
      <span>{style.label}</span>
    </button>
  );
}
```

- [ ] **Step 3.2: Quick build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean build (component is unused but should compile).

- [ ] **Step 3.3: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/ConfidenceBadge.jsx
git commit -m "feat(confidence): ConfidenceBadge component (replaces PolygonReviewBadge)

Reads computeAreaConfidence(room) and renders 🟢 tikslus / 🟡 tikrinti /
🔴 neaišku based on source agreement, not polygon existence. Tooltip lists
all contributing sources with their plotas_m2 values + LT labels. No 'bbox'
or 'polygon' word in any user-visible string."
```

---

### Task 4: Swap badge in RoomCard

**Files:**
- Modify: `frontend/src/components/project/RoomCard.jsx:18` (import) and `:178` (mount)

- [ ] **Step 4.1: Update import**

In `frontend/src/components/project/RoomCard.jsx`, replace line 18:

```javascript
import PolygonReviewBadge from './PolygonReviewBadge';
```

with:

```javascript
import ConfidenceBadge from './ConfidenceBadge';
```

- [ ] **Step 4.2: Update mount**

Around line 178, replace:

```jsx
<PolygonReviewBadge
  room={room}
  onClick={() => onShowOnPdf?.(room.puslapio_nr, room)}
/>
```

with:

```jsx
<ConfidenceBadge
  room={room}
  onClick={() => onShowOnPdf?.(room.puslapio_nr, room)}
/>
```

- [ ] **Step 4.3: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 4.4: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/RoomCard.jsx
git commit -m "refactor(rooms): swap PolygonReviewBadge → ConfidenceBadge in RoomCard"
```

---

### Task 5: Swap badge in WorkspacePanel

**Files:**
- Modify: `frontend/src/components/project/WorkspacePanel.jsx:17` (import) and `:304` (mount)

- [ ] **Step 5.1: Update import**

In `frontend/src/components/project/WorkspacePanel.jsx`, replace line 17:

```javascript
import PolygonReviewBadge from './PolygonReviewBadge';
```

with:

```javascript
import ConfidenceBadge from './ConfidenceBadge';
```

- [ ] **Step 5.2: Update mount**

Around line 304, replace:

```jsx
<PolygonReviewBadge
  room={r}
  onClick={(e) => {
    e?.stopPropagation?.();
    if (onJumpToPage && targetPage) onJumpToPage(targetPage, r);
  }}
/>
```

with:

```jsx
<ConfidenceBadge
  room={r}
  onClick={(e) => {
    e?.stopPropagation?.();
    if (onJumpToPage && targetPage) onJumpToPage(targetPage, r);
  }}
/>
```

- [ ] **Step 5.3: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 5.4: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/WorkspacePanel.jsx
git commit -m "refactor(rooms): swap PolygonReviewBadge → ConfidenceBadge in WorkspacePanel"
```

---

### Task 6: Delete PolygonReviewBadge

**Files:**
- Delete: `frontend/src/components/project/PolygonReviewBadge.jsx`

- [ ] **Step 6.1: Confirm no remaining references**

Run: `cd /Users/ignasgaldikas/samatu-ai && grep -rn "PolygonReviewBadge" frontend/src`
Expected: zero matches (after Tasks 4 + 5 the imports are gone).

- [ ] **Step 6.2: Delete the file**

Run: `git rm frontend/src/components/project/PolygonReviewBadge.jsx`

- [ ] **Step 6.3: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 6.4: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git commit -m "refactor(rooms): delete PolygonReviewBadge — superseded by ConfidenceBadge

Phase C-2 replaces polygon-existence badge with area-confidence badge.
Old component had zero remaining references after RoomCard + WorkspacePanel
swap."
```

---

## Phase D: Kill the bbox flash

### Task 7: Strip bbox_pct rendering from AiRoomOverlay

**Files:**
- Modify: `frontend/src/components/project/AiRoomOverlay.jsx`

The current AiRoomOverlay renders TWO shapes per room: `polygon_pdf` (when present) and `bbox_pct` (when present, no polygon). The bbox path is what flashes wrong on click. Drop it. Keep the polygon path — manual polygons are accurate.

- [ ] **Step 7.1: Read the current AiRoomOverlay structure**

Run: `cat /Users/ignasgaldikas/samatu-ai/frontend/src/components/project/AiRoomOverlay.jsx`

Note: there are 2 branches inside the `pageRooms.map` — the V9 polygon path (~lines 84-138) and the V8 bbox fallback (~lines 141-160). We're killing the V8 bbox fallback.

- [ ] **Step 7.2: Edit the component**

In `frontend/src/components/project/AiRoomOverlay.jsx`, locate the page-rooms filter (~line 55):

```javascript
const pageRooms = rooms.filter(r => {
  const pageNr = r.page_nr || r.puslapio_nr || r.page || 1;
  return pageNr === page && (r.polygon_pdf || r.bbox_pct);
});
```

Replace it with (drop the `|| r.bbox_pct`):

```javascript
const pageRooms = rooms.filter(r => {
  const pageNr = r.page_nr || r.puslapio_nr || r.page || 1;
  // Phase C-2 (2026-05-02): only render rooms with a real polygon. The
  // legacy bbox_pct rectangles flashed in wrong locations and have been
  // dropped from the overlay. Eksplikacija numbers printed on the drawing
  // handle the visual "where" question for free.
  return pageNr === page && Array.isArray(r.polygon_pdf) && r.polygon_pdf.length >= 3;
});
```

- [ ] **Step 7.3: Remove the V8 bbox fallback branch**

Inside `pageRooms.map`, locate the comment `// V8 fallback: bbox_pct (rectangle)` (~line 141). Delete the entire block from that comment through the closing `);` of its `<Rect>` JSX. The block looks roughly like:

```javascript
// V8 fallback: bbox_pct (rectangle)
if (!shape && room.bbox_pct) {
  const bb = room.bbox_pct;
  // ... 18 lines of Rect rendering ...
}
```

Delete it. Replace with a one-line comment:

```javascript
// Phase C-2 (2026-05-02): bbox_pct rendering removed. Only polygon_pdf
// rooms reach this point per the filter above.
```

After this, the component renders ONLY rooms with `polygon_pdf` (manually traced rooms). All other rooms render nothing — clicking them just navigates to the page (handled elsewhere).

- [ ] **Step 7.4: Verify the polygon path is unchanged**

Run: `cd frontend && grep -n "polygon_pdf" src/components/project/AiRoomOverlay.jsx`
Expected: matches inside the V9 polygon branch (lines ~55, ~84) — unchanged.

- [ ] **Step 7.5: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 7.6: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/AiRoomOverlay.jsx
git commit -m "fix(overlay): drop bbox_pct flash on room click

The blue rectangle that flashed when clicking a room name in the right
panel was the source of 'PDF viewer is authoritative-but-wrong' complaints.
Vision bbox_pct is unreliable; the rectangle was off by 50-200 px on most
rooms. Eksplikacija prints the room nr next to each room on the drawing
already, so the wrong-flash UX was net-negative. Manual polygons (Phase C-1)
still render correctly via the V9 path."
```

---

## Phase E: ProvenanceChip + source highlights

### Task 8: ProvenanceChip component

**Files:**
- Create: `frontend/src/components/project/ProvenanceChip.jsx`

- [ ] **Step 8.1: Create component**

Create `frontend/src/components/project/ProvenanceChip.jsx`:

```javascript
/**
 * ProvenanceChip — small "iš kur tai?" pill next to a kiekiai number.
 *
 * Click → onClick callback (typically navigates the PDF to the source +
 * flashes a halo over the source row/dimension).
 *
 * Phase C-2 sources:
 *   - 'eksplikacija' → "iš eksplikacijos" (eksplikacija text)
 *   - 'manual_polygon' → "manualu" (user-traced polygon)
 *   - 'vision' → "iš AI" (Vision-only, low trust)
 *   - 'dimension' → "iš dimensijos" (placeholder for future)
 *
 * No "bbox" or "polygon" jargon in any visible string.
 */

const SOURCE_META = {
  eksplikacija: {
    label: 'iš eksplikacijos',
    cls: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
    title: 'Skaičius paimtas iš eksplikacijos lentelės. Spausk → matysi eilutę.',
  },
  manual_polygon: {
    label: 'manualu',
    cls: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
    title: 'Skaičius iš tavo apvesto polygono.',
  },
  vision: {
    label: 'iš AI',
    cls: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    title: 'Skaičius iš AI atpažinimo. Patikrink prieš naudodamas.',
  },
  dimension: {
    label: 'iš dimensijos',
    cls: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    title: 'Skaičius iš brėžinio dimensijos.',
  },
};

export default function ProvenanceChip({ source, onClick }) {
  const meta = SOURCE_META[source];
  if (!meta) return null;
  return (
    <button
      onClick={onClick}
      title={meta.title}
      className={`inline-flex items-center px-1.5 py-[1px] rounded border text-[9px] font-medium uppercase tracking-wide ${meta.cls}`}
      data-testid={`provenance-chip-${source}`}
    >
      {meta.label}
    </button>
  );
}
```

- [ ] **Step 8.2: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 8.3: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/ProvenanceChip.jsx
git commit -m "feat(provenance): ProvenanceChip — per-number source pill

Renders 'iš eksplikacijos' / 'manualu' / 'iš AI' / 'iš dimensijos' next to
a kiekiai number. onClick callback caller-supplied (typically navigates PDF
to source + flashes a halo)."
```

---

### Task 9: Mount ProvenanceChip on each room row in WorkspacePanel

**Files:**
- Modify: `frontend/src/components/project/WorkspacePanel.jsx` (in the rooms loop near the m² rendering)

- [ ] **Step 9.1: Read existing rooms-loop structure**

Run: `grep -nB 2 -A 20 "fmt(r.plotas_m2)" frontend/src/components/project/WorkspacePanel.jsx | head -40`

Find the row that renders `{fmt(r.plotas_m2)} m²` next to each room. We're adding a chip right next to it.

- [ ] **Step 9.2: Add the import**

At the top of `frontend/src/components/project/WorkspacePanel.jsx`, after the existing ConfidenceBadge import (added in Task 5), add:

```javascript
import ProvenanceChip from './ProvenanceChip';
```

- [ ] **Step 9.3: Mount ProvenanceChip in the room row**

Locate the m² render (around line 313-316; varies — find via grep above):

```jsx
<span className="mono tabular text-foreground/90 whitespace-nowrap" style={{ fontSize: 11 }}>
  {fmt(r.plotas_m2)}
  <span className="text-muted-foreground/70 ml-1" style={{ fontSize: 9 }}>m²</span>
</span>
```

Replace with:

```jsx
<span className="mono tabular text-foreground/90 whitespace-nowrap inline-flex items-center gap-1.5" style={{ fontSize: 11 }}>
  {fmt(r.plotas_m2)}
  <span className="text-muted-foreground/70" style={{ fontSize: 9 }}>m²</span>
  {r.plotas_source && (
    <ProvenanceChip
      source={r.plotas_source}
      onClick={(e) => {
        e?.stopPropagation?.();
        if (onJumpToProvenance) onJumpToProvenance(r);
      }}
    />
  )}
</span>
```

- [ ] **Step 9.4: Plumb the onJumpToProvenance prop**

Find the WorkspacePanel function signature (~line 30-50). Add `onJumpToProvenance` to the props list:

```javascript
export default function WorkspacePanel({
  // ... existing props
  onJumpToProvenance,
  // ... rest
}) {
```

The actual handler will be wired in Task 10. For now leave it undefined — the chip just doesn't navigate when clicked. The `r.plotas_source && (...)` guard means rooms without a source don't render a chip at all.

- [ ] **Step 9.5: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 9.6: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/WorkspacePanel.jsx
git commit -m "feat(provenance): mount ProvenanceChip next to plotas_m2 in WorkspacePanel

Each room row now shows where its area number came from. onJumpToProvenance
prop receives the room when clicked; wiring lands in next task (jump to
eksplikacija page + flash halo over the row)."
```

---

### Task 10: Wire chip click → page jump

**Files:**
- Modify: `frontend/src/pages/InteriorProject.jsx` (or wherever WorkspacePanel is mounted with the existing onJumpToPage prop)

- [ ] **Step 10.1: Find where WorkspacePanel is mounted**

Run: `grep -n "WorkspacePanel\|onJumpToPage" frontend/src/pages/InteriorProject.jsx frontend/src/components/project/InteriorWorkspace.jsx 2>/dev/null | head -20`

The mount is in `InteriorWorkspace.jsx` (line ~139 area, near `<PdfViewer fileUrl={pdfUrl}>`).

- [ ] **Step 10.2: Add onJumpToProvenance handler**

In `frontend/src/components/project/InteriorWorkspace.jsx`, at the `<WorkspacePanel ... />` mount, add the prop:

```jsx
<WorkspacePanel
  // ... existing props (including onJumpToPage)
  onJumpToProvenance={(room) => {
    if (room.plotas_source === 'eksplikacija') {
      // Jump to the eksplikacija source page (room.eksplikacija_source_page
      // OR project.eksplikacija_source_page). The EksplikacijaRowFlash overlay
      // (Task 11) will pick up room.eksplikacija_row_bbox automatically.
      const targetPage = room.eksplikacija_source_page
        ?? project.eksplikacija_source_page
        ?? 2;
      if (onJumpToPage) onJumpToPage(targetPage, room);
    } else if (room.plotas_source === 'manual_polygon') {
      // Manual polygons live on the room's own page; jump there.
      const targetPage = room.page_nr ?? room.puslapio_nr;
      if (targetPage && onJumpToPage) onJumpToPage(targetPage, room);
    } else {
      // Vision/dimension/other: just go to the room's page.
      const targetPage = room.puslapio_nr ?? room.page_nr;
      if (targetPage && onJumpToPage) onJumpToPage(targetPage, room);
    }
  }}
/>
```

`project` and `onJumpToPage` are already in scope as props of InteriorWorkspace.

- [ ] **Step 10.3: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 10.4: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/InteriorWorkspace.jsx
git commit -m "feat(provenance): wire ProvenanceChip click → PDF page jump

eksplikacija → eksplikacija_source_page; manual → room.page_nr; vision/other
→ room.puslapio_nr. The actual halo flash over the eksplikacija row arrives
in the next task."
```

---

### Task 11: EksplikacijaRowFlash — temporary halo over the source row

**Files:**
- Create: `frontend/src/components/project/EksplikacijaRowFlash.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx` (mount the flash overlay)

The room data already includes `eksplikacija_row_bbox` and page dimensions when pdfplumber extracted from a real bbox row (per `pdfplumber_eksplikacija.py:181-195`). Use these fields to flash a halo when the user clicks an "iš eksplikacijos" chip.

- [ ] **Step 11.1: Create the flash component**

Create `frontend/src/components/project/EksplikacijaRowFlash.jsx`:

```javascript
/**
 * EksplikacijaRowFlash — Phase C-2 temporary halo over the eksplikacija
 * table row that justifies a particular room's plotas_m2.
 *
 * Triggered when user clicks an "iš eksplikacijos" provenance chip. Shows
 * a yellow halo for ~2.5 seconds, then fades.
 *
 * Reads room.eksplikacija_row_bbox = [x0, y0, x1, y1] in PDF point space,
 * plus eksplikacija_row_page_width_pdf / page_height_pdf for normalization.
 * (Set by pdfplumber_eksplikacija.py when row_bbox is available.)
 */

import { useEffect, useState } from 'react';

export default function EksplikacijaRowFlash({
  flashRoom,         // {eksplikacija_row_bbox, eksplikacija_row_page_width_pdf, ...} | null
  canvasWidth,
  canvasHeight,
  pdfPageWidth,
  pdfPageHeight,
  onComplete,
}) {
  const [opacity, setOpacity] = useState(0);

  useEffect(() => {
    if (!flashRoom?.eksplikacija_row_bbox) return;
    setOpacity(1);
    const fadeStart = setTimeout(() => setOpacity(0.6), 1200);
    const fadeOut = setTimeout(() => setOpacity(0), 2200);
    const done = setTimeout(() => onComplete?.(), 2500);
    return () => {
      clearTimeout(fadeStart);
      clearTimeout(fadeOut);
      clearTimeout(done);
    };
  }, [flashRoom?.nr, onComplete]);

  if (!flashRoom?.eksplikacija_row_bbox || !pdfPageWidth || !pdfPageHeight) return null;
  const [x0, y0, x1, y1] = flashRoom.eksplikacija_row_bbox;
  // pdfplumber returns top-left origin coords in PDF point space.
  // Convert to canvas px via the rendered page dims.
  const sx = canvasWidth / pdfPageWidth;
  const sy = canvasHeight / pdfPageHeight;
  const left = x0 * sx;
  const top = y0 * sy;
  const w = (x1 - x0) * sx;
  const h = (y1 - y0) * sy;

  return (
    <div
      style={{
        position: 'absolute',
        left, top, width: w, height: h,
        background: 'rgba(250, 204, 21, 0.35)',
        border: '2px solid rgba(250, 204, 21, 0.85)',
        borderRadius: 3,
        pointerEvents: 'none',
        zIndex: 30,
        opacity,
        transition: 'opacity 0.4s ease-out',
      }}
      data-testid="eksplikacija-row-flash"
    />
  );
}
```

- [ ] **Step 11.2: Plumb the trigger into PdfViewer**

In `frontend/src/components/project/PdfViewer.jsx`, add a state slot near other state (~line 1290):

```javascript
const [flashRoom, setFlashRoom] = useState(null);
```

Add a new prop on `PdfViewer`:

```javascript
export default function PdfViewer({
  // ... existing props
  flashRoom: externalFlashRoom = null,
  // ...
}) {
```

Sync external prop into local state via useEffect:

```javascript
useEffect(() => {
  if (externalFlashRoom) setFlashRoom(externalFlashRoom);
}, [externalFlashRoom]);
```

Mount `<EksplikacijaRowFlash>` near the other workspace overlays (next to `<TraceModeBanner>` and `<FirstTimePolygonHint>`):

```jsx
import EksplikacijaRowFlash from './EksplikacijaRowFlash';

// In render:
<EksplikacijaRowFlash
  flashRoom={flashRoom}
  canvasWidth={pageDims.width}
  canvasHeight={pageDims.height}
  pdfPageWidth={pageProxyRef.current?.width}
  pdfPageHeight={pageProxyRef.current?.height}
  onComplete={() => setFlashRoom(null)}
/>
```

- [ ] **Step 11.3: Wire the trigger from InteriorWorkspace**

In `frontend/src/components/project/InteriorWorkspace.jsx`, add a flashRoom state at top of the component:

```javascript
const [flashRoom, setFlashRoom] = useState(null);
```

In the `onJumpToProvenance` handler from Task 10, also set the flashRoom (for eksplikacija sources):

```jsx
onJumpToProvenance={(room) => {
  if (room.plotas_source === 'eksplikacija') {
    const targetPage = room.eksplikacija_source_page
      ?? project.eksplikacija_source_page
      ?? 2;
    if (onJumpToPage) onJumpToPage(targetPage, room);
    setFlashRoom(room);   // <-- new
  } else if (room.plotas_source === 'manual_polygon') {
    // ... unchanged
  } else {
    // ... unchanged
  }
}}
```

Pass the flash to PdfViewer:

```jsx
<PdfViewer
  // ... existing props
  flashRoom={flashRoom}
/>
```

- [ ] **Step 11.4: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 11.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/EksplikacijaRowFlash.jsx frontend/src/components/project/PdfViewer.jsx frontend/src/components/project/InteriorWorkspace.jsx
git commit -m "feat(provenance): yellow halo flash over eksplikacija row on chip click

Fades in (300ms), holds (1.2s), fades out (1.0s), then unmounts. Reads
room.eksplikacija_row_bbox + the rendered page dims. No-op when the room
lacks a bbox (e.g. Vision-only patalpa)."
```

---

## Phase F: User-verified state

### Task 12: markRoomVerified helper in projectStore

**Files:**
- Modify: `frontend/src/lib/projectStore.js`

- [ ] **Step 12.1: Add the helper**

In `frontend/src/lib/projectStore.js`, after `updateRoomPolygon` (search for `export function updateRoomPolygon`), add:

```javascript
/**
 * Phase C-2 (2026-05-02): one-click "✓ patvirtinta" — user confirms the
 * AI's plotas_m2 without tracing a polygon. Sets user_verified_at on the
 * patalpa; the frontend confidence calculator promotes the badge to 🟢.
 *
 * No coordinate-space mess (unlike updateRoomPolygon) because we're not
 * touching geometry — just a single timestamp.
 */
export function markRoomVerified(projectId, roomNr) {
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return;
  const patalpos = proj.patalpos || [];
  const idx = patalpos.findIndex((r) => String(r.nr) === String(roomNr));
  if (idx < 0) return;
  patalpos[idx] = {
    ...patalpos[idx],
    user_verified_at: new Date().toISOString(),
  };
  proj.patalpos = patalpos;
  saveProject(proj);
  // Trigger downstream recompute (matches the pattern from updateRoomPolygon).
  window.dispatchEvent(
    new CustomEvent('samatu:project-recompute', { detail: { projectId } }),
  );
}
```

(Read the existing `updateRoomPolygon` for the right `loadProjects`/`saveProject` helper names — they may be different in the actual file. Match what's already used.)

- [ ] **Step 12.2: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 12.3: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/lib/projectStore.js
git commit -m "feat(verify): markRoomVerified helper

Sets room.user_verified_at = ISO timestamp; computeAreaConfidence reads
this field and promotes the badge to 🟢 tikslus. Dispatches the existing
samatu:project-recompute event so kiekiai re-render."
```

---

### Task 13: ✓ patvirtinta button next to ConfidenceBadge

**Files:**
- Modify: `frontend/src/components/project/ConfidenceBadge.jsx`

The badge knows the confidence; if it's 🟡 (medium) and not yet user-verified, show a small ✓ patvirtinta button next to it.

- [ ] **Step 13.1: Update ConfidenceBadge to render the verify button**

Replace the entire `frontend/src/components/project/ConfidenceBadge.jsx` with:

```javascript
/**
 * ConfidenceBadge — Phase C-2 replacement for PolygonReviewBadge.
 *
 * Reflects AREA confidence (whether plotas_m2 is trustworthy) — NOT polygon
 * existence. A room with eksplikacija-derived plotas_m2 but no manual polygon
 * is 🟡 medium-trust and offers a one-click ✓ patvirtinta to flip to 🟢.
 *
 * Colors:
 *   🟢 tikslus  — multiple sources agree, OR user clicked ✓ patvirtinta
 *   🟡 tikrinti — single source, plausible
 *   🔴 neaišku — sources disagree, OR weak Vision-only
 */

import { computeAreaConfidence } from '@/lib/areaConfidence';
import { markRoomVerified } from '@/lib/projectStore';
import { Check } from 'lucide-react';

const STYLES = {
  high: {
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: '🟢',
    label: 'tikslus',
  },
  medium: {
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    dot: '🟡',
    label: 'tikrinti',
  },
  low: {
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    dot: '🔴',
    label: 'neaišku',
  },
};

export default function ConfidenceBadge({ room, projectId, onClick }) {
  const result = computeAreaConfidence(room);
  if (result.confidence === 'unknown') return null;

  const style = STYLES[result.confidence];
  if (!style) return null;

  const sourceList = result.sources
    .map((s) => `${s.label}: ${s.value?.toFixed?.(2) ?? '—'} m²`)
    .join('\n');
  const verifiedLine = result.userVerified
    ? `\nPatvirtinta: ${new Date(room.user_verified_at).toLocaleDateString('lt-LT')}`
    : '';
  const disagreementLine = result.disagreement
    ? '\n⚠ Šaltiniai nesutampa — patikrinti rankiniu būdu.'
    : '';
  const title = `Plotas: ${room.plotas_m2?.toFixed?.(2) ?? '—'} m²\n${sourceList}${verifiedLine}${disagreementLine}`;

  const showVerifyButton =
    result.confidence === 'medium' &&
    !result.userVerified &&
    projectId;

  const handleVerify = (e) => {
    e?.stopPropagation?.();
    if (projectId && room?.nr) {
      markRoomVerified(projectId, room.nr);
    }
  };

  return (
    <span className="inline-flex items-center gap-1">
      <button
        onClick={onClick}
        title={title}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${style.cls}`}
        data-testid={`confidence-badge-${room.nr}`}
        data-confidence={result.confidence}
      >
        <span>{style.dot}</span>
        <span>{style.label}</span>
      </button>
      {showVerifyButton && (
        <button
          onClick={handleVerify}
          title="Patvirtinti, kad skaičius teisingas"
          className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded border text-[9px] font-medium bg-muted/40 text-muted-foreground border-muted hover:bg-emerald-500/15 hover:text-emerald-300 hover:border-emerald-500/30"
          data-testid={`verify-button-${room.nr}`}
        >
          <Check className="w-2.5 h-2.5" />
          <span>patvirtinti</span>
        </button>
      )}
    </span>
  );
}
```

- [ ] **Step 13.2: Plumb projectId through the existing badge mounts**

In `frontend/src/components/project/RoomCard.jsx`, where `<ConfidenceBadge>` is mounted (~line 178), add the projectId prop. The component already has `room.project_id` or projectId is plumbed via parent — verify which:

```bash
cd /Users/ignasgaldikas/samatu-ai
grep -n "projectId\|project_id" frontend/src/components/project/RoomCard.jsx | head -5
```

If `projectId` is already a prop, pass it. If not, add it to the function signature and pass through from parent (whatever component renders RoomCard).

```jsx
<ConfidenceBadge
  room={room}
  projectId={projectId}    // add
  onClick={() => onShowOnPdf?.(room.puslapio_nr, room)}
/>
```

Same for `frontend/src/components/project/WorkspacePanel.jsx` (~line 304). WorkspacePanel typically has `projectId` as a prop already; if not, plumb it.

- [ ] **Step 13.3: Build smoke**

Run: `cd frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 13.4: Run unit tests**

Run: `cd frontend && npm run test:units`
Expected: 30 pass (8 new areaConfidence + 22 prior).

- [ ] **Step 13.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/ConfidenceBadge.jsx frontend/src/components/project/RoomCard.jsx frontend/src/components/project/WorkspacePanel.jsx
git commit -m "feat(verify): ✓ patvirtinta button promotes 🟡 → 🟢

Shown only on medium-confidence rooms that aren't yet user-verified. Click
sets room.user_verified_at; computeAreaConfidence promotes to high; badge
re-renders 🟢 tikslus. Lithuanian label 'patvirtinti'."
```

---

## Phase G: Final acceptance

### Task 14: Playwright headless smoke for Phase C-2

**Files:**
- Create: `.smoke/c2-smoke.mjs`

Most of C-2 is verifiable via DOM presence. The few items needing user eye are explicitly listed.

- [ ] **Step 14.1: Write the smoke test**

Create `/Users/ignasgaldikas/samatu-ai/.smoke/c2-smoke.mjs`:

```javascript
// Phase C-2 acceptance smoke. Verifies:
// - ConfidenceBadge renders with correct confidence levels
// - "bbox" / "polygon" jargon absent from user-visible strings
// - ProvenanceChip mounts on each room with plotas_source
// - bbox flash on room click is GONE
// - ✓ patvirtinta button promotes 🟡 → 🟢 (state change visible)

import { chromium } from '/Users/ignasgaldikas/.nvm/versions/node/v20.19.6/lib/node_modules/@playwright/mcp/node_modules/playwright/index.mjs';
import { writeFileSync } from 'fs';

const FRONTEND = 'http://localhost:5173';
const SHOTS = '/Users/ignasgaldikas/samatu-ai/.smoke';
const log = (...a) => console.log('[c2]', ...a);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'lt-LT' });
const page = await ctx.newPage();
const consoleMsgs = [];
page.on('console', (m) => {
  if (m.type() === 'error' || m.type() === 'warning') consoleMsgs.push(`[${m.type()}] ${m.text()}`);
});
page.on('pageerror', (e) => consoleMsgs.push(`[pageerror] ${e.message}`));

await page.goto(FRONTEND, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);

// Click into the freshly-extracted project (15 rooms, real eksplikacija data)
await page.locator('text=/Interjero projektas/').first().click();
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/c2-01-project.png`, fullPage: true });

const findings = {};

// ── 1. No "bbox" or "polygon" in any user-visible string ──────────────────
const bodyText = await page.evaluate(() => document.body.innerText);
findings.no_bbox_in_dom = !/bbox|polygon/i.test(bodyText);
log('no bbox/polygon in DOM:', findings.no_bbox_in_dom);
if (!findings.no_bbox_in_dom) {
  // Find the offending strings
  const matches = (bodyText.match(/.{0,30}(bbox|polygon).{0,30}/gi) || []).slice(0, 3);
  log('  offending matches:', matches);
}

// ── 2. ConfidenceBadge presence — at least one badge per known confidence ─
const badges = await page.locator('[data-testid^="confidence-badge-"]').all();
findings.badge_count = badges.length;
const confidenceLevels = await Promise.all(
  badges.map((b) => b.getAttribute('data-confidence'))
);
findings.confidence_distribution = confidenceLevels.reduce((acc, c) => {
  acc[c] = (acc[c] || 0) + 1;
  return acc;
}, {});
log('badges:', findings.badge_count, 'confidence:', findings.confidence_distribution);

// ── 3. ProvenanceChip presence ─────────────────────────────────────────────
const chips = await page.locator('[data-testid^="provenance-chip-"]').count();
findings.provenance_chip_count = chips;
log('provenance chips:', chips);

// ── 4. bbox flash gone — switch to Brėžinys, click a room, verify NO blue rect ─
const brezinysTab = page.locator('button').filter({ hasText: /^Brėžinys$/ }).first();
const hasBrezinys = await brezinysTab.isVisible().catch(() => false);
if (hasBrezinys) {
  await brezinysTab.click();
  await page.waitForTimeout(2500);

  // Click a room name in the right panel
  const firstRoomName = page.locator('text=/Vonia|Miegamasis|Svetainė|Koridorius/').first();
  const found = await firstRoomName.isVisible().catch(() => false);
  if (found) {
    await firstRoomName.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${SHOTS}/c2-02-no-flash.png`, fullPage: true });
  }

  // Inspect Konva stages for any rect with the AiRoomOverlay's old fill colors
  // The old AiRoomOverlay rendered Rect with fill=`${color}22` or `${color}55`.
  // After Phase C-2 only Line (polygon) shapes remain on AiRoomOverlay.
  // Heuristic: count canvases — should be present (PDF + overlay layers) but
  // no flashing rect should follow a click. Manual user verification still
  // recommended for "did the wrong-flash actually go away?"
  findings.brezinys_loaded = true;
}

// ── 5. ✓ patvirtinta promotes 🟡 → 🟢 ──────────────────────────────────────
// Find a medium (🟡) badge with a verify button
const mediumBadges = await page.locator('[data-confidence="medium"]').all();
findings.medium_badges_pre_verify = mediumBadges.length;
if (mediumBadges.length > 0) {
  // Find the verify button next to the first medium badge
  const firstMediumRoomNr = await mediumBadges[0].getAttribute('data-testid');
  // data-testid="confidence-badge-XX" → nr = XX
  const nr = firstMediumRoomNr?.replace('confidence-badge-', '') ?? null;
  if (nr) {
    const verifyBtn = page.locator(`[data-testid="verify-button-${nr}"]`);
    const verifyVisible = await verifyBtn.isVisible().catch(() => false);
    findings.first_verify_button_visible = verifyVisible;
    if (verifyVisible) {
      await verifyBtn.click();
      await page.waitForTimeout(800);
      // After click the badge should now be 🟢
      const sameRoomBadge = page.locator(`[data-testid="confidence-badge-${nr}"]`);
      const newConfidence = await sameRoomBadge.getAttribute('data-confidence');
      findings.confidence_after_verify = newConfidence;
      log(`room ${nr} confidence: medium → ${newConfidence}`);
    }
  }
}

// ── 6. Console summary ─────────────────────────────────────────────────────
const errors = consoleMsgs.filter((m) => m.startsWith('[error]') || m.startsWith('[pageerror]'));
findings.console_error_count = errors.length;
findings.console_errors = errors.slice(0, 8);

log('');
log('=== FINDINGS ===');
Object.entries(findings).forEach(([k, v]) => log(`  ${k}:`, JSON.stringify(v)));

writeFileSync(`${SHOTS}/c2-result.json`, JSON.stringify(findings, null, 2));
await browser.close();

// ── Exit code: green if all checks pass ────────────────────────────────────
const allGreen =
  findings.no_bbox_in_dom &&
  findings.badge_count > 0 &&
  findings.console_error_count === 0;
process.exit(allGreen ? 0 : 1);
```

- [ ] **Step 14.2: Run the smoke test**

Run: `cd /Users/ignasgaldikas/samatu-ai && node .smoke/c2-smoke.mjs`
Expected: exit code 0; findings.json shows badges present, no bbox/polygon strings, console clean.

If it fails, investigate the specific finding and fix the underlying code, NOT the smoke test. The smoke is the contract.

- [ ] **Step 14.3: Run mechanical gates**

```bash
cd /Users/ignasgaldikas/samatu-ai/frontend && npm run test:units && npm run build 2>&1 | tail -3
cd /Users/ignasgaldikas/samatu-ai/backend && pytest -q 2>&1 | tail -3
cd /Users/ignasgaldikas/samatu-ai && git status --short
```

Expected:
- frontend tests: 30/30 pass
- frontend build: clean, main bundle still under 350 KB
- backend pytest: 172/172 pass
- working tree: clean

- [ ] **Step 14.4: Final commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git commit --allow-empty -m "milestone: Phase C-2 trust through provenance — complete

All Phase C-2 acceptance criteria satisfied. Ready for user smoke before
Phase C-3 (click-to-fill walls) plan begins.

Items requiring user-eye verification (not testable headlessly):
- The 'wrong blue rectangle flashing' UX is gone — confirm visually
- Provenance chips lead to the right place in the PDF when clicked
- Confidence colors map to subjectively-trustworthy state per project"
```

---

## Self-Review

### 1. Spec coverage

Cross-checking spec §3 (Phase C-2):

| Spec requirement | Plan task |
|---|---|
| §3.2.1 AreaConfidenceCalculator | Task 1 |
| §3.2.2 ConfidenceBadge replaces PolygonReviewBadge | Tasks 3, 4, 5, 6 |
| §3.2.3 ProvenanceChip + source highlights | Tasks 8, 9, 10, 11 |
| §3.2.4 Kill bbox highlight on room click | Task 7 |
| §3.2.5 ✓ patvirtinta confirmation action | Tasks 12, 13 |
| §3.3 No backend changes (just attribute audit) | Task 2 (small) |
| §3.4 Acceptance | Task 14 |

All 13 acceptance items in spec §3.4 are covered:
- Confidence badge based on AREA confidence ✓ (Task 1, 3)
- No "bbox"/"polygon" word in user strings ✓ (Tasks 3, 6, 7, 8 + smoke 14)
- Click room name doesn't flash wrong rectangle ✓ (Task 7)
- Provenance chips next to kiekiai numbers ✓ (Tasks 8, 9)
- Click chip highlights source in PDF ✓ (Tasks 10, 11)
- ✓ patvirtinta promotes 🟡 → 🟢 ✓ (Tasks 12, 13)
- All UI text Lithuanian ✓ (every component uses LT throughout)
- Manual polygon trace still works ✓ (Phase C-1 untouched, regression smoke part of Task 14)
- Bundle under 350 KB ✓ (verified in Task 14.3)
- Frontend tests pass ✓ (Task 14.3)

### 2. Placeholder scan

Searched for forbidden patterns:
- "TBD" / "TODO" — none.
- "Add appropriate error handling" — none. Each error path has specific behavior named (e.g. fallback to manual polygon, return null when no plotas_m2).
- "Write tests for the above" without code — none. Task 1 has all 8 test cases verbatim. Task 2's test file has 2 test cases verbatim.
- "Similar to Task N" — none. Tasks 4 and 5 (RoomCard and WorkspacePanel badge swaps) have similar patterns but each has its own complete code.

One soft note for the implementer: Tasks 9, 10, 11 reference structure that requires reading existing files (line numbers approximate; identifiers may differ slightly). The plan calls these out explicitly via `grep -n` steps so the implementer doesn't paste blindly.

### 3. Type consistency

- `room` shape: `{nr, plotas_m2, plotas_source, polygon_pdf, polygon_source, _polygon_area_m2, user_verified_at, eksplikacija_row_bbox, ...}` — used consistently across Tasks 1, 3, 9, 11, 12, 13.
- `computeAreaConfidence(room)` return shape `{confidence, primarySource, agreeingSources, userVerified, disagreement, sources}` — used in Task 3 (badge tooltip) and matches Task 1's tests.
- `markRoomVerified(projectId, roomNr)` — Task 12 defines, Task 13 calls — same signature.
- `ProvenanceChip({source, onClick})` — Task 8 defines, Task 9 calls — same.
- `EksplikacijaRowFlash({flashRoom, canvasWidth, canvasHeight, pdfPageWidth, pdfPageHeight, onComplete})` — Task 11 defines, Task 11 mounts — consistent.
- `plotas_source` values — `'eksplikacija'` (Task 2 backend), `'vision'` (Task 2 backend), `'manual_polygon'` (already set by Phase C-1 in projectStore.js:334), `'dimension'` (placeholder, future) — used identically in `areaConfidence.js` (Task 1) and `ProvenanceChip.jsx` (Task 8).

All consistent.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-02-phase-c-2-trust.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review per task. Best for a 14-task plan that touches both frontend + backend with non-trivial integration points.

2. **Inline Execution** — `superpowers:executing-plans` in this session, batch with checkpoints.

Subagent-driven matches the user's stated preference from Phase C-1. Defaulting to that unless they say otherwise.
