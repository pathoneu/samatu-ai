# Pathon v3 — "Skaitymas ir spustelėjimas": programme design (draft for the founder, 2026-10-18)

**One sentence.** Pathon keeps its spine — interior finishing, Lithuanian rules, a priced sąmata with an evidence sentence and crop beside every number, free vector/text reading, learning from corrections — and gets the editor comfort of Togal and Kreo on top, with the backend reading more of the drawing (sheet zones, legends, schedules) so that every click lands on something the engine already understands.

**Status.** Draft for review before any code. Inputs: `docs/superpowers/research/2026-10-18-togal-editor-ui-re.md`, `…-kreo-editor-ui-re.md`, `…-pathon-viewer-ui-audit.md`, `…-backend-reading-inventory.md`, plus the older Togal pipeline analysis (2026-10-16) and the Rimo constraints (`docs/superpowers/plans/2026-09-04-rimo-kelione.md`). Pending input: the logged-in Kreo walkthrough (feel of hover/snap/drag, Measurements Manager, timed corrections) — it can refine details in §4 and §5, not the direction.

---

## 1. Goal, users, non-goals

**Goal.** A contractor uploads an interior project PDF and reaches a checked, priced sąmata faster and with fewer clicks than in Togal or Kreo, while seeing where every number came from. The app must feel like a professional estimating editor and still be usable by Rimas (35–60, estimates by hand today) without training.

**Users.** Rimas first: the default surface stays simple (four visible steps, plain Lithuanian, proposals he confirms). Bigger firms second: a pro layer underneath that never adds a step for Rimas — full keyboard, multi-select, density and overlay controls, isolate/visibility review, history, later roles and multi-user.

**Non-goals for v3.** All construction trades (interior stays the product), a Togal-style classification tree as the primary model, assemblies-first pricing, 3D, dark theme or any new visual identity now (Nordic Slate stays until the look is decided), billing surfaces, voice/agent copilots.

**What "merge" means.** Take their editor grammar and density; keep our checking model. Specifically:
- From Togal: light canvas inside a slate frame, floating icon tool cards, a contextual bottom pill, Space-pan / F-frame / Esc-to-select, review by visibility and isolation (Ctrl+click eye), right-click reassign, draw-to-subtract, dark toasts and compact confirms, one green for "auto-detected".
- From Kreo: review-before-create for every AI result (preview on hover, per-item accept/remove, then Create), a one-line cursor-side hint per mode, Esc that steps back one point before it exits, a floating action bar at the selection, vertex pop-up (Delete / Cut Path), one-click area with positive/negative clicks, "What changed — Undo", plan zones, rename-with-suggestions chips, schedule/table extraction with cross-reference.
- Keep ours, because the research shows it is already ahead: evidence sentences and crops per fact, the proposal-first Patikra question queue, staged run progress with reasons, "Parodyti patalpą" (wall-exact outline from one click — Togal has no one-click area at all), count removal in one click, the free re-read, the learning journal, Lithuanian everywhere.
- Skip from both: the random 18-hue rainbow and 50-colour palettes, per-item confidence sliders as the primary signal, feature breadth (repeating groups, 3D, collaboration views) until the core is done.

---

## 2. Measurable targets ("way better" in numbers)

| # | Target | Today (measured) | Togal | Kreo | v3 target |
|---|---|---|---|---|---|
| T1 | Clicks per correction, 12 common acts (audit §5) | 4–9 actions each | 1–4 | 1–8 | ≤ the better competitor on every act; ≤ half of today on the four worst |
| T2 | Human time from "PDF uploaded" to "checked sąmata" on an 11-room flat (project H), excluding the paid read | not yet measured (Patikra alone ≈ 3 min) | – | – | measured in wave 0, then ≤ 10 min with ≤ 40 clicks |
| T3 | Share of numbers the contractor never has to touch | 63 of 67 facts on H (94 %) | no per-item signal | no per-item signal | ≥ 95 % on out-of-sample projects, by Patikra's own counter |
| T4 | Reading coverage | diffusers only (H 9 / D 6 / B 20 / G 8 eye-verified); door schedule on D only, no bboxes | symbols by image search; no schedules | Auto Count + schedule export | every legend row on a marked legend counted within ±1 of a hand count on the corpus plan sheets; door and window schedules read with row bboxes on every project that has one |
| T5 | No regression | eval gate identical on every merge; browser walkthrough guide | – | – | unchanged |
| T6 | UI metrics (audit §2) | 12 font sizes, 91 % ≤ 12 px; 47 hex + 102 palette classes; toolbar 43 % hidden at 1440; 12 notice kinds; 6 of 9 zone strokes < 3:1 | – | – | ≤ 6 sizes, 14 px interface minimum; one overlay vocabulary; toolbar fits at 1280; one notice system; 0 contrast failures |

Click-count detail (today → target; competitor best in brackets): confirm scale 4 → 1 (Togal 1 chip); calibrate 6–9 → 4 (Kreo 4); fix a vertex 4+n → 2+n (Togal 2); room by one click 4 → 1 (Kreo 1–2, Togal none); merge two rooms 5 → 3; subtract a column 5–7 → 3 (Togal 4); add n counts n+2 → n+1 (both n+1); find similar 5–9+k → 3+k (both ≈ 4+k); measure a distance 4 → 3 (both 2–3); correct a quantity row 4–6 → 2; answer a Patikra question 2 → 1 (Enter); remove a false count stays 1 (Togal 3, Kreo 4).

---

## 3. The workspace (journey decision, taken from how Togal and Kreo do it)

Both competitors live in one workspace: the drawing is always present, review happens beside it. Pathon today splits into four screens and gives the drawing 32 % of the window.

**Decision: one workspace, four views.** The step rail (1 Brėžinys · 2 Patikra · 3 Sąmata · 4 Siųsti) stays as the visible journey, but steps 1–3 are views of the same workspace:
- the drawing canvas is persistent (light canvas, slate frame, floating tool cards left, zoom cluster bottom-right, scale chip bottom-left, contextual pill bottom-centre);
- the right panel is a mode host (Kreo's pattern): *Patalpos ir eilutės*, *Kiekiai*, *Patikra* (the question queue; the room sheet opens when a room is selected), *Sąmata* (rows; expands to full width on demand, the drawing collapses to a strip), *Pokalbis*;
- two-way everywhere: click a number → the drawing highlights its contributions and evidence; click or drag on the drawing → the number changes live with a Lithuanian sentence.
- The thumbnail rail collapses to a 56 px strip; the canvas gets ≈ 50 % of a 1440×900 window.

Siųsti stays a separate screen. Projektai becomes status rows (audit C17).

---

## 4. Backend capability map (tracks; built on the inventory)

Every track is €0 first (vector, text, raster math). Vision is a fallback only where vectors are absent, and only with the founder's OK per run.

**A. Sheet zones (new, `extractor/sheet_zones.py`).** Detect on every sheet: plan viewport(s), legend block, tables, title block, notes — from text density, `find_tables`, the existing title-block crop, wall-solid extent and vector density. Output `_meta.zonos[page] = [{kind, bbox_pct, label, confidence}]`. Consumers: the viewer (zone outline on hover; a click in the title block is never a room), the legend and table readers (where to look), room location (replaces the fixed 0.88 cut), counts (matches inside legends/tables create no markers, Kreo's rule). Fallback: the user drags a zone box and names it.

**B. Legend marking and symbol counting ("Pažymėti legendą").** The user accepts a suggested legend zone or draws one. `extractor/legend_rows.py` splits it into rows (glyph box + text) from text and vectors; each row becomes a count type with the glyph as template. Counting: the vector counter generalised from diffusers to any legend label, all plan pages, instances with boxes (today points, 4 pages, one regex); black-only glyphs go to the raster chamfer matcher as a server-side all-pages batch. Results arrive as hollow "rasta automatiškai" marks per page with review-before-create (per row: count, examples, ✔ / 🗑 per item, a sentence); accepted counts flow live into sąmata rows. The legend is stored per project in the existing `api/legends.py` store and offered for reuse on the architect's next project. Accept/reject keeps feeding `record-decision` and the corrections journal. Vision legend reading (`legend_injection`, role `legend`) is wired as the explicit fallback for raster legends, behind a per-run OK. Floor-covering legend lines (already read, thrown away) are surfaced the same way.

**C. Schedules and tables ("Lentelės").** A generic table reader on `find_tables` with header-role maps, each row with a bbox: eksplikacija (exists), door and window schedules (upgrade `door_schedule` to cells; add windows), finish schedule (apdailos lentelė, deterministic first; the Vision reader stays as fallback), tile specification with positions. Each row gets an evidence crop and "Rodyti brėžinyje". Reconciliation becomes Patikra questions: schedule rows vs openings drawn in the walls, finish table vs room finishes, legend totals vs computed. The free re-read and detect-run gain a "lentelės" stage (today tables are read only in the paid pass).

**D. Rooms, walls, openings — clicking.** The vector `outline_at` becomes the viewer's room tool (replacing the raster flood fill, which stays as fallback where no walls are found). Rooms become selectable by clicking the drawing (hit-test outlines and `_vieta`). Vertex editing with wall snap (exists) gains the vertex pop-up (Ištrinti · Iškirpti angą) and edge-drag. Merge = click A, Shift-click B, M. Subtract = X and a drag, or a one-click negative inside an outline. Openings editable on the drawing (width, kind). Every save returns the previous geometry so the client can offer Undo in the toast. Server cost: small additions to `room_outline.py`; the lane itself does not change.

**E. Scale.** A scale chip per sheet (measured 1:115 · patvirtinta / spėjama / nėra), one click to confirm, "visiems lapams" in the same chip, calibrate in a popover next to the line with the standard scale pre-selected. The measured-scale check (ours, stronger than Togal's OCR) stays.

**F. Measurements → sąmata.** Counts and lengths link to a row id and update it live (no „Į sąmatą"); a measured length can be dragged onto a row; the Kiekiai panel gets inline edit. Model change: a measurement carries `eilute_id`; recompute treats it as a contribution with its own ledger line.

**G. Feedback and learning.** Cursor-side hint per mode (replaces banners); the staged run panel restyled as the pill (keep stage names and reasons); "Kas pasikeitė — Atšaukti" after every lane re-read or AI proposal; one notice system; the corrections journal unchanged.

Out of the inventory, these are reused rather than rebuilt: `vector_symbols`, `cv_match.find_symbol_by_shape`, `api/legends.py`, `legend_injection`, `pdfplumber_eksplikacija`, `door_schedule`, `floor_coverings.legenda`, `outline_at`, `page_geometry`, `sheet_refs`, `evidence`, `detect_run` stages. Dead code that stays dead unless a track needs it: `/pdf-lines`, `MagicWandTool`, `CountTool`, V9 symbol routes, `vision-fill`.

---

## 5. Interaction model (the click vocabulary Pathon adopts)

| Mode | Click | Double-click | Drag | Right-click | Enter | Esc | Modifiers | Hint at the cursor |
|---|---|---|---|---|---|---|---|---|
| Select (1 / V) | selects a room, measurement or mark on the drawing | room → edit outline; measurement → edit | marquee; on a selected shape → move | room → menu (tipas / apdaila, Neskaičiuoti, Rodyti įrodymus, Sujungti, Atimti, Pervadinti); measurement → menu | – | clears selection | Shift+click adds to selection | "Spustelėkite patalpą" |
| Pan (Space held / H) | – | – | pans | – | – | – | – | – |
| Room (R) — one-click outline | inside a room → wall-exact outline, auto-commit, Undo in toast; click outside the result → expand, inside → shrink (Kreo) | – | – | – | – | drops the pending proposal, then exits | – | "Spustelėkite patalpos viduje" |
| Area / perimeter / distance (3 / 4 / 2) | adds a vertex | finishes | – | Baigti / Atšaukti pop-up (plus the visible buttons) | finishes; distance auto-commits on the 2nd click | **removes the last point; with no points left, exits** | Shift = ortho + 45°; Ctrl held = jump to snap | live length; snap marker shape says what it will hit |
| Count (6) | adds a mark; click a mark removes it | – | – | type menu | finishes | exits | – | type name + running count |
| Find similar (F) | – | – | tight box around one symbol | – | Create | cancel | – | "Apveskite vieną simbolį" |
| Legend (G) | accepts the suggested legend zone | – | draws a legend box | – | Create counts | cancel | – | row-by-row review panel |
| Edit outline (E) | vertex → select; edge → insert vertex | vertex → delete | vertex / edge drag with wall snap | vertex pop-up: Ištrinti · Iškirpti angą | saves (+ Undo toast) | reverts | – | readout + sentence |
| Merge (M) / Subtract (X) | pick B / draw the hole | – | rectangle hole | – | confirm | step back, then exit | – | consequence line under the bar |
| Scale (K) | chip → confirm; calibrate: 2 clicks | – | – | – | Apply | never auto-exits mid-calibration | – | "Spustelėkite žinomo ilgio pradžią" |

Rules: Esc order is tool → panel → selection (never drops the room while a panel is open); every tool has a key, the tooltip shows key + one sentence; Space pans from any tool; F frames the selection; keys 2/3/4/6 stay, S stays the walls layer (not snapping), U zones; a floating action bar appears at the selection with icon **and** Lithuanian text (never hover-only); every AI or lane result is reviewed before it exists (preview → ✔/🗑 → Create) and every write has Undo.

---

## 6. UI frame and overlay vocabulary (behaviour-neutral; look decided later)

- **Frame geometry from Togal, colours ours:** 56–60 px header in our slate `#192830`, light canvas, white panels, 45 px floating icon cards with short Lithuanian labels, right panel 340 px resizable, bottom pill for the active mode's options, toasts bottom-right, 300 px confirm boxes.
- **One overlay vocabulary** (replaces 11 meanings of "dashed" and 8 of "red"): solid = read or confirmed; dashed = estimated or proposed, nothing else; red = error only; selection = heavy neutral outline + label; fills at 0,12–0,20 alpha, constant 2 px strokes; labels as neutral pills with tabular numbers; meaning never by colour alone — a hover sentence and a legend card always say it. Zone fills become one neutral tint (room type shown in the label); the Patikra colour code (read / borrowed / missing) becomes the whole viewer's code.
- **Type and density:** 14 px interface minimum, 16 px body, ≤ 6 sizes; mono for numbers only; 32–40 px rows; targets ≥ 32 px (44 px for Rimas-critical buttons).
- **Notices:** one component, three tones; the re-read banner becomes a one-line chip; instructions live at the cursor and in the pill, not three times.
- Audit lists A–C (tokens, components, structure) are the work items; list D (interaction) is covered by §5.

---

## 7. Waves

Each wave: Opus 5.5 workers in worktrees with narrow briefs, this session reviews, eval gate identical, Playwright smoke of the founder's walkthrough guide, browser verification before the founder sees it, founder review on localhost, no push without OK.

| Wave | Scope | Mostly | €0? |
|---|---|---|---|
| 0 — Baselines (1–2 days) | Measure T1–T3 on H and G; turn the 2026-10-17 review guide into a Playwright smoke; fix the 7 small bugs from the audit; eval gate baseline on the togal-v2 head | tests, docs | yes |
| 1 — Workspace frame and click model | One workspace with the right-panel mode host; toolbar → icon cards + pill; select by click; room tool R (vector outline_at in the viewer); Esc/keys/Space/F; floating action bar; Undo after every save; notices → cursor hints; overlay tokens and vocabulary; density and type scale; scale chip | frontend, small backend | yes |
| 2 — Sheet zones, legend marking, symbol counting | `sheet_zones`, `legend_rows`, generalised vector counter with boxes and all pages, raster batch for black glyphs, review-before-create panel, counts → rows live, legend store reuse | backend | yes (Vision fallback behind OK) |
| 3 — Schedules and tables | generic table reader with row bboxes; door/window schedule cells; deterministic finish table; "lentelės" stage in detect-run and free re-read; reconciliation questions; "Rodyti brėžinyje" | backend | yes |
| 4 — Measurements → sąmata, Kiekiai inline edit, "Kas pasikeitė — Atšaukti" | measurement ↔ row model, recompute ledger lines, drag a length onto a row, inline edit, change banner with Undo | both | yes |
| 5 — Pro layer | full keyboard sheet with live keys, multi-select, isolate (Ctrl+click eye), overlay opacity / line width controls, legend card on PDF export, history | frontend | yes |
| 6 — Look | token pass after the founder's decision on light vs dark chrome | frontend | yes |

Paid runs: none planned. Candidates that would need one, each asked for separately with purpose and cost (≈ €2–4 per project, ≈ €15 per corpus pass): Vision legend reading on raster-only legends; a fresh read of an out-of-sample project to measure T2/T3 after waves 1–3.

Worker capacity: 4–5 in parallel at most (v2 ran 11, which cost coordination); one or two backend tracks and one frontend track per wave.

---

## 8. Risks and honest limits

- **Raster-only PDFs** (flattened re-exports such as objektas_a/b) blind the vector and text lanes: zones, legends and tables then need the user's box plus Vision. The user-marks-the-legend path is the product in that case, not a fallback.
- **Black-only symbols** depend on the raster matcher, whose accuracy at scale is unmeasured; T4 is checked on the corpus with the existing eye-verified counts before the feature is called done.
- **Vector room tool in the viewer** changes polygons where today's raster fill was used; the raster path stays for sheets with no wall solid, and every change goes through the review-before-create step.
- **The one-workspace change touches the most shared files** (InteriorWorkspace, TakeoffViewer, WorkspanePanel); it is sequenced first and alone so later waves build on a stable frame.
- **Playwright cannot drive file dialogs** in competitor apps or ours; uploads in verification steps remain manual.
- **Scope creep** — Caddie-style agents, 3D, collaboration views, assemblies-first pricing are explicitly parked.

---

## 9. Decisions (founder, 2026-10-18)

1. **One workspace, four steps as views of it — yes.**
2. **Overlay vocabulary (solid read / dashed estimated / red error only; neutral zone fills, room type in the label) — yes.**
3. **Legend marking: the app suggests the legend zone, the user confirms or redraws.** Guiding rule from the founder: the user does as little by hand as possible — every reading starts from a proposal.
4. **Wave order — manager's call:** wave 1 = workspace frame and click model (frontend) with the sheet-zones backend track started in parallel (no UI dependency), so legends (wave 2) land on a stable frame without waiting.
5. **Pro layer and multi-user — not decided yet.** Built so that the pro layer can be switched on later; nothing in waves 1–4 depends on it.
6. **Manager's call on the small ones:** the re-read banner becomes a one-line chip with the list behind a click; 14 px minimum for interface text (12 px only for metadata); one verb for outline fixes — „Taisyti kontūrą"; the assumptions button is „Prielaidos".

Wave 0 starts immediately; wave 1 gets an implementation plan (`docs/superpowers/plans/`) reviewed before any worker touches code. Programme doc: `docs/superpowers/plans/2026-10-18-pathon-v3-program.md`.
