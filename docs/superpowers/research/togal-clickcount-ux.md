# Togal.ai Click-to-Count & PDF Interaction UX — Deep Research

**Date:** 2026-04-27 — Researched live via WebSearch + WebFetch on togal.ai, help.togal.ai. Companion to `/Users/ignasgaldikas/samatu-ai/docs/superpowers/research/togal-ux-patterns.md`.

Direct-evidence statements cite a URL. Inferences are prefixed with **Inferred:**. Where sources are silent, this is stated.

---

## 1. Click-to-Count Workflow Visualization

Togal exposes counting through **two distinct entry paths** with different visual feedback:

**Path A — Manual count tool (keyboard `K`).** User selects a Count Classification first, presses K, then clicks each symbol one-by-one. The classification's **shape + color stamps onto the canvas at every click** (shape and color are configurable per-classification in its editor). If user clicks before assigning a classification, points are placed unclassified and must be batch-assigned via Shift-select + right-click → "Assign Classification" ([blog: Areas, Lines, Counts](https://www.togal.ai/blog/how-to-draw-areas-lines-counts), [help: Count Classifications](https://help.togal.ai/how-to-create-draw-edit-count-classifications)). No loading state — purely client-side stamping. Running totals update real-time in the **Quantities Panel (top-right)** ([blog: Quantities Panel](https://www.togal.ai/blog/how-to-set-project-quantities-using-the-quantities-panel-in-togal-ai)).

**Path B — AI Image Search (find-similar).** User opens magnifying-glass on left toolbar, picks "image", **draws a bbox** around an example, clicks "Search". Togal scans the **current sheet only** ("scan and find this object for us across this individual sheet" — [help: Onboarding](https://help.togal.ai/onboarding)). Matches appear as canvas highlights. If symbol contains adjacent text (a tag like "B-3"), Togal auto-extracts it and offers a **filter chip** ([help: AI Image Search](https://help.togal.ai/ai-image-search)). User clicks "Convert" → assigns matches to a new or existing Count Classification, at which point the shape/color stamps onto every match. Search history persists across the project.

**Dismissing bad matches.** Pre-Convert: "you can **left click on the text to deselect it** from the total count on the page" ([help: Text Search](https://help.togal.ai/text-search)) — exact phrasing for text search; inferred-by-symmetry for image. Post-Convert: deletion of a count point triggers a **confirmation pop-up** ("Added a confirmation pop-up when deleting markup objects" — [release notes Jan 25, 2025](https://help.togal.ai/release-notes-january-25-2025)). **Inferred:** no "review N matches before commit" modal — matches go straight onto the canvas as live, deletable items; the deselect-while-reviewing pattern *is* the review step.

---

## 2. Symbol Calibration UX

Togal uses **draw-a-bounding-box-around-one-example**, not click-once-and-find. Confirmed: "zoom in and draw a box around the symbol you want to find (such as a window tag), then click Search. Even if you select one symbol, Togal's AI is able to recognize other equivalent symbols across the sheet" ([help: AI Image Search](https://help.togal.ai/ai-image-search)). Bbox is the calibration — Togal does **not** require multiple positive examples, and **no negative-example UI is documented**.

A **Pattern Search** mode exists alongside Image and Text search ([togal.ai/features](https://www.togal.ai/features)). **Inferred:** pattern search uses a similar bbox-then-find flow tuned for repeating geometric patterns rather than labeled symbols; no public doc differentiates the UI.

The **Auto-Classify** feature is unrelated to symbol counting — it operates on already-detected *areas* (rooms): select area, right-click, "Auto-Classify", and Togal suggests a room type from its 100M+ classified-drawing model ([blog: Auto-Classify](https://www.togal.ai/blog/how-to-auto-classify-areas-using-the-automatic-classification-feature-of-togal-ai)). It does **not** auto-find symbols. The "how-to-leverage-the-export-tool" doc is about export config, not calibration ([help: Export](https://help.togal.ai/how-to-leverage-the-export-tool-inside-togal)).

---

## 3. Legend Reading

**No public documentation states Togal auto-reads the drawing legend page** to pre-populate symbol templates. All searches across help.togal.ai, blog posts, and release notes returned only user-initiated workflows: user draws bbox, types search term, creates classification.

The closest feature is post-search **text auto-extraction**: when image-searching a symbol with adjacent text (tag "W-1"), Togal OCRs that text and surfaces it as a filter ([help: AI Image Search](https://help.togal.ai/ai-image-search)). This is on-demand per-search, not pre-populated.

**Inferred:** Togal's calibration philosophy is fully user-click-to-teach, with AI doing similarity matching from one example. **No evidence found** for legend-page parsing despite three targeted searches; if it exists, it is undocumented publicly.

---

## 4. Match Review UI

Match review happens **on the canvas, not in a thumbnail grid**:

1. Search returns highlights on the current sheet ([help: Onboarding](https://help.togal.ai/onboarding)).
2. User can apply text filters auto-extracted from symbol-adjacent OCR ([help: AI Image Search](https://help.togal.ai/ai-image-search)).
3. User left-clicks any individual highlight to **deselect/exclude** it from conversion ([help: Text Search](https://help.togal.ai/text-search) — direct for text; inferred-by-symmetry for image).
4. User clicks "Convert" → matches become permanent count points with classification's shape/color stamp.
5. Post-Convert per-instance deletion triggers a confirmation pop-up ([release notes Jan 25, 2025](https://help.togal.ai/release-notes-january-25-2025)).

The classification-assignment dropdown in Convert mode is **searchable and filterable** since Jan 2025 — matters at 200+ classifications. **No "select all wrong / batch delete" UI is documented**; review is click-by-click on the canvas pre-Convert. The Jan 2025 release also added **rotation support** for Count classifications (rectangle shape only) — for symbols at multiple orientations.

---

## 5. Counts Panel

The **Quantities Panel** sits **top-right**, toggled via a "Quantities" button ([blog: Quantities Panel](https://www.togal.ai/blog/how-to-set-project-quantities-using-the-quantities-panel-in-togal-ai)):

- Filters at top: **Area / Line / Count / All** tabs.
- Folder → Classification → Item hierarchy with expand/collapse arrows.
- Each row shows shape icon, color, running total.
- Subfolders supported ([release notes Jan 25, 2025](https://help.togal.ai/release-notes-january-25-2025)).

Counts are grouped by **classification**, which typically maps 1:1 to symbol type. Custom Item Naming lets each instance have a unique name (added 2025 — [blog: 2025 Roundup](https://www.togal.ai/blog/2025-features-roundup)).

**Export:** two modes — "Screen View" (mirrors the panel hierarchy) and "Full Export" (raw flat data). Counts now export with **shape icons embedded in the spreadsheet** ([blog: 2025 Roundup](https://www.togal.ai/blog/2025-features-roundup)). Up to 3 grouping levels and scope filtering ([help: Export Tool](https://help.togal.ai/how-to-leverage-the-export-tool-inside-togal)). **Inferred:** to export only counts, filter classification type to "Count" and select count columns.

---

## 6. Page Navigation While Counting

**Togal counts per-sheet, not cross-project.** Load-bearing limitation. Direct evidence: Image Search "will go ahead and scan and find this object for us across this individual sheet" ([help: Onboarding](https://help.togal.ai/onboarding)). Prior research catalog flagged this as **AP03**, with peer-reviewed and competitor-comparison sources confirming Togal cannot cross-reference between sheets.

Practical consequence: counting outlets across 20 pages = 20 image-searches (or 20 manual K-click sessions). The Quantities Panel **aggregates totals across all pages** for a classification, but the **search action is per-sheet**. A v2.0.6 update added a "Drawing Navigator" with quantity-panel display ([release notes March 11, 2025](https://help.togal.ai/release-notes-march-3rd-2025)) but did not change the per-sheet constraint.

**Inferred** workflow: open page 1, image search, Convert to classification, switch page, image search again targeting **the same classification** (so totals accumulate). Search history is project-scoped, easing re-runs. **No auto-paginate "run on all pages" button is documented**, despite user requests visible across G2/SourceForge snippets (G2 fetch returned 403).

---

## Implications for our SymbolCounter

Current `frontend/src/components/project/SymbolCounter.jsx` — single click stamps a 5%-of-image template, fires one backend call, draws colored confidence dots, no classification grouping, no cross-page, no per-match deletion, no convert-to-line-item beyond a single "Įtraukti į pasiūlymą" button. Sprint 3 changes:

- **Replace single-click template with bbox calibration.** Drag-to-draw rectangle replaces the click-target overlay. Backend `/v9/symbols/count-by-template` already accepts `template_size_pct` — let user define the box instead of fixing 0.05. Keep preset-type buttons as fast path.

- **Make matches deletable per-instance.** Today the Konva dots are display-only (`pointerEvents: none`). Activate clicks → confirmation pop-up ("Pašalinti rastą simbolį?") → splice from `matches.matches`. Mirrors Togal's click-to-deselect + Jan-2025 confirmation pattern.

- **Introduce Count Classifications, not single-shot results.** Today each search overwrites `state.matches`. Refactor: each completed search becomes a named classification (e.g., "Rozetė — 230V" with shape/color) appended to a `classifications[]` list. Multiple searches stack with distinct shapes/colors. Our existing `PRESET_TYPES` already implies this model.

- **Move running counts into a Pozicijos-style sidebar.** Today "Rasta: 32" appears in the same toolbar that armed the search — fine for demo, wrong for serial counting. Mirror Togal: top-right Quantities Panel grouping `Klasifikacija → Kiekis` with shape icon + color + count + page-source. Reuse `PositionsPanel.jsx` shell.

- **Add cross-page accumulation as a deliberate differentiator.** Our Vision pipeline already ingests multi-page PDFs. Backend can run the same template across all pages on opt-in ("Skaičiuoti visuose puslapiuose"). Display per-page breakdown ("Iš viso: 47 — p.3: 12, p.5: 18, p.7: 17"). Directly addresses Togal's **AP03** weakness — marketable, not table stakes.

- **Adjacent-text auto-filter for tagged symbols.** When user's bbox covers a tagged symbol, backend OCRs and surfaces filter chips ("rodyti tik W-3"). Small addition to v9 endpoint returning per-match OCR text. High value for LT door/window schedules.

- **Confidence-tier pre-commit selector.** Currently we render high/medium/low dots simultaneously. Add slider: "Įtraukti tik aiškius / aiškius+galimus / visus", default high+medium. Review step becomes click-bad-ones-to-remove rather than triaging three colors — matching Togal's simplicity.

---

**Sources unconfirmable:** (a) any auto-legend-reading — three searches returned nothing; (b) detailed match-review batch UI — Togal docs gloss over it, YouTube transcripts not programmatically accessible; (c) G2 user pain-point quotes — page 403'd. Inferences marked.
