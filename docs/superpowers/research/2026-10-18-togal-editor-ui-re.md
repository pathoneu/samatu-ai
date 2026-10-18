# Togal.AI editor: visual and interaction layer, reverse-engineered (2026-10-18)

**Summary.** Togal's editor is a **light, full-viewport drawing canvas (`#F4F5F7`) framed by dark slate
chrome (`#1C2931`)**: a 60 px dark header, a white Quantities Panel docked right under it, a narrow
column of floating white icon cards on the left of the canvas, and a **dark floating pill at the bottom
centre** that shows only the options of the active mode. Everything is Proxima Nova at 12–16 px, 2 px
corners, one shadow colour (`rgba(124,147,156,.25)`), one green (`#3DB842`) for primary actions and
"auto-detected" states, and a 50-colour saturated palette reserved for takeoff classifications. Overlays
are deck.gl layers at 0.4 default fill opacity (+40 alpha on hover, +40 on selection, black outline when
selected), with user sliders for polygon opacity, line width (1–6 px), image opacity and background
removal. The click vocabulary is CAD-like: Esc returns to select, Space or Q pans, double-click or Enter
closes, Z drops the last point, Shift suppresses snapping and inverts the angle lock, Ctrl/Alt/Cmd jumps
to the snap target, and split/merge/subtract are *drawn* gestures. There is **no per-item confidence, no
stage names during processing, and no one-click area tool** in the shipped client. Pathon's evidence-first
check sheet, staged run panel and click-to-outline are already stronger; what Pathon lacks is Togal's
*frame* (dark chrome, floating icon tools, contextual pill), its density discipline, and a few fast
gestures (Space-pan, right-click reassign, draw-to-subtract). The public self-guided tour on togal.ai (a Navattic
capture of the real app, §0) confirms all of this from Togal's own replayed DOM — same class names, colours and
sizes as the bundle — and shows what Togal itself chose to demonstrate: one click on Togal, then *reviewing* the result
by showing, hiding and isolating layers in the Quantities Panel. Not one of its 45 steps shows editing a shape.

## Evidence and its limits

| Source | What it gives | Limit | Evidence IDs |
|---|---|---|---|
| REA scenario on the public login page (headless Chrome, CDP 9222) | Network inventory (83 app scripts, `index-hi58GkKm.css`, `fonts/ProximaNova-Regular.otf`), login screenshot | Login page only; editor never renders without an account | `ev_e4df74c6f61cabcb8b689e28dfc883ea7f49efc15755ea78898504687d16c90b` |
| REA `inspect_web_page` with script sources → `export_web_scripts` | 85 shipped chunks incl. `styles-D_LL_yQE.js` (design tokens), `editor-DG05iz0A.js` (defaults, palettes, modes), `permissions-Dlg-gF03.js` (mode classes, deck.gl accessors), `_baseGet-PMk6lXRP.js` (snapping, key handlers), `keysAndMouse-CHP5dohK.js` (key map), `index-C1GJ-k0i.js` (router, shortcut guide), `featureFlags-DxV1VpUs.js` (copy catalogue, 1003 strings) | Static code; minified names (some chunks keep `displayName`s and readable identifiers) | `ev_556f71667c81430e8b28bbd68a1533f4d461d81c5d48b28b807ec52d219e771f`, `ev_26d3799d0f3d626aaca9fd9da3f3869992ff696dbf38b8f46ccc53add9b02f04` |
| REA scenario DOM captures of the lazy editor chunks (public `/assets/*.js` opened as documents; text recovered from the DOM artifact, SHA-256-checked, Chrome's windows-1252 decode inverted) | `MapTakeOff-DZX4WJzI.js` (3,021,581 B, editor shell), `DrawingSheetHyperlinkHoverCard-C6aM1bFQ.js` (983,542 B, canvas layers, QP rows, legend), `ChatGPTUI-9v-lighI.js` (header, sheets, menus), `Dashboard-DEZHKrUF.js`, 14 small chunks (`toolNames`, `togal-dark-mode`, `Message`, `v2`, …) | Bytes are identical to the 2026-10-17 recovery, which matched REA's own response-body digest for `toolNames` and REA's recorded sizes for every large chunk. Scenario response bodies cap at 64 KiB; cross-origin `modulepreload` is CORS-blocked, so the DOM route was the only REA path | `ev_5e14e638ca851064d5e00e29e1743c5a80e8637bae0d209f50dbfd9ef33b36ff`, `ev_a53eb0498d20467ee5ff5e9537b474c9e2d90fdef3ff3864f48a0803a03739c8` |
| help.togal.ai screenshots viewed through REA (7 images, 2048×1200) | Assembled editor: header, left tools, QP, scale chip, scale popovers, Togal features dropdown, QP context menu and classification dialog | Marketing-curated states; red boxes drawn by the help authors | `ev_4bd7e20fb52175462e12e224f69b4e216160414a8e60b62b62927f2c6b46cac2` |
| **Public self-guided tour** `togal.ai/tour/main` → Navattic embed `togal-ai.navattic.com/rds0bpj` (4 flows, 45 steps), driven with Playwright MCP; the player iframe `#navattic-player` is same-origin and holds Togal's **captured app DOM** (286–364 KB HTML, 59 SVGs, the drawing as a 3840×1957 canvas snapshot) | Narration per step; real class names (`Header__Container-tgl__sc-kuqeza-0` …), computed colours, fonts, sizes and panel geometry read from the captured DOM; pixel colours sampled from the canvas snapshot | Curated demo data and states; a lead form at step 2 ("First Name, Email, Phone Number") was **not filled or submitted**: the tour advanced past it by itself. Playwright screenshots time out on this page, so screenshots were taken with REA in my own Chrome by opening steps I had already reached | Playwright observations (inline results, no ID); REA screenshots `ev_726583aef409d5a2d9b10af71a9cced3555204d08218a32396a4e02520a55d63` (results), `ev_b8ac1c13cfbefa851038ac26f6ed36eb8601fd398f623d10cfb5be8f3f4e1dc8` (all hidden), `ev_15cbcf8d2008479e847438c76afef8e28e506d9e40d92954a7f4c2237ff8459c` (text search), `ev_34c3e37dd38a8a1294afb1aafc1ffe95df6036ac878213e154cca46ad5df781e` (export summary) |
| Help-centre text (WebFetch) | Documented gestures: [QP overview](https://help.togal.ai/en/articles/15611909-quantities-panel-overview), [editing](https://help.togal.ai/en/articles/15463813-editing-and-modifying-takeoffs), [scale](https://help.togal.ai/en/articles/15367669-setting-up-the-scale), [Togal button](https://help.togal.ai/en/articles/15602961-the-togal-button-togal-s-automated-takeoff), [deducting](https://help.togal.ai/en/articles/15461267-deducting-an-area-or-length-from-a-takeoff), [re-Togaling](https://help.togal.ai/en/articles/15603137-re-togaling) | Help text sometimes differs from code; differences are flagged below | URLs |

Not observed: the live editor running (the tour replays captured DOM and canvas snapshots, so no deck.gl interaction, hover or drag
behaviour is seen), animation timing in practice, any server behaviour. No account, login or form submission was used. Nothing here claims the editor was executed.
The 2026-10-16 doc's REA analysis (`ev_8a6478…`) and §11 remain the source for onboarding keys and Learn-hub breadth.

## 0. The public self-guided tour (primary visual source)

OBSERVED (Playwright on the Navattic player; captured-DOM and canvas reads are inline Playwright results; screenshots are REA IDs above).
Checklist header: "Explore Togal · Poke around and see how Togal solves the pain points most estimators deal with so they can win more deals."

**Flow 1, "Takeoff QA and counts overview" (14 steps, sheet "A-103 THIRD LEVEL FLOOR PLAN").** Cover "Automate your takeoff."
→ "We know you're probably most curious about our AI tools, so first, we're gonna show you what the famous "Togal Button" can do" →
lead form (not submitted) → "Click the Togal Button to automatically run the takeoff." → "Select All Features and click Go. Togal will
automatically detect and measure areas, lines, and counts across the sheet, providing results for you to review in seconds." (the
dropdown text reads "Togal will create an automatic takeoff with all features including areas, lines and counts.") → "Bingo! Your takeoff
is done with a side panel listing all areas, lines and counts from that one click..." → "Hover over a layer's eye icon to see quick tips for
toggling visibility and isolating layers. Quickly show or hide layers to streamline your takeoff review and QA process." → "Toggle areas
on/off to confirm total area calculations." → "Click Togal areas to visualize and isolate different areas — the footprint, net area, doors area,
gross area, and gross internal area (Togal-derived)." → "You can isolate only Net area and Gross area to see the takeoff utility" → "Expand the
Lines group to review individual line types …" → "**Ctrl+click** the Wall Perimeter layer to isolate the perimeter lines. Quickly verify the total
wall length …" → "Expand the Counts group to view the itemized list of detected fixtures, furniture, and other countable objects. Review this
list to verify quantities before exporting …" → "Ready to walk through Togal with your project? … Book a Demo".
Result data in the panel: Togal areas 590 (Footprint 1 = 34,393.92 SF; Net area 156 = 30,275.92 SF; Doors area 127 = 345.54 SF; Gross area
163 = 34,561.4 SF; GIA 143 = 33,302.22 SF), Togal lines 1028 (Doors centerline 127 = 471.68 FT; Wall centerline 738 = 5,530.6 FT; Wall
Perimeter 163 = 9,262.76 FT), Togal counts 572 (Toilet 13, Sink 12, Single Swing Door 127, … Office Chair 363, Office Desk 29).

**Flow 2, "AI Search of Text, Image & Pattern" (15 steps, "A-201 EXTERIOR ELEVATIONS").** "Togal's AI Smart Search scans your plans using text,
image, and pattern recognition …" → 'Type "B" to search via text.' → "Every search result will be highlighted in green." → "84 results found!" →
"Togal can also find additional results in other drawings …" → "Results in other drawings 781" → image search: "You put a bounding box around
the image you want to find … louvers" → "93 Results" → "You can create or convert the 93 results to a classification." → Save → pattern search:
"Click Pattern, and trace a bounding box around a sample of the relevant pattern." → "Choose the design for your classification, such as the
hatch pattern." (None / Light Hatch / Dense Hatch …) → "Every matching pattern in the drawing is identified—without manually tracing …".
Search panel (screenshot `ev_15cbcf8d…`): a white card in place of the mode column with segmented Text | Image | Pattern, a "B ×" chip, "84 Results ← →",
"Convert 84 results to count · Choose classification ›", "Find in other drawings · Search set", outlined "Done"; hits are small green squares.

**Flow 3, "Collaboration" (8 steps).** "Split tasks, and get more done with Collaboration." → project users with permission levels → "+ Add Users"
→ permission picker ("Can Manage · Can edit all views …") → tablet use → "Done" → "This is David's view" / "This is James' view" → "With Collaboration,
the team leader has a bird's-eye view over the whole takeoff." (per-person views merged into a combined view).

**Flow 4, "Export" (8 steps, "A400a LEVEL 100 PARTIAL PLAN").** "Click the Export icon to see your quantity summary." → "You can sort, group-by, filter,
and adjust columns easily" → group by Classification Type → Add Filter → "Click Excel to export your table" → "Click the download icon to export PDF".
Summary view (screenshot `ev_34c3e37d…`): table panel over most of the canvas, toolbar Assembly Mode · 1 Drawing · Group · Filter · Columns · Copy All ·
green Excel; header row 30 px, data rows 31 px, classification column 240 px, panel `#F9F9FA` with a 74 px white header.

**Measured in the captured DOM (viewport 1728×850 unless noted).** Header `#canvas_header` `Header__Container-tgl__sc-kuqeza-0` 1728×60,
`rgb(28,41,49)`, Proxima Nova 14 px. `#togal_button` 103×37 at y 12, `rgb(61,184,66)`, white 14 px/600, radius 2. Page navigator
"211 of 211" 117×37; page badge "A-103" 40×22 `rgb(30,159,232)` 12 px/600 padding 3×5; title 14 px white; view switcher "Staff A View" 260×37.
Layout buttons 37×37, active `rgba(97,105,111,.3)`. **Left panel (`data-panel="left"`, drawings navigator) 350 px wide, collapsed at x −350.**
**Right panel (`#canvas-quantity-panel`) 340 px wide**, shadow `0 4px 24px rgba(124,147,156,.25)`, resize handle 20 px wide on its left edge.
Mode column at x 10, y 70: cards 45 px wide (250 / 45 / 250 px tall), 4 px padding, icon buttons 37×37, active `rgb(230,230,230)`.
2D/3D card 120×40 at x 64; active "2D" 14 px/700 on `rgb(240,241,243)`, inactive 400 `rgb(97,105,111)`.
Scale chip 136×45 at bottom-left (x 10), button text `rgb(61,184,66)` 14 px/600 ("Scale: 1/16" = 1' 0"" = auto-detected).
Panel header rows 40 px; search field 28 px; classification rows **32 px**, text `rgb(97,105,111)`; value cells 60 px wide, 12 px black; unit cells
30 px wide, 12 px `rgba(97,105,111,.5)`; nested rows `rgb(249,249,250)`, group rows `rgb(240,241,243)`. SVG icons mostly 16×16 and 20×20; avatars 36×36.
Canvas snapshot pixels after the run: dominant overlay colour `≈rgb(208,240,208)` (fits `#3DB842` at ~25 % over white, INFERRED), stronger green
`≈rgb(80,176,80)` lines, purple `≈rgb(144–160,48,176)` and magenta `≈rgb(240,64,176)` features (door lines, footprint, counts).

**Reconciliation with the bundle.** Every class name, colour, radius and size above matches the styled-components dump from the shipped chunks
(§1–§5): header 60 px `#1C2931`, Togal button green with 2 px radius, 37 px header controls, 45 px mode cards with 37 px buttons, 32 px rows,
60 px value column, scale chip in `#3DB842` when auto-detected. New from the tour (not resolvable statically): **QP 340 px and navigator 350 px default
widths**, the navigator collapsed by default, the post-run look (light green net-area wash, green outlines, small square count markers in class
colours, canvas legend top-left of the sheet), and the vendor's own emphasis on reviewing through visibility and isolation rather than editing.
The tour tooltips (dark navy with a green Next) are Navattic's styling, not Togal's.

## 1. Layout anatomy

```
┌───────────────────────────────── 60 px header #1C2931 ───────────────────────────────────┐
│[logo][≡][← 1 of 82 →][A-101 FIRST FLOOR PLAN][views]        [Togal][Togal.CHAT][▤][▦][⧉][⬇]│
├──────────────────────────────────────────────────────────────────────────┬───────────────┤
│ ┌──┐ ┌2D|3D┐ [split]                     canvas #F4F5F7, drawing white     │ Quantities    │
│ │↖ │                                                                       │ Panel (white, │
│ │✋ │  45 px floating cards, white, shadow2, 2 px radius, gap 10 px        │ right, top 60,│
│ │⊕ │  (modes: Edit, Pan, Merge, Subtract, Split, Measure)                  │ resizable)    │
│ │⊖ │                                                                       │ search 28 px  │
│ │✂ │                                                                       │ rows 32 px    │
│ │📏│                       [draggable legend, 2 px black frame]            │ ...           │
│ └──┘ ┌──┐ markup                                                           │               │
│ ┌──┐ undo/redo/history/snapshot/settings/search                            │               │
│ ┌──┐ shortcuts                                                             │               │
│[Scale: 3/32" = 1'0"]  [loader chip]   ┌ dark pill: mode options ┐   [?]   │   toasts ↘    │
└──────────────────────────────────────────────────────────────────────────┴───────────────┘
```

OBSERVED (code, [E4]=`ev_5e14e638…`, [E2]=`ev_556f7166…`; screenshots [E6]=`ev_4bd7e20f…`):
- **Editor root** `MapTakeOff__Container`: `position:absolute; 100vw × 100vh; background #F4F5F7`; with Togal.CHAT docked, width `calc(100vw − var(--togal-chat-width,450px))` [E4].
- **Header** `Header__Container`: `min-height:60px; background #1C2931`; controls 37 px tall with `1px solid #49545A` borders; hover `#61696F@10%`, active `@20–30%`; the active layout button gets a **4 px `#3DB842` bar 8 px below it**; sheet title area width var `--header-page-info-width` (DEFAULT 300, MIN 200, MAX 900, resizable) [E4 `ChatGPTUI`, E2 `permissions`]. Screenshot shows logo, hamburger, "← 1 of 82 →", blue `A-101` badge + title, views icon; right: green Re-Togal, teal Togal.CHAT (`#009568`), layout icons, download [E6 s_qp1].
- **Side panels** slide in under the header (`Header__ExpandableSide`: top 60 px, `height:calc(100vh − 60px)`, transform 0.2 s). Left = drawings navigator; right = **Quantities Panel** (`QuantityPanel__Container`: top 60, right 0, white, `border-right 1px #E3E4E8`, shadow; `data-expanded` shifts it 570 px left; `isSwitchLeftAndRightPanels` swaps sides) [E4].
- **Resizable panels** `ResizablePanel__*`: hover reveals a 4 px `#1C2931@20%` line and a 50 px dark grab pill, `cursor:col-resize` [E5 `Message`]. Floating dialogs are `MovablePanel`s with a 6-dot grip, 6 px side and 12 px corner handles [E2 `radio-checked`].
- **Mode column** `ModesSideBar__Container`: absolute, top 10 px, 55 px outside the left panel edge, cards in a column with gap 10 px; card `width:45px; padding:4px; gap:4px; white; shadow 0 4px 12px; radius 2px`; button hover `#F9F9FA`, active `#E6E6E6` [E4]. Screenshot: cards = 6 mode tools / markup / undo-redo-history-snapshot-settings-search / keyboard [E6 s_qp1].
- **2D/3D** toggle `CameraControls__CameraModeContainer` 120×40 px card, top 10 px, 64 px right of the panel; split-pane picker Single / 2-Pane / 3-Pane / 4-Pane [E4].
- **Bottom pill** `Toolbar__ToolbarContainer`: absolute, `bottom:20px` (10 px at ≤1250 px wide or ≤970 px tall), centred, z 30; pill `background #1C2931; radius 6px; min-height 40px; padding 5px; gap 5px`; white in markup mode. Element ids `#draw-mode-toolbar`, `#edit-mode-toolbar`, `#markup-mode-toolbar` mount only while that mode is active [E4].
- **Scale chip** bottom-left (`ScaleBar__*`, §9). **Loader chip** bottom-left 10/10 px, 40 px, dark. **Toasts** bottom-right (24 px + chat width). **Help launcher** dark circle bottom-right [E4, E2 `Toast`, E6].
- Settings menu: 250 px white card popping out 55 px from the mode column [E4 `Components__SettingsMenuContainer`]. History mode: bottom timeline sheet 240 px tall, width `calc(100vw − 390px)` [E4].

OBSERVED in the tour's captured DOM (§0): QP 340 px, navigator 350 px and collapsed, mode column at x 10 / y 70. INFERRED: these are the
defaults for a 1728 px window (the tour capture); minimum and maximum resize limits remain UNKNOWN.

## 2. Design tokens

OBSERVED in `styles-D_LL_yQE.js` [E2] unless noted.

| Token group | Values | Where used (code) |
|---|---|---|
| Chrome | `DARKGREY/GRAY8 #1C2931`, `HEADERGRAY #49545A`, `GRAY6 #61696F`, `SHORTCUT_DARK rgba(9,15,19,1)` | header, bottom pill, tooltips, dark menus, loader chip |
| Surfaces | `BACKGROUND/WHITE #ffffff`, `ACTIVEGREY #F4F5F7` (canvas, popover headers), `GRAY1 #F9F9FA` (hover), `GRAY2 #F0F1F3` (pressed/selected), `GRAY3 #E6E6E6` (borders, active tool), `GREY #F2F2F7` (dialog footers) | panels, rows, menus |
| Borders | `BORDER_COLOR/MIDGREY #E3E4E8`, `GRAY4 #DDDFE3`, `GRAY5 #DCDCDC`, `BORDER_DARK #d0d3d9` | panel edges, inputs, separators |
| Text | `BLACK #000000` primary, `TEXT_SECONDARY #3F4950`, `GRAY6 #61696F` secondary, `TEXT_TERTIARY #949A9E`, `UOM_GRAY #000000@46%` units, disabled `#DCDCDC` | rows, labels, units |
| Primary / AI | `MAINCOLOR/GREEN #3DB842`, `MAINCOLORLIGHT #D8F9DA` (selected cells, active scale), `MAIN2 #C5EAC6`, `MAIN1 #EFFDF0`, `SUCCESS_CONTRAST #1F5C21`, `TOGALCHAT #009568` | Togal/Save/Go buttons, auto-detected scale text, progress bars, "new" badges |
| States | `ERROR #F44336`, `STATUS_ERROR #DF0000`, `WARNING #FE7A05`, `ORANGE5 #FF9800` (scale missing, "Set scale" button), `BLUE #1E9FE8` (page-number badges, drop targets), `PURPLE #9747FF` (drag-and-drop insertion line, arc handles), `DARKPURPLE #46059C` | warnings, errors, DnD |
| Classification palette | `CLS_COLORS`: 50 saturated colours starting `#1BD6BF #009568 #F715B8 #DE48FF #FF5ADA #8953FF #3A84FF #4AEDDD #38F683 #E8ED0E #FFD706 #FF6107 #DF0000 …`; secondary 16-colour Material list picked by hashing the name [E2 `editor`, `styles`] | polygons, lines, counts, QP swatches |
| Markup palette | `#EB5757` (default), `#F2994A #F2C94C #27AE60 #2D9CDB #9B51E0 #333333 #BDBDBD #F7F7F7`; markup text Arial 12 px `#333333` [E2 `editor`] | redlines |
| Typography | `Proxima Nova, sans-serif` (100–800 OTF faces); sizes `10/12/14/16/18/20/24/30/38 px` (`FONT_TINY…FONT_TITLE`), default 14, small 12; line-heights `14/16/18/20/22/28/46`; weights `300/400/500/600/700/900` [E2 `styles`, `index`] | 14 px body, 12 px values and counts, 11 px uppercase section labels (`letter-spacing:.5px`) |
| Radii | `2px` default, `4px`, `6px` (bottom pill, primary CTAs), `100px` pills | nearly everything is 2 px |
| Shadows | `0 4px 24px rgba(124,147,156,.25)` (panels, menus), `0 4px 12px …25` (tool cards, scale chip), `0 8px 12px …5` (dropdowns) | single tinted shadow colour |
| Z layers | canvas 2–3, bottom pill 30, QP 20, loader 100, menus/popovers 100000, `Z_INDEX_MAX 100000` (+2/+3 for tooltips, onboarding), toasts 10000000 | |
| Spacing | 4 / 5 / 6 / 10 / 20 px steps; `PADDING 10px`; context-menu side padding 16 | |
| Modal widths | `MODAL_S 300, M 500, L 800, LM 900, XL 1140`; alerts 300 / 400 px | dialogs |
| Icons | in-house stroke SVG set (108 ids in `Icon-DMmYja8C.js`, viewBoxes 16/20/24) incl. tri-state `VISIBLE/PARTIALLY_VISIBLE/INVISIBLE`, `SELECTED/PARTIALLY_SELECTED/DESELECTED`; no icon library | |
| Components | styled-components (`tgl__sc-…` ids, `displayName`s kept) + Radix primitives (Popover, Tooltip, DropdownMenu, Select, ScrollArea, Collapsible, Checkbox via `--radix-*` vars) + deck.gl / nebula-style editable GeoJSON layer + three.js (3D) + mapbox-gl (map takeoff) + Jotai state; Material-UI v4 only in auth forms and legacy inputs | |
| Dark mode | Labs only: `html{filter:invert(1) hue-rotate(180deg)}`, images and chrome re-inverted, `#root` `#cddae2` [E5 `togal-dark-mode`] | a filter hack, not a theme |

## 2b. Click vocabulary (priority section for the Pathon merge)

OBSERVED from code unless marked: key map `keysAndMouse-CHP5dohK.js` [E2]; mode classes in `permissions-Dlg-gF03.js` [E2]
(registry: Edit `qp` "Edit · Escape", Pan `Jp` "Q", Draw `Y` and subclasses, Split `qh` "S", Merge `Jh` "M",
Subtract `Yh` "C", Measure `Xh` "D"); drag/key helpers in `_baseGet-PMk6lXRP.js` (`Lj`, `XA`, `YA`, `Us`) [E2]; shortcut guide data
in `index-C1GJ-k0i.js` [E2]; help articles linked above.

**Global.** Hold Space = temporary pan (`PAN_TOOL_TEMPORARY`), Q = pan mode, F = centre/frame the selection, Esc = select
tool, Ctrl+Z / Ctrl+Shift+Z undo/redo, PageUp/PageDown = previous/next sheet, Ctrl+F text search, Ctrl+E history mode,
Ctrl+Shift+G chat, T text-box markup, comparison P / O / T. Mode shortcuts are context-dependent: S = Split outside drawing
but snapping on/off while drawing; C = Subtract outside drawing but circle while drawing. Wheel zoom at the cursor is
deck.gl's default `scrollZoom` (INFERRED; camera speed setting `.25–4x`).

| Mode | Single click | Double click | Drag | Right-click | Enter / Esc / keys | Shift / Ctrl·Cmd / Alt | Hover, snap and cursor feedback |
|---|---|---|---|---|---|---|---|
| **Select / Edit** (Esc) | feature → select; empty canvas → clear; on a selected shape's vertex → **removes that vertex** (`ld`, never below a triangle); on a midpoint → **inserts a vertex** (`ud`) | feature → makes its classification the active one for the next drawing (`Dd`); grid guide → apply repeating group. Help: "Double click on a vertex to remove it" (code removes on the click path; whether a single click suffices is UNKNOWN) | vertex → move vertex; midpoint → **move the whole edge** (polygons; lines only with "Move lines as connected"); scale handle → scale; selected body → move; empty → box select (left→right = whole, right→left = partial) | context menu (§6) | Delete/Backspace delete; arrows nudge 1, Shift+arrows 10; Esc clears selection; Ctrl+A/C/V/D; Ctrl+Shift+V smart paste; Ctrl+L apply last classification; Enter applies an active repeating grid; F frames | Shift/Cmd+click toggles in selection; Alt/Cmd+drag on empty = **freehand lasso**, pressing Alt/Cmd mid-drag switches box↔lasso; Alt/Cmd+drag on a selection = drag-copy | handles appear on selection: grey `[60,60,60]` dots with outline, midpoints grey, hovered handle white and enlarged; cursor default, `grabbing` while dragging; hover +40 fill alpha |
| **Pan** (Q / hold Space) | — | — | pan | — | Esc leaves | — | cursor `grab` / `grabbing` |
| **Area draw** (double-click a classification in the QP, or L = last classification; shape type follows the classification) | add vertex | **close** (≥3 points; refused if self-intersecting, zero-area or no active Area classification) | — | — | Enter = close; Esc = leave arc mode → else cancel shape → else exit to Edit; Z = undo last point (arc-aware); R / C (before the 2nd point) = rectangle / circle; A = arc from last point; Tab = arc↔quadratic or next typed input; S = snapping on/off; H = height (3D) | **Shift held** = no geometry snapping *and* inverted angle lock (angle snap on when "Snap to angle" is off; default increment 45°, list 22.5/45/90°); **Ctrl/Alt/Cmd held** = jump to the snap target (`n&&snappedPosition` in `Us`), matching the hint "'Ctrl + click' to snap to the point" | crosshair cursor + full-screen 1 px black crosshair (on by default); live segment length label (white on black, 12 px, 10 px above the point); mode tag " Rectangle / Circle / Arc " in the class colour beside the cursor; snap guides drawn as black lines, snap point as a dark-red `[124,0,0]` dot; typed length/angle/height HUD (dark card, 10–11 px, lock indicator green) |
| **Line draw** | add vertex | finish (≥2 points) | — | — | as area | as area; with "Draw connected lines" off (default) each segment is saved as its own line, **Ctrl/Cmd at finish inverts** | as area |
| **Count** | **one click = one item** (needs an active Count classification) | — | — | — | Esc exits | — | crosshair; count symbols use the classification shape (circle, square, rectangle, triangle, diamond, pentagon, star) |
| **One-click / click-to-fill area** | **not in the shipped client**: `magic_tool` exists only as an id and icon, no mode class is registered. Togal's substitutes: the Togal run + Auto Classify, and AI image search (drag a box around a symbol → matches) | | | | | | |
| **Split** (S) | add cut point | finish | — | — | Enter finishes; R/C ignored; A = arc cut | — | the cut leaves a 0.001 cm gap; help: then delete the unwanted segment |
| **Merge** (M) | add vertex of a covering polygon | finish | — | — | Enter finishes | — | every shape of the same view touched by the drawn polygon is unioned into the first one's classification |
| **Subtract / Cut** (C) | add vertex (or R = rectangle, 2 clicks) | finish | — | — | Enter finishes | — | drawn area is cut from every shape it touches; help: shows as "solid white space"; right-click the hole → "Create and Fill" |
| **Measure** (D) | 2 clicks = a saved dimension line (2-point mode) | — | — | — | Esc | Shift/Ctrl as area | 2 px line, length label; zero-length lines discarded |
| **Scale** (bottom-left chip) | opens upward popover: click a standard scale (3×124 px grid), "No Scale Needed", or "Set Scale Manually" → **Draw Line** (2 clicks + type the real length, optional "Snap to standard scales") or **Enter Number** → Save | | | | | | auto-detected scale text green; missing scale orange chip with dot; manual scale black [E6 s_scale1, s_scale3] |

**Typical corrections, Togal (from code paths and help).**

| Correction | Gesture sequence | Count |
|---|---|---|
| Reclassify a room | right-click the polygon → "Assign classification" (searchable list with "Recently used") → pick; or select + Ctrl+L for the last-used class; or right-click → "Auto Classify" when the AI attached a suggestion | 2–3 clicks (1 click + 1 key with Ctrl+L) |
| Fix one vertex | click the polygon (handles appear) → drag the vertex; quantities recompute client-side | 1 click + 1 drag |
| Remove a false count | Esc → click the count → Delete (help: "deleted with the Delete key"); or right-click → Delete | 1 click + 2 keys, or 2 clicks |
| Deduct an opening / island from an area | C → R → 2 corner clicks (rectangle), or C + ≥3 clicks + double-click | 2 keys + 2 clicks |
| Deduct a length from a wall line | select line → S → 2 clicks across → double-click → click the cut segment → Delete (help) | ~6 actions |
| Re-run AI on one sheet | Re-Togal → (All Features / Custom) → Go → confirm "Are you sure you want to run Togal again ?" → wait ~10–15 s; reassigned classes come back as duplicates to clean up (help) | 3 clicks + wait + cleanup |

Kreo, for the merge (from `2026-09-17-tyrimas-togal-kreo.md`, not re-verified here): One-Click Area (click inside, positive and
negative points), Merge Ctrl+Alt+U, Subtract Ctrl+Alt+S, pre-create AI-confidence slider, 25-step undo.

## 3. Toolbar and tools

OBSERVED [E4, E2]: mode column order **Edit (Escape) · Pan (Q) · Merge (M) · Subtract (C) · Split (S) · Measure (D)**; comparison
adds Align; plumbing has its own set (Edit, Pipeline, Fitting, Drain, Exit Drain, Curve, Measure). Separate cards: markup, then
**Undo (Ctrl Z) · Redo (Ctrl Shift Z) · History · Snapshot · Settings · Search**, then the keyboard (shortcut guide). Buttons are
icon-only; the tooltip opens to the right (`sideOffset 10`) as a dark chip: label 14 px weight 500 white + shortcut in weight 800
`#61696F`, e.g. "Pan (Q)". Active icon black, inactive `#61696F`.
Bottom pill, draw mode: active-classification chip, **Snap to angle** (22.5° / 45° / 90°), **Snap to distance**, shape
(Polygon / Arc / Rectangle / Circle), **Automatic snapping**, Height, Reset to default. Snap menu: "Disable snappings", "Snap to
points" ("Snaps to nearest point 'Ctrl + click' to snap to the point"), "Snap to alignment", "Snap to lines", "Snap to lines Percent"
(5 / 10 / 12.5 / 25 %), "Snap to lines Distance" ("every 12 inches"), "Snap to closed edges". Pill buttons: 35 px, `#1C2931`,
border `#F9F9FA@10%`, hover `#DCDCDC@10%`, active `#F9F9FA@20%`, shortcut chips 12 px weight 700 in a 1 px light border.
No ortho mode exists; "Ortho/Persp" is the 3D camera toggle. Cursors: crosshair (draw, search), grab/grabbing (pan), move (translate),
corner-resize on scale handles, pointer over links.

## 4. Overlay rendering

OBSERVED (`permissions` accessors `Tv`/`Sv`/`xv`/`Dv`/`Ev`, `editor` defaults) [E2]:
- **Fill alpha** = `polygonOpacity × 255`, default setting **0.4** (code fallback 0.7); **+40 when hovered, +40 when selected**;
  fill colour = classification `colorStyle.fill`, grey `[160,160,160]` if none; hatch patterns from `/pattern_2.png`.
- **Stroke**: polygons alpha 200 in the class colour; **selected polygons get a black outline**; lines use the opacity setting; hover/selected +40.
- **Dim others**: when a breakdown highlight is active, everything else turns `[120,120,120,80]`. Hidden = transparent; holes black at alpha 0 (60 when selected).
- **Line width** = editor `lineWidth` (default 2 px, setting 1–6 px) or the classification's real-world thickness when "match dimensions" is set.
- **Handles**: default and midpoint `[60,60,60,250]`, hovered `[250,250,250]` radius 20 (world units, min 3–4 px, max 10 px), arc handles purple, snap point `[124,0,0]`.
- **Guides**: drawing guide `[0,0,200]` fill alpha 180 / line 240, snap guide black alpha 240, error guide `[250,50,50]`.
- **Labels**: tooltips are a deck.gl TextLayer, white on black, 14 px, 4 px padding, 12 px above the anchor. **Shape names and polygon
  dimensions are off by default** ("Show features names", "Show polygon dimensions").
- **Legend on canvas** (`canvas-legend`): white box, 2 px black inset frame, rows on a `1fr 80px 80px 80px` grid, draggable, width / height /
  size handles on hover; shown by default ("Show legend").
- **Crosshair**: full-screen 1 px black lines, on by default.
- **Comparison**: original `#F04F23`, overlay `#2F80ED`.
- **Clutter controls** (Settings, three sections): *Background image* (Color image, Image opacity 0–1 step .1, **Clear background** 0–1 step .05,
  Rotate); *Options* (Show legend, Draw connected lines, Move lines as connected, Show features names, Show polygon dimensions, Dimension fraction,
  Switch left and right panels, Tooltip fraction); *Visual properties* (Crosshair, Opaque render, Show only 3D, **Polygon opacity 0–1 step .1**,
  **Line width 1–6**, Camera speed). Plus Snap distance 1–100 px (default 12).
Screenshots show a plan with blue carpet fills and thick green wall lines over a white drawing [E6 s_qp1, s_qp2].

## 5. Quantities Panel and other panels

OBSERVED [E4 `DrawingSheetHyperlinkHoverCard`/`MapTakeOff`, E6]:
- Header rows 40 px (`padding 0 6px; border-bottom 1px #E6E6E6`): search "Search by name eg: 'Net area'" (28 px field), then "Hide all · Select all ·
  AI · + · folder · library".
- **Rows 32 px**, text `#61696F`, hover `#F9F9FA`, hidden rows at opacity 0.3, nested rows on `#F9F9FA`; 26 px icon hit areas; the **expand chevron
  and the eye appear on hover**; count pill 12 px on `#F0F1F3` with a 1 px border; "new" badge 10 px green outline; folders with children carry a
  9 px green dot.
- Values: unit grid `60px 1fr`, 12 px, right-aligned, unit text `#61696F@50%`; a value cell is selectable (hover inset 1 px `#1C2931`, selected `#D8F9DA`).
- Tree: classification → items → instances (screenshot "Carpet 18 → Items 18 → Carpet 386.3 SF …") [E6 s_qp2]; folders "Togal areas / lines / counts".
- Drag-and-drop reorder with a purple `#9747FF` insertion line and a 10 px circle handle; drop into an empty folder shows a blue tint.
- **Two-way highlight**: clicking an instance selects it on the drawing and vice versa (help); keyboard in the panel: ↑↓ move, ←→ fold, Shift+↑↓
  extend, click eye = show/hide, **Ctrl+click eye = hide all others**, double-click = draw with that classification, right-click = menu [E2 `index` guide].
- While Togal runs, a 50 px panel row shows "Togal in progress ( N% )" (12 px `#61696F`) over a 4 px green bar (red on error).
- Empty panel: "Start your new takeoff", "Start with AI: Get 95% done in seconds, then refine manually as needed.", the Togal button,
  "Or start from scratch with manual tools", "Create new classification", "Import from library", "Not sure how? Watch video tutorial" [E2 catalogue].
- Classification dialog "Edit Area Classification": dark header with grip, "× Cancel" and green "Save"; tabs Properties / Assemblies; Name, ID, Folder,
  Color, Pattern, Quantity 1–2 + UOM, Height, Offset, Slope [E6 s_edit].

## 6. Interaction model, menus, history

OBSERVED: selection rules and gestures as in §2b. **Context menus** (Radix, light or dark `#1C2931` variant, rows ~24–30 px, separators,
shortcut text weight 800):
- canvas selection: Assign classification · Assign breakdown · Create and assign · Edit · Copy · Duplicate · Edit item · Create and assign Repeating
  Group · Detach / Go to Repeating group · Delete · Ungroup · Restore · Jump to … · Draw · Delete assembly; footer "N features selected"; an
  "Auto Classify" button row appears when the selection carries AI suggestions [E4 `ChatGPTUI`];
- QP classification: Edit · Duplicate · **Delete (red)** · Jump to … · "Draw ⌘ Double click"; footer "1 classification selected" [E6 s_edit];
  folder: Expand (only folders / folders and classifications) · Collapse · Edit · Ungroup children · Duplicate · Delete;
- sheet: Move to Set · Move to different Folder · Update page name.
Undo/redo with toolbar buttons and keys; **History mode** (Ctrl+E) is a bottom timeline with green version chips and a snapshot list, "Restore
selected history" Ctrl+X [E4, E2]. Full keyboard map: the shortcut guide lists 58 entries in General / Drawing / Selecting / Comparison groups,
including Flip Ctrl+K / Ctrl+H, Group Ctrl+G, Ungroup Ctrl+U, Merge lines Ctrl+X, Rotate Ctrl+R / Ctrl+Shift+R, Duplicate Ctrl+D [E2 `index`].

## 7. Feedback and states

OBSERVED [E2, E4]: Togal button `#togal_button` green, **orange `#FF9800` while it reads "Set scale"**, spinner while running; labels Togal /
Re-Togal / Set scale. Progress has **no stage names**: server states only move the percentage (5/10/20/40/50/60/80/95/100), message
"Togal in progress", then "Togal complete" or "Error while Togaling drawing". First run: modal "Will Togal wash my car?" with "architectural
plans" vs "structural, elevation or site plans (but we have great tools to do this manually)" and "Got it". Non-drawing page: "This page appears to be
a text document … Run Togal anyway / Cancel". Re-run confirm: "Are you sure you want to run Togal again ?". **Toasts**: bottom-right, 300–400 px,
radius 4, `0 3px 10px rgba(0,0,0,.15)`, padding 12×16, 4 px coloured left bar, slide in from the right in 0.2 s; types error / info / success.
**Confirmations** (`Alert`): 300 px box over a 40 % black scrim, text 20 px padding, 76 px `#F2F2F7` button footer, rise-in 0.3 s. Banners: green
tint `#3db842@10%` with a green border, radius 4, 12 px text. Failure strings are specific ("No walls were found on this drawing. Please ensure the
drawing contains wall centrelines.").

## 8. Onboarding and help surfaces

OBSERVED: onboarding bubbles 300 px, caret 16×10, white or green `#C5EAC6`, padding 20, title 16/600, body 14/18, full-width green CTA, dismiss X
[E4 `OnboardingBubble__*`]; shape-edit card with a GIF; auto-detected-scale callout above the scale chip ("We've auto-detected the scale for this
drawing. Please ensure it's accurate before proceeding with take off." + "Don't show this again" + OK) [E6 s_scale1]. **Shortcut guide**: a dark
bottom sheet, 60 vh (max 850 px), clip-path reveal 0.3 s, two columns of 28 px rows, key chips 26 px (filled `#C5EAC6` or outlined), plus a mock
Quantities Panel with connector lines; the chip of a key **lights up while you press it** (`isPressed`) [E2 `index`]. Processing education: 420 px
video column (Wistia) with an 8 px rounded progress track during upload processing [E4 `Dashboard`]. Labs page lists experiments (dark mode,
tool belt: Carpet seams, Polygon dimensions, Auto 3D Builder, Quantities to Excel) [E5 `toolNames`]. Intrusiveness: bubbles and callouts are
dismissible; the first-run modal blocks once (INFERRED from flags).

## 9. Scale UI, page navigation, sheet names, search

OBSERVED [E4 `ScaleBar__*`, E6]: scale chip 130×45 px white, shadow2, radius 2; text "Scale: 3/32" = 1' 0"" (green when auto-detected, black
when manual, "No Scale Needed" text when chosen); orange background + 8 px dot when missing. Popover opens upward (≥300 px, 0.2 s slide):
green-bordered current-scale callout, 3×124 px grid of standard scales (active item green-tinted, auto-detected item bold), "No Scale Needed"
row (green with tick when active), "Set Scale Manually" → segmented "Draw Line | Enter Number", ratio inputs (ft/in : ft/in), Cancel / green Save.
Page navigation: header "← 1 of 82 →" (37 px), PageUp/PageDown; sheet title = **blue `#1E9FE8` number badge** (12 px/600, radius 2) + name
(heavy weight); navigator list rows 45 px or 300:240 grid cards, selected row `#D8F9DA@40%`, green-bordered grid card; sets page with list/grid,
processing and failed cards, auto-naming banner. Search: Ctrl+F text search; image search by box drag with "Previous searches in this project".

## 10. Read-across for Pathon (merge, not restyle)

Pathon today (code): one light `#F3F4F2` toolbar row of lucide icon + text buttons (thumbs, read, "psl. X / Y", zoom, layers, Žymėti, Laso,
Atstumas, Plotas, Perimetras, Kiekis, Mastelis, Rasti panašius, Masteliai, Istorija, ?) in `TakeoffViewer.jsx`; room fills by room type in
Tailwind 500 hues at 0.16 / 0.30 / 0.34 alpha (`lib/roomZones.js`, `RoomZoneLayer.jsx`; fills off by default since 2026-07-11);
`CheckLayer.jsx` mixes green read strings, red dashed missing, blue rooms, violet openings, amber; orange snap squares (`OutlineEditLayer.jsx`);
status-bar hints; right tabs "Patalpos ir eilutės / Kiekiai / Pokalbis" (`InteriorWorkspace.jsx`); keys in `lib/viewerShortcuts.js` (2/3/4/6
tools, L lasso, Enter/double-click finish, Z undo point, Esc cancel, Shift ortho, click a count mark to remove it, outline: drag corner snaps to
walls, click midpoint adds, double-click corner removes); no pan tool. Tokens: parchment `#F9FAF8`, primary deep slate `#192830`, evergreen
`#3F665C`, IBM Plex, 2 px radius (`index.css`).

| Togal does | Pathon today | Verdict |
|---|---|---|
| Dark slate frame (`#1C2931` header 60 px + bottom pill) around a light canvas | light chrome everywhere, yellow banners | **Adapt**: Pathon's own `--primary #192830` is the same slate; dark 56–60 px header and dark mode pill, white panels unchanged. Biggest single "professional" gain, no new palette |
| Icon-only floating tool cards (45 px) with dark tooltip + shortcut chip | horizontally scrolling text buttons | **Adapt**: vertical grouped cards (Žymėti/Pan · Plotas/Perimetras/Atstumas/Kiekis · Mastelis · Istorija); keep a short Lithuanian label under each icon for the 35–60 user, shortcut in the tooltip |
| Contextual bottom pill: only the active mode's options | hints in status bar and yellow banners | **Copy**: one place for "what this tool does now" (snap, ortho, finish/cancel), plain Lithuanian |
| Saturated classification palette, 0.4 fill, +40 hover/selected, black selected outline, user opacity / line-width sliders | per-room hues + several unrelated semantic colours | **Adapt**: colour = what it is (room / finish group), state = stroke weight and black outline, evidence = stroke style (solid read, dashed estimate, red only for missing); add opacity + line-width controls |
| Shape names and dimensions off by default; legend on canvas | numbered markers, labels per layer | **Keep markers**, add a legend card (finish → colour → m²) for exports and screenshots |
| Space / Q pan, F frame, Esc = select, Ctrl-click snap, Shift angle lock | no pan tool, Shift ortho exists | **Copy** Space-pan, F and Esc→Žymėti; keep number keys |
| Right-click canvas: searchable "Assign classification" + recently used | right-click only on measurements (`MeasureContextMenu`) | **Copy for rooms**: right-click a room → change type/finish, exclude, show evidence; 2 clicks |
| Draw-to-subtract (C + rectangle) | openings read from the drawing; no user deduction gesture | **Adapt**: "Atimti plotą" for islands/openings the reader missed, written back as a manual deduction with its own evidence line |
| Split / merge as drawn gestures | split-space by one line, outline vertex edit | **Keep Pathon's**; borrow the 0.001 cm-gap idea only if splits are persisted as geometry |
| Review loop = one run, then show / hide / **Ctrl+click isolate** layers in the panel to check totals (the tour's whole story) | per-room check sheet with evidence; layer toggles only for zones and walls | **Adapt**: add isolate-on-Ctrl+click and a "rodyti tik šią eilutę" eye to the Kiekiai rows, so a line's geometry lights up alone on the drawing; keep the evidence sentence beside it |
| No one-click area | "Parodyti patalpą" (click inside → wall-exact outline) | **Keep and promote**: this beats Togal and matches Kreo's One-Click Area |
| Count: 1 click add, select + Delete to remove | 1 click add, 1 click on the mark removes | **Keep Pathon's** (fewer clicks) |
| Togal progress: percentage only | `DetectRunProgress` stage names, reasons, ✓/●/✕ | **Keep Pathon's** (better); restyle as the dark pill |
| No per-item confidence | evidence sentences + crops beside every number | **Keep**, show evidence states via stroke style, not dots |
| Scale chip bottom-left, green auto / orange missing / black manual, upward popover with standard grid | status-bar sentence + "Masteliai" panel + `ScaleCheckCard` | **Adapt**: a scale chip "1:100 · patikrinta" coloured by evidence; keep measured-scale checks (stronger than Togal's OCR) |
| QP density: 32 px rows, hover-only eye/chevron, 12 px right-aligned values, 60 px unit column | wider rows, tabs | **Adapt density** for "Kiekiai"; keep room-centric "Patalpos ir eilutės" as the first tab (skip Togal's classification tree as the primary model) |
| Toasts 300–400 px bottom-right with coloured bar; 300 px confirm with grey footer | yellow banners, inline notes | **Copy** for transient results and destructive confirms |
| Header sheet badge "A-101" + title; "← 1 of 82 →" | "psl. X / Y" in toolbar, SheetRail | **Copy** badge + title into the header; keep SheetRail groups |
| Shortcut sheet with live key highlight | `ShortcutsGuide` panel + PDF | **Adapt** (add live highlight); skip the QP diagram |
| Labs dark mode via `invert()` | none | **Skip** |
| Settings: 14 visual toggles | a few layer toggles | **Adapt to three**: drawing opacity / "Išvalyti foną", polygon opacity, line width |

## Checklist status

0 Self-guided tour: **answered** (all 4 flows, 45 steps narrated; lead form left unsubmitted). 1 Layout anatomy: **answered** (QP 340 px /
navigator 350 px from the tour; resize limits unresolved). 2 Design tokens: **answered** (bundle values confirmed by computed styles). 2b Click
vocabulary: **answered** (single-vs-double click for vertex deletion unresolved; the tour shows no editing). 3 Toolbar and tools: **answered**.
4 Overlay rendering: **answered** (post-run look seen in the tour; exact default alpha on a live sheet inferred from pixels). 5 Panels: **answered**.
6 Interaction model: **answered**. 7 Feedback and states: **answered**. 8 Onboarding/help: **partial** (Appcues/Learn-hub content is server-side).
9 Scale, pages, search: **answered**. 10 Read-across: **answered**.

## Unknowns that need an account

1. Resize limits of the Quantities Panel and navigator, and how they adapt below 1440 px.
2. Whether a *single* click on a selected shape's vertex deletes it (code path) or only a double-click does (help), and the deck.gl tap/double-tap timing.
   The tour has no editing steps, so it cannot settle this.
3. The felt quality of hover, snapping and drag on a live sheet, and the exact default fill alpha (the tour's canvas snapshot suggests ~25 %, code default 0.4).
4. What "Automatic snapping" changes at runtime (the setting exists, its effect on the cursor was not traced) and whether middle-mouse pans.
5. Exact context-menu item order and conditions per selection type (order inferred from code order), and Appcues tour content.
