# Pathon viewer UI audit, the baseline for the merged product (2026-10-18)

> Worker W-PATHON-UI-AUDIT (Opus 5.5) for the Togal-v2 backend manager. Read-only, €0, no code changed.
> **Goal (founder addendum 2026-10-18):** not a restyle. Pathon merges its interior-finishing product with the best of Togal and Kreo, with the drawing viewer and the takeoff clicks at the core. This doc audits **our own** UI. Two other workers handle Togal and Kreo.
> **How it was measured.** Live app on localhost:5173/8000 (auth off), project `demo-objektas_h`, branch `togal-v2` @ 16a754c. Captured 2026-10-17 with Playwright at 1440×900, plus 1280×720 for screenshots 34–35. Only view state was touched: tools armed, panels opened, layers toggled, Esc. Nothing was saved. The versions list showed no new save after 18:35 the day before. On 2026-10-18 the dev servers were down and I did not start them. So the §5 steps that write data are traced in code, with file and line. They were not clicked.
> **Numbers.** Code counts come from a regex sweep of 52 files (18,760 lines) listed in §2. "Live" numbers come from `getComputedStyle` and `getBoundingClientRect` in the page.
> **Screenshots** (35 PNG): `/private/tmp/claude-501/-Users-ignasgaldikas-samatu-ai/0d85b50a-6fb4-4cb3-9ceb-0c98ac78a745/scratchpad/pathon-ui-audit/`. That is session scratch, and it was wiped once. A persistent copy sits in `.playwright-mcp/pathon-ui-audit/` in the repo, which is gitignored.

## 0. Summary

The viewer works; it was browser-verified end to end on 2026-10-17. It looks childish and outdated for measurable reasons:

1. **The type is tiny and comes in many sizes.** The default viewer screen shows 149 text elements in 12 distinct sizes. 91 % of them are 12 px or smaller, and 4.7 % are 16 px or larger. The body base is 13 px. Chips are 8–9 px. Rimo §5 asks for at least 16 px.
2. **Colour is used like a toy box.** The chrome alone shows 5 saturated hue families. The drawing adds up to 6 more. In scope there are 47 distinct hex literals and 102 live Tailwind palette classes. The theme promises "ONE muted evergreen accent".
3. **Meaning rides on colour alone, and the colours are overloaded.** Dashed lines carry 10+ meanings. Red means both "selected" and "error". Room-type zone colours have no legend. 6 of the 9 zone hues fall below 3:1 against the white sheet.
4. **Leftovers from the dark theme ruin contrast.** The "IŠ EKSPLIKACIJOS" chip is blue-300 on blue-500/15, which is **1.47:1** at 9 px, and it appears 11 times on the default screen. Muted text is 4.25:1. Unit text is 2.54:1.
5. **The toolbar overflows.** It holds 26 controls, or 31 with a room focused, in a 36 px bar. 43 % is hidden behind horizontal scroll at 1440 px, and 54 % with a room focused. The room tools are appended off-screen. Labels wrap, which makes some buttons 45 px tall in a 36 px bar. 83 % of the visible clickable elements are under 44 px.
6. **The type reads like a developer tool.** 46 % of visible text is monospace. There are 22 uppercase tracked labels. Whole sentences are set in bold mono. Labels on the drawing use system-ui in some layers and Plex Mono in others.
7. **Notices pile up.** There are about 12 kinds of notice. The amber re-read banner pushes the step's main button below the fold. Tool instructions repeat 2–3 times. The Sąmata step shows four tinted boxes and zero rows above the fold.
8. **The clicks fight the user.** You cannot select a room by clicking it on the drawing; a plain click deselects. Room tools sit at the far end of a scrolled toolbar. Esc also drops the selected room. A measured length cannot go to the estimate. Merge, subtract and outline-edit saves have no "Atšaukti". §5 counts 4–7 actions for jobs that take 1–3 actions in a professional editor.

## 1. Screen inventory

| # | File | Shows | Observations |
|---|---|---|---|
| 01 | 01-projects-list.png | Projektai list (dashboard) | 13 cards in three equal columns, the generic AI layout. Mono breadcrumb „00 / PROJEKTAI“. Every card carries the same uppercase „PARUOŠTA“ badge, so it carries no information. Totals are mono with the narrow no-break space rendered as a full gap („14  473 €“). |
| 02 | 02-viewer-first-load-coachmark.png | Viewer, first open | The amber banner „Brėžinys perskaitytas iš naujo“ (66 px) pushes everything down. The coach card has a 10 px mono uppercase eyebrow and a 12.5 px body. The toolbar already shows a horizontal scrollbar. „Rasti panašius“ wraps to two lines. |
| 03 | 03-viewer-coachmark-step3.png | Coach step 3 „Redaguoti kontūrą“ | The toolbar was auto-scrolled sideways to reach the anchor; page navigation is cut at the left edge. The step explains a button that does not exist yet („Mygtukas atsiras pasirinkus patalpą“). |
| 04 | 04-viewer-default.png | Default viewer, nothing selected | The drawing canvas is 706×594 px, 32 % of the window. The right list shows 11 pastel chips at 1.47:1. The chrome holds 5 hue families. The step's main button is below the fold. |
| 05 | 05-viewer-scrolled-footer-cta.png | Page scrolled by 47 px | „Brėžinį peržiūrėjau — į patikrą“ and „Atgal“ appear only after the page scrolls, and the top bar scrolls away. |
| 06 | 06-viewer-room-focused.png | Room 01 picked in the list | A red ring with an endless 1.6 s pulse, plus a chip „Tambūras 4,5 m²“, while the list says 4,48: two number formats. The ring and chip cover the drawing's own labels. |
| 07 | 07-viewer-toolbar-scrolled-room-tools.png | Toolbar scrolled to the room tools | Redaguoti kontūrą / Padalyti / Sujungti / Atimti / Taisyti kontūrą are appended at the end of the bar. Two labels wrap, making those buttons 45 px tall in a 36 px bar with 8–9 px icons. „Redaguoti“ and „Taisyti kontūrą“ sit side by side. |
| 08 | 08-viewer-zones-coloured.png | „Nuspalvinti patalpų zonas“ on | Tailwind-500 hues by room type at 16 % fill: blue, pink, green, cyan, violet, amber, grey. Nothing on screen says what the colours mean. |
| 09 | 09-viewer-zones-fitpage.png | Zones at fit-page (68 %) | The A4 sheet is small inside the column, and the zones read like a colouring map. |
| 10 | 10-viewer-walls-layer.png | „Sienų sluoksnis“ on | Grey wall fill, evergreen dashed and solid outlines, violet opening bars. The 10 px system-ui labels collide with each other („D 0,87 m D 0,87 m“) and with the drawing's text. The legend says „vektorinio PDF“. |
| 11 | 11-tool-distance-armed-snap.png | Atstumas armed, hovering a wall corner | An instruction pill sits on the drawing and the status bar repeats it. Orange snap square. The dark readout „Ilgis: 0,00 m“ is in system-ui. |
| 12 | 12-tool-count-armed.png | Kiekis armed | The count panel covers the instruction pill, cutting the text („…ėkite elementus“). The status bar says „pasirinkite tipą dešinėje“ but the panel is on the left. „Durys (AI)“ with an amber „2 AI“ chip. |
| 13 | 13-tool-calibrate-armed.png | Mastelis armed | The toolbar jumped sideways and the green button is out of view. The same pill plus status bar duplication. |
| 14 | 14-tool-find-similar-armed.png | Rasti panašius armed | The panel overlaps the sheet list by about 76 px (offset 156 against a 232 px list). A second pill at the bottom collides with the walls legend. The instruction appears three times. |
| 15 | 15-tool-lasso-armed.png | Laso armed | The pill is wider than the canvas and spills over the sheet list. The status-bar sentence runs under the right panel. |
| 16 | 16-masteliai-popover.png | Masteliai dock | 8 sheet cards „1:115 patvirtintas“, each with Patikrinti/Taisyti, so 16 buttons. The dock runs below the status bar. Esc does not close it. |
| 17 | 17-istorija-panel.png | Istorija | A sensible empty state with an 11 px footnote. Esc does not close it. |
| 18 | 18-palyginti-leidimus-popover.png | Palyginti leidimus | One stored edition, upload and trash buttons. Clear copy. |
| 19 | 19-palyginti-leidimus-overlay-skirtumas.png | An edition overlaid (view state only) | Segmented control, swatches, slider and an alignment sentence. Sheet 1 shows no visible difference (the edition is synthetic), so I did not see the overlay colours. |
| 20 | 20-shortcuts-guide.png | „?“ guide | A right-side sheet over a near-black scrim, the only dark surface on the step. Key chips are fine. |
| 21 | 21-right-panel-kiekiai.png | Kiekiai tab | Coloured dots are the only per-row signal. The footer Σ adds up unlike work types („Σ 1 559,67 m²“). |
| 22 | 22-right-panel-pokalbis.png | Pokalbis tab | The calmest panel. Rimo §4 wants chat out of the main tabs. |
| 23 | 23-versijos-panel.png | Versijos | Mono timestamps, an uppercase „DABARTINĖ“ chip, and two stacked outlined buttons on every row: a wall of identical buttons. |
| 24 | 24-patikra-questions.png | Patikra question list | A dark slate header band in a light app. Amber „?“ icons. The check viewer shows green, red and violet chips. Its status bar says „Spėjamas mastelis 1:115“ while the main viewer says „Patvirtintas“ (side finding A). |
| 25 | 25-room-sheet-01.png | Room sheet 01 | The most grown-up screen: 13–16 px, 2 px corners, evidence crops. But the crops are 105×70 px, „Teisinga“/„Pataisyti“ repeat for each of 6 facts, and values are bold mono. |
| 26 | 26-room-sheet-01-fullpage.png | Room sheet, full page (1945 px) | The drawing pane is not sticky, so it scrolls away from the facts it backs. „Viskas teisinga — kitas kambarys“ sits about 1,000 px down. |
| 27 | 27-samata-rows.png | Sąmata, top | The amber banner again, then red „Įspėjimai (1)“, amber „Verta patikrinti (6)“ and grey „Pastabos (3)“. Zero rows above the fold. The pill counts both levels as „7 įspėjimai“. |
| 28 | 28-samata-rows-scrolled.png | Sąmata rows | 43 px rows with 16 px text, which is good. Three icons per row (Σ, pencil, red trash), so 117 red bins. The price dots are not explained. |
| 29 | 29-samata-export-dropdown.png | Eksportuoti | Three items with helper lines. Fine. |
| 30 | 30-samata-row-detail.png | „Kaip suskaičiuota“ panel | A slide-over without a scrim. 10–11 px grey formula lines. Uppercase mono eyebrows. |
| 31–32 | 31-rinkiniai.png, 32-rinkiniai-expanded.png | Rinkiniai | A sparse page in a different container width (264–1224 px) from Projektai (200–1288 px) and Kainynai (332–1164 px). Boxed tables. |
| 33 | 33-price-lists.png | Kainynai | A rounder card than the 2 px theme. The copy says „po naujos analizės“, a banned word. |
| 34 | 34-viewer-1280x720.png | Viewer at 1280×720 | The toolbar shows nothing past „Žymėti“: 49 % hidden. Names are cut short („Sv…“). The canvas is 594×458 px, 29.5 % of the window. The main button is 91 px below the fold. |
| 35 | 35-outline-edit-vertex-handles.png | Redaguoti kontūrą, view state, then Esc (1280×720) | „Išsaugoti kontūrą (01)“ is clipped vertically. The red focus ring, the amber edit ring, the dark readout and the white chip all stack on one spot. The instruction appears in both the pill and the status bar. |

## 2. Token audit

### 2.1 Theme (`frontend/src/index.css`, `tailwind.config.js`)
- The tokens exist: Nordic Slate in `:root` (`--primary` #192830, `--accent-2` #3F665C, `--radius: 2px`), `--viewer-chrome-*`, `--conf-high/med/low`, `--source-*`, `--revision-*`. The app body is **13 px** (`body { font-size: 13px }`).
- **Five font families** are requested from Google Fonts: Sora, Hanken Grotesk, JetBrains Mono, IBM Plex Sans and IBM Plex Mono. Only Plex Sans and Mono load in the app (3 weights each). SVG labels on the drawing use `system-ui` (`MeasureLayer`, `DrawingGeometryLayer`, `OutlineEdit/ToolLayer`) or Plex Mono (`CheckLayer`, `SymbolSearchLayer`).
- **Radius scale is broken.** The config sets `lg = var(--radius)` = 2 px, `md = calc(2px-2px)` = 0, `sm = calc(2px-4px)` = clamped to 0, and leaves plain `rounded` at Tailwind's default 4 px. Live: top-bar buttons 4 px, toolbar buttons 2 px, warning pill 0 px, chips 4 px.
- **Stale blocks.** About 270 lines of landing CSS ("DARK GRAPHITE … Orange-on-graphite") still sit in the app stylesheet. The `.dark` block says "the app is dark by default now", which is false and inert. 28 `dark:` classes in scope are inert as well.
- **Three confidence colour schemes run side by side:**
  - `lib/confidence.js` → `.dot-high/med/low` on the `--conf-*` tokens;
  - `lib/roomZones.js` → hard-coded `#16a34a / #d97706 / #dc2626 / #9ca3af`;
  - `pages/InteriorProject.jsx` `ConfidenceDot` → `bg-green-500 / bg-yellow-400 / bg-red-500` with 🟢🟡🔴 in the tooltip.
- **One token is misused.** `--source-ai` (slate, "AI inferred") colours the wet-room chip „DRĖGNA“.
- **Tokens are bypassed.** The viewer uses 266 arbitrary `[hsl(var(--viewer-chrome…))]` classes, although `tailwind.config.js` already defines `bg-viewer-chrome` and friends. On top of that come 192 inline `style={{…}}` objects. There is no single place to restyle from.

### 2.2 Code counts, by group (comments stripped)

| group | files | lines | hex | rgb()/hsl() literal | named colours | palette classes | white/black | `[hsl(var())]` | distinct font sizes (px) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| viewer (`components/viewer/**/*.jsx`) | 27 | 6966 | 76 | 1 | 0 | 11 | 13 | 134 | 11: 9·9.5·10·10.5·11·11.5·12·12.5·13·14·16 |
| project (WorkspacePanel, InteriorWorkspace, ProjectMainView, RowDetailPanel, ExportDropdown, `pages/InteriorProject.jsx`) | 6 | 6041 | 0 | 0 | 6 | 115 | 0 | 0 | 13: 8·9·10·11·12·13·14·15·16·17·18·20·30 |
| overlay colour sources (RoomZoneLayer, lib/roomZones, lib/measurements, lib/pageTypes) | 4 | 1027 | 73 | 0 | 2 | 0 | 0 | 0 | 2: 10·11 |
| roomsheet/*.jsx | 10 | 2415 | 7 | 1 | 0 | 0 | 30 | 83 | 7: 11–17 |
| Patikra (PatikraQuestions, PatikraEntry, RoomSheet, QuestionBodies) | 4 | 1811 | 0 | 0 | 0 | 0 | 8 | 49 | 8: 12–18, 20 |
| index.css | 1 | 500 | 4 | 12 | 0 | 0 | 0 | 0 | 10·13·150 (landing) |
| **total** | **52** | **18760** | **160** (47 distinct) | 14 | 8 | **126** (102 live + 24 inert `dark:`) | 51 | **266** | **18** |

Notes on the totals:
- **Palette families:** amber, red, blue, emerald, green, slate, yellow. Nearly all of them sit in ProjectMainView (53) and InteriorProject (53).
- **Radii:** `rounded` (4 px) ×81, `rounded-[2px]` ×111, `rounded-lg` (2 px) ×11, `rounded-xl` (12 px) ×10, `rounded-md` (0) ×6, `rounded-sm` (0) ×7, `rounded-full` ×26, 1 px ×2, 3 px ×1, plus SVG `rx` 2/3/4/5/6/8. That is **7 effective radii**.
- **Shadows:** `shadow-lg` ×7, `md` ×7, `sm` ×4, `xl` ×2, `2xl` ×1, inline ×3, arbitrary ×1. All use Tailwind's default black.
- **z-index:** 10, 16, 20, 30 (×9), 40, 50, 60, 61, plus inline 2. **9 levels with no scale.** Panels at z-30 collide (§4.6).
- **Icons:** lucide-react only, 84 distinct icons. Size classes: 12 px ×31, 14 px ×60, 16 px ×103, 20 px ×8, 48 px ×1. Live in the toolbar, flex squeezes icons to 8, 9 and 11 px.
- **Emoji in UI strings:**
  - in scope: 🟢🟡🔴 (InteriorProject confidence tooltip), plus ✓ ✕ as text symbols;
  - app-wide: `lt.json` „📐 Apvedinėjamas kambarys“, „🟢 Plotas paimtas…“, „🔍 Ieškoti“, „✨ Pathon“, „✨ Paleisti Pathon“, „🔒“; also ConfidenceBadge, RoomCard, CountReviewPanel, MagicWandTool „👆“, and the Annotator toolbar. I did not check whether each string is still reachable.
- **Toasts:** 59 calls in scope (24 error, 19 success, 7 info, 5 warning, 4 plain).

### 2.3 Per-file table

| file | hex | palette | white/black | `[hsl(var())]` | font px | radii (px×n) | shadows | z | icons | emoji/symbols |
|---|---:|---:|---:|---:|---|---|---|---|---:|---|
| viewer/CalibrateDialog.jsx | 0 | 6 | 1 | 0 | 12·14 | 0×2 4×1 12×1 | 2xl×1 | 50×1 | 3 | – |
| viewer/CalloutLayer.jsx | 0 | 0 | 0 | 4 | 11 | 1px×1 2px×1 | md×1 | 40×1 | 0 | – |
| viewer/CheckLayer.jsx | 17 | 0 | 0 | 0 | 13 | svg-rx2×3 | – | – | 0 | – |
| viewer/CountLegendPanel.jsx | 0 | 0 | 0 | 2 | 10·11·12·14·16 | 2×1 4×6 0×1 | – | – | 0 | – |
| viewer/DetectRunButton.jsx | 0 | 0 | 2 | 3 | 11·12·13 | 2px×4 | – | – | 2 | – |
| viewer/DetectRunProgress.jsx | 0 | 0 | 0 | 5 | 11·12 | 2px×2 | md×2 | – | 3 | ✓ ✕ |
| viewer/DrawingGeometryLayer.jsx | 3 | 0 | 0 | 0 | 10 | – | – | – | 0 | – |
| viewer/HistoryPanel.jsx | 0 | 0 | 0 | 0 | 10.5·11·12·13 | 2px×2 | lg×1 | – | 3 | – |
| viewer/MeasureContextMenu.jsx | 6 | 0 | 0 | 0 | 11·14 | 2px×3 0×1 full×2 | – | – | 6 | – |
| viewer/MeasureLayer.jsx | 28 | 0 | 0 | 0 | 11·12 | svg-rx3/6/8 | – | – | 0 | – |
| viewer/OutlineEditLayer.jsx | 8 | 0 | 0 | 0 | 11 | svg-rx3 | – | – | 0 | – |
| viewer/OutlineToolButtons.jsx | 0 | 0 | 0 | 4 | 11 | 4×2 | – | – | 3 | – |
| viewer/OutlineToolLayer.jsx | 10 | 0 | 0 | 0 | 11 | svg-rx3 | – | – | 0 | – |
| viewer/OutlineToolPanel.jsx | 0 | 0 | 0 | 0 | 12 | 2px×6 | md×1 | 30×1 | 6 | – |
| viewer/PageOverlayHost.jsx | 0 | 2 | 1 | 3 | – | full×1 | sm×1 | – | 1 | – |
| viewer/RevisionCompareControl.jsx | 0 | 0 | 2 | 7 | 11·12·13 | 1px×1 2px×4 | – | – | 4 | – |
| viewer/RevisionOverlayLayer.jsx | 0 | 0 | 0 | 0 | – | – | – | – | 0 | – |
| viewer/ScaleCheckCard.jsx | 0 | 0 | 0 | 0 | 11·11.5·12·13·14 | 2px×2 | lg×1 | – | 1 | – |
| viewer/ScaleOverviewPanel.jsx | 0 | 0 | 0 | 2 | 10.5·11·11.5·12·13 | 2px×4 full×1 | lg×1 md×1 | 30×1 | 5 | – |
| viewer/SheetRail.jsx | 0 | 0 | 3 | 37 | 9·9.5·10·10.5·11·11.5·12 | 2px×7 full×1 | – | 10×1 | 6 | – |
| viewer/ShortcutsGuide.jsx | 0 | 0 | 0 | 0 | 11·11.5·12·12.5 | 2px×2 | – | – | 1 | – |
| viewer/SymbolReviewPanel.jsx | 0 | 0 | 2 | 9 | 10·11·12·14 | 2×1 4×8 full×3 | lg×1 | – | 4 | ✕ |
| viewer/SymbolSearchLayer.jsx | 1 | 0 | 0 | 0 | 9.5 | svg-rx2 | – | – | 0 | – |
| viewer/TakeoffViewer.jsx | 3 | 1 | 2 | 58 | 10·11·12·14 | 2px×1 4×12 0×1 full×1 | lg×1 md×2 sm×1 | 30×6 40×1 | 27 | – |
| viewer/ViewerCoachMarks.jsx | 0 | 0 | 0 | 0 | 10·12·12.5·14 | 2px×4 3px×1 | xl×1 | 60×1 61×1 | 1 | – |
| viewer/quantities/QuantitiesPanel.jsx | 0 | 0 | 0 | 0 | 10·11·12 | 4×2 | – | – | 1 | – |
| viewer/quantities/QuantityRows.jsx | 0 | 2 | 0 | 0 | 9·10·10.5·11·11.5·12 | 4×2 | arbitrary×1 | – | 5 | – |
| project/WorkspacePanel.jsx | 0 | 5 | 0 | 0 | 8·9·10·11·12 | 4×13 full×3 | inline×1 | inline 2 | 9 | – |
| project/InteriorWorkspace.jsx | 0 | 4 | 0 | 0 | 12·14 | 2×1 4×1 full×1 | – | 30×1 | 2 | – |
| project/ProjectMainView.jsx | 0 | 53 | 0 | 0 | 9·10·11·12·13·14·15·16·18 | 0×4 2×1 4×17 12×3 full×1 | lg×1 sm×1 | 10×1 50×1 | 15 | – |
| project/RowDetailPanel.jsx | 0 | 0 | 0 | 0 | 10·11·12·14·20 | 4×1 0×2 | inline×1 | 10×1 50×1 | 3 | – |
| project/ExportDropdown.jsx | 0 | 0 | 0 | 0 | 11·14 | 2×2 | lg×1 | 20×1 | 6 | – |
| pages/InteriorProject.jsx (top bar, step bar) | 0 | 53 | 0 | 0 | 10·11·12·13·14·15·16·17·18·30 | 2×5 4×16 12×6 full×6 inline 3 | xl×1 | 40×1 | 28 | 🔴 🟡 🟢 |
| project/RoomZoneLayer.jsx | 10 | 0 | 0 | 0 | 10·11 | svg-rx3/4/5 | – | 16×2 | 0 | – |
| lib/roomZones.js | 31 | 0 | 0 | 0 | – | – | – | – | 0 | – |
| lib/measurements.js | 16 | 0 | 0 | 0 | – | – | – | – | 0 | – |
| lib/pageTypes.js | 16 | 0 | 0 | 0 | – | – | – | – | 14 | – |
| roomsheet/EvidenceCrop.jsx | 1 | 0 | 0 | 4 | 12·13·14·16 | 2px×6 | inline×1 | – | 3 | – |
| roomsheet/FactRow.jsx | 0 | 0 | 5 | 28 | 11·13·14·15·16 | 2px×7 | – | – | 7 | – |
| roomsheet/FixConsequence.jsx | 0 | 0 | 0 | 3 | 13·14 | 2px×2 | – | – | 1 | – |
| roomsheet/GeneralFactsPanel.jsx | 0 | 0 | 3 | 16 | 12·13·14·15·16·17 | 2px×7 0×1 | – | – | 1 | ✓ |
| roomsheet/QuantityLine.jsx | 0 | 0 | 1 | 7 | 13·14·15·16 | 2px×3 | – | – | 4 | – |
| roomsheet/RoomDrawingPane.jsx | 6 | 0 | 8 | 10 | 13·14·16 | 2px×6 | sm×1 | – | 6 | – |
| roomsheet/RoomPlanPane.jsx | 0 | 0 | 1 | 3 | 11·12·13·14·16 | 2px×5 full×5 | – | – | 1 | – |
| roomsheet/RoomScopeSwitch.jsx | 0 | 0 | 2 | 6 | 11·13·14·15 | 2px×2 0×1 | – | – | 0 | ✓ |
| roomsheet/RoomSheetStrip.jsx | 0 | 0 | 9 | 2 | 14·17 | 2px×1 full×1 | – | – | 3 | – |
| roomsheet/YourRowsPanel.jsx | 0 | 0 | 1 | 4 | 12·13·14·15·16·17 | 2px×2 | – | – | 2 | – |
| pages/PatikraQuestions.jsx | 0 | 0 | 6 | 13 | 12·13·14·15·16·18·20 | 2px×8 | – | – | 6 | – |
| pages/PatikraEntry.jsx | 0 | 0 | 0 | 0 | – | – | – | – | 0 | – |
| pages/RoomSheet.jsx | 0 | 0 | 1 | 9 | 13·14·15·16·17 | 2px×10 | – | – | 3 | – |
| questions/QuestionBodies.jsx | 0 | 0 | 1 | 27 | 13·14·15·16 | 2px×10 | – | – | 2 | – |
| index.css | 4 | 0 | 0 | 0 | 10·13·150 | – | – | – | 0 | – |

### 2.4 Live measurements

| metric | viewer, default (1440×900) | room sheet 01 (1440×900) | viewer (1280×720) |
|---|---|---|---|
| visible text elements | 149 | 90 | – |
| distinct font sizes | **12** (9, 9.5, 10, 10.5, 11, 11.5, 12, 13, 14, 15, 16, 18) | 8 (10–17) | – |
| text ≤ 12 px / ≥ 16 px | **135 (91 %) / 7 (4.7 %)** | 27 (30 %) / 10 (11 %) | – |
| monospace / uppercase text | 68 (46 %) / 22 | 28 (31 %) / 6 | – |
| visible clickable elements / under 44 px / under 24 px | 93 / **77 (83 %)** / 27 | 51 / 31 / – | – |
| toolbar content in its box | 1621 px in 930 (2029 with a room focused) | – | 1614 px in 818 |
| drawing canvas | 706×594 px = **32.4 %** of the window | – | 594×458 px = 29.5 % |
| page height vs window | 947 / 900 (47 px of scroll; main button hidden) | 1945 / 900 | 811 / 720 (91 px) |
| saturated hue families in the chrome (drawing masked) | **5** (evergreen, blue, amber, yellow, red) | 3 | – |
| native `title` tooltips on the page | 281 (44 longer than 80 characters; toolbar median 49, max 135) | – | – |

### 2.5 Contrast (WCAG 2.x; text needs 4.5:1, graphics need 3:1)

| element | foreground / background | ratio | size | verdict |
|---|---|---:|---|---|
| Provenance chip „IŠ EKSPLIKACIJOS“ | #93c5fd / #dde9f9 | **1.47** | 9 px mono caps | fails |
| Units „m²“, „117 poz.“ (`muted-foreground/70`) | #9ca0a1 / #fafbf9 | 2.54 | 9–10 px | fails |
| Inactive step number | #74797b / #edeeec | 3.79 | 12 px | fails |
| Muted text: room nr, „PATALPOS“, „BE PVM“, „Eksportuoti matavimus“ | #74797b / #fafbf9 | 4.25 | 10–11 px | fails |
| Inactive tabs and steps, „INTERJERAS“, „Įsiminta“ | #74797b / #fff | 4.41 | 10–16 px | fails |
| Banner date | #a8653a / #fffbeb | 4.40 | 12 px | fails |
| Missing-rooms chip / search tag (white on conf-med) | #b45309 / #fef3c7, #fff / #9b6a08 | 4.51 / 4.71 | 11 / 9.5 px | borderline |
| Warning pill, status bar, rail chip | – | 5.07 / 5.16 / 7.64 | 11 / 11 / 9.5 px | pass, but tiny |
| Zone strokes on the white sheet | #f59e0b 2.15 · #22c55e 2.28 · #06b6d4 2.43 · #10b981 2.54 · #94a3b8 2.56 · #a78bfa 2.72 · #ec4899 3.53 · #3b82f6 3.68 · #64748b 4.76 | – | graphic | **6 of 9 fail 3:1** |
| Confidence dot colours on white | unknown #9ca3af 2.54 · med #d97706 3.19 · high #16a34a 3.30 · low #dc2626 4.83 | – | graphic | grey fails |

## 3. Overlay semantics inventory (what is drawn on the sheet)

| element | style now (code) | what it means | when shown | colour the only carrier? |
|---|---|---|---|---|
| Room focus ring (`RoomZoneLayer` simple mode) | `#dc2626` ring, r 16–44 px, 2.5 px; endless 1.6 s pulse | which room is selected or hovered | on focus or hover only; the drawing is clean at rest | no, but red also means "error" elsewhere |
| Room chip | white rect rx4 with a red or room-colour border; name 11 px bold `#1f2937`; area 10 px; confidence dot r4 | name, area, area confidence | while the room is focused or hovered | **yes**: the dot's only text is `<title>` „Ploto pasitikėjimas: high“ (English token, banned word) |
| Zone fills (fills mode, key U) | 9 hues by `paskirtis` (#10b981, #3b82f6, #f59e0b, #06b6d4, #a78bfa, #ec4899, #94a3b8, #64748b, #22c55e); fill 16 %, 30 % on hover, 34 % focused; stroke 1.5 / 2.5 / 3.5 px | room type | toggle on | **yes**, and there is no legend |
| Approximate geometry | dashed 6 4 (zones) or 4 3 (markers); chip text „· apytikslė vieta“ | outline made up from a box | fills mode | partly: the dash plus hover text |
| Tier-2 number markers | white circle r13, ink stroke, 11 px bold number | a room placed only by its printed label | fills mode | no |
| Missing-rooms chip | `#fef3c7` / `#fde68a` / `#b45309`, 11 px, top-left | rooms with no place on the plan | always, when any are missing | no; but it points to „Peržiūra“, which no longer exists (side finding D) |
| Walls layer (`DrawingGeometryLayer`) | walls `#475569` at 22 % fill / 70 % stroke; outlines `#2f6b4f` 1.5 px; **dashed = found automatically, solid = confirmed**; fill 4 % | what the program read from the PDF | toggle on (key S) | no; legend card at the bottom right |
| Opening bars | `#7c3aed` 5 px bar at 85 %; label „D 0,94 m“ / „L …“ 10 px system-ui, violet, no halo | door or window found in the wall, and its width | walls layer | partly (the D/L prefix), but labels collide |
| Measurement line or area | `m.color`, default `#2a6fb5` (pickable: Mėlyna, Žalia, Oranžinė, Raudona, Violetinė, Pilka); 2 px, 3 px `#1d4ed8` when selected; area fill 12 %; vertex dots r3 | the user's own measurement | always | colour is chosen by the user, so acceptable |
| Readout chip | `#1f2937` at 92 %, white 11 px **system-ui**, rx3 | value, or „nekalibruota“ | with each measurement or draft | no |
| Count markers | type colour (8-colour cycle) × shape (circle, square, diamond, check), r6 / r8; **hand-placed = filled, found by „Rasti panašius“ = hollow** | count item; hollow means unchecked | always | no (fill vs hollow), but the legend shows only while Kiekis is armed |
| Draft | `#2a6fb5` polyline; rubber band dashed 5 4; closing edge dashed 3 4 at 40 %; SVG „Baigti“ button **blue `#1d4ed8` rx6** next to white „Atšaukti“ | measurement in progress | tool armed | no; but the blue rounded button is off-theme |
| Calibration line | `#dc2626` dashed 5 4, red dots | the two clicks of „Mastelis“ | Mastelis armed | context makes it clear |
| Snap markers | `#ea580c` square (wall corner) or diamond (wall face), 2 px; `#16a34a` circle (own measurement) | what the click will land on | a measure or edit tool armed | no (shape plus a status-bar sentence) |
| Lasso | `#1d4ed8` dashed 5 4 at 6 % | selection area | Laso drag | no |
| „Rasti panašius“ candidates | amber (`--conf-med`) rect, 4 % fill, 22 % on hover; tag „n · 0,93“ 9.5 px mono, white on amber; source example evergreen | found symbol and its score | search open | **yes** (amber vs evergreen) |
| Sheet-link callouts | evergreen 2 px underline, **dashed = low confidence**, 10 % background | a reference to another sheet | sheets that have links (none in H) | style only |
| Edition overlay | server-painted PNG: evergreen = only in the new edition, clay = removed; opacity slider | drawing changes | an edition picked | **yes**; swatches only inside the popover |
| Outline edit (`OutlineEditLayer`) | amber `#b45309` ring; white vertex handles with an amber 2 px border; midpoints at 80 %; red when the outline crosses itself; orange snap; dark readout (system-ui), text `#fca5a5` when crossing | editing in progress | Redaguoti kontūrą | colour plus a text readout |
| Outline tools: split line, merge, subtract holes (`OutlineToolLayer`) | edit amber, „lieka“ evergreen `#2f6b4f`, the other part or neighbour slate `#64748b` **dashed until picked**, refused red, hole draft violet `#7c3aed`; chips 11 px system-ui | the split, merge and cut-out state | Padalyti / Sujungti / Atimti | mostly colour; the panel text explains it |
| Hole rings (cut-outs) | even-odd holes in the outline path (walls layer) | column or shaft removed from the outline | walls layer | shape |
| Check layer (Patikra): walls by source | read `#15803d`, borrowed `#b45309`, piece of outline `#64748b`, **missing `#dc2626` dashed 7 5**; chips white rx2 with a coloured border, 11 px **Plex Mono** | where each wall length came from | room check | **yes** for read / borrowed / outline (same stroke, colour only); legend present |
| Check layer: partition or imaginary line, proposal | `#1d4ed8` dashed 9 6 / 10 7 with a white casing; numbered room badges | boundary that is not a wall; the proposed split | room check | dash plus legend |
| Check layer: fact source rectangle, ringless room | amber `#d97706` dashed (solid when active); red double ring when the room has no outline | where a fact was read; no outline found | room check | colour plus state |
| Search hits | EmbedPDF default highlight | text search | search | not themed; not inspected |

**The same line style means many things.** Dashed means approximate, found automatically, missing length, draft, calibration, lasso, imaginary boundary, proposal, inactive evidence, neighbour not yet picked, and low-confidence link: **11 meanings**. Red means selected room, calibration, missing length, invalid outline, refused merge, no outline, delete on hover, and warnings. Amber or orange means snap, edit in progress, borrowed length, evidence box, found symbols, medium confidence, a count colour, and the kitchen zone. Green means high confidence, own-snap, read on the plan, confirmed outline, new edition, the primary button, a count colour, and the living-room and balcony zones. The legends that do exist differ by screen: the walls layer uses evergreen dashed/solid, Patikra uses green/amber/grey/red-dashed. So **none of this meaning survives a muted palette.** It needs one vocabulary: solid means read or confirmed, dashed means estimated (only that), red means error only, and selection is a neutral heavy outline plus a label. Each needs a sentence on hover and in a legend.

## 4. Chrome inventory

### 4.1 Toolbar (`TakeoffViewer.jsx` `Toolbar`, from line 175)
- **Order at rest:**
  - [sheet list] | **Perskaityti iš naujo** (filled evergreen) · Palyginti leidimus |
  - ‹ psl. 1 / 8 › | − 114 % + | fit width · fit page | zones · walls |
  - Žymėti · Laso · Atstumas · Plotas · Perimetras · Kiekis · Mastelis · Rasti panašius · Masteliai |
  - Istorija · ? | search | print · download.
- **Count:** 26 controls (12 with text, 13 icon only) plus 2 readouts and 7 separators. With a room focused, **Redaguoti kontūrą · Padalyti · Sujungti · Atimti · Taisyti kontūrą** are inserted before Istorija, making 31 controls and 17 labels.
- **Overflow:** `overflow-x-auto`. At 1440 px the visible part ends at about x=1003. **Everything from „Plotas“ on is hidden at rest**, and the room tools start at about x=1489. Clicking a far button scrolls the bar, so it jumps. Labels are `hidden lg:inline`, so they vanish below 1024 px.
- **Sizes:** buttons are 24×24 px (`p-1`). Wrapped labels make buttons 30–45 px tall in a 36 px bar, and their icons shrink to 8, 9 and 11 px while the rest are 14–16 px.
- **Help:** native `title` tooltips only, hover-only: 25 in the bar, up to 135 characters, slow, OS-styled.

### 4.2 Left sheet list (`SheetRail.jsx`, 232 px)
- Discipline groups have uppercase headers (10.5 px, 600) with counts.
- Each item is 97 px tall: a 60×85 thumbnail, a mono number, the sheet title in the PDF's own UPPERCASE at 11.5 px, and a 9.5 px chip with a type dot. The dots use 16 type colours from `lib/pageTypes.js`.
- Only 5 of 8 sheets fit. There is no collapse to a thin strip.

### 4.3 Right panel (`WorkspacePanel.jsx`, 400 px)
- 3 tabs at 12 px. Search, plus an eye-off toggle.
- Sections have uppercase 10 px headers with counts and m² totals.
- **Room rows are 30 px:** number 10 px mono, name 12 px, chips 9 px („sujungta į 04“, „+ 05“, „DRĖGNA“), area 11 px mono plus „m²“ 9 px, the provenance pill at 9 px mono caps, and a 16 px eye button.
- Kiekiai rows are about 28 px with 8 px dots.
- WorkspacePanel even has `fontSize: 8`.
- At 1280 px, names are cut short to „Sv…“.

### 4.4 Notices
On the Brėžinys step:
1. amber page banner (re-read);
2. free re-read banner;
3. red warning pill in the top bar;
4. coach cards (3 steps);
5. rounded-full instruction pill on the canvas;
6. the same instruction again in the status bar;
7. walls legend card;
8. count legend card;
9. „Rasti panašius“ panel and its second pill;
10. ScaleGateChip;
11. DetectRunProgress card;
12. missing-rooms chip;
13. toasts (59 calls).

On Sąmata there are three more tinted boxes (Įspėjimai, Verta patikrinti, Pastabos). Patikra has a dark slate header band. That makes **at least 12 visual kinds, in 4 tints and 3 shapes.**

### 4.5 Status bar, step bar, top bar
- **Status bar:** 24 px tall. Left side in 11 px mono: „psl. 1 / 8 · 114 % 210×297 mm (A4)“. Right side: scale status. When a tool is armed, it turns into the instruction line and overflows its column (Laso: the text runs to x=1318, under the right panel).
- **Step bar:** 44 px tall, 16 px labels. Each step has a numbered circle, an icon, a label and a „›“, so three cues for one step. „Įsiminta: 6“ sits on the right.
- **Top bar:** 52 px tall. It holds:
  - back (14 px icon);
  - name at 13 px with a pencil;
  - „INTERJERAS“ chip, 10 px caps;
  - red pill;
  - BE PVM (13 px mono) and SU PVM (18 px mono bold);
  - **„Nustatymai“**, which opens the assumptions panel even though the dashboard's „Nustatymai“ is account settings;
  - „Versijos“;
  - trash. These three buttons are 44 px.
- **Patikra and the room sheet drop the top bar entirely**, so the project name and totals vanish on two of the four steps.

### 4.6 Layout shifts and overlaps
1. The toolbar scrolls sideways at 1440 and 1280 px, and it jumps when a tool or the coach card targets a hidden button.
2. Focusing a room appends 5 buttons off-screen; the bar grows from 1621 to 2029 px.
3. The page scrolls (47 px at 1440×900, 91 px at 1280×720) because of the banner, so the step's main button is hidden.
4. The „Rasti panašius“ panel is placed at `left: railOpen ? 156 : 8` but the sheet list is 232 px wide, so they overlap by about 76 px (`TakeoffViewer.jsx` ~1491). The count panel already uses 240.
5. When the search is active its hint pill moves to `bottom-2`, under the walls legend at `bottom-2 right-2`. Both are z-30.
6. The count panel covers the top pill.
7. In outline edit, the red focus ring, the amber edit ring, the dark readout and the white chip stack on one spot. The Save label is clipped (screenshot 35).
8. The room sheet's drawing is not sticky (1945 px page).
9. Sąmata rows start below 900 px.

## 5. Click vocabulary and friction (founder addendum)

**How the steps were established.** Arming, panels and Esc behaviour were observed live on 2026-10-17. Any step that writes is traced in code (file:line) and was not clicked. "Actions" counts each click, drag, key or typed value as one; a horizontal toolbar scroll counts as one hidden action.

**Facts that apply to every row of the table:**
- **(F1) A room cannot be selected on the drawing.** At rest `RoomZoneLayer` is pointer-transparent. A plain canvas click calls `onClearFocus` (`TakeoffViewer.jsx` 1169–1181), so clicking a room **deselects**. Selecting works only from the list, or after pressing U for fills mode.
- **(F2) Room tools are off-screen** at 1440 px (§4.1).
- **(F3) Esc is overloaded.** It closes search, disarms the tool and **drops the room** (`lib/viewerShortcuts.js` id `escape`). It does not close Masteliai or Istorija, so a user who presses Esc to close a panel loses the selection instead. Seen live.
- **(F4) No keys** for Mastelis, Rasti panašius, Masteliai, Istorija, room tools or select. Keys 2, 3, 4, 6, L, U and S exist; 5 is skipped.
- **(F5) No undo after save for room operations.** Outline save, merge, split and subtract toast success with no „Atšaukti“ (`TakeoffViewer.jsx` 844, `useOutlineTool.js` 129). The only way back is a whole-project „Grąžinti“ in Versijos. Room-sheet fact fixes do have „Atšaukti pataisymą“. Rimo principle 5 requires undo everywhere.

| act | sequence today (1440×900) | actions | layout shift or focus loss | professional editor |
|---|---|---:|---|---|
| **Confirm scale** | scroll toolbar → „Masteliai“ → „Patvirtinti“ (or „Patvirtinti visus su tuo pačiu masteliu“) → ✕ to close (Esc does not) (`ScaleOverviewPanel.jsx` 52, 82) | 4 | dock covers half the canvas; button hidden at rest | 1: an inline „Patvirtinti 1:115“ chip in the status bar for this sheet, „visiems“ in the same chip |
| **Calibrate by a known length** | scroll → „Mastelis“ (no key) → click A → click B → modal: type the length (autofocus) → optionally tick „Suapvalinti iki 1:N“ → optionally change „Taikyti“ to all sheets (2) → Enter (`CalibrateDialog.jsx`) | 6–9 | instruction appears 2× (pill + status); modal covers the drawing | 4: key K, click, click, type plus Enter in a popover next to the line, with the standard scale pre-selected |
| **Fix a room outline (vertices)** | click the list row (drawing jumps to the page) → scroll toolbar about 500 px → „Redaguoti kontūrą“ → drag n vertices / click midpoint to add / double-click to remove → Enter (`TakeoffViewer.jsx` 812–861) | 4 + n | bar grows and jumps; ring, readout and chip overlap the handles; Save label clipped at 1280; no undo after save (F5) | 2 + n: double-click the room on the drawing to enter edit, drag, Enter; undo in the toast |
| **Show a room by one click** | *viewer:* row → scroll → „Taisyti kontūrą“ → click inside → saved, but the area stays from the schedule and the outline is "used for marking" (toast, 1211). *Room sheet:* Patikra step → „Peržiūrėti pagal patalpas“ → „Kitas“ × (n−1) → „Parodyti patalpą“ → click inside → saved (`RoomSheet.jsx` 252–264) | 4 (viewer); 4 + (n−1) (sheet) | two engines under two names (raster flood fill vs vector, wall-exact); no room picker on the sheet; no undo in the viewer | 1: a "room" tool (key R) in the viewer, click inside a room, wall-exact outline, auto-commit, undo toast; then click the next room |
| **Merge two rooms** | row A → scroll → „Sujungti“ → click room B's outline (must touch, same sheet) → read the consequence panel → „Sujungti“ / Enter (`OutlineToolPanel.jsx` 117–150) | 5 | panel covers the top of the canvas; Esc cancels and drops the room (F3); no undo (F5) | 3: click A, shift-click B on the drawing, M (or the selection bar); consequence shown as a line under the bar |
| **Subtract a column** | row → scroll → „Atimti“ → (rect is the default) drag a rectangle → check „Kas atimama?“ (default kolona; changing it is 2) → „Išsaugoti“ / Enter (`OutlineToolPanel.jsx` 157–210) | 5–7 | same as merge | 3: select the room, X, drag; default kolona with a one-word switch on the hole's chip; undo |
| **Add a count** | key 6 (the button is off-screen) → first type is active (a new type: „Pridėti tipą“ + name + Enter) → click each item → switch to the „Patalpos ir eilutės“ tab, open Matavimai → „Į sąmatą“ (`WorkspacePanel.jsx` 271–292, 723) | n + 2 (new type: n + 5) | the count panel covers the instruction; the hint says „dešinėje“ while the panel is on the left; the estimate row is **not live**, so you must press „Į sąmatą“ again after every recount | n + 1: key, pick a type from a list next to the cursor, click items; the estimate row updates live |
| **Find similar symbols** | scroll → „Rasti panašius“ (no key) → drag a tight box → wait ~3 s per sheet → remove wrong ones (k clicks) or move the slider → optionally „Ieškoti visuose lapuose“ → pick a type (0–2) → optionally tick the unusual-shape box → „Pridėti kaip kiekį (N vnt.)“ → still „Į sąmatą“ (`SymbolReviewPanel.jsx`) | 5–9 + k | panel overlaps the sheet list; the bottom pill collides with the walls legend; instruction 3× | 3 + k: right-click a symbol → „Rasti panašius“, review, Enter, and the count is linked to the row |
| **Measure a distance** | key 2 → click A → click B → Enter, double-click or „Baigti“ (distance is a polyline tool, `MeasureLayer.jsx` 18) | 4 | readout in system-ui; the result sits in Matavimai and **cannot be sent to a sąmata row** (only counts have „Į sąmatą“) | 3: key, click, click auto-commits; Shift-click continues the chain; the length can be dragged onto a row |
| **Correct a quantity row** | step „Sąmata“ → scroll a 7,682 px page or search (click + type) → click the quantity cell → type → Enter (blur also commits, `ProjectMainView.jsx` 370–373). The viewer's Kiekiai tab has **no inline edit**; only a right-click → „Atidaryti patikros lapą“ | 4–6 | leaves the drawing; 117 rows; banners first | 2: double-click the number where it is shown (Kiekiai row or the drawing label), type, Enter; Tab to the next |
| **Answer a Patikra question** | step „Patikra“ → the proposal is pre-filled → accept („Tinka“ / primary) (`QuestionBodies.jsx`). The "doors and windows" kind has **no in-place answer**: „Atidaryti patalpą“ → room sheet → fix → „Klausimai“ → back to the list | 2 (open-room kind: 4 + the fix) | the whole screen changes and scrolls to the top after each answer (by design); no Enter to accept | 1: Enter accepts the proposal and moves to the next; fix in place on the drawing beside it |
| **Type a fact** | room sheet → „Pataisyti“ (input auto-selected) → type → Enter or „Išsaugoti visiems N“ (`FactRow.jsx` 316–345). No blur-save; Esc cancels | 2 + typing (+ reaching the room: Kitas × (n−1)) | the evidence pane scrolls away (not sticky); next room is ~1,000 px down or Enter | 2: the same, plus a room picker and sticky evidence; digits typed straight into the focused fact |

**What the table adds up to.** Clicking costs 4–9 actions for what a professional editor does in 1–3. The overhead comes from a few causes:
- the hidden toolbar (F2, an extra scroll on 7 of 12 acts);
- having to select through the list (F1, 4 acts);
- missing keys (F4);
- results that do not flow into the estimate (counts need „Į sąmatą“; lengths cannot get there at all);
- no undo after room operations (F5).

What already works well: the room sheet's „Parodyti patalpą“ (2 clicks), „Pataisyti“ plus Enter, the proposal-first Patikra answers, and the walls snapping.

## 6. Diagnosis: why it reads as childish and outdated

Checked against the redesign-skill audit list, the taste-skill metrics, and the Rimo constraints (`docs/superpowers/plans/2026-09-04-rimo-kelione.md`).

1. **Type scale (taste: deterministic type; Rimo §5 ≥ 16 px).** 12 sizes on one screen and 91 % of text at 12 px or less (§2.4). Half-pixel sizes (9.5, 10.5, 11.5, 12.5) show there is no scale. The viewer (9–12 px) and the room sheet (13–17 px) feel like two products.
2. **Several accents, saturated (redesign: "more than one accent", "oversaturated"; taste: max one accent, saturation under 80 %).** 5 hue families in the chrome, 7 of the 9 zone hues at HSL saturation 71–94 %, 16 sheet-type colours, 8 count colours. Grey families are mixed as well: the theme's slate-green plus Tailwind gray, slate, stone and neutral hexes (`#1f2937`, `#64748b`, `#57534e`, `#525252`).
3. **Meaning by colour alone** (§3). This is the thing that blocks a muted palette, and it breaks WCAG 1.4.11 for 6 of 9 zone strokes.
4. **Broken contrast from dark-theme leftovers** (§2.5). The provenance pill was designed "for graphite" (comment in `ProvenanceChip.jsx`) and now reads 1.47:1 on parchment, 11 times per screen.
5. **The toolbar as a row of words** (§4.1). Wrapping and squeezed icons look broken. The contextual tools live off-screen, and the hit targets are 24 px against Rimo's 44 px.
6. **Developer-tool styling (taste: mono only for numbers).** 46 % of text is mono, uppercase tracked labels everywhere („00 / PROJEKTAI“, „ŽINGSNIS 1 IŠ 3“, „IŠ EKSPLIKACIJOS“, „KAIP SUSKAIČIUOTA“), and sentences in bold mono on the room sheet. It reads like a terminal, not like the contractor's paper (Rimo principle 1).
7. **Wizard and toy tropes (redesign: pill badges, generic cards, perpetual motion).** Numbered circles plus icon plus label in the step bar, an endless red pulse on the selected room, the equal three-column card grid on Projektai, rounded-full instruction pills, emoji in strings, a sparkles „✨ Pathon“ label.
8. **Notice clutter and buried actions** (§4.4, §4.6). The main button sits below the fold on every step at a laptop size. Sąmata shows no rows on its first screen. Instructions are said two or three times.
9. **Inconsistent primitives (redesign: uniform radius, arbitrary z-index, inline styles).** 7 radii against a 2 px theme. Buttons at 24, 25 and 44 px. 9 z levels. The in-canvas „Baigti“ is blue with 6 px corners. Esc closes some panels and not others. 266 arbitrary token classes and 192 inline styles.
10. **Jargon residue (Rimo principle 1, banned words):**
    - „Durys (AI)“, „2 AI“;
    - „Ploto pasitikėjimas: high“;
    - „Sienos (iš vektorinio PDF)“;
    - „po naujos analizės“;
    - „Nemokama, be dirbtinio intelekto užklausų“ (a toolbar tooltip);
    - two near-synonyms side by side (Redaguoti / Taisyti kontūrą);
    - „Nustatymai“ meaning two different things.
11. **The drawing gets about a third of the window** (32 % at 1440×900), even though it is the core of the merged product.

## 7. Ranked change list

**Ranking rule:** effect on the founder's verdict and on clicking, divided by effort and risk. "Risk" means risk to behaviour verified on 2026-10-17; none of these items moves a quantity. Lists A–C are visual and keep behaviour the same. List D changes interaction and needs a founder decision. Rank numbers run across all lists.

### A. Token-level (index.css, tailwind.config.js, shared classes)

| # | change | where | expected effect | effort | risk | verify |
|---:|---|---|---|---|---|---|
| 1 | **Contrast floor.** Make the provenance chip token-based (`--source-table` text on a /8 tint, 12 px, sentence case „iš eksplikacijos“). Darken `--muted-foreground` #73787B → ~#5F6467 (≥ 5.5:1). Ban `/70` on muted text. Darken the inactive step number. | `ProvenanceChip.jsx`, `index.css`, `WorkspacePanel.jsx` units | removes the most broken-looking element; every text at or above 4.5:1 | S | none | 04, 21, 24 plus the §2.5 probe |
| 3 | **Type scale.** Minimum 12 px for metadata only, 14 px for interface text, 16 px for body and steps. A 6-step `fontSize` scale in config. Codemod every `text-[9–11.5px]` and `fontSize: 8–11` in scope (§2.3). Body 15–16 px. | `tailwind.config.js`, `index.css`, files in §2.3 | ends the "tiny" impression; meets Rimo §5 where it matters | M | text may clip in the 400 px panel and the toolbar; pair with #7 and #9 | 04, 21, 25, 27, 34 plus a scan for `scrollWidth > clientWidth` |
| 4 | **Overlay tokens.** Add `--ov-selected / read / estimated / missing / user / opening / wall / editing / suggested`. Replace the 160 hex literals in overlay files. Collapse the zone palette to one neutral tint. Keep the revision colours, which a test locks to `api/pdf_revisions.py`. | `index.css`, `lib/roomZones.js`, `MeasureLayer`, `DrawingGeometryLayer`, `CheckLayer`, `OutlineEdit/ToolLayer`, `SymbolSearchLayer`, `RoomZoneLayer`, `RoomDrawingPane`, walls legend | one drawing language; meaning moves to line style and label | M | `roomZones.test.js` holds 16 hex values and needs updating; the revision parity test | 06, 08, 10, 11–15, 24–26, 35 |
| 6 | **Shape, elevation and stacking scale.** `borderRadius.DEFAULT = 2px`, fix the `md`/`sm` calculations, 2 px for controls and 4 px for floating panels; one tinted slate shadow token; z scale tokens (canvas 10, panel 30, popover 40, modal 50, coach 60). | `tailwind.config.js`, `index.css` | corners stop mixing; panels stop fighting | S | shadcn controls go from 0 to 2 px corners; coach marks must stay above dialogs (a known follow-up) | all screenshots |
| 8 | **Fonts.** Remove Sora, Hanken and JetBrains from the app import (load them on the landing only). SVG labels use `var(--font-sans)`. Mono only for numbers and units, not for chips, eyebrows or sentences. Sentence-case eyebrows. | `index.css`, overlay layers, `WorkspacePanel`, `RowDetailPanel`, room sheet | calm, "paper" typography; one label font on the drawing | S/M | check that the landing still renders | 04, 25, 30, landing |
| 13 | **Clean-up.** Delete the inert `.dark` block and 28 `dark:` classes. Move the landing CSS out of the app stylesheet. Replace 266 `[hsl(var(--x))]` classes with the configured utilities. | `index.css`, viewer and room-sheet files | one place to restyle from | M | typos in class names; diff the screenshots | screenshot diff |

### B. Component changes

| # | change | where | expected effect | effort | risk | verify |
|---:|---|---|---|---|---|---|
| 2 | **Toolbar becomes three icon groups plus an overflow.** Navigate (page, zoom, fit); Measure (a segmented icon control with short labels, keys 2/3/4/6 plus new K for Mastelis and F for Rasti panašius); Layers. Palyginti, Masteliai, Istorija, print, download and ? go into „Daugiau“. **Room tools move to a floating selection bar** anchored at the selected room. No wrapping; targets ≥ 32–36 px. | `TakeoffViewer.jsx` Toolbar (175–~420), `OutlineToolButtons.jsx`, `RevisionCompareControl`, `DetectRunButton` | no horizontal scroll at 1280 or 1440; room tools appear where the eye is | M–L | keep the `data-coach` anchors and `data-testid`s; coach-mark positions | 02, 03, 07, 11–15, 34, 35 |
| 5 | **One notice system.** A single `Notice` with 3 tones on tokens. The re-read banner collapses to a one-line chip with no write; the full list stays behind a click. One instruction place (pill, or status bar, not both). Sąmata's three boxes become one summary line with counts above the rows. | `RereadDiffBanner`, `FreeRereadBanner`, `ScaleInfoBanner`, `SanityWarningsBanner`, `TakeoffViewer` pill and status bar, `ProjectMainView` | main button above the fold; rows on Sąmata's first screen | M | the honest-disclosure rule: keep counts visible, never hide warnings | 05, 27, 34 |
| 7 | **Right-panel density.** Rows 36–40 px, name and area at 14 px; the provenance pill becomes a 12 px text link; chips become plain 12 px words; sentence-case section headers; eye target ≥ 24 px. | `WorkspacePanel.jsx` (555–660, SectionHeader), `ProvenanceChip`, `QuantityRows` | a legible, calm list | M | the 11-room list grows by about 110 px and scrolls | 04, 21, 34 |
| 9 | **Fix collisions and dismissal.** „Rasti panašius“ offset 156 → the count panel's rule (240). Stack or hide the hint pill when the walls legend shows. Ellipsis on the status bar. Esc closes Masteliai and Istorija. Unclip „Išsaugoti kontūrą“. Quiet the focus ring under an edit. | `TakeoffViewer.jsx` (~1427–1500), `ScaleOverviewPanel`, `HistoryPanel` | nothing overlaps; Esc is predictable | S | the Esc order in the chain (F3) | 12, 14, 15, 16, 17, 35 |
| 10 | **Copy pass on banned words.** „Durys (AI)“ → „Durys (rasta automatiškai)“; Lithuanian confidence sentences from `lib/confidence.js` instead of „high“; „Sienos, kurias programa perskaitė“; „po naujo skaičiavimo“; count hint „kairėje“; name the real place instead of „Peržiūra“; one verb per outline action (founder Q5). | `TakeoffViewer.jsx` 87, `RoomZoneLayer`, `lt.json`, `CountLegendPanel`, PriceLists | follows Rimo principle 1 | S | the banned-word guard test helps | 10, 12, 33 |
| 11 | **Calmer step bar and top bar.** Keep either the number or the icon, not both. Active step in ink with a 2 px underline. Trash goes into an overflow. The same top bar on all four steps. | `pages/InteriorProject.jsx` StepBar and ProjectTopBar, `RoomSheet`, `PatikraQuestions` | fewer cues; a stable frame | S | tests that find steps by text; keep `aria-current` | 04, 24, 25 |
| 12 | **Sąmata row actions.** Move delete into a row „⋯“ menu or show it on the selected row (not on hover only). Price-source dots become a short text („iš kainyno“). | `ProjectMainView.jsx` rows | removes 117 red bins | S/M | keep the 6 s undo on delete | 28 |

### C. Structural (layout, no change to flows)

| # | change | where | expected effect | effort | risk | verify |
|---:|---|---|---|---|---|---|
| 14 | **Give the drawing the room.** The sheet list collapses to a 56 px thumbnail strip (names on demand, not on hover). The right panel collapses or resizes (400 → 340 default). The banner leaves the column flow. | `InteriorWorkspace.jsx`, `SheetRail`, `TakeoffViewer` | canvas from 32 % to about 50 % of 1440×900 | L | fit-on-load, coach positions | 04, 34 |
| 15 | **One design language for the viewer and Patikra.** Adopt the room sheet's scale (13–17 px, tokens, 2 px) in the viewer; keep the project frame on every step. | as #3, #11 | one product, not two | L | wide visual change, so screenshot sign-off | 04 vs 25 |
| 16 | **Sticky evidence pane on the room sheet,** plus a room picker (no Kitas × n). | `RoomSheet.jsx`, `RoomDrawingPane` | evidence stays beside every number (Rimo principle 3) | M | low | 26 |
| 17 | **Projektai as status rows (Rimo E0)**, not a three-column grid; fix the mono gap inside numbers. | `Dashboard.jsx` | adult list | M | low | 01 |

### D. Interaction changes (these change behaviour; founder decision first)

| # | change | clicks saved (§5) | where it would land |
|---:|---|---|---|
| 18 | Click a room on the drawing to select it; Shift-click to select several (fixes F1) | 1 per act on 4 acts, plus enables merge in 3 | `RoomZoneLayer` simple mode, `TakeoffViewer` `handlePagePoint` |
| 19 | One "room by click" tool in the viewer: the vector, wall-exact outline from the room sheet, replacing the raster „Taisyti kontūrą“ | 4 → 1 | `TakeoffViewer`, `api/room_outline` |
| 20 | Undo toast after every outline, merge, split or subtract save (fixes F5) | n/a (Rimo principle 5) | `useOutlineTool.save`, `saveOutlineEdit` |
| 21 | Counts and lengths flow live into a sąmata row (no „Į sąmatą“); a length can be sent to a row | 1–2 per act | `WorkspacePanel` measure rows, the sąmata model |
| 22 | Distance auto-commits on the 2nd click; Enter accepts a Patikra proposal and moves on; double-click edits a quantity where it is shown | 1 each | `MeasureLayer`, `PatikraQuestions`, Kiekiai |
| 23 | Esc order: tool, then panel, then selection, with the room kept unless Esc is pressed again; keys for every tool (K, F, E = edit outline, M, X) | removes F3, F4 | `lib/viewerShortcuts.js` |

**Top 8 by rank:** #1 contrast floor · #2 toolbar regroup with a selection bar · #3 type scale · #4 overlay tokens and semantics · #5 notice system · #6 shape and stacking scale · #7 right-panel density · #8 fonts and mono only for numbers. For the merge goal, **#18–#20 belong right after #2**: they are where the click counts in §5 come from.

## 8. Open questions for the founder

1. **Zone colour.** Go fully neutral with labels, or keep one categorical cue (for example wet rooms only)? Today it is 9 bright hues with no legend.
2. **Overlay vocabulary.** Should Patikra's learned code (green = read on the plan, red dashed = no dimension, violet = openings) become the vocabulary for the whole viewer, so that the walls layer, zones and tools adopt it?
3. **The re-read banner.** May it become a one-line chip that does not write, with the list behind a click? Or must it stay a full banner until „Supratau“?
4. **Type floor.** 14 px for interface text and 16 px for body everywhere (Rimo §5), accepting a scrolling right panel and an icon-only toolbar? Or keep a 12 px dense exception in the viewer?
5. **Words.** „Nustatymai“ or „Prielaidos“ for the assumptions button? One verb for outline fixes (today „Redaguoti kontūrą“ and „Taisyti kontūrą“ do different things)? And D-list #18–#23: in scope for the merge?

## Appendix: not captured, and side findings

**Not captured:**
- **Native `title` tooltips.** There are 281 on the viewer page; headless screenshots do not render them, so I give counts instead.
- **Edition overlay colours.** The synthetic edition shows no visible difference on sheet 1.
- **Hollow "found" count marks.** None were in view on sheet 1.
- **Split, merge and subtract overlays and click-to-fill.** These lead into write flows, so they come from code only. Outline edit was entered as view state and left with Esc (35).
- **Toasts.** Triggering them needs writes.
- **The „Nustatymai“ (assumptions) panel and the Siųsti step.** Not in the brief's list.
- **EmbedPDF search highlight.**
- **Live click-through on 2026-10-18.** The servers were down, so the write-steps in §5 are traced in code.

**Side findings (possible bugs, outside the restyle):**
- **(A) Scale state disagrees between viewers.** The main viewer shows „Patvirtintas mastelis 1:115“ while the Patikra and room-sheet viewer shows „Spėjamas mastelis 1:115“ for the same sheet. `lib/scaleLabel.js`: source `lane-confirmed` vs `plan`.
- **(B) Panel offset.** `SymbolReviewPanel` uses offset 156 px, which ignores the 232 px sheet list.
- **(C) Wrong side in a hint.** The count hint says „dešinėje“ but the panel is on the left.
- **(D) Dead reference.** The missing-rooms chip says „žr. „Peržiūra““, a screen that no longer exists.
- **(E) Stale tooltip.** The zone toggle's tooltip says „dabar matomi tik numerių žymekliai“, but nothing has been drawn at rest since 2026-07-14.
- **(F) Two number formats.** The chip shows „4,5 m²“ where the list shows „4,48 m²“ (1 decimal vs 2).
- **(G) Esc is inconsistent.** It closes Versijos and the guide but not Masteliai or Istorija, and it drops the selected room.
- **(H) Clipped label.** „Išsaugoti kontūrą (01)“ is clipped at 1280 px.
- **(I) Adding unlike works.** The Kiekiai footer Σ sums different work types when no filter is set.
