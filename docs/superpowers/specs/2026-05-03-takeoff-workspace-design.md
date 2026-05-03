# Takeoff Workspace — Design Spec

**Date:** 2026-05-03
**Status:** Approved (brainstorm complete, ready for implementation plan)
**Author:** Ignas + Claude (brainstorm session)
**Predecessors:** `docs/superpowers/research/2026-05-02-competitor-viewer-ui-deep-dive.md`, `detector_bench/results/2026-05-03-bakeoff.md`, `docs/superpowers/plans/2026-05-02-phase-c-3-click-to-fill.md`

---

## 1. Executive Summary

**Problem.** Sąmatų AI today produces interior takeoff numbers via Claude Vision but the in-app PDF viewer is a passive `pdf.js` blob. Users (LT contractors) cannot verify or correct AI output without leaving the app and re-measuring with Excel + printed drawings. The current viewer is also laggy (zoom and pan trūkčioja), reinforcing an "amateur tool" perception.

**Goal.** Build a Togal/Kreo-class takeoff workspace that lets a contractor verify and correct AI output entirely in-app. Production-ready means: a real contractor uploads a real interior PDF, reaches a final KŽ (kiekių žiniaraštis), and saves measurable time vs the manual Excel baseline.

**Success metric.** Time-to-finish KŽ on a real PDF goes from a manual baseline of ~4–8h to ≤30 min in-app, measured by Sprint 0 baseline run vs Sprint 4 end-to-end test on the same PDFs.

**Scope discipline.** Interior finishing only (paint, GKP, plytelės, karnizai, glaistas, electrical/plumbing counts). No facade, no roof, no earthworks. Symbol/area accuracy ceiling is intentionally ~50% AI + fast manual correction, not chase 90% detector accuracy.

---

## 2. Scope

### In scope
- Interior takeoff workflow on `/extract-interior` pipeline
- New `<TakeoffWorkspace>` UI replacing legacy `PdfViewer` (dual-route during Sprints 1–3)
- 6 gesture types (G1–G5, G7) — see §5.4
- Verification-first default UX (queue-driven), with always-visible "Laisvas redagavimas" escape
- Tile-equivalent rendering via mip-pyramid + CSS-transform-during-interaction
- 5 Sprint-0 math fixes (audit findings) — see §7
- Cross-LLM proxy ground truth for Sprint 4 measurement

### Out of scope (explicit)
- Facade, roof, earthworks, concrete, masonry takeoff (Sections 2–11 of CLAUDE.md construction types)
- F2/F3 forms, Sistela integration
- Multi-user collab / project-level auth (still localStorage-only for MVP)
- DWG/DXF parsing (ezdxf integration deferred to post-MVP)
- Mobile / tablet UX (desktop browser only)
- Polygon vertex-level editing (G6 dropped — user signal: "polygon piesimas — nezinau kam reikalingas")

---

## 3. Approach Decision

Three approaches were considered:

- **A — Minimum Path** (~3 weeks). Math fixes + Vision G1 + lasso/click on existing viewer; lag NOT fixed. Rejected: contractor first impression remains "amateur."
- **B — Optimized Stack** (~5–6 weeks). Math fixes → mip-pyramid rendering → gesture set → polish → real-PDF testing. **Selected.**
- **C — Pro-Polish** (~6–8 weeks). Same plus react-pdf-viewer Pro ($129) + heavier custom Konva. Rejected: vendor risk and Pro features don't address rendering-engine lag.

**Locked decisions:**
- Free stack only (no PSPDFKit / Apryse / commercial licenses)
- pdf.js engine stays (lag fixed at rendering-strategy level via mip-pyramid + CSS transform, not by swapping engine)
- Sequential sprints with auto-handoff between them (no review gates between sprints, only at end of each)
- All accuracy-affecting changes feature-flag-gated
- Verification-first UX (variant B: visible escape) — power tools default-hidden behind "Laisvas redagavimas" toggle

---

## 4. Architecture

### 4.1 Frontend — new modules

| Path | Role |
|------|------|
| `frontend/src/components/project/TakeoffWorkspace.jsx` | Top-level chrome: top bar, optional tool rail, canvas, side panel, verification panel |
| `frontend/src/components/project/TakeoffCanvas.jsx` | PDF rendering with mip-pyramid + CSS transform during interaction + OffscreenCanvas settle |
| `frontend/src/components/canvas/AnnotationLayer.jsx` | Konva 3-layer hierarchy: committed (`listening=false`), active (selected), preview (hover) |
| `frontend/src/components/canvas/gestures/G1VisionFill.jsx` | Click-to-fill handler |
| `frontend/src/components/canvas/gestures/G2AddCount.jsx`, `G3RemoveCount.jsx`, `G4ColorSample.jsx`, `G5Lasso.jsx` | Gesture handlers (one file each) |
| `frontend/src/components/panels/QuantitiesPanel.jsx` | KŽ hierarchy (Folder → Classification → Item) + bidirectional highlight + 🟢🟡🔴 confidence badges |
| `frontend/src/components/panels/VerificationPanel.jsx` | Bottom panel; queue-driven question/answer flow (primary surface in default UX) |
| `frontend/src/lib/viewerStore.js` | Zustand store: `viewportTransform`, `hoveredRoomId`, `currentTool`, `selection`, `verificationQueue`, `verificationIndex` |
| `frontend/src/lib/renderQueue.js` | `p-limit(2)` concurrent render queue |
| `frontend/src/lib/tileCache.js` | LRU `ImageBitmap` cache (max 30, calls `.close()` on evict) |

### 4.2 Frontend — modified / removed

- `frontend/src/components/project/PdfViewer.jsx` — kept on legacy route `/project/:id` during Sprints 1–3; default switches to `TakeoffWorkspace` end of Sprint 3; removed Sprint 4
- `frontend/src/lib/interiorCalc.js` — paint logic deleted; recalc delegated to `POST /api/recompute-quantities`
- `frontend/src/lib/pdfStore.js` — IndexedDB blob fetcher kept; viewer state migrated to `viewerStore.js`

### 4.3 Backend — new modules

| Path | Role |
|------|------|
| `backend/extractor/verify_pass.py` | Opus 4.7 self-verify call; returns advisory `corrections[]` array (NOT overwrites) |
| `backend/extractor/grid_overlay.py` | Pillow stamps faint 1m gridline + scale bar onto floor_plan pages before Vision call |
| `backend/extractor/wall_adjacency.py` | Polygon graph builder; consumes `polygon_pct[]` from Vision, computes shared edges deterministically; outputs corrected perimetras + grindjuostės |
| `backend/extractor/scale_validator.py` | Extracts numeric scale from title block, validates room dimensions consistent with rendered DPI; emits warnings on >5% mismatch |
| `backend/extractor/proxy_gt.py` | Sprint 4 only: cross-LLM (Opus + Gemini) agreement diff; routes disagreements to human review queue |
| `backend/page_raster_cache.py` | LRU page render cache (Phase C-3 plan; finally implemented in Sprint 1) |
| `backend/api/vision_fill.py` | `POST /api/vision-fill` (G1) |
| `backend/api/recompute_quantities.py` | `POST /api/recompute-quantities` (G2/G3/G4/G7) |
| `backend/api/lasso_rerun.py` | `POST /api/lasso-rerun` (G5) |
| `backend/telemetry/session_log.py` | Append-only JSONL session timing logger |

### 4.4 Backend — modified

Sprint timing in parentheses; full per-sprint plan in §6/§7.

- `backend/extractor/prompt.py`:
  - Add `polygon_pct` to room schema (Sprint 0; consumed by `wall_adjacency` Sprint 2)
  - Add scale verification rule (Sprint 0, Fix 3)
  - Add per-room ceiling height variance instruction (Sprint 0, Fix 4)
  - Add paint class inference from spec instruction (Sprint 0, Fix 5)
  - Strip 2,000 tokens of formula text the model is told to ignore (Sprint 3, prompt cleanup)
  - `MODEL_PASS1 = "claude-sonnet-4-6"`, `MODEL_PASS2 = "claude-opus-4-7"` (Sprint 4 A/B → default-on)
- `backend/extractor/vision_call.py`:
  - Fix GKP 9.5/12.5 thickness split at line ~1010 (Sprint 0, Fix 1)
  - Fix paint formula to use paint class consistently (Sprint 0, Fix 2 — frontend side)
  - Wire two model IDs (Sprint 4)
  - Async-trigger `verify_pass` post-Pass-1 (Sprint 3)
- `backend/extractor/universal_rules.py`: drywall thickness constants finally referenced (Sprint 0); paint class inference path (Sprint 0)
- `backend/main.py`: register new endpoints (Sprints 1–2); read feature flags from env (Sprint 0)

### 4.5 New API endpoints

| Endpoint | Body / Params | Returns | Used by |
|----------|---------------|---------|---------|
| `POST /api/vision-fill` | `{page_id, click_xy, viewport_state}` | `{polygon_pct, room_id?, confidence}` | G1 click-to-fill |
| `POST /api/recompute-quantities` | `{project_id, edits: [{room_id, field, new_value, source}]}` | Updated full KŽ JSON | G2/G3/G4/G7 + Prielaidos panel |
| `POST /api/lasso-rerun` | `{page_id, lasso_polygon}` | Re-extracted symbols/zones in lassoed region | G5 |
| `GET /api/page-tile/:page/:zoom` | (cached) | PNG bitmap at fixed mip-zoom level | TakeoffCanvas |
| `GET /api/config` | — | `{feature_flags, model_ids, ...}` | All UI |

### 4.6 Dependencies

- `zustand` (frontend, ~5KB) — state store
- `p-limit` (frontend, ~3KB) — concurrent render queue
- `lru-cache` (frontend, ~6KB) — tile cache
- `@google/genai` (backend, Sprint 4 only) — Gemini SDK for proxy GT
- `opencv-python-headless==4.10.0.84` (backend, deferred — only if Vision G1 fails on edge PDFs)

### 4.7 Data flow — typical session

1. **Upload.** PDF → backend renders 3-level mip-pyramid (`0.5×`, `1.5×`, `3×`) → `/extract-interior` runs Pass-1 (Sonnet 4.6) → returns `{rooms[], polygon_pct[], pozicijos[]}` → `wall_adjacency` computes shared edges → `lt_rules` applies formulas → response: KŽ JSON + polygon overlay data + verification queue (sorted by confidence: 🔴 first).
2. **Async verify.** Backend triggers `verify_pass` (Opus 4.7) in the background → returns `corrections[]` → merged as advisory suggestions in `QuantitiesPanel` and as items in verification queue.
3. **Render.** `TakeoffWorkspace` mounts → `TakeoffCanvas` fetches canonical-zoom tile for current page from `/api/page-tile` → `AnnotationLayer` renders polygons from response → `QuantitiesPanel` renders KŽ → `VerificationPanel` shows item 1 of N.
4. **Verification flow.** User answers Yes/No on each queue item. On "No, fix" → relevant gesture auto-activates (e.g., G7 if dimension dispute, G1 if polygon dispute) → user click(s) → result persists → queue advances.
5. **Free-form (escape).** "Laisvas redagavimas" toggle in top-right shows tool rail; user can use any gesture out of queue order; queue resumes when toggle is off.
6. **Persistence.** Every gesture/edit writes to localStorage immediately; debounced sync to backend every 5s or on blur.
7. **Cancellation.** Rapid sequential gestures abort prior in-flight requests via `AbortController`.

### 4.8 Cross-cutting concerns

- **Feature flags:** backend env vars (`ENABLE_VERIFY_PASS`, `ENABLE_POLYGON_PREPASS`, `ENABLE_SONNET_PASS1`, `ENABLE_GRID_OVERLAY`, `ENABLE_PROXY_GT`); exposed via `/api/config`.
- **Telemetry:** `backend/telemetry/session_log.jsonl` (append-only). Schema: `{project_id, started_at, gestures: [{type, timestamp_ms_from_start, target: {kind, id}, outcome: "success"|"error"|"cancelled", duration_ms}], finished_at, total_seconds, exported: bool}`.
- **Migration:** dual-route during Sprints 1–3 (`/project/:id` legacy, `/project/:id?v=2` new); default switches end of Sprint 3; legacy removed Sprint 4.
- **Error handling:** every gesture endpoint returns structured error envelope `{error_code, user_message, retry_safe}`; frontend shows specific Lithuanian message ("Vision call failed, retry?"), never silent spinner.

---

## 5. UX Design

### 5.1 Layout (Kreo-style + collapsible from C)

Default layout, top to bottom, left to right:

- **Top bar (36px):** project name, page picker (current/total), zoom %, "⚙️ Laisvas redagavimas" toggle (right-aligned)
- **Left tool rail (48px, collapsed default):** hidden in verification mode; visible when "Laisvas redagavimas" is on. Icons for G1–G5 + pan default (V).
- **Canvas (flex):** `TakeoffCanvas` with mip-pyramid + Konva annotation overlay. Auto-zooms to current verification target.
- **Right panel (220px, collapsible to 32px ribbon):** `QuantitiesPanel` with category tree (paint=mėlyna, plytelės=oranžinė, GKP=žalia, elektra=geltona). When collapsed, only category icons + Σ totals visible vertically; clicking the ribbon expands.
- **Bottom verification panel (130px, primary surface):** `VerificationPanel` with progress bar ("3 iš 8"), current question, [Taip] / [Ne, pataisyti] / [Praleisti] buttons.

### 5.2 Verification-first UX (variant B)

**Default state.** App opens → user sees a question, not a toolset. The verification queue is generated from AI confidence indicators (🔴 first, 🟡 second, 🟢 never enqueued — auto-trusted). Each item:
- A short question in Lithuanian (e.g., *"Vonioje rasta plytelių zona 5.2 m². Ar tai teisinga?"*)
- PDF auto-zoomed to the relevant region with the polygon glowing
- Two primary buttons: `[Taip ✓]` (advance), `[Ne, pataisyti]` (trigger relevant gesture)
- One secondary button: `[Praleisti]` (mark unanswered, advance)

**Gesture auto-activation.** Each verification queue item carries a schema:
```
{ id, dispute_type: "polygon" | "count" | "dimension" | "color_zone",
  target: { page_id, polygon_id?, room_id?, position_value? },
  question_lt: string, current_ai_value, confidence }
```
When user clicks "Ne, pataisyti", `dispute_type` maps to the appropriate gesture (`dimension` → G7, `count` → G2 or G3, `polygon` → G1, `color_zone` → G4). User makes the correction, queue auto-advances.

**Escape hatch.** "Laisvas redagavimas" toggle (top-right, low visual weight) reveals the tool rail and lets the user freely use G1–G5 outside the queue. Queue progress is preserved; user can return to queue mode any time.

**Completion.** When all queue items are answered (or skipped): *"Visi 8 punktai patikrinti! Σ Plotas 128 m², Σ Dažai 23 l."* with [Eksportuoti KŽ] / [Dar peržiūrėti] buttons.

### 5.3 AI confidence display

Every quantity in `QuantitiesPanel` carries a confidence badge:

- 🟢 (green dot) — value read directly from drawing dimensions
- 🟡 (yellow dot) — value calculated from partial data + assumptions
- 🔴 (red dot) — value estimated from room-type fallback defaults

Hover on a badge shows the provenance ("read from skyrius A pjūvis, lubų aukštis = 2.65m"). Badges drive the verification queue ordering. Manual overrides (via G7) replace the badge with 🔒 lock + show original AI value below the user's value.

### 5.4 Gestures (G1–G5, G7)

| Gesture | Trigger | Backend call | Visual feedback | Error handling |
|---------|---------|--------------|-----------------|----------------|
| G1 — Vision click-to-fill | Click inside a room | `POST /api/vision-fill` (~3–5s, ~$0.03/click) | Crosshair → "AI..." spinner near click → polygon animates in | "Nepavyko aptikti, bandyk lasso (G5)" |
| G2 — Click-to-add count | Click on missed symbol | `POST /api/recompute-quantities` | "+" cursor → green dot lights up → KŽ row increments | n/a (local state) |
| G3 — Click-to-remove count | Click on AI-placed dot | `POST /api/recompute-quantities` | Red strike cursor → dot fades → KŽ row decrements | n/a |
| G4 — Color-sample zone | Eyedropper click on colored region | `POST /api/recompute-quantities` (with color) | Eyedropper cursor → "AI..." → all matching outlines highlight simultaneously | "Spalva neaiški, bandyk lasso" |
| G5 — Lasso re-run | Drag freehand polygon | `POST /api/lasso-rerun` | Dotted lasso follows cursor → on release "AI..." → updated dots in region | Falls back to "no changes detected" |
| G7 — Numeric override | Click on KŽ row's number in panel | `POST /api/recompute-quantities` | Inline editor → typed value → Enter; 🔒 lock badge shows manual override; AI value shown below | n/a |

**Cross-cutting:** keyboard shortcuts (`V`=pan, `1`–`5`=tool, `Esc`=cancel) are documented in tooltips but never surfaced as primary UI. Default tool is pan/zoom; tool selection is sticky until canceled.

---

## 6. Sprint Plan

| Sprint | Length | Deliverable |
|--------|--------|-------------|
| 0 | 4 days | Math fixes (5 audit findings) + baseline timing telemetry + manual baseline run |
| 1 | 5–7 days | `TakeoffCanvas` with mip-pyramid + CSS transform + OffscreenCanvas settle + p-limit(2) concurrent render queue |
| 2 | 7–10 days | Gesture set (G1–G5 + G7) + shared-walls polygon pre-pass + Konva annotation layer hierarchy |
| 3 | 5–7 days | Polish: bidirectional highlight, color-coded layers, AI confidence badges, verification panel, self-verify pass, grid overlay, Vision prompt cleanup, memory watchdog |
| 4 | 5–7 days | Real-PDF testing on 5–10 LT projects + cross-LLM proxy GT setup + Sonnet 4.6 vs Opus 4.7 Pass-1 A/B + iteration |

Total: ~5–6 weeks. Sequential, no review gates between sprints (only end-of-sprint).

---

## 7. Sprint 0 — Detailed Fixes

### Fix 1: GKP thickness split (Day 1, ~6h)
- **Where:** `backend/extractor/vision_call.py:1010`, `universal_rules.py:79-80`
- **Change:** Track `lubu_tipas == "gkp"` separately from wall GKP. Output two pozicijos rows: "GKP lapai sienoms (12.5 mm)" and "GKP lapai luboms (9.5 mm)".
- **Test:** Snapshot Excel exports of test PDFs (P1, P2, P3); verify two rows where there was one; sums match.
- **Risk (medium):** Excel structure changes — CHANGELOG.md called out clearly; tooltip on new row for first 30 days.

### Fix 2: Frontend paint formula → backend delegation (Day 1, ~2h)
- **Where:** `frontend/src/lib/interiorCalc.js:187-188`, new `POST /api/recompute-quantities`
- **Change:** Delete frontend hardcoded `*2/9`, `*2/10`. New endpoint takes `edits[]`, returns updated KŽ. Frontend on Prielaidos edit → debounced call → re-render.
- **Test:** Edit paint class in Prielaidos; verify frontend value equals backend value (no divergence).
- **Risk (low):** pure bug fix.

### Fix 3: Scale verification (Day 2, ~4h)
- **Where:** new `backend/extractor/scale_validator.py`, called from `vision_call.py`
- **Change:** Extract numeric scale ("M 1:50" → 50). Validate room dimensions consistent with rendered DPI (3×4m at 1:50 + 200dpi → ~107.7px diagonal). Emit warning to user if mismatch >5%.
- **Test:** Test PDF with intentionally wrong scale; verify in-app warning appears; quantities NOT modified.
- **Risk (low):** warnings only.

### Fix 4: Ceiling height per room (Day 3, ~3h)
- **Where:** `backend/extractor/prompt.py:378-388` (zoom prompt), `vision_call.py` parsing
- **Change:** Pass-2 zoom prompt asks: *"If ceiling heights vary room-by-room (dropped soffit, etc.), report each room's height separately."* Populate `lubu_auksciai{room_name: height}`.
- **Test:** PDF with soffit (in test set) → per-room heights in result, not single average.
- **Risk (low):** additive data only.

### Fix 5: Paint class inference from spec (Day 3, ~3h)
- **Where:** `backend/extractor/prompt.py:418-422`
- **Change:** Vision prompt asks for surface finish from spec ("Q1/Q2/Q3/Q4 + matinis/pusiau matinis/blizgus"). Populate `rules_override.paint_class` if found; else fall back to wizard default.
- **Test:** 5 PDFs with explicit Q2/Q3 spec; measure inference accuracy. Target >80%.
- **Risk (low):** advisory only with fallback.

### Fix 6: Baseline timing telemetry + manual baseline run (Day 4, ~3h) **(P0)**
- **Where:** new `backend/telemetry/session_log.py`, frontend events instrumentation
- **Change:** JSONL append-only session log. Manual run: complete 1–2 real KŽ by hand (Excel + drawing), stopwatch each. Record in `docs/baseline-timing-2026-05.md` as pre-MVP anchor.
- **Test:** Open project → make 5 gestures → close → verify JSONL log line with correct schema.
- **Risk (none):** observability only.
- **Why P0:** without this, Sprint 4 has no baseline to measure success against.

### Sprint 0 Definition of Done
- All 6 fixes merged to main, behind feature flags where appropriate
- Pre/post Excel snapshots archived for 3 test PDFs
- `docs/baseline-timing-2026-05.md` committed with real numbers ("PDF1 manual: 4h 23min, 487 rows")
- Telemetry JSONL accumulating; min 1 session logged with verified schema
- No regression: existing `pytest` (backend) and `vitest` (frontend) suites green
- `CHANGELOG.md` updated; user-facing changes (GKP split) clearly noted

---

## 8. Accuracy Guardrails

Five commitments to prevent regression as we ship:

1. **No accuracy-affecting change ships without A/B** vs the current pipeline on the test set (3 PDFs minimum: P1, P2, P3).
2. **All new accuracy paths are feature-flag-gated** (one-line revert).
3. **Sprint 0 establishes the benchmark** (5–10 test PDFs with known eksplikacija sums).
4. **Each subsequent sprint runs the benchmark post-merge.** Regression alarm if any `coverage_N` drops >3pp.
5. **Cross-LLM proxy GT is spot-checked manually on 10% of items**; the caveat ("measured against proxy GT, not human GT") is documented in spec and surfaced in UI.

---

## 9. Out of Scope / Future Work

- **DWG/DXF parsing** (`ezdxf`) — high-value true ground truth where available; deferred to post-MVP if a contractor partner supplies DWGs (~10–20% of LT projects).
- **Multi-user collaboration** — locks, conflict resolution, real-time sync. Single-user localStorage MVP only.
- **Mobile/tablet UX** — non-trivial canvas adaptation; desktop-only MVP.
- **Sistela / F2 / F3 export** — KŽ Excel export only.
- **Facade, roof, earthworks, concrete, masonry takeoff** — Sections 2–11 of CLAUDE.md formulas exist but no code; not in this MVP.
- **Polygon vertex-level editing (G6)** — explicitly removed at user's signal that it isn't needed and adds complexity.
- **Auth / DB / project history** — projects in localStorage only.
- **OpenCV-based G1 fallback** — only if Vision-based G1 fails on edge PDFs in Sprint 4 testing.

---

## 10. Open Questions / Risks

### Risks (with mitigations)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Sonnet 4.6 silently degrades on Pass-1 vs Opus 4.7 | Medium | A/B in Sprint 4 on 3–5 LT PDFs before default-on; feature-flag-gated; one-line revert |
| Self-verify pass over-corrects (introduces new errors) | Low | Output is advisory `corrections[]` (suggests, never overwrites); kill-switch flag |
| Shared-walls polygon pre-pass produces worse grindjuostės than current Vision count | Medium | Validate against golden test PDFs (5–10 known answers) before default-on; feature-flag-gated; fall-back to current Vision count if polygon detection fails |
| Cross-LLM proxy GT bias (both LLMs share a hallucination) | Medium | Manual spot-check 10% of items; document caveat in spec and UI |
| Mip-pyramid memory exceeds Mobile Safari 250MB tab kill | Low | Only canonical (1.5×) zoom resident for all pages; preview/deep-zoom only for visible±1; LRU evicts ImageBitmap with `.close()` |
| pdf.js worker memory leak (#20198) over long sessions | Low | Memory watchdog: >500MB heap + 30s idle → silent destroy + recreate from cached Blob (Sprint 3) |
| Verification queue too sparse / too dense (UX flop) | Medium | Sprint 4 real-PDF testing tunes the heuristic for what enters the queue; tunable threshold per confidence tier |

### Open questions (deferred decisions)

- **Bidirectional highlight on multi-page polygons** — when a KŽ row aggregates polygons across pages, does hovering it cycle through pages or only highlight current-page polygons? Decision deferred to Sprint 3 once concrete examples exist.
- **G4 color-sample auto-confirm vs manual confirm** — does AI auto-add all matching zones, or does user confirm each one? Bias toward auto-confirm with single "undo all" button; revisit after Sprint 4 testing.
- **Verification queue persistence on reload** — if user closes and reopens, do they resume queue at last position or restart? Current assumption: resume; persisted via localStorage.

---

## 11. References

- Locked-in research: `docs/superpowers/research/2026-04-28-accuracy-priorities.md`, `2026-05-02-competitor-viewer-ui-deep-dive.md`, `togal-ux-patterns.md`, `togal-clickcount-ux.md`, `industry-takeoff-tools.md`, `2026-04-29-phase-c-libraries.md`
- Bake-off conclusions: `detector_bench/results/2026-05-03-bakeoff.md`
- Predecessor plan (subsumed into Sprint 2): `docs/superpowers/plans/2026-05-02-phase-c-3-click-to-fill.md`
- External: FloorplanVLM (arXiv 2602.06507), CVPR 2025 self-verification paper, EmbedPDF (reference architecture, MIT, not adopted)
