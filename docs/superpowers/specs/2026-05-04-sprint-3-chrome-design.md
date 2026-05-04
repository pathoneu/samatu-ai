# Sprint 3 — Chrome + Verification Wizard — Design Spec

**Date:** 2026-05-04
**Status:** Approved (brainstorm complete, ready for implementation plan)
**Author:** Ignas + Claude (brainstorm session)
**Predecessors:**
- `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md` (parent — Sprint 0–4 roadmap)
- `docs/superpowers/research/2026-05-02-competitor-viewer-ui-deep-dive.md` (Togal/Kreo/Bluebeam analysis)
- Live togal.ai help-center walkthrough (2026-05-04 Playwright session) — confirmed actual togal tool list, AI button workflow, layout proportions
- Sprint 2 work on `worktree-sprint-2-gestures` branch (26 commits, plumbing for all gestures + endpoints)

---

## 1. Executive Summary

**Problem.** Sprint 2 shipped the gesture plumbing (G1–G5 + G7 + backend endpoints + AnnotationLayer) on a deliberately minimal `/v2` UI surface — a single `MiniKZPanel` and keyboard-only tool selection. End-user feedback during smoke-test: "puslapi pdf tik vieną rodo ir vienintelis dalykas ką galiu daryti tai pakeisti skaičiukus" — the UI is below the bar of a working takeoff product.

**Goal.** Replace the Sprint 2 minimal chrome with a togal-style takeoff workspace in our existing light palette, plus a structured verification wizard that lets contractors patikrinti AI's uncertain positions step-by-step.

**Success metric.** A contractor opens `/project/<id>/v2`, sees a workspace they recognize as a takeoff tool (top bar / left tool rail / canvas / tabbed right panel), can use any gesture without keyboard memorization, and can opt-in to a structured 🟡/🔴 verification flow that auto-zooms to each item. No retraining vs. legacy `/project/<id>` for users familiar with togal/kreo.

**Scope discipline.** Frontend chrome + wizard component only. All backend endpoints from Sprint 2 reused as-is (no API changes). Spec §6 also lists self-verify pass / grid overlay / prompt cleanup under Sprint 3 — included here as a Section 8 backend appendix; if budget runs short, that appendix moves to Sprint 4.

---

## 2. Scope

### In scope
- Top bar component (project name, page nav, zoom, Patikrinti button, AI button)
- Left tool rail (visible tool buttons replacing Sprint 2 keyboard-only)
- Tabbed right panel (✨ AI / 📋 Kiekiai / 📊 Suvestinė)
- Full QuantitiesPanel replacing MiniKZPanel — category tree + filter pills + bidirectional highlight + confidence badges
- VerificationWizard component (bottom panel ~140px) — opt-in via top-bar button, 🟡+🔴 queue, Taip/Pataisyti/Praleisti
- "Pataisyti" inline editing surface (number → bottom panel input, polygon → canvas G1 cursor)
- Color-coded confidence dots using existing `--conf-high/med/low` tokens
- Polygon overlay using existing `--primary` brand blue (no rainbow per-category)
- AI tab content (Vision history list + new Vision-run button — wraps the same backend endpoints from Sprint 2)
- Suvestinė tab content (Σ totals, breakdown by category)
- Page navigation (prev/next + page picker dropdown) — InteriorProjectV2 currently hardcodes `pageIdx={0}`
- Bidirectional highlight: hover KŽ row → polygon glow on canvas; hover canvas polygon → KŽ row scrolls into view
- Light palette throughout (`#f6f5f2` paper, `#2a6fb5` blue, `#fbfaf7` panel)
- "Mastelis 1:50 🔒" badge bottom-left of canvas (Kreo pattern)
- Subtle blueprint grid background under canvas (Kreo pattern)
- ✨ icon next to AI-using tools in left rail (G1, G4, G5)

### In scope (Section 8 — backend, can move to Sprint 4 if budget runs short)
- Self-verify pass (`backend/extractor/verify_pass.py`, `ENABLE_VERIFY_PASS=1`)
- Grid overlay (`backend/extractor/grid_overlay.py`, `ENABLE_GRID_OVERLAY=1`)
- Vision prompt cleanup (strip ~2,000 tokens of formula text the model is told to ignore)
- Memory watchdog refinement (Sprint 1 shipped, may need tuning under heavier polygon load)

### Out of scope (explicit)
- Polygon vertex-level editing (Merge/Split/Cut/Subtract — togal's polygon-classification paradigm). Our paradigm is "Vision returns numeric quantities, polygon is visualization only" — pivoting to polygon-as-source-of-truth is Sprint 4+ work.
- Multi-page navigation thumbnails sidebar (page picker dropdown only — thumbnails Sprint 4 if needed).
- Real Vision G1 / G5 calls (Sprint 2 stubs stay; Sprint 4 wires actual Pass-2 zoom + crop+symbol-extract).
- Cross-LLM proxy GT (Sprint 4 per spec §6).
- Real-PDF testing on 5–10 LT projects (Sprint 4).
- Rebuilding existing PDF viewer (`/project/:id` legacy) — left untouched. Default still switches to `/v2` end of Sprint 3 per parent spec §4.8.
- AssumptionsPanel field-name mismatch fix (Sprint 0 follow-up #12, separate cleanup).
- Drawing comparison / version history / collaboration features (togal has them; we don't need them).

---

## 3. Approach Decision

Three approaches considered during brainstorm:

- **A — Filter-only verification.** No wizard component. Top-bar button filters KŽ panel to 🟡+🔴 only; user clicks each row to edit. Minimum new code (~50 lines). **Rejected:** user smelled this would miss again — "strukturizuota ir lengva naudotis būtų geriau".
- **B — Verification-first (spec §5.1 original).** Wizard as primary surface, free-form behind a "Laisvas redagavimas" toggle. **Rejected:** togal-style mental model — power users want to dive in, not answer questions first. Verification is the secondary mode.
- **C — Free-form default + opt-in wizard.** **Selected.** Workspace opens in togal-style free-form. Top-right shows `🟡 N →` button; click opens structured wizard (bottom panel ~140px, 🟡+🔴 queue, auto-zoom canvas, Taip/Pataisyti/Praleisti). User can close wizard mid-way; skipped items remain queued.

**Locked decisions:**
- Free-form default workspace — togal layout patterns (top bar / left rail / canvas / tabbed right panel)
- Light palette throughout — `#f6f5f2` paper + `#2a6fb5` construction blue + warm-paper-1 sidebar (`#fbfaf7`). Existing `--conf-high/med/low` tokens for confidence dots.
- Single brand-blue polygon stroke — no rainbow per-category. Selection state: thicker stroke + glow.
- Verification wizard is OPT-IN, NOT primary — bottom panel slides up only on explicit click; closed by ✕ or Esc.
- Wizard scope: 🟡 + 🔴 by default. 🟢 auto-trusted (never queued). Settings opt-in for "review everything" — Sprint 4.
- "Taip ✓" default = NOT lock 🔒 (AI may still recompute on next run). Shift+Taip = lock 🔒. User explicitly confirmed.
- "Pataisyti" UI surface = dispute_type-dependent. Number dispute → bottom-panel input editor. Polygon dispute → canvas G1 cursor activates. After fix, wizard auto-advances.
- Kept Sprint 2 keyboard shortcuts (V / 1–5 / Esc) as accelerators alongside visible tool buttons.
- Dropped Merge/Split/Cut polygon-edit tools — togal paradigm requires polygon-as-source-of-truth that we don't have.

---

## 4. Architecture

### 4.1 Frontend — new modules

| Path | Role |
|------|------|
| `frontend/src/components/workspace/TopBar.jsx` | Top bar chrome: logo, project name, page nav, zoom, Patikrinti button, AI button |
| `frontend/src/components/workspace/ToolRail.jsx` | Left vertical tool rail with visible buttons; reads/writes `viewerStore.currentTool` |
| `frontend/src/components/workspace/RightPanel.jsx` | Tabbed container with 3 tabs (AI / Kiekiai / Suvestinė); switches via internal state |
| `frontend/src/components/panels/QuantitiesPanel.jsx` | Replaces MiniKZPanel: category tree + filter pills + search + bidirectional highlight + confidence badges + footer (Σ + Eksportuoti) |
| `frontend/src/components/panels/AiPanel.jsx` | AI tab content: "Run Sąmatų AI" button + recent run history + status |
| `frontend/src/components/panels/SuvestinePanel.jsx` | Suvestinė tab: totals card + breakdown chart + PVM line + export button |
| `frontend/src/components/wizard/VerificationWizard.jsx` | Bottom panel ~140px; reads `viewerStore.verificationQueue` + `verificationIndex`; renders question card + Taip/Pataisyti/Praleisti buttons + progress dots |
| `frontend/src/components/wizard/InlineEditor.jsx` | Bottom-panel input editor used during Pataisyti when dispute_type === "number" |
| `frontend/src/components/canvas/PageNavigator.jsx` | Page picker dropdown — replaces hardcoded `pageIdx={0}` |
| `frontend/src/lib/verificationQueue.js` | Pure module: builds queue from rooms+pozicijos by confidence; orders 🔴 first; provides `dispute_type` + auto-zoom target per item |
| `frontend/src/lib/verificationQueue.test.js` | |
| `frontend/src/lib/categoryColor.js` | Maps `skyrius_enum` to category accent stripe color (single primary blue with optional border-left tint per category) |
| `frontend/src/lib/categoryColor.test.js` | |
| `frontend/src/lib/scaleStore.js` | Zustand sub-store for scale-badge state (display 1:N + lock) |

### 4.2 Frontend — modified

- `frontend/src/pages/InteriorProjectV2.jsx` — body swapped from current direct mount to compose `<TopBar>` + `<ToolRail>` + `<TakeoffCanvas>` (with renderOverlay) + `<RightPanel>` + `<VerificationWizard>` (conditionally rendered when queue active)
- `frontend/src/components/canvas/TakeoffCanvas.jsx` — add page navigation (currentPage from viewerStore drives `pageIdx`); add background-grid CSS pattern (subtle blueprint); add scale badge bottom-left
- `frontend/src/lib/viewerStore.js` — flesh out `verificationQueue` + `verificationIndex` (Sprint 2 stubs) with: `setVerificationQueue`, `advanceVerification`, `wizardOpen` boolean, `wizardItemPolygon` (auto-zoom target), `lockOnConfirm` boolean (default false; Shift+Taip flips it for one click)
- `frontend/src/components/canvas/AnnotationLayer.jsx` — accept `highlightedRoomId` from `viewerStore.hoveredRoomId`; thicken stroke + brighten fill on highlight; vertices visible only on `selection`
- `frontend/src/components/canvas/gestures/G1VisionFill.jsx`, `G2…G5` — no API changes; just verify they read `viewerStore.currentTool` driven by ToolRail clicks (already do)
- `frontend/src/components/panels/MiniKZPanel.jsx` — DELETED (replaced by `QuantitiesPanel`)

### 4.3 Backend — new modules (Section 8 appendix)

| Path | Role |
|------|------|
| `backend/extractor/verify_pass.py` | Opus 4.7 self-verify call after Pass-1; returns advisory `corrections[]` array; merged into result as suggestions, NOT overwrites. Gated by `ENABLE_VERIFY_PASS=1`. |
| `backend/extractor/grid_overlay.py` | Pillow stamps faint 1m gridline + scale bar onto floor_plan pages before Vision call. Gated by `ENABLE_GRID_OVERLAY=1`. |

### 4.4 Backend — modified (Section 8 appendix)

- `backend/extractor/prompt.py` — strip ~2,000 tokens of formula text the model is told to ignore (legacy V8 carryover).
- `backend/extractor/vision_call.py` — async-trigger `verify_pass` post-Pass-1 when flag on; merge `corrections[]` into result.

### 4.5 Data flow

**Default load (free-form):**
1. `InteriorProjectV2` mounts, fetches project from `projectStore.getProject(id)` (Sprint 2 fix)
2. `viewerStore.verificationQueue` populated by `lib/verificationQueue.js` from rooms+pozicijos confidence
3. Top-bar `Patikrinti N →` button shown when queue non-empty
4. User interacts free-form: hover KŽ row → `setHoveredRoomId` → AnnotationLayer thickens that polygon's stroke; click row → `setSelection`; click row's kiekis → G7 inline edit; press `1` or click ToolRail G1 button → `setCurrentTool("g1")` → click canvas → vision-fill etc.

**Verification wizard flow:**
1. User clicks `Patikrinti N →` → `viewerStore.wizardOpen = true`, `verificationIndex = 0`
2. `<VerificationWizard>` slides up (CSS transition); UI rest gets `opacity: 0.45 + pointer-events: none` overlay; canvas zooms to `verificationQueue[0].polygon` via `viewerStore.setTransform`
3. User clicks Taip ✓ → `recordGesture({type: "verify_yes", target})` → if Shift held: lock pozicija via `overrideQuantity`-like API call with `lock_only: true` flag → `advanceVerification`
4. User clicks Pataisyti → branches by `verificationQueue[index].dispute_type`:
   - `"number"` → `<InlineEditor>` replaces wizard question card; user types new value + Enter → `overrideQuantity` API call → `advanceVerification`
   - `"polygon"` → `setCurrentTool("g1")` + close wizard temporarily; on next vision-fill click, wizard auto-reopens at next index
   - `"count"` → `setCurrentTool("g2")` (or g3); user clicks canvas; on `recompute` complete, wizard auto-advances
5. User clicks Praleisti → mark item skipped (in-memory; not persisted across page reload) → `advanceVerification`
6. After last item: wizard footer text changes to "Visi N patikrinti! Σ ... [Eksportuoti KŽ] [Grįžti]"
7. User closes via ✕ or Esc → `wizardOpen = false`, queue persisted (skipped items survive); top-bar button shows remaining count

### 4.6 Cross-cutting concerns

- **Bidirectional highlight:** `viewerStore.hoveredRoomId` drives both KŽ row scroll-into-view (in QuantitiesPanel) AND polygon stroke thicken (in AnnotationLayer). Reverse: hover polygon on canvas (Konva onMouseEnter) → setHoveredRoomId → KŽ row scrolls + highlights yellow.
- **Auto-zoom math:** `wizardItemPolygon` (Array<[x,y]> in pdf-pct) → compute bounding box → set `viewerStore.scale` and `translate` so polygon centered + 30% padding around it. Smooth CSS transition (300ms ease).
- **Confidence semantics:** existing `--conf-high/med/low` tokens. Provenance hover-popover (Sprint 2 carry, not changed).
- **Lock badge:** 🔒 icon on row when `pozicija.override_locked = true`. Lock comes from G7 explicit override OR Shift+Taip in wizard.
- **Telemetry:** wizard open/close/answer events emitted via Sprint 0's `recordGesture`. New event types: `verify_yes`, `verify_fix`, `verify_skip`, `wizard_complete`, `wizard_close`. Schema: `{type, target: {kind: "pozicija"|"room", id}, outcome, duration_ms}`.

### 4.7 Component boundary checklist

For each new component file:

- `<TopBar>` — props: project name, current page, total pages, zoom %, queue count, callbacks for page nav / zoom / wizard open / AI run. Internal state: zoom dropdown open. Tested via lib (no JSX test runner per Sprint 1 follow-up #2).
- `<ToolRail>` — props: callbacks none (reads viewerStore directly). Renders 10 buttons, calls `setCurrentTool`. Pure presentation.
- `<RightPanel>` — props: rooms, pozicijos, currentAssumptions, callbacks. Internal state: active tab. Wraps three sub-panels.
- `<QuantitiesPanel>` — props: rooms, pozicijos, onSelect, onHover, onRecomputed, onGestureEvent. Reads `viewerStore.hoveredRoomId` for bidirectional highlight. Calls `overrideQuantity` for G7.
- `<VerificationWizard>` — props: rooms, pozicijos, currentAssumptions, onRecomputed, onGestureEvent. Reads `viewerStore.verificationQueue + index + wizardOpen`. Internal state: showInlineEditor boolean, editValue string.
- `<InlineEditor>` — props: pozicija, onCommit, onCancel. Pure controlled input.

---

## 5. UX Design

### 5.1 Layout (light palette)

```
┌─ TopBar 48px ─────────────────────────────────────────────────────────┐
│ [SĄ logo] Vilniaus 12 / Vidaus apdaila │ ← 3/12 ▾ → AP-03 Aukšto p.   │
│                                          │ [− 142% +] [🔍 Ieškoti]    │
│                                                              [🟡 3 →] │
│                                                       [✨ Sąmatų AI]  │
├─[ToolRail 50px]┬──────── canvas (flex) ────────────┬─[RightPanel 320px]
│ ↖ Selection   │                                    │ ✨AI │📋Kiekiai│📊
│ ✥ Pan         │  white PDF page on f6f5f2 paper    │ ─────────────────│
│ ⊏ Liniuotė    │  + subtle blueprint grid bg        │ [Filtruoti…   ⚙] │
│ ───           │  + brand-blue polygon overlays     │ ─────────────────│
│ ⌖✨ G1        │  + green dot symbols               │ ▾ Apdaila    12  │
│ ◌✨ G5        │  + selection vertices (violet ▢)   │   Sienų dažymas  │
│ 🎨 G4         │  + amber highlight on hovered room │   145.2 m²    🟢 │
│ ───           │                                    │   ...            │
│ ＋ G2         │                                    │ ▾ Plytelių darbai│
│ − G3          │                                    │ ▸ Elektra        │
│ ───           │                                    │ ▸ Gipskartonis   │
│ ↶ Undo        │                                    │ ──────────────── │
│ ✎ Markup      │  [Mastelis 1:50 🔒]                │ Σ 12 458 €  [Eksp]│
└───────────────┴────────────────────────────────────┴──────────────────┘
```

Verification wizard (when active) replaces 140px from canvas bottom + dims rail/panel/topbar to 0.45 opacity:

```
[chrome dimmed]
[canvas, auto-zoomed to current item, polygon glowing amber]
┌─ VerificationWizard 140px ────────────────────────────────────────────┐
│  1/3   ●○○    │ 🟡 Reikia patikrinti · Plytelių darbai                 │
│  ━━━           │ Vonioje rasta plytelių zona 23.4 m² (sienos iki 2.0m)│
│                │ Šaltinis: AI iš spec'o. Detaliau ↗                   │
│                │              [✓ Taip] [Pataisyti]   Praleisti →    ✕│
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Color & confidence

- **Polygon stroke (committed):** `--primary` `#2a6fb5` 1.5px, fill `rgba(42,111,181,0.10)`
- **Polygon stroke (selected):** same color but 2.5px + `box-shadow: 0 0 0 1px primary` glow
- **Polygon stroke (verification target):** `--source-ai` amber 3px + `0 0 24px rgba(201,122,44,0.55)` glow
- **Vertices on selected polygon:** `--source-computed` violet `#6f5fa3` 6px squares
- **Symbol dots (electrical/plumbing):** `--source-table` green `#2f7d5b` 7px circles + 1.5px white ring
- **Confidence dots (KŽ row):** `--conf-high` (green) | `--conf-med` (amber) | `--conf-low` (red) — small 7px circle right edge of row
- **Lock badge:** 🔒 emoji + `--source-computed` violet color on the kiekis text
- **Background grid:** `linear-gradient(rgba(42,111,181,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(42,111,181,0.025) 1px, transparent 1px)` 24px×24px

### 5.3 Verification wizard mechanics

- **Trigger:** `🟡 N →` button visible top-bar right of zoom controls when `verificationQueue.length > 0`. Cream-amber `--source-ai` styling.
- **Open animation:** bottom panel translateY 0% → −140px (slide up); main area opacity 1 → 0.45 over 200ms; canvas auto-zoom transform animates 300ms ease.
- **Layout:** 60px progress block (left) + question card (flex) + buttons block (200px right) + close ✕ (top-right, 30px from edge).
- **Question structure:**
  - Tiny label: `🟡 Reikia patikrinti · {skyrius_label}` (amber, uppercase, 11px)
  - Title: `{patalpa_pavadinimas}-je rasta {kiekis} {vnt}` (15px bold)
  - Subtitle: `Šaltinis: {saltinis_human}` + `Detaliau ↗` link (opens provenance popover from Phase C-2)
- **Buttons:**
  - **`[✓ Taip]`** — `--primary` blue solid, primary action. Hover: darker blue. Shift+click: lock 🔒.
  - **`[Pataisyti]`** — `--source-ai` amber border, cream fill. Triggers contextual gesture per `dispute_type`.
  - **`Praleisti →`** — text-link style, no border, `--muted-foreground`. Subtle.
- **Progress dots:** 16px wide × 4px tall pills, 4px gap. Active: `--source-ai` amber. Pending: `--accent` light grey. Completed: `--conf-high` green.
- **Inline editor (number dispute):** when Pataisyti pressed and dispute_type === "number", question card swaps to `[← back] {pavadinimas}: [______ m²] [✓ Įrašyti]`. Backspace/← back returns to question. Enter commits.
- **Polygon dispute fix flow:** when Pataisyti pressed and dispute_type === "polygon", wizard temporarily collapses (height 36px showing only "Spustelk ant teisingo polygon centro · ✕"); cursor becomes G1 crosshair; canvas regains pointer-events. On vision-fill response, wizard re-expands with next item. Esc cancels and returns to question.
- **Skipped items:** stay 🟡 in panel; queue marks them `skipped: true` (in-memory only). Top-bar button text changes to `🟡 N (1 praleista) →` showing skipped count subtly.
- **Completion state:** when `index >= queue.length`, wizard footer changes to:
  ```
  ✓ Visi 3 patikrinti
  Σ 12 458 € + 21% PVM = 15 074 €
  [Eksportuoti KŽ]  [Grįžti į workspace]
  ```
- **Close mid-way:** ✕ button or Esc → wizardOpen=false, queue preserved. User can reopen anytime.

### 5.4 Top-bar behaviors

- **Page nav:** ← prev / `3 / 12 ▾` / → next. Dropdown shows page list with thumbnails (small 80×100 PNG previews) and page-type label (Aukšto planas / Sienų išklotinė / Eksplikacija). Sprint 4 may add page-type filter pills (per Kreo pattern in research §2.4) — out of scope here.
- **Zoom:** −/+ buttons, percentage display, click % to type custom value. Existing `viewerStore.scale`. Keyboard: Cmd/Ctrl+`=` zoom in, Cmd/Ctrl+`−` zoom out.
- **🔍 Ieškoti:** opens command palette (Sprint 4 — placeholder button now, dispatches `Cmd+F` event).
- **🟡 N →:** wizard open. Hidden when `verificationQueue.length === 0`.
- **✨ Sąmatų AI:** primary action. Click → calls existing extraction endpoint (legacy `/extract-interior`); shows progress in AI tab. NOT a modal popup with checkboxes — user already chose extraction settings via assumptions. Just runs Vision again on current page. (Differs from togal's "what to extract" modal — our model is per-project not per-button.)
- **⋯ menu:** Settings / Sąmatos prielaidos / Apie / Atsijungti — dropdown.

### 5.5 ToolRail behaviors

- **Active state:** primary blue background + white icon (matches Sprint 1 pan/zoom default visual).
- **Hover:** muted background.
- **Tooltips:** title attribute with shortcut letter (e.g. "Selection (Esc)", "Click-to-fill (1)").
- **AI badges:** ✨ icon at top-right corner of G1, G4, G5 buttons (uses Vision endpoint — research §2.3 Kreo pattern).
- **Keyboard shortcuts:** unchanged from Sprint 2 (`V`, `1`–`5`, `Esc`).

### 5.6 RightPanel tabs

- **✨ AI tab:** "Run Sąmatų AI" prominent button + recent run history (timestamps, page count, ✓/✗ status, model used). Click history item → loads that run's results back into Kiekiai. Sprint 4 may add per-page selective run.
- **📋 Kiekiai tab (default):** filter pills (Visos / 🔴 N / 🟡 N / 🔒 N) + search + category tree. Each row: aprasymas (left) | kiekis vnt (right) | confidence dot (far right). Click row → setSelection (drives G2/G3 target). Click kiekis text → G7 inline edit. Hover row → setHoveredRoomId (bidirectional highlight). Footer: Σ neto + Eksportuoti button.
- **📊 Suvestinė tab:** Σ cards (medžiagos / DU / mechanizmai / pridėtinės / pelnas / PVM 21% → bendra suma). Breakdown by category with horizontal bars showing relative share. Export buttons (Excel + PDF).

### 5.7 Tab badge counts

- **AI tab:** `2` if 2 corrections from self-verify pass pending (Sprint 3 backend section)
- **Kiekiai tab:** `47` total pozicijos count
- **Suvestinė tab:** no badge

---

## 6. Backend appendix (Sprint 3 §6 items)

These are smaller backend items from parent spec §6 Sprint 3 list. If frontend chrome runs over budget, they move to Sprint 4. Plan should split them as separate task groups so they can be deferred cleanly.

### 6.1 Self-verify pass

- New `backend/extractor/verify_pass.py` — accepts Pass-1 result, calls Opus 4.7 with prompt: "Here's the AI's output. Identify quantities you'd disagree with and explain why." Returns `corrections: [{pozicija_id, suggested_value, reason, confidence}]`.
- Wired into `vision_call.py` post-Pass-1 when `ENABLE_VERIFY_PASS=1`.
- Frontend AI tab surfaces `corrections` count badge; clicking opens corrections list overlay (NOT auto-applied to KŽ).
- **A/B requirement (parent spec §8):** can't ship default-on without 3-PDF accuracy comparison.

### 6.2 Grid overlay

- New `backend/extractor/grid_overlay.py` — Pillow draws 1m×1m faint gridlines + scale bar onto floor_plan pages before Pass-1 Vision call.
- Goal: improves AI's ability to verify scale and read dimensions visually.
- Gated by `ENABLE_GRID_OVERLAY=1`.

### 6.3 Vision prompt cleanup

- `backend/extractor/prompt.py` — current prompt ~12K tokens; ~2K is formula text the model is told to ignore (legacy V8 carryover).
- Strip those 2K tokens. Validate accuracy unchanged via 3-PDF benchmark per parent spec §8.

### 6.4 Memory watchdog refinement (optional)

- Sprint 1 memory watchdog (`MemoryWatchdog.jsx`) shipped with `>500MB heap + 30s idle` → reset trigger.
- After Sprint 3 polygon load (potentially 200+ shapes per session), thresholds may need tuning.
- Likely no code change; just document threshold review in Sprint 3 follow-ups.

---

## 7. Migration & Compatibility

- **Sprint 2 components reused as-is:**
  - All gesture hooks (`useG1Handler` etc.) — driven by ToolRail clicks (was: keyboard) AND keyboard (kept).
  - `<AnnotationLayer>` — extended with `highlightedRoomId` prop.
  - `<TakeoffCanvas>` — extended with page navigation + scale badge + grid background.
  - All backend endpoints — no API changes.
- **Sprint 2 throwaway:**
  - `MiniKZPanel.jsx` — deleted, replaced by `QuantitiesPanel.jsx`.
  - `InteriorProjectV2.jsx` body — restructured around new chrome (TopBar + ToolRail + canvas + RightPanel + Wizard).
- **Legacy `/project/:id` route untouched.** Default route switch (legacy → /v2) still scheduled for end of Sprint 3 per parent spec §4.8.
- **Database / localStorage:** no schema changes. `verificationQueue.skipped` is in-memory only; survives wizard close but NOT page reload.

---

## 8. Out of Scope / Future Work

- Polygon vertex-level editing (Merge / Split / Cut / Subtract) — togal's polygon-classification paradigm. Our paradigm is "Vision quantities, polygon as visualization". Pivoting is Sprint 4+ work.
- Page thumbnails sidebar — picker dropdown sufficient for MVP.
- Page-type filter pills (Kreo pattern, research §2.4) — Sprint 4 if user signals friction.
- Real Vision G1/G5 calls — Sprint 4 wires actual Pass-2 zoom and crop+symbol-extract on top of current stubs.
- Cross-LLM proxy GT, Sonnet 4.6 vs Opus 4.7 A/B — Sprint 4.
- Drawing comparison / version history / collaboration features — out of MVP scope.
- AssumptionsPanel field-name mismatch fix — Sprint 0 follow-up #12, separate cleanup PR.
- "Review everything" wizard mode (queue 🟢 too) — Sprint 4 setting.
- Settings / preferences UI — Sprint 4.

---

## 9. Open Questions / Risks

### Risks (with mitigations)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Wizard interaction model confusing on first use ("what does Pataisyti do?") | Medium | First-launch coachmark explaining 3 buttons; help icon next to ✕. Sprint 4 user testing on 2-3 contractors. |
| Bidirectional highlight performance on large drawings (200+ rooms) | Low | AnnotationLayer's committed layer is `listening=false` (Sprint 2 design); hover updates only `selection` layer (small). Worst case 2-3 polygon updates per hover frame. |
| Auto-zoom math wrong on rotated PDFs / non-square pages | Medium | Test against Sprint 4 5-10 LT PDFs; bbox calculation already used by Sprint 0 `bbox_pct` zoom flow. |
| User accidentally Shift+clicks Taip → unintended lock | Low | Lock action shows toast "🔒 Pozicija užfiksuota — atšaukti?" with Cmd+Z support. |
| "Patikrinti" button hidden when queue empty → confusing once shown ("where did it go?") | Low | Empty-state subtle text in top bar position: "✓ Patikrinta" greyed out, click reopens last completed wizard for review. |
| Sprint 3 chrome runs over 5-7 day budget | Medium | Section 6 backend items (self-verify, grid overlay, prompt cleanup) move to Sprint 4 cleanly — they're independent of chrome. |
| Migrating MiniKZPanel state to QuantitiesPanel breaks Sprint 2 G7 wiring | Low | Sprint 2 G7 logic moves verbatim into QuantitiesPanel row component; tests stay green. |

### Open questions (deferred)

- **Page picker dropdown content** — show thumbnails (slow) or text labels only (fast, less informative)? Default to text labels with page-type prefix; thumbnails Sprint 4.
- **AI tab "Run" button on per-page or per-project basis** — current `/extract-interior` endpoint runs per-project (all pages). Per-page selective re-run is Sprint 4 feature.
- **Suvestinė tab chart library** — SVG inline (zero deps) vs Chart.js? Default to inline horizontal bars (no library) for Sprint 3; revisit Sprint 4 if bigger charts needed.
- **Wizard "Pataisyti" on count dispute (G2/G3)** — same canvas-cursor pattern as polygon dispute; user clicks symbol; wizard auto-advances on recompute. UX-tested against the polygon flow in Sprint 4 if confusion.

---

## 10. References

- Parent spec: `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md` (§4.1, §5.1 layout, §5.4 gestures, §6 Sprint plan, §10 risks)
- Sprint 2 plan: `docs/superpowers/plans/2026-05-04-sprint-2-gestures.md`
- Sprint 2 commits: `worktree-sprint-2-gestures` branch (26 commits, NOT yet merged)
- Sprint 2 follow-ups: `docs/sprint-2-followups.md`
- Competitor research: `docs/superpowers/research/2026-05-02-competitor-viewer-ui-deep-dive.md`
- Live togal walkthrough (2026-05-04): `https://help.togal.ai/how-to-get-started-with-the-editor-mode` + `/how-to-use-togal-automated-takeoff` + `/shortcuts`
- Brainstorm session mockups (4 iterations): `.superpowers/brainstorm/7837-1777907247/content/sprint-3-layout-{v1..v4}.html` — v4 is the locked design
- Theme tokens source: `frontend/src/index.css`
- Existing sub-libs ready for reuse: `viewerStore.js`, `coordTransform.js`, `gestureApi.js`, `abortRegistry.js`, `keyboardShortcuts.js`, `tileCache.js`, `mipPyramid.js`, `renderQueue.js`, `recomputeApi.js`, `projectStore.js`, `pdfStore.js`, `telemetry.js`
