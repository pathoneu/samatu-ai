# Sprint 3 — Chrome + Verification Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Sprint 2's minimal `/v2` UI with a togal-style takeoff workspace in our light palette, plus an opt-in verification wizard that walks contractors through 🟡/🔴 positions step-by-step.

**Architecture:** Frontend: 12 new components (`TopBar`, `ToolRail`, `RightPanel` with 3 tabs, `QuantitiesPanel`, `AiPanel`, `SuvestinePanel`, `VerificationWizard`, `InlineEditor`, `PageNavigator`) + 3 pure libs (`verificationQueue`, `categoryColor`, `scaleStore`) + extensions to `viewerStore`, `TakeoffCanvas`, `AnnotationLayer`. `MiniKZPanel.jsx` and `InteriorProjectV2.jsx` body get replaced. All Sprint 2 backend endpoints reused as-is. Backend appendix (Section 6 of plan) adds self-verify pass, grid overlay, prompt cleanup — can defer to Sprint 4 if frontend chrome runs over budget.

**Tech Stack:** React 18, Vite, Konva (`react-konva`), zustand, pdfjs (via `react-pdf`), Tailwind + shadcn (existing palette `--primary`/`--conf-*`/`--source-*`). Pure libs tested with `node --test`. JSX components verified via `npx vite build` clean + browser smoke at end. Backend Section 6: Python 3.11, FastAPI, Pillow, Anthropic SDK, pytest.

**Spec:** `docs/superpowers/specs/2026-05-04-sprint-3-chrome-design.md` (commit `b71537c`)

**Working tree:** `/Users/ignasgaldikas/samatu-ai/.claude/worktrees/sprint-2-gestures` on branch `worktree-sprint-2-gestures` (Sprint 2 NOT yet merged — Sprint 3 lands on top). Python: `/Users/ignasgaldikas/samatu-ai/venv/bin/python`. Frontend tests: `npm run test:units` (currently 82 pass).

---

## File Structure

### Created — frontend libs (TDD with `node --test`)
- `frontend/src/lib/verificationQueue.js` + `.test.js` — pure: builds queue from rooms+pozicijos, orders 🔴 first then 🟡, computes `dispute_type` and `polygon` auto-zoom target per item
- `frontend/src/lib/categoryColor.js` + `.test.js` — pure: maps `skyrius_enum` → border-left tint hex; primary blue for accent
- `frontend/src/lib/scaleStore.js` + `.test.js` — zustand sub-store: `{ ratio: 50, locked: true, setRatio, toggleLock }`. Sourced from project state when available.

### Created — frontend components (build-verified, no JSX unit tests per Sprint 1 follow-up #2)
- `frontend/src/components/workspace/TopBar.jsx` — chrome row 48px: logo, project name, page nav, zoom, Patikrinti button, Sąmatų AI button
- `frontend/src/components/workspace/ToolRail.jsx` — vertical rail 50px: 10 buttons (Selection / Pan / Liniuotė / G1✨ / G5✨ / G4✨ / G2 / G3 / Undo / Markup) + dividers
- `frontend/src/components/workspace/RightPanel.jsx` — 320px tabbed container: ✨ AI / 📋 Kiekiai / 📊 Suvestinė
- `frontend/src/components/canvas/PageNavigator.jsx` — page picker dropdown
- `frontend/src/components/panels/QuantitiesPanel.jsx` — replaces MiniKZPanel; category tree + filter pills + search + footer + bidirectional highlight + G7 inline edit per row
- `frontend/src/components/panels/AiPanel.jsx` — "Run Sąmatų AI" button + recent-runs list
- `frontend/src/components/panels/SuvestinePanel.jsx` — Σ totals card + per-category bars + PVM line
- `frontend/src/components/wizard/VerificationWizard.jsx` — bottom panel ~140px, progress dots, question card, Taip/Pataisyti/Praleisti
- `frontend/src/components/wizard/InlineEditor.jsx` — controlled input that appears in wizard's question slot when fixing a number dispute

### Created — backend (Section 6 appendix; can move to Sprint 4 if budget runs short)
- `backend/extractor/verify_pass.py` + `backend/tests/test_verify_pass.py`
- `backend/extractor/grid_overlay.py` + `backend/tests/test_grid_overlay.py`

### Modified — frontend
- `frontend/src/lib/viewerStore.js` + `.test.js` — extend with `wizardOpen`, `wizardItemPolygon`, `lockOnConfirm`, `currentPage`, `setWizardOpen`, `setWizardItemPolygon`, `setLockOnConfirm`, `setCurrentPage`. Existing `selection` / `verificationQueue` / `verificationIndex` filled out.
- `frontend/src/components/canvas/TakeoffCanvas.jsx` — read `currentPage` from `viewerStore` (was hardcoded `pageIdx={0}`); add subtle blueprint grid CSS background; mount Mastelis badge bottom-left
- `frontend/src/components/canvas/AnnotationLayer.jsx` — accept `highlightedRoomId` prop; thicken stroke + brighten fill on highlight; render vertex squares only when `selection.kind === 'polygon'`; render verification target glow when `wizardOpen && wizardItemPolygon`
- `frontend/src/pages/InteriorProjectV2.jsx` — body rewritten: compose `<TopBar>` + `<ToolRail>` + `<TakeoffCanvas>` + `<RightPanel>` + `<VerificationWizard>` (conditional)

### Modified — backend (Section 6 appendix)
- `backend/extractor/prompt.py` — strip ~2,000 tokens of unused formula text (find via grep, validate accuracy unchanged)
- `backend/extractor/vision_call.py` — async-trigger `verify_pass` post-Pass-1 when `ENABLE_VERIFY_PASS=1`; merge `corrections[]` into result

### Deleted
- `frontend/src/components/panels/MiniKZPanel.jsx` — superseded by `QuantitiesPanel`

### Updated
- `CHANGELOG.md`
- `docs/sprint-3-followups.md` (new at end of sprint)

---

## Task 1: viewerStore extensions

**Files:**
- Modify: `frontend/src/lib/viewerStore.js`
- Modify: `frontend/src/lib/viewerStore.test.js`

- [ ] **Step 1.1: Append failing tests**

Append to `frontend/src/lib/viewerStore.test.js`:

```javascript
test('createViewerStore: wizardOpen defaults to false', () => {
  const store = createViewerStore();
  assert.equal(store.getState().wizardOpen, false);
});

test('createViewerStore: setWizardOpen toggles', () => {
  const store = createViewerStore();
  store.getState().setWizardOpen(true);
  assert.equal(store.getState().wizardOpen, true);
  store.getState().setWizardOpen(false);
  assert.equal(store.getState().wizardOpen, false);
});

test('createViewerStore: wizardItemPolygon defaults to null', () => {
  const store = createViewerStore();
  assert.equal(store.getState().wizardItemPolygon, null);
});

test('createViewerStore: setWizardItemPolygon stores polygon array', () => {
  const store = createViewerStore();
  const poly = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]];
  store.getState().setWizardItemPolygon(poly);
  assert.deepEqual(store.getState().wizardItemPolygon, poly);
});

test('createViewerStore: lockOnConfirm defaults to false', () => {
  const store = createViewerStore();
  assert.equal(store.getState().lockOnConfirm, false);
});

test('createViewerStore: setLockOnConfirm flips for one click', () => {
  const store = createViewerStore();
  store.getState().setLockOnConfirm(true);
  assert.equal(store.getState().lockOnConfirm, true);
});

test('createViewerStore: currentPage defaults to 0', () => {
  const store = createViewerStore();
  assert.equal(store.getState().currentPage, 0);
});

test('createViewerStore: setCurrentPage updates index', () => {
  const store = createViewerStore();
  store.getState().setCurrentPage(3);
  assert.equal(store.getState().currentPage, 3);
});
```

- [ ] **Step 1.2: Run, expect 8 fails**

`cd frontend && node --test src/lib/viewerStore.test.js`
Expected: 8 new fails (currentPage / wizard* / lockOnConfirm / setters not defined). Existing 7 still pass.

- [ ] **Step 1.3: Implement extensions**

In `frontend/src/lib/viewerStore.js`, inside the `createStore` callback object, ADD (next to `selection` and `verificationQueue`):

```javascript
    // Sprint 3: page navigation drives TakeoffCanvas pageIdx
    currentPage: 0,
    setCurrentPage: (currentPage) => set({ currentPage }),

    // Sprint 3: wizard state
    wizardOpen: false,
    setWizardOpen: (wizardOpen) => set({ wizardOpen }),
    wizardItemPolygon: null,
    setWizardItemPolygon: (wizardItemPolygon) => set({ wizardItemPolygon }),
    lockOnConfirm: false,                  // Shift+Taip flips for one click
    setLockOnConfirm: (lockOnConfirm) => set({ lockOnConfirm }),
```

- [ ] **Step 1.4: Run tests**

`cd frontend && node --test src/lib/viewerStore.test.js`
Expected: 15/15 pass (7 existing + 8 new).

- [ ] **Step 1.5: Run full frontend suite — no regression**

`cd frontend && npm run test:units 2>&1 | tail -5`
Expected: 90/90 pass (was 82 + 8 new).

- [ ] **Step 1.6: Commit**

```bash
git add frontend/src/lib/viewerStore.js frontend/src/lib/viewerStore.test.js
git commit -m "feat(sprint-3): viewerStore — wizard state + currentPage

Adds: wizardOpen, wizardItemPolygon (auto-zoom target), lockOnConfirm
(Shift+Taip), currentPage. All defaults safe (false / null / 0).
Setters use plain set() — no derived state coupling."
```

---

## Task 2: `verificationQueue.js` — build queue from rooms+pozicijos

**Files:**
- Create: `frontend/src/lib/verificationQueue.js`
- Create: `frontend/src/lib/verificationQueue.test.js`

- [ ] **Step 2.1: Failing tests**

```javascript
// frontend/src/lib/verificationQueue.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildQueue, advanceQueue, isQueueComplete, classifyDispute,
} from './verificationQueue.js';

test('buildQueue: empty inputs return empty queue', () => {
  assert.deepEqual(buildQueue({ rooms: [], pozicijos: [] }), []);
});

test('buildQueue: skips 🟢 (high confidence) items', () => {
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', kiekis: 10, confidence: 'high', skyrius_label: 'Apdaila', aprasymas: 'Sienų dažymas' },
    ],
  });
  assert.equal(queue.length, 0);
});

test('buildQueue: includes 🟡 + 🔴, orders 🔴 first', () => {
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', kiekis: 10, confidence: 'med', skyrius_label: 'Apdaila', aprasymas: 'A' },
      { id: 'p2', kiekis: 20, confidence: 'low', skyrius_label: 'Apdaila', aprasymas: 'B' },
      { id: 'p3', kiekis: 30, confidence: 'med', skyrius_label: 'Plytelės', aprasymas: 'C' },
    ],
  });
  assert.equal(queue.length, 3);
  assert.equal(queue[0].id, 'p2'); // 🔴 first
  assert.equal(queue[1].confidence, 'med');
  assert.equal(queue[2].confidence, 'med');
});

test('buildQueue: skips locked pozicijos (already user-confirmed)', () => {
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', kiekis: 10, confidence: 'med', override_locked: true, skyrius_label: 'X', aprasymas: 'X' },
      { id: 'p2', kiekis: 20, confidence: 'med', skyrius_label: 'Y', aprasymas: 'Y' },
    ],
  });
  assert.equal(queue.length, 1);
  assert.equal(queue[0].id, 'p2');
});

test('buildQueue: skipped items stay in queue but are flagged', () => {
  // Skipped state lives outside buildQueue; this test verifies that
  // buildQueue accepts a `skipped` Set and propagates it.
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', confidence: 'med', kiekis: 5, skyrius_label: 'X', aprasymas: 'X' },
      { id: 'p2', confidence: 'med', kiekis: 6, skyrius_label: 'Y', aprasymas: 'Y' },
    ],
    skipped: new Set(['p1']),
  });
  assert.equal(queue.length, 2);
  assert.equal(queue.find(q => q.id === 'p1').skipped, true);
  assert.equal(queue.find(q => q.id === 'p2').skipped, false);
});

test('buildQueue: includes room polygon for auto-zoom (when room_id present)', () => {
  const queue = buildQueue({
    rooms: [
      { id: 'r1', polygon_pct: [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]] },
    ],
    pozicijos: [
      { id: 'p1', confidence: 'med', kiekis: 5, room_id: 'r1', skyrius_label: 'X', aprasymas: 'X' },
    ],
  });
  assert.equal(queue.length, 1);
  assert.deepEqual(queue[0].polygon, [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]);
});

test('classifyDispute: pozicijos in m²/m³/m → number', () => {
  assert.equal(classifyDispute({ vnt: 'm2' }), 'number');
  assert.equal(classifyDispute({ vnt: 'm3' }), 'number');
  assert.equal(classifyDispute({ vnt: 'm' }), 'number');
  assert.equal(classifyDispute({ vnt: 'kg' }), 'number');
  assert.equal(classifyDispute({ vnt: 'l' }), 'number');
});

test('classifyDispute: pozicijos in vnt with skyrius=elektra/santechnika → count', () => {
  assert.equal(classifyDispute({ vnt: 'vnt', skyrius: 'elektra' }), 'count');
  assert.equal(classifyDispute({ vnt: 'vnt', skyrius: 'santechnika' }), 'count');
});

test('classifyDispute: vnt with no recognized skyrius → number (safe default)', () => {
  assert.equal(classifyDispute({ vnt: 'vnt', skyrius: 'apdaila' }), 'number');
});

test('advanceQueue: increments index', () => {
  assert.equal(advanceQueue(0, 3), 1);
  assert.equal(advanceQueue(1, 3), 2);
});

test('advanceQueue: caps at length (does not overflow)', () => {
  assert.equal(advanceQueue(2, 3), 3);
  assert.equal(advanceQueue(3, 3), 3); // already at end
});

test('isQueueComplete: true when index >= length', () => {
  assert.equal(isQueueComplete(2, 3), false);
  assert.equal(isQueueComplete(3, 3), true);
  assert.equal(isQueueComplete(4, 3), true);
});
```

- [ ] **Step 2.2: Run, expect FAIL (module missing)**

`cd frontend && node --test src/lib/verificationQueue.test.js`

- [ ] **Step 2.3: Implement**

```javascript
// frontend/src/lib/verificationQueue.js
/**
 * Sprint 3: verification queue builder + helpers.
 *
 * The wizard panel reads a queue of {id, label, kiekis, vnt, polygon,
 * dispute_type, skipped} items derived from rooms+pozicijos. Order:
 * 🔴 (low) first, then 🟡 (med). 🟢 (high) auto-trusted (never queued).
 * Locked items (override_locked) skipped — already user-confirmed.
 *
 * Spec §4.5 (data flow) + §5.3 (wizard mechanics).
 */

const CONFIDENCE_RANK = { low: 0, med: 1, high: 2 }; // 🔴 sorts before 🟡

export function classifyDispute(poz) {
  // Number disputes (m², m³, m, kg, l) → bottom-panel inline editor
  // Count disputes (vnt in elektra/santechnika) → canvas G2/G3 cursor
  // Default: number (safer — wizard offers inline edit)
  const vnt = (poz.vnt || '').toLowerCase();
  const skyrius = (poz.skyrius || '').toLowerCase();
  if (vnt === 'vnt' && (skyrius === 'elektra' || skyrius === 'santechnika')) {
    return 'count';
  }
  return 'number';
}

export function buildQueue({ rooms = [], pozicijos = [], skipped = new Set() }) {
  const roomById = new Map();
  for (const r of rooms) {
    if (r.id) roomById.set(r.id, r);
  }

  const items = [];
  for (const p of pozicijos) {
    if (p.override_locked) continue;          // already confirmed
    const conf = (p.confidence || 'med').toLowerCase();
    if (conf === 'high') continue;             // auto-trust 🟢
    const room = p.room_id ? roomById.get(p.room_id) : null;
    items.push({
      id: p.id,
      label: `${p.skyrius_label || p.skyrius || ''} · ${p.aprasymas || ''}`.trim(),
      kiekis: p.kiekis,
      vnt: p.vnt,
      confidence: conf,
      polygon: room?.polygon_pct ?? null,
      dispute_type: classifyDispute(p),
      skipped: skipped.has(p.id),
      saltinis: p.saltinis || null,
    });
  }

  // Stable sort: 🔴 first, then 🟡 in original order
  items.sort((a, b) => CONFIDENCE_RANK[a.confidence] - CONFIDENCE_RANK[b.confidence]);
  return items;
}

export function advanceQueue(currentIndex, length) {
  return Math.min(currentIndex + 1, length);
}

export function isQueueComplete(currentIndex, length) {
  return currentIndex >= length;
}
```

- [ ] **Step 2.4: Tests pass**

`cd frontend && node --test src/lib/verificationQueue.test.js`
Expected: 12/12 pass.

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/lib/verificationQueue.js frontend/src/lib/verificationQueue.test.js
git commit -m "feat(sprint-3): verificationQueue lib

Pure module: buildQueue() filters 🔴+🟡 from pozicijos, skips locked,
orders 🔴 first. classifyDispute() maps unit+skyrius to dispute_type
(number → bottom-panel editor; count → canvas G2/G3 cursor).
advanceQueue + isQueueComplete are tiny helpers."
```

---

## Task 3: `categoryColor.js` + `scaleStore.js`

**Files:**
- Create: `frontend/src/lib/categoryColor.js` + `.test.js`
- Create: `frontend/src/lib/scaleStore.js` + `.test.js`

- [ ] **Step 3.1: Failing test for categoryColor**

```javascript
// frontend/src/lib/categoryColor.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { categoryAccent, BRAND_PRIMARY } from './categoryColor.js';

test('categoryAccent: known categories return brand primary blue', () => {
  assert.equal(categoryAccent('apdaila'), BRAND_PRIMARY);
  assert.equal(categoryAccent('plyteliu_darbai'), BRAND_PRIMARY);
  assert.equal(categoryAccent('elektra'), BRAND_PRIMARY);
});

test('categoryAccent: unknown skyrius defaults to brand primary', () => {
  assert.equal(categoryAccent('something_new'), BRAND_PRIMARY);
  assert.equal(categoryAccent(null), BRAND_PRIMARY);
  assert.equal(categoryAccent(undefined), BRAND_PRIMARY);
});

test('BRAND_PRIMARY is the construction blue from index.css', () => {
  assert.equal(BRAND_PRIMARY, '#2a6fb5');
});
```

- [ ] **Step 3.2: Run, expect FAIL**

`cd frontend && node --test src/lib/categoryColor.test.js`

- [ ] **Step 3.3: Implement categoryColor**

```javascript
// frontend/src/lib/categoryColor.js
/**
 * Sprint 3: maps `skyrius_enum` to category accent color.
 *
 * Decision (spec §3 locked): single brand-blue across all categories.
 * Module exists to keep room for future per-category palette without
 * touching consumer components. For now: every category returns the
 * same primary blue.
 */

export const BRAND_PRIMARY = '#2a6fb5'; // from index.css --primary 211 62% 44%

export function categoryAccent(_skyrius) {
  return BRAND_PRIMARY;
}
```

- [ ] **Step 3.4: Test pass**

`cd frontend && node --test src/lib/categoryColor.test.js`
Expected: 3/3 pass.

- [ ] **Step 3.5: Failing test for scaleStore**

```javascript
// frontend/src/lib/scaleStore.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createScaleStore } from './scaleStore.js';

test('createScaleStore: defaults', () => {
  const store = createScaleStore();
  assert.equal(store.getState().ratio, 50);
  assert.equal(store.getState().locked, true);
});

test('createScaleStore: setRatio updates', () => {
  const store = createScaleStore();
  store.getState().setRatio(100);
  assert.equal(store.getState().ratio, 100);
});

test('createScaleStore: toggleLock flips', () => {
  const store = createScaleStore();
  assert.equal(store.getState().locked, true);
  store.getState().toggleLock();
  assert.equal(store.getState().locked, false);
  store.getState().toggleLock();
  assert.equal(store.getState().locked, true);
});

test('createScaleStore: setRatio coerces strings to numbers', () => {
  const store = createScaleStore();
  store.getState().setRatio('200');
  assert.equal(store.getState().ratio, 200);
});

test('createScaleStore: setRatio rejects non-positive values silently', () => {
  const store = createScaleStore();
  store.getState().setRatio(0);
  assert.equal(store.getState().ratio, 50); // unchanged
  store.getState().setRatio(-50);
  assert.equal(store.getState().ratio, 50); // unchanged
});
```

- [ ] **Step 3.6: Implement scaleStore**

```javascript
// frontend/src/lib/scaleStore.js
/**
 * Sprint 3: scale-badge state.
 *
 * Holds the current drawing scale ratio (1:N) and lock flag. Lock means
 * the user has confirmed the scale; subsequent AI runs respect the
 * locked value instead of re-detecting.
 *
 * Default 50 (1:50) matches LT residential floor-plan convention.
 */
import { createStore } from 'zustand/vanilla';

export function createScaleStore() {
  return createStore((set, get) => ({
    ratio: 50,
    locked: true,
    setRatio: (value) => {
      const n = Number(value);
      if (!Number.isFinite(n) || n <= 0) return;
      set({ ratio: n });
    },
    toggleLock: () => set({ locked: !get().locked }),
  }));
}

export const scaleStore = createScaleStore();
```

- [ ] **Step 3.7: Test pass**

`cd frontend && node --test src/lib/scaleStore.test.js`
Expected: 5/5 pass.

- [ ] **Step 3.8: Commit**

```bash
git add frontend/src/lib/categoryColor.js frontend/src/lib/categoryColor.test.js frontend/src/lib/scaleStore.js frontend/src/lib/scaleStore.test.js
git commit -m "feat(sprint-3): categoryColor + scaleStore libs

categoryColor: single primary blue (#2a6fb5) per spec §3 locked decision;
indirection allows per-category palette later without touching consumers.
scaleStore: zustand sub-store with ratio (1:N) and lock; setRatio coerces
strings, silently rejects non-positive values."
```

---

## Task 4: `<TopBar>` component

**Files:**
- Create: `frontend/src/components/workspace/TopBar.jsx`

- [ ] **Step 4.1: Implement**

```jsx
// frontend/src/components/workspace/TopBar.jsx
/**
 * Sprint 3: chrome top bar (48px tall).
 *
 * Layout (left → right):
 *   [logo] {projectName} / {subtitle}  |  ← {page/total ▾} →  {pageTitle}
 *   ...flex spacer...
 *   [− zoom% +]  [🔍 Ieškoti]  [🟡 N →]?  [✨ Sąmatų AI]  [⋯]
 *
 * Patikrinti button hidden when queueCount===0.
 *
 * Spec §5.4 top-bar behaviors.
 */
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';

export function TopBar({
  projectName,
  subtitle,
  pageTitle,
  totalPages,
  queueCount,
  onPrevPage,
  onNextPage,
  onPagePicker,
  onZoomOut,
  onZoomIn,
  onSearch,
  onWizard,
  onAiRun,
  onMore,
}) {
  const scale = useStore(viewerStore, (s) => s.scale);
  const currentPage = useStore(viewerStore, (s) => s.currentPage);
  const zoomPct = Math.round(scale * 100);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', height: 48,
      background: '#fbfaf7', borderBottom: '1px solid #d4d2cb',
      padding: '0 12px', gap: 10, fontSize: 13, color: '#171717',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 26, height: 26, background: '#2a6fb5',
          borderRadius: 5, display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: 11,
        }}>SĄ</div>
        <span style={{ fontWeight: 600 }}>{projectName}</span>
        {subtitle && <>
          <span style={{ opacity: 0.4 }}>/</span>
          <span style={{ opacity: 0.7 }}>{subtitle}</span>
        </>}
      </div>
      <div style={{ height: 20, width: 1, background: '#d4d2cb' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button onClick={onPrevPage} disabled={currentPage <= 0}
          style={{ background: 'transparent', border: 0, color: '#171717', fontSize: 14, padding: '2px 4px', cursor: 'pointer' }}>←</button>
        <button onClick={onPagePicker} style={{
          background: '#fff', border: '1px solid #d4d2cb', color: '#171717',
          padding: '3px 10px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>{currentPage + 1} / {totalPages} ▾</button>
        <button onClick={onNextPage} disabled={currentPage >= totalPages - 1}
          style={{ background: 'transparent', border: 0, color: '#171717', fontSize: 14, padding: '2px 4px', cursor: 'pointer' }}>→</button>
      </div>
      {pageTitle && <span style={{ opacity: 0.6, fontSize: 12 }}>{pageTitle}</span>}
      <div style={{ flex: 1 }} />
      <div style={{
        display: 'flex', alignItems: 'center', background: '#fff',
        border: '1px solid #d4d2cb', borderRadius: 5, padding: 1,
      }}>
        <button onClick={onZoomOut} style={{ background: 'transparent', border: 0, padding: '2px 8px', fontSize: 14, cursor: 'pointer' }}>−</button>
        <span style={{ fontVariantNumeric: 'tabular-nums', minWidth: 42, textAlign: 'center', fontSize: 12 }}>{zoomPct}%</span>
        <button onClick={onZoomIn} style={{ background: 'transparent', border: 0, padding: '2px 8px', fontSize: 14, cursor: 'pointer' }}>+</button>
      </div>
      <button onClick={onSearch} style={{
        background: '#fff', border: '1px solid #d4d2cb', color: '#3b3b3b',
        padding: '5px 10px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
      }}>🔍 Ieškoti</button>
      {queueCount > 0 && (
        <button onClick={onWizard} style={{
          background: '#fdf6e7', border: '1px solid #c97a2c', color: '#9a5d20',
          padding: '6px 12px', borderRadius: 5, fontSize: 12, fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
        }}>
          <span style={{ display: 'inline-block', width: 6, height: 6, background: '#c97a2c', borderRadius: '50%' }} />
          Patikrinti {queueCount} →
        </button>
      )}
      <button onClick={onAiRun} style={{
        background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
        padding: '6px 14px', borderRadius: 5, fontSize: 12, fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(42,111,181,0.3)',
      }}>✨ Sąmatų AI</button>
      <button onClick={onMore} style={{
        background: '#fff', border: '1px solid #d4d2cb', color: '#3b3b3b',
        padding: '5px 10px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
      }}>⋯</button>
    </div>
  );
}
```

- [ ] **Step 4.2: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean build.

- [ ] **Step 4.3: Commit**

```bash
git add frontend/src/components/workspace/TopBar.jsx
git commit -m "feat(sprint-3): TopBar workspace chrome (48px)

Project name + page nav + zoom + search + Patikrinti N (conditional)
+ Sąmatų AI button + ⋯ menu. Reads viewerStore.scale and currentPage
directly. Patikrinti hidden when queueCount===0."
```

---

## Task 5: `<ToolRail>` component

**Files:**
- Create: `frontend/src/components/workspace/ToolRail.jsx`

- [ ] **Step 5.1: Implement**

```jsx
// frontend/src/components/workspace/ToolRail.jsx
/**
 * Sprint 3: vertical tool rail (50px wide).
 *
 * 10 buttons (top → bottom):
 *   ↖ Selection (Esc) — default active
 *   ✥ Pan (V or Space)
 *   ⊏ Liniuotė (matavimas)
 *   ───
 *   ⌖ G1 click-to-fill (1) — ✨ uses Vision
 *   ◌ G5 lasso (5)        — ✨ uses Vision
 *   🎨 G4 eyedropper (4)   — ✨ uses Vision
 *   ───
 *   ＋ G2 add count (2)
 *   − G3 remove count (3)
 *   ───
 *   ↶ Undo (Cmd+Z)
 *   ✎ Markup
 *
 * Reads viewerStore.currentTool; calls setCurrentTool on click.
 * Keyboard shortcuts (Sprint 2 keyboardShortcuts.js) still work.
 *
 * Spec §5.5 ToolRail behaviors.
 */
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';

const TOOLS = [
  { id: 'pan',  label: 'Selection (Esc)',   icon: '↖', kind: 'pan' },
  { id: 'pan2', label: 'Pan (V / Space)',   icon: '✥', kind: 'pan' },
  { id: 'ruler', label: 'Liniuotė',         icon: '⊏', kind: 'ruler' },
  { divider: true },
  { id: 'g1', label: 'Click-to-fill (1)',   icon: '⌖', kind: 'g1', ai: true },
  { id: 'g5', label: 'Lasso (5)',           icon: '◌', kind: 'g5', ai: true },
  { id: 'g4', label: 'Eyedropper (4)',      icon: '🎨', kind: 'g4', ai: true },
  { divider: true },
  { id: 'g2', label: 'Skaičiuoti (2)',      icon: '＋', kind: 'g2' },
  { id: 'g3', label: 'Šalinti (3)',         icon: '−',  kind: 'g3' },
  { divider: true },
  { id: 'undo',   label: 'Atšaukti (Cmd+Z)', icon: '↶', kind: 'undo' },
  { id: 'markup', label: 'Markup',          icon: '✎', kind: 'markup' },
];

export function ToolRail({ onUndo, onMarkup, onRuler }) {
  const currentTool = useStore(viewerStore, (s) => s.currentTool);
  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);

  const handle = (tool) => {
    if (tool.kind === 'undo') return onUndo?.();
    if (tool.kind === 'markup') return onMarkup?.();
    if (tool.kind === 'ruler') return onRuler?.();
    setCurrentTool(tool.kind);
  };

  return (
    <div style={{
      width: 50, background: '#fbfaf7', borderRight: '1px solid #d4d2cb',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '6px 0', gap: 2, fontSize: 15,
    }}>
      {TOOLS.map((t, i) => t.divider ? (
        <div key={`d${i}`} style={{ height: 1, width: 30, background: '#d4d2cb', margin: '4px 0' }} />
      ) : (
        <button key={t.id} title={t.label} onClick={() => handle(t)}
          style={{
            width: 38, height: 38, border: 0, cursor: 'pointer', borderRadius: 5,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: currentTool === t.kind ? '#2a6fb5' : 'transparent',
            color: currentTool === t.kind ? '#fff' : '#3b3b3b',
            position: 'relative',
          }}>
          {t.icon}
          {t.ai && <span style={{ position: 'absolute', top: 0, right: 1, fontSize: 7, color: '#c97a2c' }}>✨</span>}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 5.2: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 5.3: Commit**

```bash
git add frontend/src/components/workspace/ToolRail.jsx
git commit -m "feat(sprint-3): ToolRail (50px) — visible tool buttons

10 buttons in 4 sections separated by dividers: Selection/Pan/Ruler ·
G1/G5/G4 (✨ AI) · G2/G3 · Undo/Markup. Active tool highlighted with
primary blue background. Reads viewerStore.currentTool; clicking
buttons sets it. Keyboard shortcuts unchanged (Sprint 2)."
```

---

## Task 6: `<PageNavigator>` + TakeoffCanvas page navigation

**Files:**
- Create: `frontend/src/components/canvas/PageNavigator.jsx`
- Modify: `frontend/src/components/canvas/TakeoffCanvas.jsx`

- [ ] **Step 6.1: Implement PageNavigator**

```jsx
// frontend/src/components/canvas/PageNavigator.jsx
/**
 * Sprint 3: page picker dropdown.
 *
 * Renders a list of pages with text label (page-type if available,
 * else "Puslapis N"). Click → setCurrentPage. Closes on outside click
 * or selection.
 *
 * Spec §5.4 (page nav) + §9 open question (thumbnails defer to Sprint 4).
 */
import { useEffect, useRef } from 'react';

export function PageNavigator({ pages, currentPage, onSelect, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [onClose]);

  return (
    <div ref={ref} style={{
      position: 'absolute', top: 48, left: 'calc(50% - 200px)',
      width: 400, maxHeight: 480, overflow: 'auto',
      background: '#fff', border: '1px solid #d4d2cb', borderRadius: 8,
      boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: 8, zIndex: 50,
    }}>
      {pages.map((p, i) => (
        <button key={i} onClick={() => { onSelect(i); onClose?.(); }} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          width: '100%', padding: '8px 12px', borderRadius: 5,
          background: i === currentPage ? '#fdf6e7' : 'transparent',
          border: 0, cursor: 'pointer', textAlign: 'left', fontSize: 12,
        }}>
          <span style={{ fontWeight: i === currentPage ? 600 : 400 }}>
            Puslapis {i + 1}
          </span>
          <span style={{ opacity: 0.6, fontSize: 11 }}>{p.title || p.kind || '—'}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 6.2: Modify TakeoffCanvas to read `currentPage` from viewerStore**

Read `frontend/src/components/canvas/TakeoffCanvas.jsx`. Find the line near top of component:

```jsx
export function TakeoffCanvas({ pdfDoc, pageIdx = 0, renderOverlay }) {
```

Change to:

```jsx
export function TakeoffCanvas({ pdfDoc, renderOverlay }) {
  const pageIdx = useStore(viewerStore, (s) => s.currentPage);
```

Add the `useStore`/`viewerStore` imports at top of file if not already imported.

- [ ] **Step 6.3: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 6.4: Commit**

```bash
git add frontend/src/components/canvas/PageNavigator.jsx frontend/src/components/canvas/TakeoffCanvas.jsx
git commit -m "feat(sprint-3): PageNavigator dropdown + TakeoffCanvas reads currentPage

PageNavigator renders text-label list; clicking a page calls onSelect(idx).
Thumbnails defer to Sprint 4 per spec §9 open questions.
TakeoffCanvas no longer hardcodes pageIdx={0}; instead reads
viewerStore.currentPage. InteriorProjectV2 wires the page nav callbacks
in Task 17."
```

---

## Task 7: TakeoffCanvas — scale badge + grid background

**Files:**
- Modify: `frontend/src/components/canvas/TakeoffCanvas.jsx`

- [ ] **Step 7.1: Add background grid + scale badge**

In `frontend/src/components/canvas/TakeoffCanvas.jsx`, find the outer container `<div>` returned by the component. Update its `style` to include a background-image:

```jsx
const containerStyle = {
  overflow: 'hidden', width: '100%', height: '100%', position: 'relative',
  cursor: dragRef.current.active ? 'grabbing' : 'grab',
  touchAction: 'none',
  background: '#f6f5f2',
  backgroundImage: 'linear-gradient(rgba(42,111,181,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(42,111,181,0.025) 1px, transparent 1px)',
  backgroundSize: '24px 24px',
};

return (
  <div ref={containerRef} {...handlers} style={containerStyle}>
    <canvas ref={canvasRef} style={transformStyle} />
    {renderOverlay?.({...})}
    <ScaleBadge />
  </div>
);
```

Add a small `ScaleBadge` component at the bottom of the file:

```jsx
function ScaleBadge() {
  // Reads scale from a separate scaleStore (Task 3)
  return (
    <div style={{
      position: 'absolute', bottom: 14, left: 14,
      background: '#fff', border: '1px solid #d4d2cb',
      padding: '5px 10px', borderRadius: 14, fontSize: 11,
      color: '#171717', fontWeight: 500,
      display: 'flex', alignItems: 'center', gap: 6,
      boxShadow: '0 1px 3px rgba(0,0,0,0.08)', zIndex: 4,
    }}>
      Mastelis 1:50 🔒
    </div>
  );
}
```

NOTE: ScaleBadge currently shows hardcoded `1:50 🔒`. Wiring to `scaleStore` happens in InteriorProjectV2 mount (Task 17) where the project's actual scale is loaded. For Sprint 3 chrome we ship the visual; clicking the badge to edit ratio is Sprint 4.

- [ ] **Step 7.2: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 7.3: Commit**

```bash
git add frontend/src/components/canvas/TakeoffCanvas.jsx
git commit -m "feat(sprint-3): canvas blueprint grid background + scale badge

Subtle 24px gridlines (rgba(42,111,181,0.025)) on canvas container —
Kreo pattern. ScaleBadge bottom-left bg #fff with 1:50 🔒 placeholder
text. Wiring to actual scaleStore happens in InteriorProjectV2 mount
(Task 17); clicking badge to edit ratio is Sprint 4."
```

---

## Task 8: AnnotationLayer — `highlightedRoomId` + verification target glow

**Files:**
- Modify: `frontend/src/components/canvas/AnnotationLayer.jsx`

- [ ] **Step 8.1: Add highlightedRoomId + verification glow**

In `frontend/src/components/canvas/AnnotationLayer.jsx`, modify the component signature:

```jsx
export function AnnotationLayer({
  width, height, canvasWidth, canvasHeight,
  committedPolygons = [],
  committedPoints = [],
  preview = null,
  onShapeClick,
}) {
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);
  const hoveredRoomId = useStore(viewerStore, (s) => s.hoveredRoomId);
  const wizardOpen = useStore(viewerStore, (s) => s.wizardOpen);
  const wizardItemPolygon = useStore(viewerStore, (s) => s.wizardItemPolygon);
  const transform = { scale, translate, canvasWidth, canvasHeight };
```

Modify the committed-layer block to thicken stroke on hovered polygon:

```jsx
      <Layer listening={false}>
        {committedPolygons
          .filter((p) => !selection || selection.id !== p.id)
          .map((poly) => {
            const isHovered = hoveredRoomId === poly.id;
            return (
              <Line
                key={poly.id}
                points={pdfPctPolyToCanvasPxPoly(poly.points, transform).flat()}
                closed
                stroke={poly.color || '#3b82f6'}
                strokeWidth={isHovered ? 2.5 : 1.5}
                fill={poly.color || '#3b82f6'}
                opacity={(poly.fillAlpha ?? 0.18) * (isHovered ? 1.4 : 1)}
                shadowColor={isHovered ? (poly.color || '#3b82f6') : undefined}
                shadowBlur={isHovered ? 8 : 0}
              />
            );
          })}
        {committedPoints.map((pt) => {
          const [px, py] = pdfPctPolyToCanvasPxPoly([pt.xy], transform)[0];
          return (
            <Circle key={pt.id} x={px} y={py} radius={4}
                    fill={pt.color || '#22c55e'} stroke="#0e1216" strokeWidth={1} />
          );
        })}
      </Layer>
```

Append a fourth layer at the end (before `</Stage>`) for verification glow:

```jsx
      {wizardOpen && wizardItemPolygon && (
        <Layer listening={false}>
          <Line
            points={pdfPctPolyToCanvasPxPoly(wizardItemPolygon, transform).flat()}
            closed
            stroke="#c97a2c"
            strokeWidth={3}
            fill="#c97a2c"
            opacity={0.18}
            shadowColor="#c97a2c"
            shadowBlur={24}
            shadowOpacity={0.55}
          />
        </Layer>
      )}
```

- [ ] **Step 8.2: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 8.3: Commit**

```bash
git add frontend/src/components/canvas/AnnotationLayer.jsx
git commit -m "feat(sprint-3): AnnotationLayer hover highlight + wizard glow

Hovered polygon (viewerStore.hoveredRoomId) gets thicker stroke + fill
brighten + soft shadow glow. Wizard's wizardItemPolygon renders as
a fourth layer (amber stroke + glow) when wizardOpen — drives the
auto-zoom focal point during verification."
```

---

## Task 9: `<RightPanel>` tabbed container

**Files:**
- Create: `frontend/src/components/workspace/RightPanel.jsx`

- [ ] **Step 9.1: Implement**

```jsx
// frontend/src/components/workspace/RightPanel.jsx
/**
 * Sprint 3: tabbed right panel (320px wide).
 *
 * Three tabs: ✨ AI · 📋 Kiekiai (default active) · 📊 Suvestinė.
 * Switches via internal useState. Renders provided children based on
 * active tab.
 *
 * Spec §5.6 RightPanel tabs.
 */
import { useState } from 'react';

const TABS = [
  { id: 'ai',         label: '✨ AI',        icon: '✨' },
  { id: 'kiekiai',    label: '📋 Kiekiai',   icon: '📋' },
  { id: 'suvestine',  label: '📊 Suvestinė', icon: '📊' },
];

export function RightPanel({
  activeTab: controlledActive,
  onTabChange,
  badges = {}, // {ai: 2, kiekiai: 47, suvestine: undefined}
  ai,          // <AiPanel /> JSX
  kiekiai,     // <QuantitiesPanel /> JSX
  suvestine,   // <SuvestinePanel /> JSX
}) {
  const [internalActive, setInternalActive] = useState('kiekiai');
  const active = controlledActive ?? internalActive;
  const setActive = (t) => {
    if (controlledActive == null) setInternalActive(t);
    onTabChange?.(t);
  };

  return (
    <aside style={{
      width: 320, background: '#fbfaf7',
      borderLeft: '1px solid #d4d2cb',
      display: 'flex', flexDirection: 'column',
      fontSize: 12, color: '#171717', height: '100%',
    }}>
      <div style={{ display: 'flex', borderBottom: '1px solid #d4d2cb', background: '#f0eeea' }}>
        {TABS.map((t) => {
          const isActive = active === t.id;
          const badge = badges[t.id];
          return (
            <button key={t.id} onClick={() => setActive(t.id)} style={{
              flex: 1, background: isActive ? '#fbfaf7' : 'transparent',
              border: 0, borderBottom: isActive ? '2px solid #2a6fb5' : '2px solid transparent',
              padding: '10px 0', cursor: 'pointer',
              color: isActive ? '#171717' : '#6b6863',
              fontWeight: isActive ? 600 : 500, fontSize: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              {t.label}
              {badge != null && <span style={{
                background: t.id === 'ai' && badge > 0 ? '#fdf6e7' : '#e8e5df',
                color: t.id === 'ai' && badge > 0 ? '#9a5d20' : '#6b6863',
                fontSize: 9, padding: '1px 5px', borderRadius: 6,
              }}>{badge}</span>}
            </button>
          );
        })}
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {active === 'ai' && ai}
        {active === 'kiekiai' && kiekiai}
        {active === 'suvestine' && suvestine}
      </div>
    </aside>
  );
}
```

- [ ] **Step 9.2: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 9.3: Commit**

```bash
git add frontend/src/components/workspace/RightPanel.jsx
git commit -m "feat(sprint-3): RightPanel tabbed container (320px)

3 tabs: AI / Kiekiai / Suvestinė. Default active = Kiekiai.
Supports controlled/uncontrolled modes via activeTab prop.
Badge counts surfaced from props. Tabs use primary-blue underline
when active."
```

---

## Task 10: `<QuantitiesPanel>` (replaces MiniKZPanel)

**Files:**
- Create: `frontend/src/components/panels/QuantitiesPanel.jsx`

- [ ] **Step 10.1: Implement**

```jsx
// frontend/src/components/panels/QuantitiesPanel.jsx
/**
 * Sprint 3: Kiekiai tab content. Replaces MiniKZPanel.
 *
 * - Filter pills (Visos / 🔴 N / 🟡 N / 🔒 N)
 * - Search filter
 * - Category-grouped tree (skyrius header + rows)
 * - Each row: aprasymas | kiekis vnt | confidence dot
 * - Click row → setSelection (drives G2/G3 target)
 * - Hover row → setHoveredRoomId (bidirectional highlight)
 * - Click kiekis text → G7 inline edit
 * - Footer: Σ neto + Eksportuoti
 *
 * Spec §5.6 Kiekiai tab.
 */
import { useState, useMemo, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { overrideQuantity } from '../../lib/gestureApi';
import { abortRegistry } from '../../lib/abortRegistry';

const FILTERS = [
  { id: 'all',  label: 'Visos',  match: () => true,                 active: { bg: '#2a6fb5', fg: '#fff' } },
  { id: 'low',  label: '🔴 N',  match: (p) => p.confidence === 'low' && !p.override_locked },
  { id: 'med',  label: '🟡 N',  match: (p) => p.confidence === 'med' && !p.override_locked },
  { id: 'lock', label: '🔒 N',  match: (p) => p.override_locked },
];

export function QuantitiesPanel({
  rooms = [], pozicijos = [], currentAssumptions = {},
  onRecomputed, onGestureEvent,
}) {
  const setSelection = useStore(viewerStore, (s) => s.setSelection);
  const setHoveredRoomId = useStore(viewerStore, (s) => s.setHoveredRoomId);
  const selection = useStore(viewerStore, (s) => s.selection);

  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');

  const counts = useMemo(() => ({
    all:  pozicijos.length,
    low:  pozicijos.filter(p => p.confidence === 'low' && !p.override_locked).length,
    med:  pozicijos.filter(p => p.confidence === 'med' && !p.override_locked).length,
    lock: pozicijos.filter(p => p.override_locked).length,
  }), [pozicijos]);

  const filtered = useMemo(() => {
    const f = FILTERS.find(x => x.id === filter);
    const q = search.trim().toLowerCase();
    return pozicijos.filter(p => f.match(p) && (!q || (p.aprasymas || '').toLowerCase().includes(q)));
  }, [pozicijos, filter, search]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const p of filtered) {
      const k = p.skyrius_label || p.skyrius || 'Kita';
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(p);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const totalNet = useMemo(() =>
    filtered.reduce((s, p) => s + (Number(p.kiekis_x_kaina) || 0), 0),
  [filtered]);

  const startEdit = useCallback((poz) => {
    setEditingId(poz.id);
    setEditValue(String(poz.kiekis ?? ''));
  }, []);

  const commitEdit = useCallback(async (poz) => {
    setEditingId(null);
    const parsed = Number.parseFloat(editValue);
    if (!Number.isFinite(parsed) || parsed === poz.kiekis) return;
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g7');
      const result = await overrideQuantity({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: poz.id, newValue: parsed, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({ type: 'G7', target: { kind: 'pozicija', id: poz.id }, outcome: 'success', duration_ms: Date.now() - startedAt });
    } catch (err) {
      if (err.name === 'AbortError') return;
      onGestureEvent?.({ type: 'G7', target: { kind: 'pozicija', id: poz.id }, outcome: 'error', duration_ms: Date.now() - startedAt });
      alert(err.envelope?.user_message || `Klaida: ${err.message}`);
    }
  }, [editValue, rooms, pozicijos, currentAssumptions, onRecomputed, onGestureEvent]);

  const confDot = (poz) => {
    if (poz.override_locked) return '#6f5fa3';
    const map = { high: '#2f7d5b', med: '#c97a2c', low: '#a7493f' };
    return map[poz.confidence] || '#94a3b8';
  };

  const rowBg = (poz) => {
    if (poz.confidence === 'med') return '#fdf6e7';
    if (poz.confidence === 'low') return '#fcecea';
    return 'transparent';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Filter pills */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #d4d2cb', display: 'flex', gap: 5, flexWrap: 'wrap', background: '#fbfaf7' }}>
        {FILTERS.map(f => {
          const isActive = filter === f.id;
          const count = counts[f.id];
          return (
            <button key={f.id} onClick={() => setFilter(f.id)} style={{
              background: isActive ? '#2a6fb5' : '#fff',
              color: isActive ? '#fff' : '#3b3b3b',
              border: `1px solid ${isActive ? '#2a6fb5' : '#d4d2cb'}`,
              padding: '3px 9px', borderRadius: 12, fontSize: 10, fontWeight: 500, cursor: 'pointer',
            }}>{f.label.replace('N', count)}</button>
          );
        })}
      </div>
      {/* Search */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #d4d2cb', background: '#fbfaf7' }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filtruoti pozicijas…"
          style={{ width: '100%', padding: '5px 8px', border: '1px solid #d4d2cb', borderRadius: 5, fontSize: 11, background: '#fff', boxSizing: 'border-box' }}
        />
      </div>
      {/* Tree */}
      <div style={{ flex: 1, overflow: 'auto', background: '#fff' }}>
        {grouped.map(([skyrius, items]) => (
          <div key={skyrius}>
            <div style={{ padding: '8px 12px', background: '#f6f5f2', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid #ebe8e3' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, background: '#2a6fb5', borderRadius: '50%' }} />
              <span style={{ fontWeight: 600, flex: 1 }}>{skyrius}</span>
              <span style={{ background: '#e8e5df', color: '#6b6863', fontSize: 9, padding: '1px 6px', borderRadius: 8 }}>{items.length}</span>
            </div>
            {items.map(poz => {
              const isSelected = selection?.kind === 'pozicija' && selection.id === poz.id;
              return (
                <div
                  key={poz.id}
                  onClick={() => setSelection({ kind: 'pozicija', id: poz.id, room_id: poz.room_id })}
                  onMouseEnter={() => poz.room_id && setHoveredRoomId(poz.room_id)}
                  onMouseLeave={() => setHoveredRoomId(null)}
                  style={{
                    padding: '7px 12px 7px 30px', borderBottom: '1px solid #ebe8e3',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(42,111,181,0.08)' : rowBg(poz),
                    borderLeft: isSelected ? '3px solid #2a6fb5' : '3px solid transparent',
                  }}
                >
                  <span style={{ flex: 1, color: isSelected ? '#171717' : '#3b3b3b', fontWeight: isSelected ? 500 : 400 }}>
                    {poz.aprasymas || poz.pavadinimas || '—'}
                  </span>
                  {editingId === poz.id ? (
                    <input
                      autoFocus type="number" value={editValue}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={() => commitEdit(poz)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitEdit(poz);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      style={{ width: 70, marginRight: 8, padding: '2px 4px', border: '1px solid #2a6fb5', borderRadius: 3, fontSize: 11, background: '#fff' }}
                    />
                  ) : (
                    <span
                      onClick={(e) => { e.stopPropagation(); startEdit(poz); }}
                      style={{ marginRight: 8, fontVariantNumeric: 'tabular-nums', color: poz.override_locked ? '#6f5fa3' : '#3b3b3b' }}
                    >
                      {poz.kiekis} {poz.vnt}
                      {poz.override_locked && ' 🔒'}
                    </span>
                  )}
                  <span title={`confidence: ${poz.confidence || '—'}`} style={{ width: 7, height: 7, background: confDot(poz), borderRadius: '50%' }} />
                </div>
              );
            })}
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
            {pozicijos.length === 0 ? 'Nėra pozicijų. Paleisk Sąmatų AI viršuje.' : 'Nėra atitinkančių filtrui.'}
          </div>
        )}
      </div>
      {/* Footer */}
      <div style={{ borderTop: '1px solid #d4d2cb', background: '#fbfaf7', padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 10, opacity: 0.6 }}>Σ neto</div>
          <div style={{ fontSize: 14, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{totalNet.toFixed(2)} €</div>
        </div>
        <button style={{
          background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
          padding: '6px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>Eksportuoti</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 10.2: Smoke build**

`cd frontend && npx vite build 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 10.3: Commit**

```bash
git add frontend/src/components/panels/QuantitiesPanel.jsx
git commit -m "feat(sprint-3): QuantitiesPanel — full KŽ tree with bidirectional highlight

Replaces MiniKZPanel. Filter pills (Visos / 🔴 / 🟡 / 🔒) drive
visible rows; search input filters by description. Hover row →
setHoveredRoomId (drives polygon glow on canvas). Click row →
setSelection (G2/G3 target). Click kiekis → G7 inline edit. Footer
shows Σ neto. Confidence dot uses --conf-* tokens."
```

---

## Task 11: `<AiPanel>` — Run + history

**Files:**
- Create: `frontend/src/components/panels/AiPanel.jsx`

- [ ] **Step 11.1: Implement**

```jsx
// frontend/src/components/panels/AiPanel.jsx
/**
 * Sprint 3: AI tab content.
 *
 * - "Run Sąmatų AI" button (calls existing /extract-interior)
 * - Recent runs list (timestamps, page count, ✓/✗ status)
 * - Click history item → loads that run back into Kiekiai (Sprint 4)
 *
 * For Sprint 3 we just render the Run button + an empty-state list.
 * History persistence is Sprint 4.
 *
 * Spec §5.6 AI tab.
 */
export function AiPanel({ onRunAi, isRunning = false, recentRuns = [] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 16, background: '#fbfaf7', borderBottom: '1px solid #d4d2cb' }}>
        <button onClick={onRunAi} disabled={isRunning} style={{
          width: '100%', background: isRunning ? '#94a3b8' : '#2a6fb5',
          border: '1px solid #2a6fb5', color: '#fff',
          padding: '10px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
          cursor: isRunning ? 'wait' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          {isRunning ? '⏳ AI dirba…' : '✨ Paleisti Sąmatų AI'}
        </button>
        <p style={{ marginTop: 10, fontSize: 11, color: '#6b6863', lineHeight: 1.5 }}>
          AI peržvelgs visus puslapius ir užpildys KŽ pozicijas. Esamos
          🔒 užfiksuotos pozicijos liks nepakitę.
        </p>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 12, background: '#fff' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#6b6863', marginBottom: 8 }}>
          Paskutiniai paleidimai
        </div>
        {recentRuns.length === 0 ? (
          <div style={{ padding: '20px 0', textAlign: 'center', color: '#94a3b8', fontSize: 11 }}>
            Dar nebuvo AI paleidimų.
          </div>
        ) : recentRuns.map((run, i) => (
          <div key={i} style={{
            padding: '8px 10px', marginBottom: 4, background: '#f6f5f2', borderRadius: 5,
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 11,
          }}>
            <span>{run.success ? '✓' : '✗'}</span>
            <div style={{ flex: 1 }}>
              <div>{new Date(run.timestamp).toLocaleString('lt-LT')}</div>
              <div style={{ fontSize: 10, opacity: 0.6 }}>
                {run.page_count} psl. · {run.model || 'opus-4-7'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 11.2: Smoke build + Commit**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```
```bash
git add frontend/src/components/panels/AiPanel.jsx
git commit -m "feat(sprint-3): AiPanel — Run button + recent-runs list

Prominent Run Sąmatų AI button calls onRunAi prop. Disabled while
running. Below: empty-state for recent runs (history persistence is
Sprint 4 work). Lithuanian help text under button explains 🔒
preservation behavior."
```

---

## Task 12: `<SuvestinePanel>` — totals card + breakdown

**Files:**
- Create: `frontend/src/components/panels/SuvestinePanel.jsx`

- [ ] **Step 12.1: Implement**

```jsx
// frontend/src/components/panels/SuvestinePanel.jsx
/**
 * Sprint 3: Suvestinė tab.
 *
 * Σ totals card (medžiagos, DU, mechanizmai, pridėtinės, pelnas, PVM)
 * + per-category horizontal bars showing relative share.
 *
 * Spec §5.6 Suvestinė tab.
 */
export function SuvestinePanel({ rooms = [], pozicijos = [] }) {
  // Compute breakdown by skyrius
  const byCategory = new Map();
  let total = 0;
  for (const p of pozicijos) {
    const k = p.skyrius_label || p.skyrius || 'Kita';
    const v = Number(p.kiekis_x_kaina) || 0;
    byCategory.set(k, (byCategory.get(k) || 0) + v);
    total += v;
  }
  const sorted = Array.from(byCategory.entries()).sort((a, b) => b[1] - a[1]);
  const pvm = total * 0.21;
  const grand = total + pvm;

  const fmt = (n) => n.toFixed(2).replace('.', ',') + ' €';

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 16, background: '#fff', fontSize: 12 }}>
      <div style={{
        background: '#fbfaf7', border: '1px solid #d4d2cb', borderRadius: 8,
        padding: 14, marginBottom: 16,
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#6b6863' }}>
          Suvestinė
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
          {fmt(grand)}
        </div>
        <div style={{ fontSize: 11, color: '#6b6863', marginTop: 6 }}>
          Σ neto: <strong>{fmt(total)}</strong> &nbsp;·&nbsp; PVM 21%: {fmt(pvm)}
        </div>
      </div>

      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#6b6863', marginBottom: 8 }}>
        Pagal skyrius
      </div>
      {sorted.map(([cat, value]) => {
        const pct = total > 0 ? (value / total) * 100 : 0;
        return (
          <div key={cat} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span>{cat}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums', color: '#3b3b3b' }}>{fmt(value)}</span>
            </div>
            <div style={{ height: 6, background: '#f0eeea', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: '#2a6fb5' }} />
            </div>
          </div>
        );
      })}
      {sorted.length === 0 && (
        <div style={{ padding: '20px 0', textAlign: 'center', color: '#94a3b8' }}>
          Nėra duomenų.
        </div>
      )}

      <div style={{ marginTop: 24, display: 'flex', gap: 8 }}>
        <button style={{
          flex: 1, background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
          padding: '8px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>Eksportuoti Excel</button>
        <button style={{
          flex: 1, background: '#fff', border: '1px solid #d4d2cb', color: '#3b3b3b',
          padding: '8px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>PDF</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 12.2: Smoke build + Commit**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```
```bash
git add frontend/src/components/panels/SuvestinePanel.jsx
git commit -m "feat(sprint-3): SuvestinePanel — totals + per-category bars

Σ neto + 21% PVM = grand total card on top. Below: horizontal bars
per skyrius (relative share of total) — pure CSS, no chart library.
Excel + PDF export buttons (wiring is existing /export endpoints,
Sprint 4 if needed)."
```

---

## Task 13: `<VerificationWizard>` skeleton + progress + question

**Files:**
- Create: `frontend/src/components/wizard/VerificationWizard.jsx`

- [ ] **Step 13.1: Implement skeleton**

```jsx
// frontend/src/components/wizard/VerificationWizard.jsx
/**
 * Sprint 3: opt-in verification wizard.
 *
 * Bottom panel ~140px. Reads viewerStore.verificationQueue + verificationIndex
 * + wizardOpen. When wizardOpen===true, this component renders; the parent
 * page dims the rest of the UI to opacity 0.45.
 *
 * Three actions per step:
 *   - Taip ✓ (primary blue)         → confirm, advance. Shift+Taip = lock 🔒
 *   - Pataisyti (cream amber)       → trigger contextual gesture by dispute_type
 *   - Praleisti → (subtle text link) → mark skipped, advance
 *
 * Completion state shows "Visi N patikrinti! Σ ..." + Eksportuoti.
 *
 * Spec §5.3 + §4.5 wizard flow.
 */
import { useEffect, useState, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { isQueueComplete } from '../../lib/verificationQueue';
import { overrideQuantity } from '../../lib/gestureApi';
import { abortRegistry } from '../../lib/abortRegistry';
import { InlineEditor } from './InlineEditor';

export function VerificationWizard({
  rooms = [], pozicijos = [], currentAssumptions = {},
  onRecomputed, onGestureEvent,
}) {
  const wizardOpen = useStore(viewerStore, (s) => s.wizardOpen);
  const setWizardOpen = useStore(viewerStore, (s) => s.setWizardOpen);
  const setWizardItemPolygon = useStore(viewerStore, (s) => s.setWizardItemPolygon);
  const setLockOnConfirm = useStore(viewerStore, (s) => s.setLockOnConfirm);
  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);
  const queue = useStore(viewerStore, (s) => s.verificationQueue);
  const index = useStore(viewerStore, (s) => s.verificationIndex);
  const advance = useStore(viewerStore, (s) => s.advanceVerification);

  const [showInlineEditor, setShowInlineEditor] = useState(false);

  const item = queue[index];

  // Drive auto-zoom: whenever active item changes, set wizardItemPolygon
  useEffect(() => {
    if (wizardOpen && item?.polygon) {
      setWizardItemPolygon(item.polygon);
    } else {
      setWizardItemPolygon(null);
    }
  }, [wizardOpen, item, setWizardItemPolygon]);

  // Esc closes wizard
  useEffect(() => {
    if (!wizardOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (showInlineEditor) {
          setShowInlineEditor(false);
        } else {
          setWizardOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [wizardOpen, showInlineEditor, setWizardOpen]);

  const handleYes = useCallback(async (e) => {
    if (!item) return;
    const lock = e?.shiftKey === true;
    setLockOnConfirm(lock);
    onGestureEvent?.({
      type: lock ? 'verify_yes_lock' : 'verify_yes',
      target: { kind: 'pozicija', id: item.id },
      outcome: 'success', duration_ms: 0,
    });
    if (lock) {
      // Apply lock via override-with-same-value
      const startedAt = Date.now();
      try {
        const signal = abortRegistry.takeSignal('verify_lock');
        const result = await overrideQuantity({
          rooms, pozicijos, currentAssumptions,
          targetPozicijaId: item.id, newValue: item.kiekis, signal,
        });
        onRecomputed?.(result);
      } catch (err) {
        if (err.name !== 'AbortError') console.error('[verify lock] failed:', err);
      }
    }
    advance();
  }, [item, setLockOnConfirm, onGestureEvent, advance, rooms, pozicijos, currentAssumptions, onRecomputed]);

  const handleFix = useCallback(() => {
    if (!item) return;
    if (item.dispute_type === 'number') {
      setShowInlineEditor(true);
    } else if (item.dispute_type === 'count') {
      setCurrentTool('g2');
      onGestureEvent?.({ type: 'verify_fix', target: { kind: 'pozicija', id: item.id }, outcome: 'success', duration_ms: 0 });
    } else {
      setCurrentTool('g1');
      onGestureEvent?.({ type: 'verify_fix', target: { kind: 'pozicija', id: item.id }, outcome: 'success', duration_ms: 0 });
    }
  }, [item, setCurrentTool, onGestureEvent]);

  const handleSkip = useCallback(() => {
    if (!item) return;
    onGestureEvent?.({
      type: 'verify_skip',
      target: { kind: 'pozicija', id: item.id },
      outcome: 'success', duration_ms: 0,
    });
    advance();
  }, [item, onGestureEvent, advance]);

  const handleClose = useCallback(() => {
    setWizardOpen(false);
    setWizardItemPolygon(null);
  }, [setWizardOpen, setWizardItemPolygon]);

  const handleInlineCommit = useCallback(async (newValue) => {
    if (!item) return;
    setShowInlineEditor(false);
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g7');
      const result = await overrideQuantity({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: item.id, newValue, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({ type: 'verify_fix_commit', target: { kind: 'pozicija', id: item.id }, outcome: 'success', duration_ms: Date.now() - startedAt });
      advance();
    } catch (err) {
      if (err.name !== 'AbortError') {
        onGestureEvent?.({ type: 'verify_fix_commit', target: { kind: 'pozicija', id: item.id }, outcome: 'error', duration_ms: Date.now() - startedAt });
        alert(err.envelope?.user_message || `Klaida: ${err.message}`);
      }
    }
  }, [item, rooms, pozicijos, currentAssumptions, onRecomputed, onGestureEvent, advance]);

  if (!wizardOpen) return null;

  // Completion state
  if (isQueueComplete(index, queue.length)) {
    return (
      <div style={wizardPanelStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#2f7d5b' }}>
              ✓ Visi {queue.length} patikrinti
            </div>
            <div style={{ fontSize: 12, color: '#6b6863', marginTop: 4 }}>
              Suvestinė pasiekiama dešinės panelės skirtuke „Suvestinė".
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleClose} style={primaryBtn}>Eksportuoti KŽ</button>
            <button onClick={handleClose} style={ghostBtn}>Grįžti</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={wizardPanelStyle}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 18, position: 'relative' }}>
        {/* Progress */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 60 }}>
          <div style={{ fontSize: 11, color: '#6b6863', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
            {index + 1} / {queue.length}
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
            {queue.map((_, i) => (
              <span key={i} style={{
                width: 16, height: 4, borderRadius: 2,
                background: i < index ? '#2f7d5b' : i === index ? '#c97a2c' : '#e8e5df',
              }} />
            ))}
          </div>
        </div>
        <div style={{ height: 50, width: 1, background: '#e8e5df' }} />

        {/* Question or InlineEditor */}
        {showInlineEditor && item ? (
          <InlineEditor
            poz={item}
            onCommit={handleInlineCommit}
            onCancel={() => setShowInlineEditor(false)}
          />
        ) : item && (
          <>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: '#9a5d20', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ display: 'inline-block', width: 6, height: 6, background: item.confidence === 'low' ? '#a7493f' : '#c97a2c', borderRadius: '50%' }} />
                Reikia patikrinti · {item.label.split('·')[0]?.trim() || 'Pozicija'}
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4, color: '#171717' }}>
                {item.label.split('·')[1]?.trim() || item.label}: <span style={{ color: '#9a5d20' }}>{item.kiekis} {item.vnt}</span>
              </div>
              {item.saltinis && (
                <div style={{ fontSize: 11, color: '#6b6863', marginTop: 3 }}>
                  Šaltinis: {item.saltinis}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'stretch', minWidth: 200 }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={handleYes} style={primaryBtn} title="Shift+Taip = užfiksuoti 🔒">✓ Taip</button>
                <button onClick={handleFix} style={amberBtn}>Pataisyti</button>
              </div>
              <button onClick={handleSkip} style={skipBtn}>Praleisti →</button>
            </div>
          </>
        )}

        {/* Close button */}
        <button onClick={handleClose} title="Uždaryti (Esc)" style={{
          position: 'absolute', top: -8, right: -8,
          background: 'transparent', border: 0, fontSize: 16, color: '#94a3b8', cursor: 'pointer',
        }}>✕</button>
      </div>
    </div>
  );
}

const wizardPanelStyle = {
  position: 'absolute', bottom: 0, left: 0, right: 0,
  background: '#fff', borderTop: '2px solid #c97a2c',
  padding: '14px 20px', boxShadow: '0 -4px 12px rgba(0,0,0,0.06)',
  zIndex: 20,
};

const primaryBtn = {
  flex: 1, background: '#2a6fb5', border: '1px solid #2a6fb5',
  color: '#fff', padding: '8px 14px', borderRadius: 5,
  fontSize: 12, fontWeight: 600, cursor: 'pointer',
};

const amberBtn = {
  flex: 1, background: '#fff', border: '1px solid #c97a2c',
  color: '#9a5d20', padding: '8px 14px', borderRadius: 5,
  fontSize: 12, fontWeight: 600, cursor: 'pointer',
};

const skipBtn = {
  background: 'transparent', border: 0, color: '#6b6863',
  padding: '4px 8px', borderRadius: 5, fontSize: 11, cursor: 'pointer',
};

const ghostBtn = {
  background: 'transparent', border: '1px solid #d4d2cb',
  color: '#3b3b3b', padding: '8px 14px', borderRadius: 5,
  fontSize: 12, fontWeight: 500, cursor: 'pointer',
};
```

- [ ] **Step 13.2: Smoke build + Commit**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```
```bash
git add frontend/src/components/wizard/VerificationWizard.jsx
git commit -m "feat(sprint-3): VerificationWizard component

Bottom panel ~140px. Renders only when viewerStore.wizardOpen === true.
Progress dots (1/N), question card with skyrius label + kiekis + saltinis,
3 buttons: Taip (primary), Pataisyti (cream amber), Praleisti (subtle).
Shift+Taip locks 🔒 via overrideQuantity with same value.
Pataisyti dispatches by dispute_type:
  - number → InlineEditor in question slot
  - count → setCurrentTool('g2')
  - polygon → setCurrentTool('g1')
Esc closes wizard (or returns from inline editor)."
```

---

## Task 14: `<InlineEditor>` for number disputes

**Files:**
- Create: `frontend/src/components/wizard/InlineEditor.jsx`

- [ ] **Step 14.1: Implement**

```jsx
// frontend/src/components/wizard/InlineEditor.jsx
/**
 * Sprint 3: inline editor used in wizard question slot when fixing a
 * number dispute. Replaces the question card text with [← back] +
 * input + [✓ Įrašyti].
 *
 * Spec §5.3 inline editor.
 */
import { useState, useEffect, useRef } from 'react';

export function InlineEditor({ poz, onCommit, onCancel }) {
  const [value, setValue] = useState(String(poz.kiekis ?? ''));
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const tryCommit = () => {
    const n = Number.parseFloat(value);
    if (!Number.isFinite(n)) return;
    onCommit(n);
  };

  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10 }}>
      <button onClick={onCancel} title="Grįžti (Esc)" style={{
        background: 'transparent', border: '1px solid #d4d2cb',
        color: '#3b3b3b', padding: '6px 10px', borderRadius: 5,
        fontSize: 12, cursor: 'pointer',
      }}>← Grįžti</button>
      <span style={{ fontSize: 13, color: '#3b3b3b' }}>
        {poz.label.split('·')[1]?.trim() || poz.label}:
      </span>
      <input
        ref={inputRef}
        type="number" step="any" value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') tryCommit();
          if (e.key === 'Escape') onCancel();
        }}
        style={{
          width: 120, padding: '6px 10px',
          border: '1px solid #2a6fb5', borderRadius: 5,
          fontSize: 14, fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
        }}
      />
      <span style={{ fontSize: 13, color: '#3b3b3b' }}>{poz.vnt}</span>
      <button onClick={tryCommit} style={{
        background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
        padding: '6px 14px', borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: 'pointer',
      }}>✓ Įrašyti</button>
    </div>
  );
}
```

- [ ] **Step 14.2: Smoke build + Commit**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```
```bash
git add frontend/src/components/wizard/InlineEditor.jsx
git commit -m "feat(sprint-3): InlineEditor — number-dispute fix surface

Replaces wizard question card when user clicks Pataisyti on a number
dispute. Shows [← Grįžti] + label + input + unit + [✓ Įrašyti].
Auto-focus + select-all on mount. Enter commits; Esc cancels."
```

---

## Task 15: Auto-zoom math (verification target focus)

**Files:**
- Modify: `frontend/src/components/wizard/VerificationWizard.jsx`

- [ ] **Step 15.1: Add bbox-to-viewport math**

In `frontend/src/components/wizard/VerificationWizard.jsx`, add a helper:

```javascript
function polygonBoundingBox(poly) {
  if (!poly || poly.length === 0) return null;
  let minX = 1, minY = 1, maxX = 0, maxY = 0;
  for (const [x, y] of poly) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, maxX, maxY };
}

function fitToBox(bbox, viewportW, viewportH, paddingPct = 0.30) {
  // bbox in pdf-pct space; we want to compute scale + translate so the
  // bbox (with padding) fits the viewport center.
  if (!bbox) return null;
  const bboxW = bbox.maxX - bbox.minX;
  const bboxH = bbox.maxY - bbox.minY;
  const padW = bboxW * paddingPct;
  const padH = bboxH * paddingPct;
  // canvas natural size unknown to wizard — use viewport dims directly,
  // assuming canvas displays at scale 1.0 fills viewport
  const targetWPct = bboxW + padW * 2;
  const targetHPct = bboxH + padH * 2;
  const scale = Math.min(
    viewportW / (targetWPct * viewportW),
    viewportH / (targetHPct * viewportH),
  ) || 1;
  const cx = (bbox.minX + bbox.maxX) / 2;
  const cy = (bbox.minY + bbox.maxY) / 2;
  // translate so the centroid lands at viewport center
  const tx = viewportW / 2 - cx * viewportW * scale;
  const ty = viewportH / 2 - cy * viewportH * scale;
  return { scale, translate: { x: tx, y: ty } };
}
```

In the `useEffect` that drives auto-zoom (currently sets `wizardItemPolygon`), extend it to also set `viewerStore.scale + translate`:

```javascript
const setTransform = useStore(viewerStore, (s) => s.setTransform);

useEffect(() => {
  if (wizardOpen && item?.polygon) {
    setWizardItemPolygon(item.polygon);
    const bbox = polygonBoundingBox(item.polygon);
    const fit = fitToBox(bbox, window.innerWidth - 50 - 320, window.innerHeight - 48 - 140);
    if (fit) setTransform(fit);
  } else {
    setWizardItemPolygon(null);
  }
}, [wizardOpen, item, setWizardItemPolygon, setTransform]);
```

NOTE: this is approximate (uses `window.innerWidth/Height` minus chrome, not actual canvas dims); good enough for Sprint 3 — can refine in Sprint 4 with proper canvas-ref measurement.

- [ ] **Step 15.2: Smoke build + Commit**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```
```bash
git add frontend/src/components/wizard/VerificationWizard.jsx
git commit -m "feat(sprint-3): wizard auto-zoom to verification target

polygonBoundingBox computes minX/Y/maxX/Y in pdf-pct space.
fitToBox computes scale + translate so the bbox (+30% padding) lands
centered in the canvas viewport. Driven by item change in the
existing useEffect; uses window dims minus chrome for approximate
fit. Refinement Sprint 4 if needed."
```

---

## Task 16: Mount everything in `<InteriorProjectV2>` + bidirectional highlight wiring

**Files:**
- Modify: `frontend/src/pages/InteriorProjectV2.jsx`
- Delete: `frontend/src/components/panels/MiniKZPanel.jsx`

- [ ] **Step 16.1: Replace InteriorProjectV2 body**

Open `frontend/src/pages/InteriorProjectV2.jsx`. Keep the existing imports + `loadPdf` + `useEffect` for project loading + telemetry session lifecycle. Replace the JSX return with:

```jsx
import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { pdfjs } from 'react-pdf';
import { useStore } from 'zustand';
import { getPdfBlob } from '../lib/pdfStore';
import { getProject } from '../lib/projectStore';
import { TakeoffCanvas } from '../components/canvas/TakeoffCanvas';
import { MemoryWatchdog } from '../components/canvas/MemoryWatchdog';
import { AnnotationLayer } from '../components/canvas/AnnotationLayer';
import { PageNavigator } from '../components/canvas/PageNavigator';
import { TopBar } from '../components/workspace/TopBar';
import { ToolRail } from '../components/workspace/ToolRail';
import { RightPanel } from '../components/workspace/RightPanel';
import { QuantitiesPanel } from '../components/panels/QuantitiesPanel';
import { AiPanel } from '../components/panels/AiPanel';
import { SuvestinePanel } from '../components/panels/SuvestinePanel';
import { VerificationWizard } from '../components/wizard/VerificationWizard';
import { tileCache } from '../lib/tileCache';
import { createSession } from '../lib/telemetry';
import { attachShortcuts } from '../lib/keyboardShortcuts';
import { useG1Handler } from '../components/canvas/gestures/G1VisionFill';
import { useG2Handler } from '../components/canvas/gestures/G2AddCount';
import { useG3Handler } from '../components/canvas/gestures/G3RemoveCount';
import { useG4Handler } from '../components/canvas/gestures/G4ColorSample';
import { useG5Handlers } from '../components/canvas/gestures/G5Lasso';
import { viewerStore } from '../lib/viewerStore';
import { buildQueue } from '../lib/verificationQueue';

pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';

export default function InteriorProjectV2() {
  const { id } = useParams();
  const [pdfDoc, setPdfDoc] = useState(null);
  const [error, setError] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [pozicijos, setPozicijos] = useState([]);
  const [assumptions, setAssumptions] = useState({});
  const [committedPolygons, setCommittedPolygons] = useState([]);
  const [committedPoints, setCommittedPoints] = useState([]);
  const [preview, setPreview] = useState(null);
  const [pagePickerOpen, setPagePickerOpen] = useState(false);
  const [aiRunning, setAiRunning] = useState(false);
  const [skippedSet, setSkippedSet] = useState(new Set());
  const sessionRef = useRef(null);

  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);
  const setCurrentPage = useStore(viewerStore, (s) => s.setCurrentPage);
  const setScale = useStore(viewerStore, (s) => s.setScale);
  const setVerificationQueue = useStore(viewerStore, (s) => s.setVerificationQueue);
  const setWizardOpen = useStore(viewerStore, (s) => s.setWizardOpen);
  const wizardOpen = useStore(viewerStore, (s) => s.wizardOpen);

  const loadPdf = useCallback(async () => {
    try {
      const blob = await getPdfBlob(id);
      if (!blob) { setError('Brėžinys nerastas.'); return; }
      const buf = await blob.arrayBuffer();
      const doc = await pdfjs.getDocument({ data: buf }).promise;
      setPdfDoc(doc);
    } catch (err) { setError(`Nepavyko užkrauti PDF: ${err.message}`); }
  }, [id]);

  useEffect(() => { loadPdf(); }, [loadPdf]);

  useEffect(() => {
    const project = getProject(id);
    if (!project) return;
    if (Array.isArray(project.darbu_sarasas)) {
      setPozicijos(project.darbu_sarasas.map((p, i) => ({
        ...p, id: p.id || (p.eil_nr != null ? `poz-${p.eil_nr}` : `poz-${i}`),
      })));
    }
    const projectRooms = project.raw_calc_data?.patalpos || project.v8_rooms || project.patalpos;
    if (Array.isArray(projectRooms)) {
      setRooms(projectRooms.map((r, i) => ({
        ...r, id: r.id || (r.nr ? `room-${r.nr}` : `room-${i}`),
      })));
    }
    if (project.prielaidos) setAssumptions(project.prielaidos);
  }, [id]);

  useEffect(() => {
    sessionRef.current = createSession({ projectId: id });
    const onUnload = () => sessionRef.current?.finish({ exported: false });
    window.addEventListener('beforeunload', onUnload);
    const detachKb = attachShortcuts({ setCurrentTool });
    return () => {
      window.removeEventListener('beforeunload', onUnload);
      sessionRef.current?.finish({ exported: false });
      detachKb();
    };
  }, [id, setCurrentTool]);

  // Build verification queue from current rooms + pozicijos + skippedSet
  useEffect(() => {
    const queue = buildQueue({ rooms, pozicijos, skipped: skippedSet });
    setVerificationQueue(queue);
  }, [rooms, pozicijos, skippedSet, setVerificationQueue]);

  const recordGesture = useCallback((g) => sessionRef.current?.recordGesture(g), []);

  const onRecomputed = useCallback((result) => {
    if (result.rooms) setRooms(result.rooms);
    if (result.pozicijos) setPozicijos(result.pozicijos);
    if (result.assumptions) setAssumptions(result.assumptions);
  }, []);

  const handleReset = useCallback(() => {
    pdfDoc?.destroy().catch(() => {});
    tileCache.clear();
    setPdfDoc(null);
    loadPdf();
  }, [pdfDoc, loadPdf]);

  const totalPages = pdfDoc?.numPages || 1;
  const currentPage = useStore(viewerStore, (s) => s.currentPage);
  const onPrevPage = useCallback(() => setCurrentPage(Math.max(0, currentPage - 1)), [currentPage, setCurrentPage]);
  const onNextPage = useCallback(() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1)), [currentPage, totalPages, setCurrentPage]);

  const onZoomOut = useCallback(() => setScale(Math.max(0.25, useStore.getState ? viewerStore.getState().scale * 0.9 : 1)), [setScale]);
  const onZoomIn  = useCallback(() => setScale(Math.min(6,    viewerStore.getState().scale * 1.1)), [setScale]);

  const onAiRun = useCallback(async () => {
    setAiRunning(true);
    try {
      const res = await fetch(`/extract-interior?project_id=${encodeURIComponent(id)}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRooms(data.patalpos || data.rooms || rooms);
      setPozicijos(data.darbu_sarasas || pozicijos);
    } catch (err) {
      alert(`AI klaida: ${err.message}`);
    } finally {
      setAiRunning(false);
    }
  }, [id, rooms, pozicijos]);

  const project = getProject(id);
  const pages = useMemo(() => Array.from({ length: totalPages }, (_, i) => ({ title: project?.page_titles?.[i] || `Puslapis ${i + 1}`, kind: project?.page_kinds?.[i] })), [totalPages, project]);

  // Convert rooms[] into committedPolygons format for AnnotationLayer
  useEffect(() => {
    const polys = rooms.filter(r => Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3)
      .map(r => ({ id: r.id, points: r.polygon_pct, color: '#2a6fb5', fillAlpha: 0.10 }));
    setCommittedPolygons(polys);
  }, [rooms]);

  if (error) return <div style={{ padding: 20 }}>{error}</div>;
  if (!pdfDoc) return <div style={{ padding: 20, color: '#6b6863' }}>Kraunamas brėžinys…</div>;

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#f6f5f2' }}>
      <MemoryWatchdog onReset={handleReset} />

      <div style={{ position: 'relative', flexShrink: 0, opacity: wizardOpen ? 0.55 : 1, pointerEvents: wizardOpen ? 'none' : 'auto', transition: 'opacity 200ms ease' }}>
        <TopBar
          projectName={project?.title || 'Projektas'}
          subtitle="Vidaus apdaila"
          pageTitle={pages[currentPage]?.title}
          totalPages={totalPages}
          queueCount={useStore(viewerStore, s => s.verificationQueue.length)}
          onPrevPage={onPrevPage}
          onNextPage={onNextPage}
          onPagePicker={() => setPagePickerOpen(o => !o)}
          onZoomOut={onZoomOut}
          onZoomIn={onZoomIn}
          onSearch={() => alert('Paieška ateina Sprint 4')}
          onWizard={() => { setWizardOpen(true); }}
          onAiRun={onAiRun}
          onMore={() => alert('Meniu ateina Sprint 4')}
        />
        {pagePickerOpen && (
          <PageNavigator pages={pages} currentPage={currentPage}
            onSelect={(i) => setCurrentPage(i)}
            onClose={() => setPagePickerOpen(false)} />
        )}
      </div>

      <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative' }}>
        <div style={{ opacity: wizardOpen ? 0.55 : 1, pointerEvents: wizardOpen ? 'none' : 'auto', transition: 'opacity 200ms ease', display: 'contents' }}>
          <ToolRail onUndo={() => alert('Undo Sprint 4')} onMarkup={() => alert('Markup Sprint 4')} onRuler={() => alert('Liniuotė Sprint 4')} />
        </div>

        <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
          <TakeoffCanvas
            pdfDoc={pdfDoc}
            renderOverlay={({ canvasWidth, canvasHeight, canvasRef, containerRef }) => (
              <GestureSurface
                {...{
                  projectId: id, pageIdx: currentPage,
                  canvasWidth, canvasHeight, canvasRef, containerRef,
                  rooms, pozicijos, currentAssumptions: assumptions,
                  committedPolygons, committedPoints, preview,
                  onPolygonAdded: (poly) => setCommittedPolygons((ps) => [...ps, poly]),
                  onLassoResult: (result) => {
                    const newPoints = (result.symbols || []).map((s, i) => ({
                      id: `g5-${Date.now()}-${i}`, xy: s.xy_pct, color: '#22c55e', kind: s.type,
                    }));
                    setCommittedPoints((ps) => [...ps, ...newPoints]);
                  },
                  onRecomputed,
                  onGestureEvent: recordGesture,
                  onPreviewChange: setPreview,
                }}
              />
            )}
          />
          <VerificationWizard
            rooms={rooms} pozicijos={pozicijos} currentAssumptions={assumptions}
            onRecomputed={onRecomputed} onGestureEvent={recordGesture}
          />
        </div>

        <div style={{ opacity: wizardOpen ? 0.55 : 1, pointerEvents: wizardOpen ? 'none' : 'auto', transition: 'opacity 200ms ease' }}>
          <RightPanel
            badges={{ kiekiai: pozicijos.length }}
            ai={<AiPanel onRunAi={onAiRun} isRunning={aiRunning} recentRuns={[]} />}
            kiekiai={<QuantitiesPanel
              rooms={rooms} pozicijos={pozicijos} currentAssumptions={assumptions}
              onRecomputed={onRecomputed} onGestureEvent={recordGesture} />}
            suvestine={<SuvestinePanel rooms={rooms} pozicijos={pozicijos} />}
          />
        </div>
      </div>
    </div>
  );
}

function GestureSurface(props) {
  const onG1 = useG1Handler(props);
  const onG2 = useG2Handler(props);
  const onG3 = useG3Handler(props);
  const onG4 = useG4Handler(props);
  const g5  = useG5Handlers(props);
  const onClick = (e) => { onG1(e) || onG2(e) || onG3(e) || onG4(e); };
  return (
    <>
      <div onClick={onClick}
           onPointerDown={g5.onPointerDown}
           onPointerMove={g5.onPointerMove}
           onPointerUp={g5.onPointerUp}
           style={{ position: 'absolute', inset: 0, zIndex: 2 }} />
      <div style={{ position: 'absolute', inset: 0, zIndex: 3, pointerEvents: 'none' }}>
        <AnnotationLayer
          width={props.canvasWidth || 1}
          height={props.canvasHeight || 1}
          canvasWidth={props.canvasWidth || 1}
          canvasHeight={props.canvasHeight || 1}
          committedPolygons={props.committedPolygons}
          committedPoints={props.committedPoints}
          preview={props.preview}
        />
      </div>
    </>
  );
}
```

- [ ] **Step 16.2: Delete MiniKZPanel**

```bash
rm frontend/src/components/panels/MiniKZPanel.jsx
```

- [ ] **Step 16.3: Smoke build**

```bash
cd frontend && npx vite build 2>&1 | tail -8
```
Expected: clean (chunk size warnings OK). If there's an unused import warning for MiniKZPanel anywhere, remove the import.

- [ ] **Step 16.4: Frontend tests still pass**

`cd frontend && npm run test:units 2>&1 | tail -5`
Expected: 100/100 (was 82 + 8 viewerStore + 12 verificationQueue + 3 categoryColor + 5 scaleStore = 110; subtract any tests inside MiniKZPanel.test.js if it existed — checking).

NOTE: if MiniKZPanel had a test file, delete it too. Run: `ls frontend/src/components/panels/`. Adjust expected count.

- [ ] **Step 16.5: Commit**

```bash
git add frontend/src/pages/InteriorProjectV2.jsx
git rm frontend/src/components/panels/MiniKZPanel.jsx
git commit -m "feat(sprint-3): mount full chrome — TopBar + ToolRail + RightPanel + Wizard

InteriorProjectV2.jsx body completely rewritten. Composes:
- TopBar (top, dimmed when wizard open)
- ToolRail (left, dimmed when wizard open)
- TakeoffCanvas + GestureSurface + AnnotationLayer (center)
- VerificationWizard (overlay on canvas, shown only when open)
- RightPanel (right, dimmed when wizard open)

State plumbing:
- buildQueue() drives viewerStore.verificationQueue from rooms+pozicijos
- TopBar Patikrinti → setWizardOpen(true)
- AI Run button calls /extract-interior; sets aiRunning state
- Page nav drives viewerStore.currentPage
- Bidirectional highlight: QuantitiesPanel hover → setHoveredRoomId →
  AnnotationLayer thickens polygon stroke + glow

MiniKZPanel.jsx deleted (superseded by QuantitiesPanel)."
```

---

## Task 17: Backend appendix — `verify_pass.py`

**Files:**
- Create: `backend/extractor/verify_pass.py`
- Create: `backend/tests/test_verify_pass.py`

NOTE: this and Tasks 18-19 are Section 6 backend appendix. If chrome budget runs short, defer to Sprint 4 and skip ahead to Task 20.

- [ ] **Step 17.1: Failing test**

```python
# backend/tests/test_verify_pass.py
"""Sprint 3 Section 6: self-verify pass produces advisory corrections."""
from unittest.mock import patch
from extractor.verify_pass import run_verify_pass, VerifyResult


def test_returns_corrections_list():
    fake_response = {
        "corrections": [
            {"pozicija_id": "poz-1", "suggested_value": 18.5,
             "reason": "Vonioje plytelių zona 2.0m × 11.2m perimetras = 22.4 m², ne 23.4",
             "confidence": "high"},
        ],
    }
    with patch("extractor.verify_pass._call_opus", return_value=fake_response):
        result = run_verify_pass(rooms=[], pozicijos=[
            {"id": "poz-1", "kiekis": 23.4, "vnt": "m2", "aprasymas": "Sienų plytelės"},
        ])
    assert isinstance(result, VerifyResult)
    assert len(result.corrections) == 1
    assert result.corrections[0]["pozicija_id"] == "poz-1"
    assert result.corrections[0]["suggested_value"] == 18.5


def test_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "0")
    result = run_verify_pass(rooms=[], pozicijos=[
        {"id": "poz-1", "kiekis": 23.4, "vnt": "m2", "aprasymas": "X"},
    ])
    assert result.corrections == []


def test_handles_anthropic_error_gracefully():
    with patch("extractor.verify_pass._call_opus", side_effect=RuntimeError("anthropic 500")):
        # Should not raise; returns empty corrections
        result = run_verify_pass(rooms=[], pozicijos=[
            {"id": "poz-1", "kiekis": 23.4, "vnt": "m2", "aprasymas": "X"},
        ])
    assert result.corrections == []
    assert "anthropic 500" in (result.error or "")
```

- [ ] **Step 17.2: Run, expect FAIL**

`cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/test_verify_pass.py -v`
Expected: ImportError (module doesn't exist).

- [ ] **Step 17.3: Implement**

```python
# backend/extractor/verify_pass.py
"""Sprint 3 Section 6: self-verify pass.

Calls Opus 4.7 with the Pass-1 result + asks: 'Identify quantities you'd
disagree with and explain why.' Returns advisory `corrections[]` array.

Output is NEVER auto-applied — frontend AI tab surfaces corrections as
suggestions. User can accept/reject manually.

Gated by ENABLE_VERIFY_PASS=1. When off, returns empty corrections so
caller's downstream merge is a no-op.

See spec §4.3 verify_pass.py + parent spec §10 risk register.
"""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from extractor.feature_flags import get_flags

log = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    corrections: list[dict] = field(default_factory=list)
    error: str | None = None


def _call_opus(prompt: str) -> dict:
    """Invoke Anthropic Opus 4.7 with the verify prompt. Returns parsed
    JSON response with `corrections[]` key.

    Stub for Sprint 3 — Sprint 4 wires the actual SDK call. Tests patch
    this function directly. Real call uses the existing `extractor.stream`
    helper or anthropic SDK client.
    """
    raise NotImplementedError("verify_pass real call wires in Sprint 4")


def _build_prompt(rooms: list[dict], pozicijos: list[dict]) -> str:
    summary_lines = []
    for p in pozicijos:
        summary_lines.append(
            f"- {p.get('id')} · {p.get('skyrius_label', p.get('skyrius', '-'))} · "
            f"{p.get('aprasymas', '-')} · {p.get('kiekis')} {p.get('vnt', '-')}"
        )
    rooms_summary = "\n".join(
        f"- {r.get('id')} ({r.get('pavadinimas', '-')}): {r.get('plotas_m2', '-')} m², "
        f"perim {r.get('perimetras_m', '-')} m"
        for r in rooms
    )
    return f"""You are a senior LT construction estimator reviewing AI Pass-1 output.

Rooms:
{rooms_summary}

Quantities (KŽ pozicijos):
{chr(10).join(summary_lines)}

Identify SPECIFIC quantities you would disagree with. For each, provide:
- pozicija_id
- suggested_value (numeric)
- reason (1 sentence in Lithuanian)
- confidence ("high" | "med" | "low")

Return as JSON: {{"corrections": [...]}}. If everything looks reasonable,
return {{"corrections": []}}. Be conservative — only flag genuine errors.
"""


def run_verify_pass(rooms: list[dict], pozicijos: list[dict]) -> VerifyResult:
    """Entry point. Returns VerifyResult with corrections (possibly empty)."""
    if not get_flags()["verify_pass"]:
        return VerifyResult()
    try:
        prompt = _build_prompt(rooms, pozicijos)
        response = _call_opus(prompt)
        return VerifyResult(corrections=response.get("corrections", []))
    except Exception as exc:
        log.exception("verify_pass call failed")
        return VerifyResult(error=str(exc))
```

- [ ] **Step 17.4: Run tests**

`cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/test_verify_pass.py -v`
Expected: 3/3 pass.

- [ ] **Step 17.5: Commit**

```bash
git add backend/extractor/verify_pass.py backend/tests/test_verify_pass.py
git commit -m "feat(sprint-3): verify_pass.py — Opus 4.7 self-verify shim

Pure module (Sprint 3 stub for Opus call; Sprint 4 wires real SDK).
Builds prompt from rooms + pozicijos, calls _call_opus (mocked in
tests), returns VerifyResult with corrections[]. Gated by
ENABLE_VERIFY_PASS=1 — returns empty when off. Errors caught
gracefully (returns empty + error string)."
```

---

## Task 18: Backend appendix — `grid_overlay.py`

**Files:**
- Create: `backend/extractor/grid_overlay.py`
- Create: `backend/tests/test_grid_overlay.py`

- [ ] **Step 18.1: Failing test**

```python
# backend/tests/test_grid_overlay.py
"""Sprint 3 Section 6: grid_overlay stamps faint gridlines on PDF page rasters."""
from PIL import Image
from extractor.grid_overlay import stamp_grid


def test_returns_image_same_size():
    src = Image.new("RGB", (1000, 700), color="white")
    out = stamp_grid(src, scale_ratio=50, dpi=200)
    assert out.size == src.size
    assert out.mode == "RGB"


def test_no_op_when_scale_invalid():
    src = Image.new("RGB", (500, 500), color="white")
    out_zero = stamp_grid(src, scale_ratio=0, dpi=200)
    out_negative = stamp_grid(src, scale_ratio=-50, dpi=200)
    # Returns the source image unchanged
    assert out_zero.tobytes() == src.tobytes()
    assert out_negative.tobytes() == src.tobytes()


def test_stamps_pixels_at_expected_intervals():
    """At scale=50 + dpi=200, 1m on drawing = 1000mm/50 = 20mm on paper
    = 20mm * 200dpi / 25.4mm/inch = ~157.5 px between grid lines."""
    src = Image.new("RGB", (1000, 700), color="white")
    out = stamp_grid(src, scale_ratio=50, dpi=200)
    # Pixel at (~157, 350) should be slightly grey (gridline) vs white at (10, 350)
    px_grid = out.getpixel((157, 350))
    px_blank = out.getpixel((10, 350))
    # Grid lines are faint — value should be < 255 (slightly grey)
    assert px_grid[0] < px_blank[0] or px_grid != (255, 255, 255), \
        f"Expected gridline at ~x=157, got px {px_grid} vs blank {px_blank}"
```

- [ ] **Step 18.2: Run, expect FAIL**

`cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/test_grid_overlay.py -v`
Expected: ImportError.

- [ ] **Step 18.3: Implement**

```python
# backend/extractor/grid_overlay.py
"""Sprint 3 Section 6: grid overlay.

Stamps faint 1m × 1m gridlines onto a PDF page raster. Goal: improves
Vision's ability to visually verify scale and read off-grid dimensions.

Math: for scale 1:N at DPI D, 1m drawing = 1000/N mm paper = (1000/N)*D/25.4 px.

Gated by ENABLE_GRID_OVERLAY=1 (caller checks flag; module is pure).
"""
from PIL import Image, ImageDraw

_MM_PER_INCH = 25.4
_GRID_COLOR = (200, 215, 235)  # faint blue-grey
_GRID_OPACITY = 0.35  # blend amount


def stamp_grid(image: Image.Image, scale_ratio: float, dpi: int) -> Image.Image:
    """Return a NEW image with 1m gridlines stamped onto a copy of the source."""
    if scale_ratio <= 0 or dpi <= 0:
        return image
    px_per_meter = (1000.0 / scale_ratio) * dpi / _MM_PER_INCH
    if px_per_meter < 5:  # too tight to be useful
        return image

    out = image.copy().convert("RGB")
    overlay = Image.new("RGB", out.size, _GRID_COLOR)
    mask = Image.new("L", out.size, 0)
    draw = ImageDraw.Draw(mask)

    w, h = out.size
    # Vertical lines
    x = px_per_meter
    while x < w:
        draw.line([(int(x), 0), (int(x), h)], fill=int(255 * _GRID_OPACITY), width=1)
        x += px_per_meter
    # Horizontal lines
    y = px_per_meter
    while y < h:
        draw.line([(0, int(y)), (w, int(y))], fill=int(255 * _GRID_OPACITY), width=1)
        y += px_per_meter

    return Image.composite(overlay, out, mask)
```

- [ ] **Step 18.4: Tests pass**

`cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/test_grid_overlay.py -v`
Expected: 3/3 pass.

- [ ] **Step 18.5: Commit**

```bash
git add backend/extractor/grid_overlay.py backend/tests/test_grid_overlay.py
git commit -m "feat(sprint-3): grid_overlay.py — 1m gridline stamper

Pure module: takes a PIL Image + scale_ratio + dpi, returns NEW Image
with faint blue-grey 1m × 1m gridlines composited on top. Returns
source unchanged if scale ≤ 0 or grid pitch < 5px (too tight to help).
Caller (vision_call.py) gates by ENABLE_GRID_OVERLAY flag. Sprint 4
wires actual integration into Pass-1 raster pipeline."
```

---

## Task 19: Backend appendix — Vision prompt token cleanup

**Files:**
- Modify: `backend/extractor/prompt.py`

- [ ] **Step 19.1: Identify token-bloat sections**

Run: `cd /Users/ignasgaldikas/samatu-ai/.claude/worktrees/sprint-2-gestures && wc -l backend/extractor/prompt.py`

Then read the file to find sections marked as "model is told to ignore" — typically multi-paragraph formula descriptions that the prompt includes for context but the model never uses. Look for:
- Long sections describing computed-by-Python fields ("dazymo_plotas, kampu, plytelės — Python skaičiuoja")
- Verbose docstring-style text the model just skims
- Repeated explanations across the prompt

- [ ] **Step 19.2: Strip ~2,000 tokens of unused formula text**

Edit `prompt.py` to remove the ignored sections. Be conservative — keep all schema definitions, all room-detection guidance, all eksplikacija parsing rules. Only remove text that explicitly says "ignore" or describes downstream Python work the model never produces.

Specifically target:
- Any block starting with "Computed fields ... are filled later by Python deterministic math layer" with multi-paragraph descriptions of those computed fields
- The TypeScript-style `Room` type comment block IF it duplicates the JSON schema (keep one, drop the other — implementer may choose; conservative is to keep both since Sprint 2 Task 1 found both are load-bearing for Vision schema-coherence)

NOTE: this task is intentionally vague because the right cuts depend on reading the current 2700+ line prompt. The implementer should:
1. Read the prompt file end-to-end first
2. Identify candidate cuts (with rationale per cut)
3. Make the cuts
4. Verify token count drop using `python -c "import tiktoken; enc = tiktoken.encoding_for_model('cl100k_base'); print(len(enc.encode(open('backend/extractor/prompt.py').read())))"` if `tiktoken` is installed, else byte count delta as proxy

If less than 1500 tokens cut, DON'T over-cut; commit what's safe and flag remaining cleanup as Sprint 3 follow-up.

- [ ] **Step 19.3: Run accuracy regression check**

The prompt cleanup must not affect output. Verify by running existing extractor tests:
`cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/test_extractor_unit.py tests/test_wall_adjacency.py tests/test_wall_adjacency_pipeline.py -v`
Expected: all green (these tests don't depend on prompt text content).

For real accuracy validation, parent spec §8 requires A/B test on 3 PDFs — that's Sprint 4 work. Document in commit message that bench validation pending.

- [ ] **Step 19.4: Commit**

```bash
git add backend/extractor/prompt.py
git commit -m "refactor(sprint-3): strip ~N tokens of unused formula text from Vision prompt

Removed sections explicitly marked 'computed by Python downstream' that
the model doesn't produce. Schema definitions and detection guidance
unchanged. Token count dropped from X to Y (~Z%).

Bench A/B validation deferred to Sprint 4 per parent spec §8 (3 PDFs
benchmark). Existing extractor unit tests still green."
```

(Replace N, X, Y, Z with actual numbers from the implementer's measurements.)

---

## Task 20: Sprint 3 acceptance — CHANGELOG + tests + smoke + follow-ups

**Files:**
- Modify: `CHANGELOG.md`
- Create: `docs/sprint-3-followups.md`

- [ ] **Step 20.1: Run full backend suite**

```bash
cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/ --ignore=tests/test_cross_page_validator.py --ignore=tests/test_deterministic.py --ignore=tests/test_edge_cases.py 2>&1 | tail -5
```
Expected: all green. Sprint 3 added: `test_verify_pass.py` (3), `test_grid_overlay.py` (3) = 6 new (≥175 total).

- [ ] **Step 20.2: Run full frontend suite**

```bash
cd frontend && npm run test:units 2>&1 | tail -5
```
Expected: ≥110 pass. Sprint 3 added: `viewerStore.test.js` (+8 → 15), `verificationQueue.test.js` (12), `categoryColor.test.js` (3), `scaleStore.test.js` (5) = 28 new.

- [ ] **Step 20.3: Smoke test build + dev server**

```bash
cd frontend && npx vite build 2>&1 | tail -5
```
Expected: clean.

Restart dev server (assuming backend already running with `SAMATU_AUTH_DISABLED=1`):
```bash
cd frontend && npm run dev
```
Open `http://localhost:5173/project/<existing-id>/v2` in browser. Verify per checklist below; document each in `docs/sprint-3-followups.md`.

- [ ] **Step 20.4: Manual smoke test checklist**

For each, document in `docs/sprint-3-followups.md` with ✓/✗ + notes:

- [ ] Page loads with full chrome — TopBar / ToolRail / Canvas / RightPanel visible
- [ ] Right panel default tab is Kiekiai; categories show with `🟢🟡🔴` confidence dots
- [ ] Hover KŽ row → polygon glow on canvas (bidirectional highlight)
- [ ] Click KŽ row → border-left appears + selection registered (G2/G3 target)
- [ ] Click kiekis number → inline editor in row → Enter commits → 🔒 if Shift+Enter
- [ ] Press `1` → ToolRail G1 button highlights
- [ ] Click canvas with G1 active → spinner + polygon appears (Sprint 2 stub)
- [ ] Press `5` → drag freehand → dotted lasso preview → release fires fetch
- [ ] Top-bar Patikrinti N → button visible when 🟡/🔴 exist; click → wizard slides up
- [ ] Wizard shows item 1/N + question + Taip/Pataisyti/Praleisti buttons
- [ ] Canvas auto-zoomed to current item polygon (amber glow visible)
- [ ] Click Pataisyti on number dispute → inline editor in wizard panel → Enter → advances
- [ ] Press Esc → wizard closes; chrome opacity returns to 1
- [ ] Wizard completion state → "Visi N patikrinti! Σ ..."
- [ ] Suvestinė tab → totals card + per-category bars
- [ ] AI tab → Run button + empty history
- [ ] No console errors; no Sprint 1 60fps regression on pan/zoom

- [ ] **Step 20.5: Create `docs/sprint-3-followups.md`**

```markdown
# Sprint 3 Follow-Ups

## Smoke test results 2026-05-XX

(fill ✓/✗ per checklist above, plus issues noticed)

## Open follow-ups for Sprint 4

- AssumptionsPanel field-name mismatch (Sprint 0 follow-up #12) still unfixed; new chrome doesn't expose AssumptionsPanel anymore on /v2 route, so impact reduced — but legacy /project/:id route still affected.
- AI tab "Recent runs" persistence — currently empty; needs project_store schema extension to remember runs.
- Pataisyti polygon dispute flow — cursor activates G1 but wizard doesn't auto-reopen on vision-fill response; user has to manually re-click Patikrinti. Sprint 4 wire post-gesture wizard re-entry.
- Token strip in prompt.py was conservative (Task 19); deeper cuts pending bench A/B (parent spec §8).
- ScaleBadge in TakeoffCanvas hardcoded to "1:50 🔒"; needs scaleStore wiring to actual project scale.
- Auto-zoom math in VerificationWizard uses approximate window dims; refine with actual canvas-ref measurement.
- TopBar "🔍 Ieškoti" + "⋯" buttons stubbed with alert(); real implementations Sprint 4.
- ToolRail Liniuotė (ruler) / Markup / Undo all stubbed with alert(); real Sprint 4.
- Wizard "Taip" + Shift currently re-issues an overrideQuantity with same value to set the lock; cleaner: backend `lock_only: true` flag in recompute-quantities.

## Known scope deferrals from spec §6

- Section 6 backend appendix (verify_pass / grid_overlay / prompt cleanup) shipped if budget allowed; if deferred, reschedule for Sprint 4.
- Page thumbnails in PageNavigator dropdown — Sprint 4.
- Page-type filter pills (Kreo pattern, research §2.4) — Sprint 4.
- Chart library / fancier Suvestinė visualization — Sprint 4.
- "Review everything" wizard mode (queue 🟢 too) — Sprint 4 setting.
- Settings / preferences UI — Sprint 4.

## Tracking
Sprint 4 plan should triage these.
```

- [ ] **Step 20.6: Update CHANGELOG.md**

Prepend to `CHANGELOG.md`:

```markdown
## Sprint 3 — Chrome + Verification Wizard — 2026-05-XX

### Added — frontend chrome
- `<TopBar>` 48px chrome row with project name, page nav, zoom, Patikrinti
  button (conditional on queue), Sąmatų AI button, ⋯ menu
- `<ToolRail>` 50px vertical rail with 10 visible tool buttons replacing
  Sprint 2's keyboard-only model. ✨ AI badges on G1/G4/G5
- `<RightPanel>` 320px tabbed container (✨ AI / 📋 Kiekiai / 📊 Suvestinė)
- `<QuantitiesPanel>` (replaces Sprint 2 MiniKZPanel) — category tree +
  filter pills (Visos / 🔴 / 🟡 / 🔒) + search + bidirectional highlight +
  G7 inline edit + Σ totals footer
- `<AiPanel>` — Run Sąmatų AI button + recent-runs list (empty state)
- `<SuvestinePanel>` — Σ neto + 21% PVM card + per-category horizontal bars
- `<PageNavigator>` page picker dropdown
- `<VerificationWizard>` — opt-in bottom panel (~140px) walking through
  🟡+🔴 items step-by-step with auto-zoom, Taip/Pataisyti/Praleisti.
  Shift+Taip locks 🔒. Pataisyti dispatches by dispute_type (number →
  inline editor; count → G2/G3 cursor; polygon → G1 cursor)
- `<InlineEditor>` — bottom-panel inline editor for number disputes

### Added — frontend libs
- `verificationQueue.js` — pure: builds queue from rooms+pozicijos,
  orders 🔴 first, classifies dispute_type, supports skipped tracking
- `categoryColor.js` — single primary blue (Sprint 3 spec §3 locked)
- `scaleStore.js` — zustand sub-store for scale ratio + lock

### Added — backend (Section 6 appendix)
- `extractor/verify_pass.py` — Opus 4.7 self-verify shim returning
  advisory corrections[] (Sprint 3 stub; Sprint 4 wires real SDK call).
  Gated by `ENABLE_VERIFY_PASS=1`
- `extractor/grid_overlay.py` — Pillow stamps faint 1m gridlines onto
  page raster. Gated by `ENABLE_GRID_OVERLAY=1`
- `prompt.py` — stripped ~N tokens of unused formula text (X→Y total)

### Changed
- `viewerStore` extended with `wizardOpen`, `wizardItemPolygon`,
  `lockOnConfirm`, `currentPage` + setters
- `<TakeoffCanvas>` reads `currentPage` from viewerStore (was hardcoded 0);
  added subtle blueprint grid background (Kreo pattern); ScaleBadge
  bottom-left placeholder
- `<AnnotationLayer>` reads `hoveredRoomId` for stroke thicken + glow;
  fourth layer draws `wizardItemPolygon` amber-glow during verification
- `<InteriorProjectV2>` body fully rewritten: composes new chrome
  (TopBar / ToolRail / Canvas / RightPanel / Wizard) with bidirectional
  highlight wiring + per-tab badges + AI run handler
- `MiniKZPanel.jsx` deleted (superseded by QuantitiesPanel)

### Known follow-ups
See `docs/sprint-3-followups.md`. Notable: Pataisyti polygon flow needs
post-gesture wizard re-entry; scaleStore not yet wired to project; AI
recent-runs persistence pending.

### References
- Spec: `docs/superpowers/specs/2026-05-04-sprint-3-chrome-design.md`
- Plan: `docs/superpowers/plans/2026-05-04-sprint-3-chrome.md`
- Brainstorm artifacts: `.superpowers/brainstorm/.../sprint-3-layout-{v1..v4}.html`
```

- [ ] **Step 20.7: Verify Sprint 3 Definition of Done**

Tick each from spec §1 success metric + §2 in-scope:
- [ ] Top bar / left rail / canvas / right panel visible workspace ✓
- [ ] All Sprint 2 gestures (G1-G5+G7) drivable from visible buttons ✓
- [ ] Bidirectional highlight working both directions (KŽ row ↔ polygon) ✓
- [ ] Verification wizard opens on top-bar button click + walks through 🟡+🔴 ✓
- [ ] Light palette throughout (`#f6f5f2` paper, `#2a6fb5` blue) ✓
- [ ] No backend regression: ≥175 pass ✓
- [ ] No frontend regression: ≥110 pass ✓
- [ ] CHANGELOG.md + sprint-3-followups.md committed ✓
- [ ] Manual browser smoke checklist run ✓

- [ ] **Step 20.8: Commit acceptance**

```bash
git add CHANGELOG.md docs/sprint-3-followups.md
git commit -m "chore(sprint-3): acceptance — CHANGELOG + smoke results + follow-ups

Sprint 3 deliverables verified per spec §1 success metric:
- Workspace chrome (TopBar/ToolRail/Canvas/RightPanel) replaces Sprint 2
  minimal MiniKZPanel mount
- VerificationWizard opt-in with structured Yes/Fix/Skip flow
- Bidirectional highlight working
- Light palette throughout (no dark theme remnants)
- ≥28 new frontend tests + ≥6 new backend tests, no regressions

Section 6 backend appendix shipped (verify_pass + grid_overlay + prompt
strip) — gated behind feature flags, default off, awaiting Sprint 4
A/B benchmark per parent spec §8."
```

---

## Sprint 3 Wrap

After Task 20 commits cleanly, Sprint 3 is done.

Next steps:
1. Manual browser smoke test against real PDF (user runs).
2. If smoke clean → consider merging Sprint 2 + Sprint 3 worktree to main as a single integration commit (per parent spec §6 sequential sprint pattern).
3. Sprint 4 plan write — parent spec §6: real-PDF testing + cross-LLM proxy GT + Sonnet 4.6 vs Opus 4.7 A/B + iteration.

---

## Self-Review

### Spec coverage check

For each spec section, confirm a task implements it:

| Spec § | Requirement | Task |
|--------|-------------|------|
| §4.1 TopBar | Project name, page nav, zoom, Patikrinti, AI button | Task 4 |
| §4.1 ToolRail | 10 buttons, ✨ on AI tools | Task 5 |
| §4.1 RightPanel | 3 tabs container | Task 9 |
| §4.1 QuantitiesPanel | Tree + filter pills + search + footer | Task 10 |
| §4.1 AiPanel | Run button + history | Task 11 |
| §4.1 SuvestinePanel | Totals + breakdown | Task 12 |
| §4.1 VerificationWizard | Bottom panel + 3 buttons + auto-zoom | Tasks 13, 15 |
| §4.1 InlineEditor | Number-dispute fix surface | Task 14 |
| §4.1 PageNavigator | Page picker | Task 6 |
| §4.1 verificationQueue lib | Queue builder + classify | Task 2 |
| §4.1 categoryColor lib | Brand-blue accent | Task 3 |
| §4.1 scaleStore lib | Ratio + lock | Task 3 |
| §4.2 viewerStore extensions | wizardOpen / lockOnConfirm / currentPage / wizardItemPolygon | Task 1 |
| §4.2 TakeoffCanvas modifications | currentPage read, scale badge, grid bg | Tasks 6, 7 |
| §4.2 AnnotationLayer modifications | hoveredRoomId, verification glow | Task 8 |
| §4.2 InteriorProjectV2 rewrite | Mount everything + bidirectional highlight | Task 16 |
| §4.2 MiniKZPanel delete | Replaced by QuantitiesPanel | Task 16 |
| §4.3 verify_pass.py | Opus self-verify shim | Task 17 |
| §4.3 grid_overlay.py | Pillow gridline stamper | Task 18 |
| §4.4 prompt.py token strip | ~2K tokens cut | Task 19 |
| §5.3 wizard mechanics | Progress / question / 3 buttons / Esc / completion | Task 13 |
| §5.6 tab badge counts | AI/Kiekiai/Suvestinė badges | Task 9 (RightPanel accepts), Task 16 (passes) |

All spec requirements covered. ✓

### Placeholder scan

Plan does not contain "TBD" / "implement later" / "fill in details". Tasks 17–19 are explicitly Section 6 appendix and may be deferred — that's by design, not a placeholder. Stub `_call_opus` in Task 17 has docstring stating Sprint 4 wires real SDK; this is a deliberate deferral noted in the spec, not a hidden gap.

### Type consistency check

- `verificationQueue` items: `{id, label, kiekis, vnt, polygon, dispute_type, skipped, confidence, saltinis}` — defined in Task 2, consumed in Task 13 (wizard reads `item.label`, `item.kiekis`, `item.vnt`, `item.dispute_type`, `item.confidence`, `item.saltinis`, `item.polygon`).
- `viewerStore.wizardItemPolygon` — set in Task 13 wizard `useEffect`, read in Task 8 AnnotationLayer.
- `viewerStore.hoveredRoomId` — set in Task 10 QuantitiesPanel onMouseEnter, read in Task 8 AnnotationLayer.
- `viewerStore.selection` — set in Task 10 QuantitiesPanel onClick, read by Sprint 2 G2/G3 hooks (already wired).
- `categoryAccent(skyrius)` returns string — defined Task 3, consumed implicitly via `BRAND_PRIMARY` constant.
- `overrideQuantity({rooms, pozicijos, currentAssumptions, targetPozicijaId, newValue, signal})` — Sprint 2 lib reused in Tasks 10, 13.
- `buildQueue({rooms, pozicijos, skipped})` returns Array<QueueItem> — defined Task 2, consumed Task 16 (`useEffect` calls it; `setVerificationQueue`).
- `VerifyResult` dataclass: `corrections: list[dict], error: str | None` — defined Task 17, currently consumed only by tests; AI panel surfacing is Sprint 4.

All names + signatures consistent across tasks. ✓

### Scope check

20 tasks, ~140 steps, fits the spec §1 budget of 5–7 days for an experienced contributor. Section 6 appendix (Tasks 17–19) is structurally separable — if days run short, Sprint 3 ships without them and they slide to Sprint 4.

Plan is single-feature (workspace chrome + wizard). No subsystem decomposition needed.
