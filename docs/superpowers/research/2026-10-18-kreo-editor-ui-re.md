# Kreo 2D Takeoff: editor UI and interaction reverse-engineering (2026-10-18)

**Summary.** I captured Kreo's shipped 2D Takeoff frontend (`takeoff.kreo.net`, build `a3cb1e972fc7979df758`) with REA from its public `/sso` page. That page boots the full single-page-app bundle without logging in. I then read the minified code directly and checked it against the public help centre's product screenshots. Six findings matter for Pathon's merge:

- **Theme.** The editor is a **dark-by-default** styled-components app (navy `#1D2733`, one blue accent `#2974AD`/`#32A6FE`, Proxima Soft, 10 px radii) with an optional light theme and eight user-selectable dark tones.
- **Overlay.** Drawing overlays are paper.js on top of a PDFTron/Apryse page. Stroke and handle sizes are divided by zoom, so they stay constant on screen. Every measurement gets a **random colour from 18 fully saturated hues**, with fill = colour alpha × 0.7.
- **Interaction.** A strict, discoverable model: digit hotkeys `1`–`7`; Esc steps back one point before it exits a tool; double-click enters vertex edit; a floating selection "fly-menu"; a right-click "Create / Reset" pop-up while drawing; and **a cursor-side hint sentence for every AI state**.
- **AI tools.** Each AI tool has a review step before anything is created: a mask preview on hover, an "AI Confidence" slider, "Fix with AI", thumbs-down and delete per contour, then **Create**.
- **Gating.** Paid features are gated by explicit dialogs and trial run counters.
- **What to take.** Pathon should copy the interaction grammar (cursor hints, Esc semantics, fly-menu, vertex pop-up, review-before-create), not the look. The dark theme and the random rainbow fills are exactly what the founder called childish, and Pathon's evidence-first sheet is already ahead of Kreo's property sheet.

Nothing here comes from running the logged-in editor. No account was created and no login was attempted. Every behaviour below is either read from shipped code or shown in Kreo's own help screenshots.

Legend: **OBS** = observed (code or screenshot, with citation); **INF** = inferred by me; **UNK** = unknown. Code cites use character offsets in the exported files: `M@n` = `main-a3cb1e972fc7979df758.js` (sha256 `bc96921a…8384`), `V@n` = `vendors~main-a3cb1e972fc7979df758.js` (sha256 `3a866906…e615`). Webpack module IDs are given where useful, for example `jnRQ`.

## Evidence and its limits

| ID | Source | What it gives | Limit |
|---|---|---|---|
| E1 | REA `inspect_web_page` on `https://takeoff.kreo.net/sso` with script sources (`ev_87453375b166595f104b69311791a3642ffc0986022373ac0696dcaeabfab94c`) | Full bytes of `main` (8,754,695 B) and `vendors~main` (10,900,964 B), PDFNet/WebViewer core, SignalR | Static code. The editor was never executed. Source maps are declared (`*.js.map`) but **not fetched**, by rule. |
| E2 | REA `export_web_scripts` (`ev_37c4997052dd93cf6906f2e91bdf160bf95e55d1205ddd3f4cd552964d081bef`) | Digest-verified files in my scratchpad, used for all `M@`/`V@` reads | Minified identifiers; I read the code directly (Wakaru recovery is unavailable on macOS) |
| E3 | REA `analyze_web_bundle` (`ev_dd0a9cbe8a74bcc6dd39f6043b7b342f0960a8a166de91348397cfb673b12456`) | webpack runtime ×3, React fingerprint, only one dynamic import (`/static/KreoEngine.js`, the 3D engine), so the 2D editor ships inside `main` | Fingerprint detectors are coarse; 182 endpoint "candidates" are mostly noise |
| E4 | REA `list_browser_targets` (`ev_03144585a5f03363821857028b0a60fcce00e9dadb563916620ab26800b83998`) | `/sso` stays on the single-page app (title "Kreo"). `/2d/` redirects to Keycloak "Sign in to Kreo" within seconds (seen 2026-10-17; that evidence was not retained after REA restarted) | Login-gated screens are only reachable through code |
| S1–S6 | REA `capture_web_screenshot` of help-centre images (Gleap CDN), dated 2025-07-15. S1 MM-intro `ev_30f3e18e…` (…091119_1799). S2 right panel `ev_a551f339…` (…091126_9182). S3 selection + fly-menu `ev_179c1db2…` (…091126_7558). S4 Settings tab `ev_c7a06b8f…` (…091126_0369). S5 AM 2.0 running `ev_461f54d3…` (…090948_0685). S6 Auto Count results `ev_69f8f231…` (…090948_8550) | Real editor chrome, panels, labels and overlays in context | Marketing hands are drawn on top; images are 15 months older than this build; S1 shows an older left-rail layout |
| H | help-takeoff.kreo.net articles: Drawing Settings, Keyboard Shortcuts, Navigation, Modify measurements, Operations with count items, Knife, Subtract, Scale, One-Click Area, Auto Count, AM 2.0, MM intro, Work with data in MM, Rename with AI | Step wording and click flows | Some steps are stale versus code. The help page says Paste With a Point = Ctrl+Shift+V; code says Ctrl+V (`M@7254425`). **Code wins.** |
| R | kreo.net release notes: "Hey, Spot" (2026-10-14); "AI Classification, PDF Bookmarks…" (2026-09-17); post list since 2025-09 | Spot voice agent; region-aware counting; AI Classification scope | Marketing prose. The Auto Measure 3.0 and Caddie posts are already summarised in the 09-17 doc and not repeated here. |
| — | Served CSS (`main-…css` 644 KB, `vendors~main-…css` 335 KB) | **Not read.** REA's page inspection does not retain stylesheet bodies, and the scenario capture keeps at most 64 KiB per body. Downloading CSS outside REA is excluded by rule. | Component styles live in styled-components inside `main.js` (read); the CSS files are probably global/vendor styles (INF) |
| P | Pathon repo (read only): `frontend/src/components/viewer/MeasureLayer.jsx`, `TakeoffViewer.jsx`, `lib/viewerShortcuts.js`, `index.css` | Today's Pathon behaviour, for section 11 | Not browser-verified in this task |

## 1. Layout anatomy

**OBS (S2, S3, S5; code):**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Project | Plans | Assemblies          «Building project ›»        (?)  [Share] │ row 1 ≈35px
│ ⣿logo  🔍  [▣¹ Floor 1 / file.pdf] [▣² …]  (+)                    🔔 💬  (AY)  │ row 2 ≈70px, page tabs = thumbnail cards, red count badge
│ ↶ ↷        [⌖][▭▾][╱▾][∘∘] │ [🪣 One-click Area ✨][⌁ One-click Line ✨][◎ Auto Count ✨] │ [▢▾]   [13][▭] │ row 3 ≈45px
├─────────────────────────────────────────────────────────────┬────────────────┤
│                                     ┌─fly-menu 40px────────┐│ [Page|Settings]│ right panel ≈300px
│        canvas (PDF page + paper.js overlay)                 ││ SCALE        › │
│                                                             ││ AUTO MEASURE › │
│                                          ┌zoom cluster─────┐ ││ AUTO MEAS. 2.0 │
│                                          │🔍▢ 🗺 ⊕ ⟷ ⊖ 3D │ ││ ASK AI · COMPARE│
│                                          └─────────────────┘ ││ TEXT SEARCH ·  │
├─────────────────────────────────────────────────────────────┴┤ EXPORT · STYLE │
│ ⋮  + Create report      (spreadsheet / report pane, collapsed) │ COLOR/HEIGHT…  │
└──────────────────────────────────────────────────────────────┴────────────────┘
```
- The zoom cluster floats on the canvas at `bottom:10px; right:11px; z-index:12`, on a `backgroundRush` card with a `0 0 0 1px pale` ring and `border-radius:10px` (`M@3227977`). Buttons are 30 px icons: Fullscreen, Marquee Zoom, Minimap, Zoom In, Home, Zoom Out, then a 2D/3D switch. Gray at rest, turquoise when active (`M@4181380`).
- The fly-menu is `position:absolute; height:40px; z-index:1000`, with shadow `xl`, background `backgroundRush`, radius 10 and 1 px dividers. When pinned (the default) it sits at `top:10px; left:50%` (`M@8077038`–`8078300`).
- The right panel is a mode host. Modes: `Default, Scale, AutoMeasure, AutoMeasure2, AiChatDialog, AskAi, ComparePages, TextSearch, Export, StyleFilter, ShowAiInsight`. Each has a title, an info icon and a close ✕ (`M@4012654`).
- The Measurements Manager is an "entity panel" with a persisted `{position:{top,left,width,height}, show:true}` (`M@501526`). Hotkey `M` toggles it (`M@8358734`). Help says it opens in the bottom-right and shows the measurement count above its icon. S2/S5 show a count badge (`13`, `0`) at the right of row 3.
- Persisted layout keys: `splitterPaneSize`, `isPagesTabsMinified`, `drawingMinimapOpened:true`, `drawingEngineViewMode:Split` (`M@501526`).

**INF.** The MM is a floating, movable and resizable window rather than a docked column; S1 (older) docks it on the left beside a vertical tool rail. **UNK:** exact panel widths in CSS. The px values above are measured from screenshots.

## 2. Design tokens

**OBS, from the UI kit module `k1XP` (`V@8890879`).** Each theme key is a `[night, day]` pair, and `THEMES=[DARK_THEME, LIGHT_THEME]` (`V@7183618`):

| key (uses in `main`) | dark (default) | light | used for |
|---|---|---|---|
| background (493) | `#1D2733` navyBlue | `#F5F7FB` | page / chrome background, dividers |
| backgroundRush (320) | `#222E3C` darkBlue | `#FFFFFF` | panels, cards, menus, zoom cluster |
| pale (218) | `#293849` | `#E8F2FF` | hover fills, rings |
| mainFont (179) | `#FFFFFF` | `#222E3C` | primary text |
| gray (217) | `#79A5D6` | `#79A5D6` | secondary text, idle icons |
| turquoise (447) — the accent | `#2974AD` | `#32A6FE` | active tool, primary buttons, toggles |
| turquoiseFont (19) | `#5C7EA3` | `#4E6A8A` | captions, file names |
| disabled (123) | `#314357` | `#CDD8E5` | disabled controls, scrollbar thumb |
| additionalFont / icon | `#79A5D6` / `#79A5D6` | `#1D2733` / `#F5F7FB` | — |
| red / green / orange / yellow | `#E15556` / `#29AD67` / `#FF8E6A` / `#E0E155` | same | danger, AI preview, secondary, warning |

- **Default theme is dark** (OBS): persisted defaults are `theme:"dark", darkTone:"night", lightTone:"day"` (`M@501526`). `getTheme()` falls back to `DARK_THEME` and persists it (`M@415719`).
- Tones override colours. `DARK_TONES`: black (`#191A1C`…), grey, royal blue, cyan, dark purple, dark magenta, dark green, grey green. `LIGHT_TONES`: green, lemon, lola (`V@8890879`+). They are chosen from the user menu under "Themes", next to a "Night Mode" switch (`M@5785422`).
- **Shadows** (`V@7182803`): dark `xs 0 1px 1px rgba(0,0,0,.3)`, `s 0 1px 4px /.12`, `m 0 4px 8px /.12`, `l 0 8px 12px /.08`, `xl 0 15px 40px /.12`. Light uses `.1/.02/.04/.08/.12`. Inset `xl` = `inset 0 0 40px rgba(0,0,0,.1)`.
- **Motion:** `xs .1s`, `s .175s` (95 uses), `m .35s`, `l .75s`, `xl 1s`. Easing `oq cubic-bezier(.25,.46,.45,.94)`. Breakpoints run 375 px → 1920 px.
- **Type** (OBS): one family, `'Proxima Soft', sans-serif` (19 declarations). Monospace only in code views. Size usage in `main`: 14 px dominates (336 props), then 12 / 10 / 16 / 11 / 18. Weights 400 / 500 / 600. The UI-kit scale (`M/m9`, `V@3519643`): H1 60/75, H2 52/78, H3 36/54, H4 30/45, H5 22/33, H6 18/27, `Text` 16/24 (line-height = ⌈1.5 × size⌉), `TinyText` 12/18. Numbers use the same family; no tabular-figure setting was found (bounded search for `tabular-nums`: 0 hits).
- **Radii** (CSS literal counts): 10 px (116), 5 px (108), 15 px (85), 20 px (47), 6 px, 40 px (pills). Segmented "round pickers" use 30 px.
- **Overlay tokens** (module `jnRQ`, `M@7308487`): `lineStroke 3`, `infoLinesStroke 2`, `snappingStroke 3`, `defaultSnappingSize 10`, `pointRadius 6`, `countRadius 10`, `fontSize 12`, `snappingThreshold 15`, `snappingAngleStep 15`, `angleCircleRadius 30`, `doubleClickDelay 300`, `backgroundOpacity .7`, `thicknessOpacity .6`, `regionOpacity .35`, `selectedOpacity .5`, `zoomInCoefficient 1.1`, `menuButtonSize 40`, `previewDashArray [4,2]`. Colours: vertex/utility `#8000FF`, primary figure `#FF57C7`, secondary `#FFC500`, AI-autocomplete green `#29AD67` (fill `…40`, hover `…80`), warning red `#E15556` (fill `…40`).
- **Library fingerprint** (OBS, E1/E3): React + styled-components (`.div\`` 2,073 times; `e.theme.color.*` 2,273 times), react-hotkeys (`HotKeys keyMap handlers`), redux-saga, Immutable, react-dnd, ag-grid (report), three.js (3D), paper.js (`PaperScope`), Apryse/PDFTron WebViewer `lib115`, OpenLayers 4.6.5 CSS, SignalR, Gleap (help widget), Sentry, Segment, Chargebee, Rive (the "Searching..." animation). Icons are an in-house SVG set (`o.Icons.*`, for example `AITool`, `Bucket`, `AutoCount2D`). No MUI or Tailwind.

## 3. Click vocabulary (founder priority)

All rows are **OBS** from code unless marked. "Engine" refers to the draw processor (`M@7477012`–`7486800`).

**Global rules.**
- Wheel zooms ×1.1 per step. Pan is right or middle mouse button, or **Space + left drag** (cursor `grab`/`grabbing`) (`M@8358734`, H Navigation).
- Cursor priority: `wait` (AI busy) > `crosshair` (eraser) > `grabbing` > `grab` (Space) > `zoom-in` (marquee) > `crosshair` (drawing) > `grab` (hover over a *selected* shape, so it can be moved) > `pointer` (hover over any shape) (`M@3887334`).
- **A cursor hint sentence sits to the right of the pointer** in every mode (`CursorHint position:"right"`, `M@7840167`). It can be hidden (`hideCursorHint`).
- Undo/redo while drawing: Ctrl+Z removes the last *point*. The 45×40 Undo/Redo buttons (turquoise = available) are disabled mid-drawing (`M@6115645`).

| Mode | Single click | Double click | Drag | Right-click | Enter | Esc | Modifiers | Hover / snap feedback |
|---|---|---|---|---|---|---|---|---|
| **Select** (`1`/`V`) | Selects the shape. Ctrl/⌘+click toggles it in the selection (`M@2800551`, `M@7110379`) | Selects and **enters Modify**; a rectangle is silently converted to a polygon (`onDoubleMainGeometryClick`, `M@7110379`) | On empty canvas: marquee (turquoise `#32A6FE` stroke 3 / fill α .2, `M@4342961`). On a selected shape: moves it | On a shape: keeps the current selection and opens its context menu (`onEntityClick`) | — | Unselect | **Alt+drag = duplicate**; **Shift+drag = ortho move** (`M@73671`) | Pointer over a shape; grab over a selected one; selection box plus fly-menu |
| **Polygon** (`3`), Rect 2-pt (`4`), Rect 3-pt (`5`) | Adds a vertex. Clicking the first vertex (once there are >2) closes the shape. Rect 2-pt finishes on 2 clicks, Rect 3-pt on the 3rd (`M@7480641`) | Finishes if valid (`doubleClick`) | — | If completable: **"Create / Reset" pop-up** (`openFinishPopup`, `M@7483661`, `M@2961174`); otherwise the context menu | Finish | **Removes the last point; with no points left, exits the tool** (`removeLastPointOrCancel`, `M@6555954`) | Hold **Shift = strict angle** (15° steps, `snappingAngleStep`); Backspace / Ctrl+Z = undo point | Live segment lengths and an angle arc (r 15, right-angle mark), snap marker 10 px within 15 px. An invalid click (self-intersection) flashes the shape red |
| **Polyline** (`2`) | Adds a vertex | Finishes | — | Finish pop-up | Finish | Same step-back rule | Same | Same; "Continue" (turquoise arrow on the fly-menu) extends an existing line: "Select the point you want to continue from" |
| **Count** (`7`) | Adds a mark (a second click on the same spot is ignored) | — | — | Finish pop-up | Finish ("To finish the Count, press Enter") | Step back | — | Marks: 9 shapes, r 10; a dashed trace line joins them in Modify (help) |
| **One-click Area** (bucket) | First click = positive seed. Next click **outside** the result = expand; **inside** = negative (shrink). Clicking an existing seed removes it (`M@318917`). Every click waits 300 ms for a possible double-click | Finishes (help) | — | Finish pop-up | Create (help) | Step back | AI Turbo Boost on: "Mode" Auto / Big / Small areas (requires a scale, else a "not scaled" dialog) (`M@271367`) | Hover previews the mask before the first click. Hints: "Set the first point to define the area." / "Adding a point inside shrinks the area." / "Adding a point outside expands it." / "Optimizing the area. Please wait..." / "To extend current area, please click closer to it" (a red bounding square) |
| **One-click Line** | Click on a line or a wall centre; next clicks inside bend, outside extend; Ctrl+click forces negative (`M@7456387`) | Finishes | — | Finish pop-up | Finish | Step back | — | Hints: "Adding a point inside bends the polyline inward." and so on (`M@7840167`) |
| **Auto Count** (`6`, Finder) | Click a result tile to untick it (S6) | — | **Drag a box** around the reference; Eraser removes geometry from it | Finish (wizard) pop-up | **Apply** | **Cancel** (wizard listener) | Rotation / flip toggles; "Add Search Area" | Results boxed with cluster colour α .25 (.75 on hover), 4 px radius (`M@4415172`); "20 results found", "Similarity 80%" slider, "Reset", "Create" (S6); count = matches with `similarity ≥ slider` |
| **Auto Measure review** | Click a contour to open its mini-menu: **Fix with AI** · 👎 "Don't search areas like this" (max 4 input polygons) · 🗑 (`M@2962043`) | — | "AI Confidence" slider 0–100 (`M@2677898`) | — | — | — | — | Fix states: Loading → Loaded (✔ Apply / "Again" / 🗑) → Failed ("Again") |
| **Knife** (fly-menu) | Adds a cut-line point. "Draw a line according to which you'd like to separate the measurements" | Finishes the cut | — | Finish pop-up | Finish | Step back | Ortho applies | Cut-line preview |
| **Merge / Subtract** | Fly-menu or context-menu buttons, Ctrl+Alt+U / Ctrl+Alt+S (`M@7263235`, `M@8082649`). Subtract: pick the base polygon, then **Apply**; "Keep polygons" option (H Subtract) | | | | | | | — |
| **Modify** (vertex edit) | Click a vertex to select it; Ctrl/⌘+click to add to the selection (H). **Click on an edge inserts a vertex** (H; `addPoint` on edge, `M@481523`). Click on empty canvas: the 1st clears the vertex selection, the 2nd exits Modify (`M@7153230`) | Count mark: no-op in Modify (`M@6761109`) | Drag a vertex; **drag an edge moves the whole segment**; **Ctrl+drag an edge duplicates it** (`M@7794519`); marquee selects vertices | — | — | Exit Modify | — | Vertices are purple `#8000FF` r 6. With vertices selected, a pop-up appears: **Delete** (red) · **Split** (counts) / **Cut Path** (polylines; "With a start and end point, this action is not available") · Align Left / Right / Top / Bottom (`M@7272291`); Delete/Backspace also work |
| **Dimension line** (`R`) | Click start, then click end: done (`M@7480641`) | — | — | — | — | Step back | — | Annotation, not a quantity |
| **Scale / Calibrate** | Two clicks, then type the real length, pick Metric/Imperial, Apply (H Scale). Minimum length 0.1 (`minimumCalibrationLength`) | — | Calibration points can be dragged (`M@7110379`+) | — | — | **Does not exit** when empty (calibrate is excluded from cancel) | — | AI scale suggestion with one "Apply"; "Scale multiple pages" |

**Typical corrections (INF: click counts derived from the code paths above, not executed).**
- **Rename / regroup a room:** select (1) → Page tab "Name" ✎ (1) → type → Enter. Regroup: "Group" dropdown (2), or fly-menu **Move To** (1) + pick (1), or one drag in the MM. **Best case: 1 click.** With **AI Classification** on, a chip menu of suggested names appears right after creation; one click renames (H One-Click Area; `drawingsGeometryClassificationSuggestedName`). → ~1–3 clicks + typing.
- **Fix one vertex:** double-click the shape (1) → drag the vertex, which snaps (1) → Esc (1). → **3 actions.**
- **Remove a false count:** before Create, untick its tile in the results list (**1 click**). After Create: double-click the count (1) → click the mark (1) → Delete (1) → Esc (1). → **4.**
- **Deduct a doorway from a wall-finish polyline:** before Create, "Remove Doorways" toggle (**1 click**, the AM 2.0 default for wall finishes is on: `drawingsAutoMeasure2DoorWays:true`). After Create: double-click (1) → click the edge at both jambs (2) → select both vertices (2) → **Cut Path** (1) → select the doorway piece (1) → Delete (1). → **~8.**
- **Re-run Auto Measure on one sheet:** open the sheet (1) → AUTO MEASURE 2.0 (1) → mode chip (1) → **Launch/Restart** (1, label switches `M@3472654`) → wait (progress) → AI Confidence drag (1) → **Create** (1). → **~6 + wait.** Alternative: the Caddie tool "Run Auto Measure by Text", typed (`M@6635676` area).

## 4. Toolbar and tools

**OBS** (definition in module `X/O9`, `M@6179199`/`6180332`; hotkeys in module `uCQm`, `M@8358734`):
1. **Select** `1`/`V`.
2. Group **Area**: Polygon `3` · Rectangle 2 Point `4` · Rectangle 3 Point `5` │ Wand · Dropper.
3. Group **Line**: Polyline `2` │ Wand · Dropper.
4. **Count** `7`.
5. │ **One-click Area** · **One-click Line** · **Auto Count** `6`, each with an `AITool` badge in its tooltip. In the toolbar they show as **icon + text + ✨** (S2).
6. │ Group **Annotations**: Drawing Legend · Sticker `N` · Dimension Line `R` · Symbols.
7. **Comment** `C` · Callout.

Grouped tools open from a ▾ chevron (S2). Every tool tooltip carries `name`, `hotKey` and a one-to-two-sentence `description`. Example: Polygon: "To finish the polygon, click on the initial point or press the "Enter" button or use the right-click and choose the "Finish" option." Visibility is permission-gated per tool (`Takeoff2dWizzardAccess`, `…FinderAccess`, `Takeoff2dAnnotations`, `Comment2d`; `M@6180332`+).

- Wand settings: "Connect", "Enclose".
- Bucket settings: "AI Classification", "AI Turbo Boost", "Mode".
- Snapping options: Line Intersection, Line Midpoint, **Path EndPoint** (the default), Point On Line, Dynamic Guideline (`M@4017390`); `S` toggles snapping. Orthogonal Mode is a setting (S4).

## 5. Overlay rendering

- **Colour (OBS):** each new measurement takes `getColorFromList()`, a **random** pick from 18 hues 20° apart: `#ff3f3f #ff7f3f #ffbf3f #ffff3f #bfff3f #7fff3f #3fff3f #3fff7f #3fffbf #3fffff #3fbfff #3f7fff #3f3fff #7f3fff #bf3fff #ff3fff #ff3fbf #ff3f7f`, named red…rose (`M@4287470`, `M@4478731`). The picker adds white plus five slate-blues (`#6d93bf…#314256`).
- **Stroke/fill/thickness factory (OBS):** `getPaperColor(hex)` → stroke = colour; fill = colour α × **0.7**; thickness band = α × **0.6** (`M@6997011`).
- **Stroke widths (OBS):** widths are divided by zoom (constant screen px). New-geometry stroke defaults to **6 px** (`drawingNewInstanceStrokeWidth:6`; S3 shows "Stroke 6 px").
- **INF:** the screenshots look lighter than 70 % fill, so stored colours probably carry their own alpha. **UNK** without an account.
- **"Same colour = same size" (OBS):** Auto Measure 2.0 clusters results by **Size** by default (`drawingsAutoMeasure2SelectedClusterTypes:[Size]`); the options are "By Size" / "By Appearance" (Objects: "By Label" / "By Type" / "By Appearance") (`M@3456926`, `M@3480268`).
- **States (OBS):**
  - **Drawing:** in-progress shape plus a dashed preview (`[4,2]`, 1 px).
  - **Invalid:** red `#E15556` stroke, 25 % fill, flashing.
  - **AI preview:** green `#29AD67` with a 50 % fill mask (`M@7310485`).
  - **Selected:** bounding rectangle plus fly-menu.
  - **Modify:** purple vertices r 6 plus hover lines on edges.
  - **Zone/region boxes:** α .35 fill, 1 px stroke, 5 px radius (`M@7082793`).
  - **Auto Count result boxes:** α .25.
- **Labels (OBS):** a pill (padding 3/12, radius 11, stroke 2) filled with the shape colour. Text is white or `#222E3C` chosen by background luminance (`needReverseTextColorByBackground`), 12 px. Two lines: area m², perimeter m (S2, S3, `M@7309418`). "Show Dimensions" hides them, including in PDF export (`M@4020911`).
- **Drawing-settings fly-out (OBS defaults, `M@501069`):** Pin flymenu **on** · Black & white off · Night mode off (dark theme only) · Rotate · Show Dimensions **on** · Display Thickness **on** · Show Text Links off · Opacity **100**. The Opacity tooltip says lower values make measurements stand out. Measurements section: Keep Names off · Auto Focus **off** · Keep Structure on. 3D: orthographic, fill .8, drawing opacity .5.
- **On-canvas Drawing Legend (OBS):** an annotation tool ("Visualize the measurement data… save a key… when exporting to PDF"). Legend panel controls cover sort, filter, pivot, hide empty groups, colour picker and so on (control-name enum, 343 keys, `M@7969xxx`).

## 6. Measurements Manager and right panel

- **OBS (H, S1–S3, code):**
  - Folder tree with drag and drop, a ✎ inline rename, and an 👁 visibility toggle per row. **Double-click a row = isolate** (H).
  - A colour assigned to a folder is inherited by the measurements in it (H).
  - Row selection: Ctrl-click toggles, **Shift-click selects a range** (`M@2804777`).
  - ⋮ menu: Select all · Templates · Invert selection · Delete empty folders (S1).
  - Filters: by type (incl. Count), by origin ("All / Auto Measure / Manual measurements"), by pages ("Current page"…), by colour, by report cell range (`M@6630029`; H).
  - Defaults: pivot mode on, quick search visible, `showTableUnits:true`, `showTableTotal:false`.
  - **Page tab with a selection** = property sheet: Name ✎ · Type · Stroke · Style · Color · Group · Height · Offset · Count · Perimeter · Area · Vertical Area · Volume. Below it, assemblies: "No applied items and assemblies yet" / [Choose] (S3). The maths is `verticalArea = perimeter × height`, `volume = area × height` (`M@4478731` area).
  - **Page tab without a selection:** mode rows plus COLOR / HEIGHT / OFFSET summaries with counts (S2).
  - Report: ag-grid spreadsheet in a bottom pane ("+ Create report") with formula bar, format panel and "Auto move to cell".
- **UNK:** MM column set and row height in px. `MENU_ITEM_HEIGHT=50` exists, but that is for menus.

## 7. Interaction model: keyboard map (code is authoritative, module `uCQm`, `M@8358734`)

| Group | Keys |
|---|---|
| Tools | Select `1` / `V` · Polyline `2` · Polygon `3` · Rect 2-pt `4` · Rect 3-pt `5` · Auto Count `6` · Count `7` · Comment `C` · Sticker `N` · Dimension `R` |
| View | Zoom in `Shift + =` (shown "Shift + +") · Zoom out `-` · Home/fit `0` · pan: right/middle button or `Space`+drag |
| Drawing | `Esc` (step back / exit) · `Enter` finish · `Backspace` or `Ctrl+Z` remove last point · hold `Shift` strict angle · `Delete`/`Backspace` remove selected vertices |
| Manage | Show all `Ctrl+H` · Hide/show `H` · Focus `F` · Isolate `I` · Select all `Ctrl+A` · Unselect `Esc` · MM panel `M` · Merge `Ctrl+Alt+U` · Subtract `Ctrl+Alt+S` · Delete · Group `Ctrl+G` · Ungroup `Ctrl+Shift+G` · Duplicate `Ctrl+D` · Snapping `S` |
| Clipboard / history | Copy `Ctrl+C` · **Paste with a point `Ctrl+V`** · Paste `Ctrl+Shift+V` · Cut `Ctrl+X` · Undo `Ctrl+Z` · Redo `Ctrl+Y` / `Ctrl+Shift+Z` |

The Mac mapping comes from `isCtrlOrCommandKeyDown` (⌘ on Mac). Undo depth "up to 25 actions… reset on refresh" (Kreo blog, see the 09-17 doc); no limit constant was found in code (bounded search).

**Context menu (OBS, module `j2uI`, `M@7254425`)**, in order with filters:
- Modify (one selected)
- Group `Ctrl+G` / Ungroup
- Focus `F`
- Search for areas (AI badge)
- TraceLink
- Copy / Duplicate / Cut / Paste With a Point / Paste / Paste in the Same Place
- Hide `H` / Show
- Isolate `I`
- Delete `Del`
- Show All `Ctrl+H`
- Group to Cell / Dynamic Table to Cell / Move to Cell (submenus)
- Select Like (submenu) / Select All
- Full Screen / Exit Full Screen
- Add Comment
- Move to Group

Above the items: a style header (colour, stroke style and width, count shape) and a segmented row of 40×40 op buttons: Merge, Subtract, Extract polyline from polygon, Join Counts, Join Polyline, Enclose, Split polyline into segments. They have a 10 px outer radius; icons turn gray → turquoise on hover and scale to .8 when pressed; tooltip width 210 (`M@7263235`).

**Fly-menu (OBS, `M@8082649`):** AI "find similar areas" (max 4 polygons) · Transform ▾ (Flip V/H, Rotate ±90°) · Modify · Move To · Knife · Offset · Merge · Subtract · Enclose · Extract polyline · Split polyline · Join · Group · Trace Link. Each item has availability rules (`OnlyOneSelected`, `IsArea`, `IsLine`, `CanBoolWithPolygons`, …).

## 8. Feedback and states

**OBS:**
- **AM 2.0 progress:** the button turns into "Searching..." with a spinner; the panel shows "Searching Rooms · about 15 seconds remaining · 44 %" (S5); errors read "Try again" (`M@3472654` area); a Rive animation labelled "Searching...".
- **Results:** "Find N objects" + Create + Reset (Objects mode).
- **"Too many measurements"** warning: "You're saving too many measurements, risking performance issues…"
- **Drawing-type guard:** "Unsupported Drawing Detected" / "Based on your drawing. Our AI has determined that it is an … Auto Measure only works on residential floor plans." / "Couldn't recognize the type of drawing. You may have mistakes in results" (`M@8664130`).
- **Gating:** "The Auto Measure feature is not available. To use the feature, add the Auto Measure add-on to your account first." / "The Auto Measure Trial period has expired. Contact your company owner…".
- **Trial counter** per feature (`featureUsageCounter {autoCount, autoMeasure2, oneClickArea}`): "During the trial, you get N {feature} runs" / "You've used all N free … runs. To continue: Activate a subscription… or Contact us…", with buttons [Activate subscription] [Chat with us] (`M@4010637`).
- **AI change banner:** "What changed — Canvas updated by AI" [Undo] [Dismiss] (`M@562457`).
- **Feedback prompts:** rating + text for AM 2.0 / Magic Search; Caddie early close: "Why did you close Caddie before the response finished?" [Skip] [Send] (`M@3799314`).
- **Confirmation dialogs:** 'Are you sure you want to exit the "Upload files" Mode?' / "This action cannot be undone".

**UNK:** whether there is a toast system. No toast library string was found in a bounded search.

## 9. Onboarding and help

- **OBS:** Gleap help/feedback widget, loaded in the HTML shell (`sdk.gleap.io`), with 21 references in `main`. The help centre is also Gleap-hosted.
- **OBS:** persisted `disableShowTourList {}`, `disableShowDialogList`, `viewedReleaseNotesVersion`, `isTryAiPanelShown:false`, `hideSmallScreenDialog`, `isChatCloudDismissed`.
- **OBS:** a 35-entry tour-target enum (`selectTool` … `aiTurboBoost`, `M@758677` area).
- **OBS:** add-on "advertisement" dialogs with video, header, description, a features list and Confirm / Chat buttons. Example for Auto Measure: "Works for residential floorplans only · Applicable for vector graphics only · …".
- **OBS:** rich tooltips (title + hotkey + description, adjustable `speed`) and cursor hints.
- **OBS:** "Spot" settings (`spotHeadVisible`, `spotLiveEnabled`, `spotLiveVoice`, `spotMicrophoneConsent`), confirmed by release note R ("Hey, Spot", 2026-10-14).
  - Activation: a Spot button plus a microphone prompt, then you talk.
  - It acts on what the user points at or has selected: creates area, perimeter or length measurements, places a callout, or runs Auto Count / Find similar.
  - It answers aloud and hands multi-step jobs to Caddie.
  - Without a scale it refuses to give numbers and offers to set the scale first.
  - Pointing mechanics (cursor versus click): UNK.
- **UNK:** how intrusive tours are in practice, and how they are dismissed. Account needed.

## 10. Scale, pages, zones, renaming, Caddie

- **Scale (H + code):**
  - A reminder on unscaled pages offers manual or AI scaling.
  - **AI:** a suggested scale and one "Apply".
  - **Calibrate:** 2 clicks → length → Metric/Imperial → Apply.
  - **Standard:** "List" (paper size) + "Scale" dropdowns → Apply.
  - **Multi-page:** "Scale multiple pages", with "Select All".
  - Changing the scale recalculates every measurement. In the right panel it is a "SCALE ›" row (S2); Turbo Boost refuses to run without a scale (`M@271367`).
- **Pages (OBS):** opened pages are **thumbnail tab cards** with a red badge and a file-name subtitle, plus "+" (S2). The File Manager offers grid/list views grouped by file (`pdfManagerView:Grid`, `pdfManagerGroupBy:fileName`), quick-access open/close-all and Rasterize. **Rename with AI** works three ways: "Apply all AI names" (1 click); right-click a tab → up to three suggestions → Rename; or a custom prompt → Improve → Apply. Limit: "AI can only extract information from the drawing if there is text content."
- **Zones (OBS code, H title "Plan Zones"):** spatial-understanding controls Run / Retry / Show regions / Focus / Re-run. Regions draw as α .35 boxes. Release note R: counts default to the identified drawing regions, so matches in schedules, legends and title blocks stay searchable but create no count markers unless asked. **UNK:** region type colours (`nn.a[type]`).
- **Caddie (OBS):** chat dialog with skills (search, create, edit, duplicate, run), a "collect user choices" wizard (progress segments, Cancel / Next 24 px buttons) and a "confirm intent" panel (Looks correct / Send / Refine / Cancel). It also has fullscreen mode, chat history with pin / rename, and a trace log. Tools include `run_auto_measure_v2` "Run Auto Measure by Text" and `rename_measurements_with_ai`. The default copilot model identifier in state is `gemini38Flash` (`M@8361804`).

## 11. Read-across for Pathon (merge, not restyle)

Pathon today (P): a horizontally scrolling text toolbar (Žymėti, Laso, Atstumas, Plotas, Perimetras, Kiekis, Mastelis, …); hotkeys 2/3/4/6/L/S/U/?; Enter or double-click finishes; **Esc cancels the whole draft**; z/Backspace undoes a point; Shift = ortho + 45°; snapping to drawing and measurements with a snap kind; a right-click menu (rename, change type, delete, show in list); an outline editor (drag a vertex with wall snap, click a midpoint to insert, double-click a vertex to delete, Enter saves, Esc cancels); Nordic Slate light tokens with 2 px radius and IBM Plex; evidence crops and Lithuanian sentences beside each number.

| Kreo does | Pathon today | Verdict |
|---|---|---|
| Esc steps back one point, then exits; calibration never auto-exits | Esc throws away the whole draft | **Copy.** Less destructive for a 35–60 contractor; matches "nothing breakable". |
| Cursor-side hint sentence per mode and AI state | Yellow banners above the viewer | **Copy.** Puts the instruction at the drawing (founder rule); one line, Lithuanian, plus the cause when nothing happened. |
| Right-click while drawing → "Create / Reset" pop-up; double-click / Enter also finish | Baigti / Atšaukti buttons on canvas, double-click, Enter | **Keep Pathon's visible buttons + adopt the right-click pop-up.** Never hover-only. |
| Double-click a shape → Modify; click an edge inserts a vertex; drag an edge moves the segment; vertex pop-up Delete / Cut Path / Align | Outline editor: midpoint insert, double-click vertex = delete | **Adapt.** Keep wall snapping (Pathon is better); add a vertex pop-up with "Ištrinti" and "Iškirpti angą" (Cut Path) for doorway deductions; skip Align and Ctrl-edge-duplicate (expert features). |
| Floating fly-menu at the selection (40 px, pinned top-centre by default) | Right-click menu only | **Adapt.** 4–5 Lithuanian actions (Pervadinti, Keisti tipą, Iškirpti, Ištrinti, Rodyti sąraše) with icon **and** text. |
| Review before create: hover mask preview, AI Confidence slider, per-item Fix with AI / 👎 / 🗑, then Create | Patikra question queue with proposed answers | **Adapt.** Use hover preview and per-item ✔ / 🗑; **skip the confidence slider** (founder: no confidence as primary signal); keep the evidence sentence + crop. |
| AI Classification name chips right after a shape is created (1-click rename) | Rename through a menu | **Copy, as a question.** "Ar tai Virtuvė? [Taip] [Kita…]". |
| Random saturated 18-hue rainbow, fill α ×0.7 | Saturated blue / green / orange zone fills ("childish") | **Skip the rainbow.** Colour by meaning (room vs wall finish vs opening vs needs-check), low-alpha fill, constant 2–3 px screen stroke. |
| Labels: colour-filled pill r 11, auto white/dark text, area + perimeter | Bright green dimension-string boxes | **Adapt.** Neutral pill (white / slate) with tabular numbers; colour only on a 3 px edge. |
| One utility colour for edit handles (`#8000FF`) and one AI-preview colour (green) | Orange snap markers, purple opening bars, red dashed partitions | **Adapt.** One handle colour and one "proposed" style (dashed evergreen) across all tools. |
| Icon toolbar, grouped ▾, tooltips with name + key + sentence; AI tools as labelled pills | Scrolling text buttons | **Adapt.** Icon + short label for the 4 core tools; overflow ▾ for the rest; tooltip = key + one sentence. |
| Digit hotkeys `1`–`7` (3 = polygon, 7 = count) | 2 = distance, 3 = area, 4 = perimeter, 6 = count, `S` = walls layer | **Adapt.** Keep 3 = area; consider `1` = select. Do **not** bind `S` to snapping (Pathon uses `S` for walls). |
| Zoom cluster floating bottom-right + minimap + marquee zoom | Status bar with the scale sentence | **Copy the cluster**, keep the scale sentence (Pathon explains the scale; Kreo only shows a row). |
| Property sheet per selection (Name … Volume) | Evidence sheet: crops + Lithuanian sentences | **Pathon is ahead.** Borrow only the compact two-column label/value rhythm. |
| "What changed — Canvas updated by AI" [Undo] [Dismiss] | History panel | **Copy** for lane re-reads and AI proposals. |
| Dark default, eight tones, Proxima Soft, 10–20 px radii | Light Nordic Slate, IBM Plex, 2 px | **Skip.** Professional feel comes from grammar and density, not dark chrome. Adopt a 14 px base and tabular numbers. |
| Thumbnail tab cards for open pages | Left thumbnail rail with page-type chips | **Pathon is better** for multi-sheet Lithuanian sets; skip. |
| Trial counters and add-on upsell dialogs | Billing built, not live | **Skip for now.** Revisit with the payment wall. |

**INF, design direction:** merge Kreo's *grammar* (step-back Esc, cursor hints, fly-menu, vertex pop-up, review-before-create) with Togal-style one-button AI, on top of Pathon's evidence-first sheet. That combination is something neither competitor ships.

## Checklist status

"Walkthrough" = needs the founder's logged-in session (the manager runs it separately; this worker never logs in).

| # | Question | Status (public sources) | Walkthrough needed for |
|---|---|---|---|
| 1 | Layout anatomy | **partial**: regions, order and positions observed | exact panel widths and docking in the current build; MM default position |
| 2 | Design tokens | **answered** (colours, tones, shadows, motion, type, radii, overlay tokens, libraries) | only to eyeball the light theme and tones |
| 3 | Click vocabulary (founder addendum) | **answered** from code for every mode; correction click counts are INF | timing the five corrections (W3) and the right-drag versus menu threshold |
| 4 | Toolbar and tools | **answered** (order, icons, keys, tooltips, gating) | icon artwork and the overflow behaviour at narrow widths |
| 5 | Overlay rendering | **mostly answered** | real fill opacity and the hover/selected stroke change (W1) |
| 6 | Measurements Manager / right panel | **partial** | MM columns, row height, drag-drop feel (W2) |
| 7 | Interaction model / keyboard / context menus | **answered** | none (code is authoritative) |
| 8 | Feedback and states | **mostly answered**; toast system UNK | toasts, empty states, canvas AM progress (W4) |
| 9 | Onboarding / help | **partial** | tour intrusiveness and dismissal (W5) |
| 10 | Scale, pages, zones, Rename with AI, Caddie, Spot | **mostly answered**; zone colours UNK | zone colours; the AI Classification chip menu in practice |
| 11 | Read-across for Pathon | **answered** (section 11) | confirm the "copy" rows by feel |

## Questions for the logged-in walkthrough (founder's session; business trial)

- **W1.** Draw one polygon: screenshot the default, hover, selected and Modify states. What fill opacity do you see? (Code: fill = colour α × 0.7.) Does the stroke thicken on select?
- **W2.** Measurements Manager: where does it open; which columns; row height; does the ✎ rename work inline; does drag-drop into a folder recolour the shape?
- **W3.** Time the five corrections from section 3 (rename/regroup, fix a vertex, remove a false count, cut a doorway from a wall-finish line with **Cut Path**, re-run Auto Measure on one sheet). Count the clicks against my estimates of 1–3 / 3 / 4 (or 1 before Create) / ~8 (or 1 with "Remove Doorways") / ~6.
- **W4.** Run Auto Measure 2.0 on one floor plan: what shows on the canvas while it runs, how long it takes, what the "AI Confidence" slider does visually, and whether "Fix with AI" is usable.
- **W5.** First run: which tours or dialogs appear and how they close; what happens on a page with no scale (reminder copy).
- **W6.** Right-button drag versus right-click menu; touchpad pinch/two-finger behaviour; whether Esc really steps back one point (code says yes).
- **W7.** Knife: clicks to finish, and whether the original shape is kept.

## 12. Logged-in walkthrough (2026-10-18, business trial, demo project)

**Legend for this section.** **LIVE** = I did it in the founder's signed-in Kreo session (Claude desktop browser pane, viewport emulated at 1440×900 unless stated) and saw the result. Measurements come from `getBoundingClientRect` / `getComputedStyle`; persisted defaults come from reading `localStorage["persist:kreo_state"]` (inspection only, nothing written). **PENDING** = needs a drawing on the canvas (see 12.0).

### 12.0 Setup, and what blocked the drawing half

- **Demo projects are templates without drawings (LIVE).** Clicking a card in "Demo projects" (bottom-left of the projects page) at once copies it into "My projects" and opens it. I opened three: **Painting** (project 293178), **Flooring** (293179) and **General Contractor Project** (293180). For all three, `GET …/drawings/filesystem` returned `{"folders":[],"files":[]}` and the project's `viewModelsStatuses` showed `DrawingsCopy: Empty`. What a demo actually contains is a measurement-group tree plus a report: Painting has a "Spreadsheet" tab with a priced bill (codes 1.1–1.3, m², rate); Flooring and General Contractor have a pivot "Takeoffs/Items Report". The demo list API (`/demo-projects/Project2D`) lists 17 projects, each with only a name, tags and a logo.
- The empty canvas offers three cards: "Open File Manager", "Upload New Files" and "Upload Map View". Map View opens an OpenStreetMap picker with a "Create a Snapshot" button. That snapshot would be Kreo-generated, public map data, but the permission layer refused it as an unrequested commit. I did not retry it and I uploaded nothing.
- **So W1, W3, W4, W6, W7 and the scale checks are PENDING** until a non-confidential drawing exists in one of these copies. Everything below that needs no drawing was walked in **General Contractor Project**.
- **Instrument caveat.** The browser pane was hidden for this session. In that state the pane screenshot often showed the frame *before* the last action. Twice a menu I had already closed was still in the picture, and once a context menu showed only after the next key press. Every claim below was checked against the DOM, not only against a screenshot. Hover tooltips rendered in the Measurements Manager (MM) but **not on the toolbar while no page is open**. The toolbar is inert without a page: digit keys and the ▾ chevrons do nothing.
- **Side effects left in the account:** the three demo copies above. My test group ("New Group", renamed "Walk test", moved into "Internal Finishing") was deleted again, so the tree is back as shipped, except that "Internal Finishing" is now expanded. No AI run was used: `featureUsageCounter {autoCount:0, autoMeasure2:0, oneClickArea:0}`.

### 12.1 Layout anatomy as shipped (LIVE, measured)

At 1440×900, with no page open:

| region | x, y, w × h (px) | background | notes |
|---|---|---|---|
| Row 1 top nav | 0, 0, 1440 × **25** | `#1D2733` | Project · Plans · Assemblies · Skills (12 px; the active tab is a `#222E3C` chip with 5 px top radius). Project name centred (14 px). Settings (14/500) · ? · Share pill (120 × 24) on the right |
| Row 2 header | 0, 25, 1440 × **61** | `#222E3C` | Logo; page-search magnifier (40 × 50); a large ⊕ = open File Manager (40 × 40, where the page tabs sit); notifications 20 px; comments 20 px; avatar |
| Row 3 toolbar | 0, 86, 1440 × **40** | `#222E3C` | Undo / Redo 45 × 40 at the far left; tools centred (12.3); far right: measurement-count badge "0" + a 40 × 40 **MM toggle** |
| Body | 0, 126, 1440 × 774 | — | a three-way splitter |
| **MM, docked left** | 0, 126, **340** × (top split) | `#222E3C` | `drawings-legend-splitter`; persisted `DrawingLayoutSize: 340` |
| Canvas | 340, 126, **820** × (top split) | `#1D2733` | empty state: three 147 px cards |
| **Report pane, bottom** | 0, 428, 1160 × **472** | `#1D2733` | open by default; persisted `ReportPaneSize ≈ 459`; tab bar 38 px; ag-grid header 32 px, 14/600 |
| Right panel | 1160, 126, **280** × 774 | `#222E3C` | persisted `ManagePaneSize: 280`. **Empty** when nothing is selected and no page is open. With a group selected it shows Assemblies: "No applied items and assemblies yet · Choose from the library · Create from scratch" |
| Zoom cluster, minimap, fly-menu | — | — | PENDING (they need a page) |

At **1280×720**: chrome is still 126 px. MM stays 340 and the right panel stays 280. **The canvas shrinks to 660 × 250** and the report pane takes 1000 × 340. **Nothing collapses:** the AI pills keep their text labels and no tool moves into an overflow. The splitter positions are persisted, so after resizing back to 1440 the panes did not return to their first-load sizes.

**Type and rows (LIVE, computed styles):**
- One family, `ProximaSoft, Helvetica, Arial`.
- MM row: **24 px tall on a 28 px pitch** (4 px gap), 325 px wide, radius 6. Name 14/21 px weight 400 white, **truncated at 100 px** ("Structural Co…", "Internal Finish…"). Each nesting level indents by **20 px**.
- MM row controls, all 20 × 20 on 30 px pitch:
  - expand chevron (28 × 20);
  - count "0", 12 px turquoise `#2974AD`;
  - colour picker (a ring when the group has no colour);
  - "+" create-new, a filled turquoise circle;
  - eye (tooltip "Hide");
  - an **author-initials avatar "IG" with 7 px text**;
  - a final icon whose tooltip reads "No entities are applicable" while the group is empty.
- Row hover: background drops to `#1D2733` and a **pin** button appears (tooltip "Pin").
- Selected row: background `#293849` with a **1 px `#2974AD` ring**. **The parent group's name turns turquoise** to show where the selection lives.
- MM header: 8 icon buttons 20 × 20 at 30 px pitch: menu · add-new-group · duplicate-groups · move-to-group · expand-all · sort · rename-tool · filter. Below them a "Current page" chip (12 px) and, at the bottom, a 40 px "Search in measurements" field.
- Tooltip: card `#222E3C`, **radius 15**, padding 8 × 30, `xl` shadow, 12 px text, about 30 px above its target.
- Context menu: 242 × 226, radius **20**, items 40 px tall, 14 px text.
- Report tabs: the **active report tab is red `#FF3F3F` text with a red underline**, not the turquoise accent.

### 12.2 Toolbar as shipped (LIVE)

From the left (x at 1440): Undo · Redo │ **Select** (375) · **Polygon** (413) ▾ · **Polyline** (469) ▾ · **Count** (525) │ **One-click Area** pill 167 × 30 (588) · **Auto Count** pill 145 × 30 (763) │ **Legend annotation** (941) ▾ · **Comment** (997) · **Callout** (1035) … far right: count badge + MM toggle.

- Tool tiles are 30 × 30 with **7 px radius**. Idle icon `#79A5D6`; **active = filled `#2974AD` tile with a white icon**.
- **There is no One-click Line button and no separate rectangle buttons.** The rectangle tools sit under Polygon ▾. One-click Line is presumably under a ▾ or gated (PENDING).
- In-app Shortcuts dialog (Help ? → Shortcuts; 1008 × 504, radius 30, tabs Tools / General / Navigation / Spreadsheet). Its Tools tab reads exactly: Select `1` or `V` · Polyline `2` · Polygon `3` · Rectangle 2 points `4` · Rectangle 3 points `5` · Auto Count `6` · Count `7` · Sticker `N` · Dimension Line `R` · Comment `C`. This **matches §7**.
- Help ? menu: Chat with us · Referral program · Help Center · What's New · Video Tutorials · Shortcuts.

### 12.3 Measurements Manager (W2, LIVE, without measurements)

- **Where it opens:** **docked as a left column (340 px)** under the toolbar, beside the canvas and above the report pane. It is not a floating window and not bottom-right. Persisted `isOpenDrawingsAnnotationLegendPanel: true`. A separate floating `entityPanel {show:true, position:null}` also exists in state, but nothing floating was on screen.
- **Toggle:** key **`M` works** (verified both ways), and so does the 40 px monitor icon at the far right of the toolbar, next to the measurement-count badge.
- **Create a group:** **1 click** (header "add-new-group"). It appears at the bottom of the tree named "New Group", about 1 s later (a server round trip), and is **not** in edit mode.
- **Inline rename:** **double-click the name** turns the row into a borderless 14 px input with the **caret at the end and nothing pre-selected**. Cmd+A did not select inside it (Kreo binds Ctrl/Cmd+A to "select all measurements"). I cleared it with Backspace, typed, and **Enter committed**. Cost: double-click + clear + type + Enter. (Help says double-click a row = isolate; on a group row it is rename.)
- **Drag into a folder:** **one plain mouse drag** of a row onto another group nests it, indented 20 px, and collapses the target. It worked with a synthetic drag; no drop indicator was captured.
- **Recolour on move: not testable** (no shapes). The moved group kept "no colour".
- **Context menu on a selected group:** Delete `Del` · Group to Cell (disabled) · Dynamic Table to Cell (disabled) · Full Screen · Move to Group. A right-click on a row that was not selected showed nothing; a left-click first was needed.
- **Delete an empty group:** immediate, **no confirmation, no toast**. The Undo arrow turned turquoise (`#2974AD` = available).
- **⋮ menu:** toggles Search · Hide empty groups (off) · Show only groups (off) · **Pivot (on)**; actions Select All · Templates ▸ · Invert selection · Delete empty groups.
- **Columns:** the MM has no column header. Each row is name + count + controls. The quantity columns (Area / Perimeter / Count / Qty / Rate) live in the **bottom report pane** (ag-grid, pivot, "Level 1 / Level 2 Grouping" chips, a Columns/Filters side bar).
- **Two-way highlight, isolate, visibility on shapes:** PENDING.
- Demo template colours come from the same 18-hue random palette as §5 (`#7FFF3F`, `#FF3F3F`, `#3F3FFF` on Floor Tiling / Wall Painting / Ceiling Painting).

### 12.4 Settings dropdown (LIVE)

A **360 × 820 dropdown** from the top bar's "Settings", not a right-panel tab as S4 suggested. Defaults as seen:
- **Unit system:** Metric (on) / Imperial.
- **Snapping:** Enable snapping **on** · Line Intersection off · Line Midpoint off · **Path EndPoint on** · Point On Line off · Dynamic Guideline off · Orthogonal Mode off.
- **Drawing:** **Pin the flymenu at the top on** · Black and white off · Night mode off · **Show Dimensions on** · **Display Thickness on** · Show Text Links off · **Opacity 100 %**.
- **Measurements:** Keep Names off · Auto Focus off · **Keep Structure on**.
- **3D:** Orthographic · Fill Opacity 80 % · Show Drawing · Drawing Opacity 50 % · Drawing Offset 0 · Measurements above drawings.
- "Reset to default" sits top-right.

This matches the code defaults in §5. "Rotate" was not listed while no page was open. **Esc does not close it**; only clicking "Settings" again does.

### 12.5 Tours, dialogs, help (W5, LIVE)

- **No tour, coach-mark or modal appeared** on the projects page, the demo picker, three first project openings or a reload. Persisted `disableShowTourList: {}` (no tour dismissed), `isTryAiPanelShown: false`, `viewedReleaseNotesVersion: null`, `hideSmallScreenDialog: true`. Tours, if any, must be tied to opening a page or a tool (PENDING).
- The Gleap chat bubble sits bottom-right (about 45 px circle, `#2974AD`).
- **Feedback state seen:** after about 3 minutes idle, a red pill appeared at top centre, "Oops, you seem to be offline. Please go online to view this page [Refresh]". `navigator.onLine` was `true`. The pill blocked project opening until I pressed Refresh, which reloads the page. Likely a dropped SignalR or socket connection in the hidden pane.
- **Page search (header magnifier):** a popup "Start typing · No results found · → Open the File Manager". Neither Esc, nor a click outside, nor the magnifier closed it; only a reload did. That fits the dropdown pattern in 12.4.

### 12.6 Keyboard and Esc with no page (LIVE)

- `M` toggles the MM.
- `3` does nothing without a page (the tool stays on Select).
- **Esc closes context menus but not the dropdowns** (Settings, page search, help).
- The Esc step-back while drawing (W6) is PENDING.

### 12.7 Persisted defaults worth knowing (LIVE, `persist:kreo_state`)

- `drawingNewInstanceStrokeWidth: 6`, `countStyle: "Shape"`, `drawingSnappingModes: [8]` (Path EndPoint), `drawingAutocomplete: false`.
- `drawingUseGroupNameForNewGeometry: true`: a new shape takes its group's name.
- `aiClassificationEnabled: true`: name chips on by default.
- `drawingsAutoMeasureVersion: 2`, `drawingsAutoMeasure2DoorWays: true`, `…IngoreDoors/IngoreWindows: true`, `…RemoveWindowsMode: "full_height"`, `drawingsAutoMeasure2SelectedClusterTypes: ["By Size"]`, `drawingAm2DoorExportType: "Center line"`.
- `selectedFilterPages: "current"`, `selectedMeasurementSort: createdAt ascending`, `drawingMeasurementsPivot: true`, `showTableUnits: true`, `showTableTotal: false`.
- `spotHeadVisible: true`, `spotLiveEnabled: true`, `spotLiveVoice: "Achird"`, `spotMicrophoneConsent: null`.
- `magicSearchDpi: 300`, `drawingMinimapOpened: true`, `drawingEngineViewMode: "split"`.
- Keep-original flags all false: `drawingSplitKeepOld`, `drawingIsKeepPolygon`, `drawingIsKeepBasePolygon`, `drawingIsKeepSubtractedPolygon`, `drawingOpenKeepOld`. **So Knife, Subtract and Open discard the original by default** (W7 still needs the live check).

### 12.8 Doc corrections so far (code or doc said / the app does)

| # | Earlier sections said | Live app |
|---|---|---|
| 1 | MM is a floating, movable window; help: bottom-right (§1, §6) | **Docked left column, 340 px**, in a splitter; toggled by `M` or the far-right toolbar icon with the count badge |
| 2 | Chrome rows ≈35 / 70 / 45 px (§1, from screenshots) | **25 / 61 / 40 px** = 126 px of chrome |
| 3 | Right panel ≈300 px with mode rows (§1) | **280 px**; empty with no page; Assemblies when a group is selected |
| 4 | Report pane collapsed ("+ Create report") (§1) | **Open by default**, ≈459 px tall (more than half the body at 900 px); demo templates ship a report or spreadsheet tab |
| 5 | Toolbar shows One-click Area · One-click Line · Auto Count; 10 px radii (§1, §4) | Only **One-click Area** and **Auto Count** pills; tiles **7 px** radius; active = filled `#2974AD` tile |
| 6 | Settings is a right-panel tab (S4) | **Top-bar dropdown**, 360 × 820; Esc does not close it |
| 7 | Double-click an MM row = isolate (§6, help) | On a **group** row, double-click = **inline rename** (caret at end, no pre-selection) |
| 8 | MM columns / row height UNK (§6) | No columns in the MM; **24 px rows, 28 px pitch, 14 px names cut at 100 px**; quantities live in the report grid |
| 9 | Demo projects would carry drawings (walkthrough plan) | **Templates only**: groups plus a report, no files |
| 10 | Tooltips "title + hotkey + description" (§9) | MM tooltips are one word ("Pin", "Hide"); toolbar tooltips did not render with no page (PENDING with a page) |
| 11 | Accent = turquoise everywhere (§2) | The **active report tab is red `#FF3F3F`**, a second accent |
| 12 | Toast system UNK (§8) | No toast after delete or create; the only banner seen was the red "offline" pill |

### 12.9 Updated checklist (after the no-drawing half)

| # | Question | Status now | Still open |
|---|---|---|---|
| 1 | Layout anatomy | **answered (LIVE)** for chrome, MM, report pane and right panel at 1440×900 and 1280×720 | zoom cluster, minimap and fly-menu positions (need a page) |
| 2 | Design tokens | answered; LIVE adds 7 px tool radius, 15 px tooltip radius, 20 px menu radius and the red report-tab accent | — |
| 3 | Click vocabulary | answered from code; **corrections W3 PENDING** | the five timed corrections, right-drag versus menu |
| 4 | Toolbar and tools | **answered (LIVE)**: shipped order, pills, no One-click Line button, no collapse at 1280 | toolbar tooltips with a page open |
| 5 | Overlay rendering | mostly answered (code) | **W1 PENDING** |
| 6 | Measurements Manager / right panel | **answered (LIVE)** for docking, rows, rename, drag-to-folder, menus | two-way highlight, isolate, recolour on move (need shapes) |
| 7 | Keyboard / context menus | answered; LIVE confirms the Tools tab and `M`; Esc does not close dropdowns | Esc step-back while drawing (W6) |
| 8 | Feedback and states | mostly answered; LIVE adds the offline pill, no toasts | W4 Auto Measure progress |
| 9 | Onboarding / help | **answered (LIVE) for first open**: no tours or modals; help menu items listed | tours tied to opening a page or tool |
| 10 | Scale, pages, zones, Caddie, Spot | mostly answered (code) | scale UI live (needs a page) |
| 11 | Read-across | answered (§11) | confirm after W1/W3 |
