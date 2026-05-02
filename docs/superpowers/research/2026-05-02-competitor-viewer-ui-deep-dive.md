# Competitor PDF-Viewer UI — Deep Dive

**Date:** 2026-05-02
**Goal:** Visual research across Togal.AI, Kreo, and Bluebeam Revu to inform the next polish pass on Sąmatų AI's PDF viewer. Captured live via Playwright MCP.

**Sources:**
- Togal.AI: G2 high-res screenshot (`AI-Image-Search.png` 1600×928), help center, marketing thumbnails
- Kreo: their homepage hero is their actual viewer, plus product page sections (Auto Measure / Caddie AI / Drawing Intelligence)
- Bluebeam: bluebeam.com/product/markups-and-data hero (laptop frame, full UI visible at 1920×1200)

Reference screenshots in `.smoke/`: `deep-03-togal-ai-image-search.png`, `deep-06..10-kreo-*.png`, `deep-15-bluebeam-hero-large.png`.

---

## 1. Three distinct design languages — pick what fits us

| Dimension | Togal | Kreo | Bluebeam |
|---|---|---|---|
| Chrome color | Dark navy `#1a1f2e` | Dark navy `#0e1521` (almost black) | Light gray `#e8e8e8` |
| Drawing area | White, generous | Dark blueprint `#0a1424` with grid | White, dense |
| Polygon style | Thin stroke, light fill | Vibrant colored fill + matching stroke | Filled solid, semi-transparent |
| Polygon palette | Single accent (green) | Rainbow per type (red/yellow/green/cyan/blue/purple) | Per-markup-type (red/green/orange/blue/cyan) |
| Top toolbar density | Sparse, breathing | Multi-row (project tabs / floor selector / tool bar) | Dense, classical desktop menus |
| Left tool rail | ~64 px, icon only | Same | Wider w/ stamp library + tool chest |
| Right panel | Modal dialogs over canvas | Persistent panel w/ scale + categories | Persistent w/ markup list |
| Typography | Crisp Inter-like sans | Same | System (varies by OS) |
| AI features visibility | Green "Togal" CTA | Cyan ✨ badges per AI feature | None (no AI) |
| Modal style | Light-on-dark, rounded | Same | Native OS dialogs |
| Aesthetic | Clean & balanced | Polished & vibrant | Functional & dense |

**My honest take:** Kreo is the look the user wants. Dark navy chrome + vibrant colored polygons + AI-feature badges = "modern, premium, intelligent". Togal is a softer version of the same direction. Bluebeam is power-user territory we shouldn't chase (20 years of feature accretion, requires desktop-app density).

---

## 2. Patterns to copy

### 2.1 Chrome (dark navy, vibrant accents)

Both Togal and Kreo use a dark navy chrome that frames the white/dark drawing area. The key insight: **the chrome should disappear visually so the drawing pops**. Light chrome (our current C-4 polish) competes with the document.

- Top bar: dark navy `hsl(220, 30%, 12%)` ish
- Tool rail: same
- Border between chrome and drawing: a subtle `1px` cyan/blue accent (Kreo) or no border at all (Togal)
- All chrome text: white or near-white (`#e2e8f0`)
- Active state: cyan/blue accent (Kreo: `#3a91d3`) or brand green (Togal)

### 2.2 Polygon rendering (vibrant fills, colored strokes)

Kreo's polygon rendering is the gold standard:
- Each takeoff CATEGORY gets its own COLOR (Rooms = teal, Doors = cyan, Walls Internal = bright cyan, Walls External = magenta, etc.)
- Polygon = semi-transparent FILL (~25% opacity) + SOLID matching STROKE (2 px)
- Vertices/anchor points = small SQUARE markers in a contrasting color (purple `#a855f7`)
- Walls drawn as DASHED LINES in their category color
- When selected: stroke thickens, fill brightens

Our current `AiRoomOverlay` uses a single cyan color for all polygons. Should accept a `category_color` field per polygon for differentiation.

### 2.3 AI feature badges (visible value proposition)

Kreo puts a `✨ AI` badge next to every AI-powered feature button. This is huge for product perception — every time the user sees that badge they're reminded the tool is intelligent.

Examples in Kreo:
- "One-click Area ✨" (Bluebeam Dynamic Fill = our Phase C-3)
- "Auto Count ✨"
- "AI Scale Detection" (auto-detects scale)
- "AUTO MEASURE [AI]"

Our existing AI features (eksplikacija reader, Vision room detect, polygon trace) should all wear this badge.

### 2.4 Multi-row top bar (project context > floor selector > tool bar)

Kreo splits the top region into THREE rows:
1. **Project tabs**: "Project | Plans | Assemblies" (which view of the project)
2. **Floor selector**: horizontal strip of cards "Floor 00 / 01 / 02 / Roof" each with a page-count badge
3. **Tool bar**: tools + AI features

Our current top toolbar has page nav + zoom + Sluoksniai/Pažangu/Eksplikacija crammed into one row. Splitting into project context + page selector + tools would breathe.

Note: we're single-floor by default but multi-page. The "Floor selector" pattern translates as **page-type strip** (`Aukšto planas | Sienų išklotinė | Eksplikacija | Lubų planas | …`) with quick-jump buttons.

### 2.5 Right panel cards (Kreo's "category cards")

Kreo's right side has small rounded cards each titled by feature ("Multiple measurement categories", "Automatic classification") with an icon, title, and 2-3 line description. We could mimic this for our existing "Patalpos / Plytelės / Glaistymas" sections — instead of dense table rows, group by skyrius into elegant cards.

### 2.6 Tag pill design (Kreo's drawing-reference tags)

Kreo's "Cross-Reference Intelligence" panel showed tag pills with a beautiful pattern:
```
[●] Title text [TYPE-PILL]
```
Where:
- `[●]` is a SOLID DOT colored by category (red/cyan/green/blue)
- `Title text` is the entity name
- `[TYPE-PILL]` is a tiny rounded pill with the type (`DRAWING`, `LEGEND`, `TABLE`, `STAMP`)

Our existing skyrius headers + plytelės/glaistymas labels could adopt this. Visual hierarchy in 3 words.

### 2.7 Scale lock badge (Kreo)

Kreo has a permanent badge in the right panel showing **`SCALE 1:100 🔒`**. The lock icon is crucial — it tells the user "this value is committed; click to change". Our current "Mastelis nenustatytas — naudok „Pažangu" → liniuotė" status-bar message would become a small persistent badge in the same spot.

### 2.8 Subtle blueprint background (Kreo)

Kreo uses an extremely subtle BLUEPRINT GRID texture in the dark drawing background — barely visible but adds professionalism. Easy to add via CSS background-image.

---

## 3. Patterns to NOT copy

### 3.1 Bluebeam's tool chest density

Bluebeam's left panel has dozens of categorized stamp presets. Beautiful for power users with 20-year muscle memory; terrible for our target Lithuanian estimator who just wants to verify quantities. We keep our minimal left rail.

### 3.2 Togal's "search by image" modal

Togal lets you draw a sample symbol and search for instances. Very cool feature; not on our roadmap. Skip.

### 3.3 Bluebeam's dense menu bar

`File / Edit / View / Document / Batch / Tools / Window / Help` is desktop-app convention — we're a web app, not Acrobat. Skip.

### 3.4 Kreo's 3D rendering view

The "isometric 3D" floor plan view is impressive marketing but adds zero value to the takeoff workflow. Skip until we have idle dev time.

---

## 4. Concrete polish changes for our viewer

Ordered by impact:

### High impact (do first)

1. **Flip chrome to dark navy** — `bg-card` (currently light) → dark navy in PDF viewer chrome only (toolbar + tool rail + thumbnail sidebar). Drawing area stays white. Theme tokens stay app-wide; PDF viewer becomes a "tool" surface within the app.

2. **Add ✨ AI badges to AI features** — eksplikacija reader chip, Vision-derived data, future click-to-fill. One small lucide `<Sparkles className="w-3 h-3" />` icon next to the label.

3. **Color-coded polygons by category** — `room.category_color` field; pass through to `AiRoomOverlay` Line `fill` and `stroke`. Default per-paskirtis palette: vonia=cyan, miegamasis=blue, virtuvė=amber, etc.

4. **Split top toolbar into 2 rows** — row 1: page nav + scale badge + view toggles. Row 2: tools + AI actions. Currently everything's in one cramped row.

### Medium impact

5. **Permanent SCALE badge with lock icon** — replaces the wordy "Mastelis nenustatytas" status-bar message. Small chip in upper-right of viewer, click to set/change.

6. **Page-type strip below toolbar** — horizontal strip of "page kind" tabs (Aukšto planas / Sienų išklotinės / Eksplikacija / Lubų planas) that filters thumbnails by type. Faster navigation than scrolling 65 thumbnails.

7. **Subtle blueprint grid background** behind the drawing area — barely visible CSS pattern.

### Low impact (nice to have)

8. **Tag pill redesign** for skyrius headers in right panel — `[●] Plytelės [m²]` pattern.
9. **Card-style right panel sections** — replace table-density with rounded cards per skyrius.
10. **Cyan/blue brand accent** on active states (replacing the current primary blue).

---

## 5. Implementation strategy

This is the second polish pass on top of C-4. Three commits:

**Commit A**: Chrome dark-flip + ✨ AI badges
- Modify `PdfViewer.jsx` toolbar + tool rail + thumbnails to use `bg-slate-900` / `text-slate-200` / `border-slate-700` (or define new theme tokens `--viewer-chrome` / `--viewer-chrome-foreground`)
- Add `<AiBadge />` component, sprinkle on eksplikacija + Vision sources

**Commit B**: Polygon color-by-category
- Extend room schema with `category_color` (frontend-derived from paskirtis)
- `AiRoomOverlay` reads it; defaults to cyan if missing
- Update `ProvenanceChip` color when source = AI

**Commit C**: Top toolbar 2-row split + SCALE badge + page-type strip
- Restructure `ToolBar` JSX into 2 vertical rows
- Replace bottom-status "Mastelis" with a top-right pill
- Add `<PageTypeStrip>` filter chip row

After each commit: build + Playwright screenshot of the running app (you'll need to inject a PDF into IndexedDB for me to see the viewer with content — or I can show you the empty-state chrome only).

---

## 6. References (file paths)

Screenshots collected this session:
- `.smoke/deep-03-togal-ai-image-search.png` — Togal's actual UI, full-res
- `.smoke/deep-06-kreo-home.png` — Kreo viewer hero on homepage
- `.smoke/deep-07-kreo-fold2.png` — Kreo isometric transition
- `.smoke/deep-08-kreo-fold3.png` — Kreo rainbow polygons + feature cards
- `.smoke/deep-09-kreo-fold4.png` — Kreo Caddie AI tag pills
- `.smoke/deep-10-kreo-fold5.png` — Kreo "Drawing Intelligence" + Scale Detection widget
- `.smoke/deep-15-bluebeam-hero-large.png` — Bluebeam Revu in laptop frame, dense tool chest

Sibling research:
- `docs/superpowers/research/2026-04-29-phase-c-competitor-tech.md` — architectural / pricing analysis
- `docs/superpowers/research/2026-04-29-phase-c-libraries.md` — stack decision (locked: react-pdf + react-konva)
- `docs/superpowers/research/2026-04-29-phase-c-polygon-ux.md` — manual polygon UX patterns (already shipped C-1)
