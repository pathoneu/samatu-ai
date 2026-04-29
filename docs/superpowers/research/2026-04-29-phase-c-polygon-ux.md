# Phase C — Polygon-Editor UX Research

**Date:** 2026-04-29
**Author:** Research subagent (Opus 4.7, 1M)
**Scope:** Interaction design for the manual polygon trace + edit tool that will replace unreliable Vision `bbox_pct` highlighting in Sąmatų AI's PDF workspace. This document is the *interaction layer* spec — the rendering stack (react-pdf + react-konva) and the competitor architecture are already locked, see:
- `docs/superpowers/research/2026-04-29-phase-c-libraries.md` (stack decision)
- `docs/superpowers/research/2026-04-29-phase-c-competitor-tech.md` (competitor reverse-engineering)
- `docs/superpowers/research/togal-ux-patterns.md` (P-pattern catalogue)

This file fills the remaining gap: *how the user's mouse and keyboard should behave when tracing a room*.

---

## 0. Executive recommendation (one paragraph)

**Build a Bluebeam-style polygon tool on react-konva, with one explicit twist for floor plans: orthogonal mode ON by default.** Concretely: the user presses `P` to enter trace mode, clicks corner-by-corner, sees a rubber-band preview with a 90° guideline (Shift toggles free-angle). The polygon closes on `Enter`, `Double-click`, or click-on-first-vertex (whichever comes first — accept all three, never require pixel-perfect return). `Esc` cancels mid-edit; `Backspace` removes the last vertex. After commit, vertices become draggable circles with a 16-px hit radius and a 24-px touch radius; clicking on a polygon edge inserts a new vertex at the click point; selecting a vertex and pressing `Delete` removes it. Snap-to-vertex on adjacent rooms is on by default (12 px tolerance, fades to a 4 px crosshair when active). Snap-to-edge from a Hough/Canny pre-pass on the rendered PDF is a v2 feature — get the manual flow shipped first because that single pass already replicates 80% of Bluebeam's perceived precision. Use existing `react-konva` (it's in the stack and the edit ergonomics are best-in-class for our scale) — do **not** introduce Fabric.js or paper.js. Mobile is not a v1 target: ship a "use desktop" banner and finish iPad polish in a later sprint when we can budget a magnifier loupe and a separate vertex-handle layer with 44 px touch targets.

---

## 1. Per-tool teardown — what the leaders actually do

### 1.1 Bluebeam Revu (the AEC reference)

Bluebeam's polygon tool is the *de facto* mental model for every construction estimator who's ever done a takeoff. Match it where it makes sense; deviate only with a reason.

| Action | Behaviour |
|---|---|
| Enter polygon mode | `Shift+P` |
| Place vertex | Single click |
| Remove last vertex | `Backspace` |
| Close polygon (3 paths!) | (a) click first vertex, (b) press `Enter` twice, OR press `C`, (c) double-click on last placement |
| Orthogonal constraint | Hold `Shift` while moving cursor — locks to 0°/45°/90° |
| Snap to existing geometry | Toggle "Snap to Content" globally; combine with `Shift` for ortho-on-snapped lines |
| Edit after drawing | Select shape → yellow control handles appear at every vertex |
| Curve a segment | `Ctrl`+drag on a yellow handle |
| Insert/remove vertex | Right-click handle → "Add/Remove Control Point" |

**What they got right:** Three independent ways to close the polygon. A pro uses double-click; a beginner clicks back to start; a keyboard-first user hits Enter. Nobody is forced to hunt the start vertex pixel.

**What they got wrong (or quirky):** Curving a polygon edge with `Ctrl`+drag is a hidden feature; most estimators discover it years in. We have no curved-room use case, so skip it.

> Source: [Bluebeam Polygon Tool docs](https://support.bluebeam.com/online-help/revu21/Content/RevuHelp/Menus/Tools/Markup/Polygon-Tool--MTV.htm), [Bluebeam Modifier Keys](https://support.bluebeam.com/articles/revu-use-modifier-keys-efficiently/), [Bluebeam Snap docs](https://www.brightergraphics.com/guides/how-to-use-snap-feature-in-bluebeam-revu).

### 1.2 PlanSwift / OST (legacy desktop takeoff)

PlanSwift's "wall trace" and area takeoff confirm the same skeleton:

- Linear takeoff = click-click-click; **double-click on final point** to commit and stay in record mode (so you can immediately start the next polygon).
- `Backspace` undoes the last point. `Ctrl+Z` undoes the last *polygon*.
- They expose every shortcut as user-rebindable hotkeys. Pros remap.

**Lesson:** Distinguish vertex-undo (`Backspace`) from operation-undo (`Ctrl+Z`). Bluebeam does this; PlanSwift does it; we should too.

> Source: [PlanSwift hotkeys](https://defkey.com/planswift-shortcuts), [PlanSwift Linear Takeoff](https://help.constructconnect.com/03-a-detailed-look-at-the-home-tab-and-drawing-takeoff-and-annotations-176/planswift-03-11-02-using-the-linear-takeoff-connected-segments-tools-1810).

### 1.3 Togal.AI (auto-detect first, edit second)

Togal's primary flow is *not* manual draw — they auto-segment, then the user edits. Their 2025 release notes explicitly call out a fully rewritten snapping engine with edge-snap, 22.5°/45° angle constraints, and percentages. Mode indicator is a giant green pill at the top.

**What they got right:** The user's default action is *accept/edit*, not *draw*. Single-click acceptance of a suggested polygon. After acceptance, vertices are editable identically to a manually drawn polygon — no separate "auto vs manual" mode.

**What we should copy verbatim:** Vision suggestions and manually drawn polygons must live in the **same edit model**. If the user fixes a Vision-detected room, it should feel exactly like fixing a manually drawn one. No separate UI.

> Source: [Togal 2025 Features Roundup](https://www.togal.ai/blog/2025-features-roundup), [Togal Release Notes Jan/Mar 2025](https://help.togal.ai/release-notes-january-25-2025).

### 1.4 AutoCAD (the gold standard for vertex editing)

AutoCAD's `PEDIT` and grip-edit conventions have been baked into estimator muscle memory for 40 years. Specifically:

- Right-click on a vertex grip → "Stretch Vertex / Add Vertex / Remove Vertex". This is the de-facto mental model.
- `F8` toggles Ortho mode globally (not just while drawing). Many estimators leave it on.
- `C` closes a polyline (typed at command prompt; equivalent to Bluebeam's `C`).
- Grips are blue/green squares; hovered grip turns red; selected grip turns red+filled. Very legible.

**What we should copy:** The right-click-on-vertex menu pattern. Estimators expect it. A vertex's right-click menu should expose: Insert vertex before / Insert vertex after / Delete vertex / Set as start.

> Source: [AutoCAD Modify Polylines With Grips](https://knowledge.autodesk.com/support/autocad/learn-explore/caas/CloudHelp/cloudhelp/2015/ENU/AutoCAD-Core/files/GUID-2070C02C-E18A-4333-BDC4-240F49F1C102-htm.html), [AutoCAD PEDIT](https://knowledge.autodesk.com/support/autocad/learn-explore/caas/CloudHelp/cloudhelp/2015/ENU/AutoCAD-Core/files/GUID-6242DF04-BD00-4A5D-891C-B131184D0D36-htm.html).

### 1.5 Figma / Adobe Illustrator (consumer pen-tool conventions)

Both use `P` for the pen tool, both close on click-on-first-vertex (with a small circle indicator), both accept `Enter` to finalize an open path. Illustrator's `Esc` to interrupt mid-edit is universally expected by anyone who's ever touched design software.

**Bezier vs straight-only?** Figma/Illustrator default to Bezier with implicit control handles. **For floor plans we want straight only.** Bezier handles confuse estimators and slow them down. If we ever need curved walls we add it later as a `Ctrl`+drag affordance (Bluebeam style); ship straight-only first.

> Source: [Figma Pen Tool](https://help.figma.com/hc/en-us/articles/360039957634-Edit-vector-layers), [Illustrator Pen Tool ESC](https://community.adobe.com/t5/illustrator-discussions/keyboard-shortcut-to-interrupt-pen-tool/m-p/9160797).

### 1.6 Google Maps polygon drawing (the consumer pattern)

Maps trains the broader public: click to place vertices, **double-click to finish**. Right-click removes the last vertex. After completion the polygon is editable: every vertex is a small circle; every edge midpoint is a slightly smaller "ghost" circle that becomes a real vertex when dragged. **This midpoint-ghost-vertex pattern is the cleanest insert-vertex affordance in the industry — it's what we should copy.**

> Source: [Google Maps Polygon Auto-Completion](https://developers.google.com/maps/documentation/javascript/examples/polygon-autoclose), [Google Maps Drawing](https://developers.google.com/maps/documentation/javascript/shapes).

### 1.7 CVAT / V7 / Roboflow (image annotation tools)

| Action | CVAT | Roboflow | V7 |
|---|---|---|---|
| Finish polygon | `N` (also opens another) | Double-click OR click-first-vertex | Click-first or `Enter` |
| Cancel mid-edit | `Esc` | `Esc` | `Esc` |
| Edit existing | `Shift`+click → enters edit mode | Click polygon | Click polygon |
| Auto-bordering / snap to nearby polygon | Hold `Ctrl` while drawing | SAM-based smart-fill | Auto-Annotate (model-based) |

**What CVAT got right:** `Ctrl`-held auto-bordering — when you're drawing a polygon adjacent to an existing one, holding `Ctrl` makes new vertices snap to the existing polygon's edge. **This is exactly what we need for adjacent rooms sharing a wall.**

**What Roboflow/V7 got right:** SAM/AI single-click region acceptance. Out of scope for v1 — but the UI pattern (hover preview → click to commit) is what we should reach for once we replace Vision-derived bboxes with deterministic flood-fill (per `2026-04-29-phase-c-competitor-tech.md`).

> Source: [CVAT Shortcuts](https://docs.cvat.ai/docs/manual/advanced/shortcuts/), [CVAT Polygon Annotation](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/annotation-with-polygons/), [Roboflow Smart Polygon](https://docs.roboflow.com/annotate/use-roboflow-annotate/enhanced-smart-polygon-with-sam).

### 1.8 Mapbox-GL-Draw / Leaflet.draw

Both ship the same `MapboxDraw.modes.draw_polygon` API: click vertices, double-click or Enter to finish, Esc cancels, vertex drag works after drawing, midpoint ghosts insert vertices. **Mapbox-GL-Draw has zero snap support out of the box** — the entire snapping ecosystem is third-party plugins (geoman, route-snapper). For our use case (floor plans, not maps) we'd be importing a 200KB map engine just to render a static PDF. Not worth it; build native on Konva.

> Source: [Mapbox GL Draw Modes](https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/MODES.md), [MapLibre Geoman vs Mapbox GL Draw](https://geoman.io/blog/maplibre-geoman-vs-mapbox-gl-draw).

---

## 2. Library comparison matrix (focused on polygon edit ergonomics)

The deeper analysis is in `2026-04-29-phase-c-libraries.md` — this matrix is *only* about manual polygon-edit fitness.

| Library | Bundle (gzip) | Out-of-box polygon edit | Snap support | Edit ergonomics for our case | Verdict |
|---|---|---|---|---|---|
| **react-konva** (current) | ~70 KB | ✅ Line + Circle vertex pattern, well-documented | ❌ build it (50-80 LOC) | Imperative drag with `useRef.position()` is exactly the right pattern; reconciles cleanly with React state on `dragend` | **Adopt** |
| Fabric.js | ~120 KB | ✅ Built-in `controls` API for vertex editing | ❌ no native edge-snap | Older API, leaks if `dispose()` skipped, hit-graph less precise | Skip |
| paper.js | ~140 KB | ✅ great vector math (boolean ops, `simplify()`) | ❌ build it | Beautiful for free-form drawing; overkill for floor plans where we want straight lines | Skip |
| Pixi.js (WebGL) | ~110 KB | ❌ no scene primitives — you build everything | ❌ build it | 60 fps wins are irrelevant at our polygon counts; debug DX is worse | Skip |
| Mapbox-GL-Draw | ~200 KB + map engine | ✅ first-class | ❌ plugins only | Drags entire map engine for a static PDF | Skip |
| Leaflet + Leaflet.draw | ~180 KB | ✅ first-class, easier than Mapbox | ❌ plugins only | Same problem — map engine for non-map use case | Skip |
| Raw SVG + React | 0 KB | ❌ build everything | ❌ build it | DOM event reflow kills perf past ~300 elements; we already have ~12 rooms × ~25 positions = 300 | Skip |
| OpenLayers | ~250 KB | ✅ via `ol/interaction/Modify` | ✅ via Snap interaction! | Best-in-class snap among map libs; but again, map engine for floor plans | Skip |

**Pick: react-konva.** It's already in the stack, edit ergonomics are excellent with the Line+Circle+midpoint-ghost pattern, and there's a working CodePen reference for editable polygons we can lift verbatim.

> Sources: [Konva Editable Polygon CodePen](https://codepen.io/akitanak/pen/wEMQvL), [Konva polygon annotation tutorial (DevMuscle)](https://devmuscle.com/blog/react-konva-image-annotation), [Konva polygon discussion #1075](https://github.com/konvajs/konva/discussions/1075).

---

## 3. Critical interaction details — what to ship

### 3.1 Vertex placement: single click

Click-to-add. Drag-to-add adds bezier handles which we don't want. Stay strictly click-to-place. *Exception:* if user holds mouse-button down and drags > 5 px, treat as a pan, not a vertex placement (so accidental clicks don't drop spurious vertices).

### 3.2 Closing the polygon: accept all three ways

Never force the user to hit the start vertex pixel-perfect. Accept:
- **Click on the first vertex** (with 12 px snap radius — first-vertex circle gets a yellow halo when cursor is in range)
- **Double-click anywhere** (places final vertex + closes)
- **`Enter` key** (closes between current cursor and first vertex)

If the polygon has fewer than 3 vertices when close is attempted, ignore and beep (visual flash on the first vertex).

### 3.3 Mid-edit cancel: Escape

`Esc` discards the in-progress polygon entirely. Show a tiny toast: "Atšaukta" (Lithuanian per project rules). No confirmation dialog — undo recovers it.

### 3.4 Vertex drag with snapping

After commit, every vertex becomes a Konva `Circle` (radius 6 visible, hit-area 12 desktop / 22 touch). Drag updates a single point in the polygon's `points` array via `useRef` + `Layer.batchDraw()`; commit to React state on `dragend`. Snap targets in priority order:
1. Vertex of any other polygon on the same page (12 px tolerance) — visual: target vertex glows cyan
2. Edge of any other polygon (8 px tolerance) — visual: cyan dot at the snap location with the edge highlighted
3. Detected wall lines from a Hough/Canny pass on the rendered page (v2; 6 px tolerance) — visual: dashed cyan line
4. Grid (only if user has set a scale and enabled grid) — visual: faint dot
5. Free (no snap) — visual: nothing

Snap can be temporarily disabled by holding `Alt` (Bluebeam: "Hold Alt to ignore snaps").

### 3.5 Insert vertex: midpoint ghost on hover

On every committed polygon edge, render a smaller "ghost" circle (radius 4, opacity 0.4) at the midpoint when the polygon is selected. Hovering the ghost makes it solid; clicking-and-dragging creates a real vertex at the click point. **This is the Google Maps pattern.**

Alternative: right-click anywhere on an edge → context menu → "Įterpti tašką". Both should work; pros use the right-click, beginners use the ghost.

### 3.6 Delete vertex: select + Delete

Click a vertex to select (it turns red-filled). `Delete` or `Backspace` removes it. Right-click on vertex → "Pašalinti tašką". Polygons with 3 vertices reject the delete (minimum triangle); show flash + tooltip "Polygonui reikia mažiausiai 3 taškų".

### 3.7 Multi-select vertices

`Shift`+click on additional vertices adds them to selection. Drag any selected vertex moves the whole selection together (preserving relative offsets). `Esc` deselects.

This is critical for fixing a wrong-by-translation polygon — frequently the AI gets the room shape right but offset by a few pixels, and the user wants to grab all 4 corners and shift together.

### 3.8 Orthogonal-90° mode (the floor-plan-specific killer feature)

**Default ON.** Floor plans are overwhelmingly axis-aligned. Auto-snap each new edge to the nearest 90° from the previous edge's direction (within ±15° tolerance — beyond that, accept the user's intended angle). Hold `Shift` to *force* ortho even at large angles; hold `Alt` to *temporarily disable* ortho for diagonal walls.

Visual feedback: when the rubber-band edge is being ortho-snapped, render it with a small "⊥" badge near the cursor.

This single behaviour will eliminate ~80% of the "polygon looks crooked" complaints estimators have with consumer pen tools.

### 3.9 Undo/redo granularity

Two scopes:
- **In-progress polygon:** `Backspace` removes last vertex (single-step undo within the current draw operation)
- **Committed polygon:** `Ctrl/Cmd+Z` undoes the last *operation* (close polygon, drag vertex, insert vertex, delete vertex, delete polygon). Use a flat operation log; don't try to be clever with transactional groups.

`Ctrl/Cmd+Shift+Z` redoes. Limit history to 50 ops per page.

---

## 4. Snap behaviour — the deep-dive

This is where we differentiate. Bluebeam's snap-to-content is the gold standard; the open question is what we can replicate cheaply in browser-side JS.

### 4.1 Snap-to-vertex of adjacent polygons (v1, ship now)

Trivial: spatial-hash all polygon vertices on the active page; on every cursor move while in trace or drag mode, query the hash within `tolerance_px` and pick the nearest. Tolerance default 12 px desktop, 18 px touch. Visual: target vertex glows cyan; cursor jumps to its exact position.

**Why this matters for us:** Bathroom + bedroom share a wall. If we don't snap-to-vertex, the user creates two slightly different corner positions and the rooms don't share an edge cleanly. Then `S_walls` double-counts and totals are wrong. Snap-to-vertex prevents this without any image processing.

### 4.2 Snap-to-edge of adjacent polygons (v1, ship now)

Same spatial hash but with line segments. For each segment within tolerance, compute perpendicular foot of cursor onto segment; if it's within the segment + tolerance, that's the snap point. Pick the nearest among all candidates (including vertex candidates from §4.1). Vertices win ties (estimators expect "snap to corner" before "snap to wall").

### 4.3 Snap-to-detected-wall (v2, defer to next sprint)

Run a one-time Canny + probabilistic Hough on the page raster (we already render the PDF at 300 DPI). Cache the line segments per page in localStorage / IndexedDB. During trace/drag, snap to these segments with the same logic as §4.2 but tinted differently (cyan dashed instead of solid).

**Cost estimate:** ~200 ms one-time compute per page in WebAssembly OpenCV (`opencv.js` is ~9 MB gzipped — we'd lazy-load only when v2 ships). Or do it server-side and cache (matches our existing pipeline).

This is the Bluebeam "Dynamic Fill"-adjacent feature: line weights from the rendered PDF *are* the wall positions.

### 4.4 Snap-to-grid (v2)

Only meaningful once the user has calibrated scale (clicked two points and entered a real-world distance). Then offer a 100mm/250mm/500mm grid toggle. Useful for quick-sketch rooms when no underlay PDF exists; not for tracing existing PDFs.

### 4.5 Tolerance configuration

Single global setting in the workspace toolbar: a slider with 4 stops — None, Tight (6 px), Normal (12 px), Loose (24 px). Default Normal.

### 4.6 Visual feedback for active snap

The rule: **the user must always know which snap target is active**. Implementation:

- Cursor changes to a small crosshair (4 px) when any snap is active
- The snap target itself is highlighted (cyan glow, 200 ms fade-in)
- A tiny label near the cursor shows the snap type: "kampas" (vertex) / "kraštas" (edge) / "siena" (detected wall) / "tinklelis" (grid)

If the user can't tell which target is being snapped to, they don't trust the tool, and they turn snap off. Then they double-place vertices. Then totals are wrong.

---

## 5. Keyboard shortcuts table — the spec

These are the bindings to ship. Pulled from Bluebeam (estimator expectations) + Figma/Illustrator (modifier conventions) + AutoCAD (vertex editing). Lithuanian shortcut labels in `[]` for tooltips.

| Action | Shortcut | Notes |
|---|---|---|
| Enter polygon trace mode | `P` | [Polygonas]. Single-key; Bluebeam uses `Shift+P` because they have ~30 markup tools — we don't. |
| Pan tool | `H` or hold spacebar | Industry standard. |
| Selection tool | `V` | Figma/Sketch convention. |
| Place vertex (in trace) | left-click | |
| Remove last vertex (in trace) | `Backspace` | |
| Close polygon (in trace) | `Enter` OR double-click OR click-first-vertex | All three accepted. |
| Cancel current trace | `Esc` | |
| Constrain to 90°/45° (override default ortho) | hold `Shift` while moving | |
| Disable ortho temporarily | hold `Alt` while moving | |
| Disable snap temporarily | hold `Alt` while moving | (Same key — Alt = "freeform mode") |
| Select polygon | left-click on polygon body or edge | |
| Multi-select polygons | `Shift`+click | |
| Select all polygons on page | `Ctrl/Cmd+A` | |
| Delete selected polygon(s) | `Delete` or `Backspace` | |
| Delete vertex (vertex selected) | `Delete` or `Backspace` | Different operation than polygon delete; resolved by what's selected. |
| Insert vertex | drag midpoint ghost OR right-click edge → "Įterpti tašką" | |
| Multi-select vertices | `Shift`+click on additional vertices | |
| Move selected vertices | drag any selected vertex | All move with same offset. |
| Undo | `Ctrl/Cmd+Z` | Operation-level. |
| Redo | `Ctrl/Cmd+Shift+Z` | |
| Zoom in/out | `Ctrl/Cmd+=` / `Ctrl/Cmd+-` or scroll wheel | |
| Fit page | `Ctrl/Cmd+0` | |
| Toggle ortho default | `F8` | AutoCAD convention; toggles the default behaviour, not the per-edge override. |
| Toggle snap | `F3` | AutoCAD convention. |
| Duplicate polygon | `Ctrl/Cmd+D` | For Repeating Groups (P06 from togal patterns). |
| Open command palette | `Ctrl/Cmd+K` | For everything we forgot. |

> Sources: [Bluebeam Keyboard Shortcuts PDF](https://support.bluebeam.com/wp-content/uploads/2018/03/Revu-2018_KeyboardShortcuts.pdf), [Figma Shortcuts](https://shortcuts.design/tools/toolspage-figma/), [AutoCAD Polylines](https://www.engineering.com/everything-you-ever-wanted-to-know-about-making-and-using-polylines-in-autocad/).

---

## 6. Mobile / touch — be honest

**v1: desktop only.** Show a non-blocking banner on mobile: *"Geriausia naudoti kompiuteryje. Mobilus režimas yra peržiūros tik."* Edit operations are disabled on touch in v1.

**v2 (future) — what mobile should look like:**

- Vertex hit-area expands to 44 px (Apple HIG / WCAG accessibility minimum).
- Touching a vertex shows a 100×100 px **magnifier loupe** anchored above the touch point, showing 3× zoom of the area under the finger. Apple Maps does this; iMark image annotation does this; Adobe Fresco does this. Without it, finger occlusion makes precision impossible on small vertices.
- Two-finger pinch always zooms (never accidentally creates polygons). One-finger drag pans in select mode, places vertices in trace mode.
- Long-press on vertex → context menu (replaces right-click).
- A separate "Lock" toggle in trace mode prevents accidental vertex drops; user has to deliberately "Add vertex" via a floating button.

**Realistic assessment:** Estimators do not estimate on tablets. They estimate on desktops and *review* on tablets. Optimize for review (zoom, scroll, tap-to-highlight) on touch — not for creation.

> Sources: [LogRocket Touch Target Sizes](https://blog.logrocket.com/ux-design/all-accessible-touch-target-sizes/), [Smashing Mag Touch Target Cheatsheet](https://www.smashingmagazine.com/2023/04/accessible-tap-target-sizes-rage-taps-clicks/).

---

## 7. Onboarding / discoverability

### Mode indicator (mandatory)

Bluebeam, Togal, AutoCAD all have an unmissable "you are now drawing" affordance:
- Cursor changes to a crosshair with a small "P" badge in trace mode.
- The toolbar button stays highlighted (filled, not outlined) while in trace mode.
- A persistent banner at the top of the canvas: **"Apvedinėjamas kambarys — paspauskite Enter užbaigti, Esc atšaukti"** (only while in trace mode).

Without these, users get lost — "why is clicking not selecting?" is the #1 support ticket on every annotation tool with an unclear mode model.

### First-time tooltip

On the first time a user enters trace mode in a project, show a transient overlay (dismisses on first vertex click):

> **Apveskite kambarį spustelėdami kampus**
> Enter / dvigubas paspaudimas — užbaigti
> Esc — atšaukti  ·  Backspace — pašalinti paskutinį tašką  ·  Shift — laisva kryptis

Don't show it ever again unless the user re-triggers via "?" in the toolbar.

### Help layer

`?` (shift+/) opens a keyboard cheat sheet overlay. Never modal — overlays the canvas with backdrop blur, dismisses on any key.

---

## 8. Accessibility

### Keyboard-only polygon creation: not a v1 priority but cheap to ship

Estimators don't draw polygons keyboard-only. But the basics (`Tab` to focus a polygon, `Enter` to enter edit mode, `arrow keys` to nudge a selected vertex by 1 px / `Shift+arrow` by 10 px / `Esc` to deselect) are 4 hours of work and make the tool *much* better for screen-reader users and motor-impaired estimators. Ship them.

### Color contrast on busy backgrounds

Floor plans are line drawings — black-on-white with thin grey hatching. Polygon outlines must be visible against this without obscuring the underlay.

- **Outline:** semi-transparent #00B8D9 (cyan) at 70% opacity, 2 px stroke.
- **Fill:** same color at 12% opacity. Tested on grey hatch backgrounds: legible.
- **Selected polygon:** outline jumps to 100% opacity + 3 px stroke. No fill change (avoids "is it selected because the fill changed or because I'm hovering?" ambiguity).
- **Hover:** outline at 85% opacity. Subtle.
- **Vertex:** white circle with 1.5 px cyan border. On a grey background, white-with-border is the most universal vertex marker (this is what every CAD tool uses).
- **Selected vertex:** filled cyan, no border. Unmistakable.

---

## 9. Anti-patterns we will not ship

Lessons learned from researching every tool above and the friction points users complain about.

1. **Forcing pixel-perfect "click first vertex" to close.** Always accept Enter and double-click as alternatives. Maps does this; Bluebeam does this; CVAT/Roboflow do this. Tools that don't (some legacy WebGIS) get ratio'd in user forums.

2. **Bezier curves on by default.** Floor plans are polygonal. Bezier handles confuse estimators and slow them down. Straight only; add curves later behind a modifier key.

3. **Modal "edit mode" vs "view mode" with no obvious indicator.** If the user can't tell which mode they're in, they don't trust clicks. Always show the mode in 3 places: cursor, toolbar, banner.

4. **Snap on by default with no override.** A snap that can't be turned off mid-drag is worse than no snap. Always offer Alt-to-disable.

5. **Tiny vertex hit areas.** The visible vertex circle is small (6 px) but the hit area must be ≥12 px desktop / ≥22 px touch. Otherwise pros miss vertices and curse the tool.

6. **Hidden context menus.** "Right-click on vertex shows nothing" = user assumes the feature doesn't exist. Always populate the right-click menu with at least: Delete, Insert before, Insert after, Properties.

7. **Auto-saving polygon on Esc.** If Esc commits the in-progress polygon, that's the opposite of every other tool. Esc cancels. Always.

8. **Re-rendering everything on every state update.** Imperative drag (refs + `.position()`), commit to state on `dragend`. The `2026-04-29-phase-c-libraries.md` perf section already captures this.

9. **Confusing two undos.** `Backspace` in trace mode = remove last vertex. `Ctrl+Z` in trace mode = ALSO remove last vertex (so users can't get confused). After commit, `Backspace` deletes the *polygon*; `Ctrl+Z` undoes the last *operation*. PlanSwift's split is the right model.

10. **No way to cancel a snap.** Always offer Alt-as-modifier to ignore the active snap.

11. **Showing snap to dozens of targets at once.** Pick exactly one active snap and highlight only that. Multiple highlights confuse the eye.

12. **Polygons that can self-intersect silently.** When drawing, detect self-intersection and refuse to commit. Highlight the bad edge in red; show "Polygonas susikerta" toast. Self-intersecting polygons break area calculations.

---

## 10. Concrete UX spec — handoff to frontend dev

This is the spec a developer should be able to implement directly.

### 10.1 Component tree

```
<PdfPolygonWorkspace>
  <Stage>                       # react-konva
    <Layer name="pdf-backdrop">             # listening: false
      <KonvaImage src={renderedPagePng} />
    </Layer>

    <Layer name="committed-polygons">       # listening: true (for selection)
      {polygons.map(poly => (
        <PolygonShape
          key={poly.id}
          points={poly.points}            # flat array [x1,y1,x2,y2,...]
          selected={poly.id === selectedId}
          onSelect={() => setSelectedId(poly.id)}
        />
      ))}
    </Layer>

    <Layer name="active-edit">              # listening: true
      {selectedId && <VertexHandles polygon={selected} onChange={updatePolygon} />}
      {tracingPolygon && <ActiveTraceShape vertices={tracing.vertices} cursor={cursor} />}
      {snapTarget && <SnapIndicator target={snapTarget} />}
    </Layer>
  </Stage>

  <Toolbar />                     # P / V / H / Esc / Enter / undo
  <ModeBanner visible={tracingPolygon !== null} />
  <FirstTimeHelp visible={firstTime} />
  <CommandPalette open={cmdK} />
</PdfPolygonWorkspace>
```

### 10.2 State shape

```typescript
type Vertex = { x: number; y: number };  // page coords (pre-zoom)

type Polygon = {
  id: string;
  pageNumber: number;
  vertices: Vertex[];           // closed; first ≠ last
  label: string | null;         // "Vonios kambarys"
  roomType: RoomType | null;
  source: 'manual' | 'vision' | 'flood-fill';
  confidence: 'high' | 'medium' | 'low';
};

type WorkspaceState = {
  mode: 'select' | 'trace' | 'pan';
  polygons: Polygon[];
  selectedPolygonId: string | null;
  selectedVertexIndices: number[];       // multi-select within selected polygon
  tracing: { vertices: Vertex[] } | null;
  snap: { enabled: boolean; tolerance: number; ortho: boolean };
  history: Operation[];                  // for undo/redo
  historyCursor: number;
};
```

### 10.3 Hit-priority order on mouse-down (in `select` mode)

1. Vertex of selected polygon (within hit-radius)
2. Midpoint ghost of selected polygon
3. Edge of selected polygon
4. Body of selected polygon (drag = move whole polygon)
5. Any other polygon (vertex/edge/body of unselected)
6. Empty canvas (clear selection or start drag-select rectangle if `Shift` held)

### 10.4 Hit-priority order on mouse-down (in `trace` mode)

1. First vertex (close polygon if ≥3 vertices placed)
2. Snap target (place vertex at snap)
3. Empty canvas (place vertex at cursor, with ortho if applicable)

### 10.5 Snap algorithm (pseudocode, runs on every mousemove)

```typescript
function findSnapTarget(cursor: Vertex, ctx: SnapContext): SnapTarget | null {
  if (!ctx.snap.enabled || ctx.altHeld) return null;

  const tol = ctx.snap.tolerance;

  // 1. Vertices of all other polygons (cheapest)
  const vertexHit = ctx.spatialHash
    .queryVertices(cursor, tol)
    .sort(byDistance(cursor))[0];
  if (vertexHit) return { type: 'vertex', point: vertexHit, label: 'kampas' };

  // 2. Edges of all other polygons
  const edgeHit = ctx.spatialHash
    .queryEdges(cursor, tol)
    .map(seg => ({ seg, foot: perpFoot(cursor, seg) }))
    .filter(({ seg, foot }) => onSegment(foot, seg))
    .sort(byDistance(cursor, e => e.foot))[0];
  if (edgeHit) return { type: 'edge', point: edgeHit.foot, label: 'kraštas' };

  // 3. Detected wall lines (v2)
  // 4. Grid (v2 if scale is set)

  return null;
}
```

### 10.6 Ortho-90° rubber band (pseudocode)

```typescript
function applyOrtho(prev: Vertex, cursor: Vertex, ctx: OrthoCtx): Vertex {
  if (!ctx.orthoEnabled || ctx.altHeld) return cursor;

  const dx = cursor.x - prev.x;
  const dy = cursor.y - prev.y;
  const angle = Math.atan2(dy, dx);
  const angleDeg = angle * 180 / Math.PI;

  // Snap to nearest of 0°, 45°, 90°, 135°, 180°, ...
  const snapAngles = ctx.shiftHeld ? [0, 45, 90, 135] : [0, 90];
  const nearest = nearestAngle(angleDeg, snapAngles, /*tolerance*/ 15);
  if (nearest === null) return cursor;

  const dist = Math.hypot(dx, dy);
  return {
    x: prev.x + dist * Math.cos(nearest * Math.PI / 180),
    y: prev.y + dist * Math.sin(nearest * Math.PI / 180),
  };
}
```

### 10.7 Operation log (for undo/redo)

```typescript
type Operation =
  | { type: 'create-polygon'; polygon: Polygon }
  | { type: 'delete-polygon'; polygon: Polygon }
  | { type: 'move-vertex'; polygonId: string; index: number; from: Vertex; to: Vertex }
  | { type: 'insert-vertex'; polygonId: string; index: number; vertex: Vertex }
  | { type: 'delete-vertex'; polygonId: string; index: number; vertex: Vertex }
  | { type: 'move-polygon'; polygonId: string; offset: Vertex };
```

Apply forward = redo, apply inverse = undo. Cap at 50 ops per page.

### 10.8 Persistence

Polygons are persisted to localStorage under `samatu_projects[projectId].pages[pageNumber].polygons`. Phase C migration (per `2026-04-29-phase-c-libraries.md` §4.4) moves this to Postgres JSON when we add multi-user. Until then, localStorage is fine.

### 10.9 Acceptance criteria for "polygon editor v1 done"

- [ ] User can press `P`, click 4 corners of a room, press `Enter`, and see a labelled polygon.
- [ ] Closing via Enter, double-click, AND click-first-vertex all work.
- [ ] `Esc` mid-trace cancels with no residue.
- [ ] `Backspace` removes last vertex while tracing.
- [ ] Default ortho-90° is on; holding `Alt` disables.
- [ ] Selected polygon shows draggable vertex circles.
- [ ] Selected polygon shows midpoint ghost circles that, when dragged, become real vertices.
- [ ] Snap to vertex of adjacent polygon works at 12 px tolerance with cyan halo.
- [ ] Snap to edge of adjacent polygon works at 8 px tolerance.
- [ ] `Ctrl+Z` / `Ctrl+Shift+Z` undo/redo across create / delete / vertex moves.
- [ ] Polygon area is computed via shoelace formula and shown in a sidebar pill.
- [ ] Self-intersecting polygons are refused on commit with a Lithuanian error toast.
- [ ] All UI labels Lithuanian (per CLAUDE.md project rules).
- [ ] Performance: drag 100-vertex polygon stays at 60 fps on a 2021 MacBook Pro.

---

## 11. What to read next (for the implementer)

1. [Konva editable polygon CodePen (akitanak)](https://codepen.io/akitanak/pen/wEMQvL) — the cleanest single-file reference; copy the vertex-drag + edge-click-to-insert pattern verbatim.
2. [DevMuscle React-Konva annotation tutorial](https://devmuscle.com/blog/react-konva-image-annotation) — full React component scaffold, ~500 lines.
3. [Bluebeam Polygon docs](https://support.bluebeam.com/online-help/revu21/Content/RevuHelp/Menus/Tools/Markup/Polygon-Tool--MTV.htm) — read this once, internalize the closure-three-ways pattern.
4. [CVAT Polygon Annotation guide](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/annotation-with-polygons/) — read the auto-bordering / Ctrl-snap section.
5. [Konva All Performance Tips](https://konvajs.org/docs/performance/All_Performance_Tips.html) — `transformsEnabled: 'position'`, `perfectDrawEnabled: false`, layer separation. Already cited in `2026-04-29-phase-c-libraries.md`; re-read before implementation.

---

## Sources

### Primary tool documentation
- [Bluebeam — Polygon Tool](https://support.bluebeam.com/online-help/revu21/Content/RevuHelp/Menus/Tools/Markup/Polygon-Tool--MTV.htm)
- [Bluebeam — Modifier Keys](https://support.bluebeam.com/articles/revu-use-modifier-keys-efficiently/)
- [Bluebeam — Snap Feature](https://www.brightergraphics.com/guides/how-to-use-snap-feature-in-bluebeam-revu)
- [Bluebeam — Keyboard Shortcuts (PDF)](https://support.bluebeam.com/wp-content/uploads/2018/03/Revu-2018_KeyboardShortcuts.pdf)
- [PlanSwift Hotkeys — DefKey](https://defkey.com/planswift-shortcuts)
- [PlanSwift Linear Takeoff guide](https://help.constructconnect.com/03-a-detailed-look-at-the-home-tab-and-drawing-takeoff-and-annotations-176/planswift-03-11-02-using-the-linear-takeoff-connected-segments-tools-1810)
- [AutoCAD — Modify Polylines With Grips](https://knowledge.autodesk.com/support/autocad/learn-explore/caas/CloudHelp/cloudhelp/2015/ENU/AutoCAD-Core/files/GUID-2070C02C-E18A-4333-BDC4-240F49F1C102-htm.html)
- [AutoCAD — PEDIT command](https://knowledge.autodesk.com/support/autocad/learn-explore/caas/CloudHelp/cloudhelp/2015/ENU/AutoCAD-Core/files/GUID-6242DF04-BD00-4A5D-891C-B131184D0D36-htm.html)
- [Figma — Edit Vector Layers](https://help.figma.com/hc/en-us/articles/360039957634-Edit-vector-layers)
- [Figma — Pen Tool tutorial (Designilo)](https://designilo.com/2025/08/12/how-to-use-the-pen-tool-in-figma/)
- [Figma — Shortcuts reference](https://shortcuts.design/tools/toolspage-figma/)
- [Adobe Illustrator — Pen Tool ESC discussion](https://community.adobe.com/t5/illustrator-discussions/keyboard-shortcut-to-interrupt-pen-tool/m-p/9160797)
- [Adobe Illustrator — Quick Pen Tool shortcuts](https://helpx.adobe.com/illustrator/web/add-and-edit-artwork/draw-and-edit-paths/quick-pen-tool-keyboard-shortcuts.html)
- [Google Maps — Polygon Auto-Completion](https://developers.google.com/maps/documentation/javascript/examples/polygon-autoclose)
- [Google Maps — Shapes and Lines](https://developers.google.com/maps/documentation/javascript/shapes)

### Annotation tools
- [CVAT — Polygon Annotation](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/annotation-with-polygons/)
- [CVAT — Shortcuts](https://docs.cvat.ai/docs/manual/advanced/shortcuts/)
- [CVAT — Edit Polygon](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/annotation-with-polygons/edit-polygon/)
- [Roboflow — Smart Polygon with SAM](https://docs.roboflow.com/annotate/use-roboflow-annotate/enhanced-smart-polygon-with-sam)
- [Roboflow — Polygon Annotation guide](https://blog.roboflow.com/polygon-annotation-labeling/)
- [Label Your Data — Polygon Annotation Best Practices 2026](https://labelyourdata.com/articles/data-annotation/polygon-annotation)
- [Togal — 2025 Features Roundup](https://www.togal.ai/blog/2025-features-roundup)
- [Togal — Release Notes Jan/Mar 2025](https://help.togal.ai/release-notes-january-25-2025)

### Map drawing libraries
- [Mapbox GL Draw — Modes documentation](https://github.com/mapbox/mapbox-gl-draw/blob/main/docs/MODES.md)
- [MapLibre Geoman vs Mapbox GL Draw](https://geoman.io/blog/maplibre-geoman-vs-mapbox-gl-draw)
- [MapLibre + mapbox-gl-draw example](https://maplibre.org/maplibre-gl-js/docs/examples/draw-polygon-with-mapbox-gl-draw/)

### React-Konva references
- [Konva Editable Polygon CodePen (akitanak)](https://codepen.io/akitanak/pen/wEMQvL)
- [DevMuscle — React-Konva Annotation Tool](https://devmuscle.com/blog/react-konva-image-annotation)
- [Konva Polygon Discussion #1075](https://github.com/konvajs/konva/discussions/1075)
- [Imam Rasheedat — Interactive Polygon Editor in React-Konva (Medium)](https://medium.com/@imamrasheedatahmad1993/how-to-build-an-interactive-polygon-editor-in-react-using-react-konva-1b085e0b04de)
- [definite2/kanva-draggable-polygon (GitHub)](https://github.com/definite2/kanva-draggable-polygon)
- [Konva — Performance Tips](https://konvajs.org/docs/performance/All_Performance_Tips.html)

### Accessibility / touch
- [LogRocket — Touch Target Sizes](https://blog.logrocket.com/ux-design/all-accessible-touch-target-sizes/)
- [Smashing Mag — Accessible Touch Target Cheatsheet](https://www.smashingmagazine.com/2023/04/accessible-tap-target-sizes-rage-taps-clicks/)
- [Flexy — Target Size UX Tips](https://www.flexy.global/resources/digital-product-design/master-digital-product-design-ux-tips-for-target-size)

### Internal references (sibling research files)
- `docs/superpowers/research/2026-04-29-phase-c-libraries.md` — stack decision (locked: react-pdf + react-konva)
- `docs/superpowers/research/2026-04-29-phase-c-competitor-tech.md` — competitor architecture
- `docs/superpowers/research/togal-ux-patterns.md` — 20-pattern catalogue, esp. P02/P04/P05/P06
- `docs/superpowers/research/togal-clickcount-ux.md` — interaction click-count benchmarks
- `docs/superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md` — NRM2/RICS/DIN standards baseline
