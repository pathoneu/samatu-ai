# Takeoff Standards & PDF Interactive UX — Research Findings

> **Date:** 2026-04-28
> **Trigger:** Pre-roadmap research session — validate CLAUDE.md formulas against international standards + benchmark our PDF viewer vs togal.ai/competitors
> **Method:** Two parallel general-purpose research agents (WebSearch + WebFetch on 30+ authoritative sources)

---

## PART A — Interior Finishing Calculation Gaps

### A1. NRM2 Tiered Opening Deduction (CRITICAL GAP)

**Source:** RICS NRM2, IS 1200, theconstructor.org

International convention is tiered, not binary:
- **≤ 0.5 m²** → no deduction, no reveal addition (CLAUDE.md §1.1 ✅)
- **0.5–3 m²** → deduct ONE face only when both faces same finish; **NO reveal addition**
- **> 3 m²** → deduct both faces + add reveals separately

**Current CLAUDE.md status:** Adds reveals on EVERY window regardless of size. Over-quantifies small windows by ~5 m of reveal each.

**Fix:** Implement tiered logic in `extractor/universal_rules.py::calc_room_quantities()`. Add `paint_deduction_standard` setting: NRM2 (3 m²) | VOB DIN 18363 (2.5 m²) | LT (default = NRM2).

### A2. Polygon-Based Tile Zones (HIGH IMPACT)

**Source:** NKBA Chapter 12, MeasureSquare workflow

Current formula `tiled_wall_length × tile_height` (CLAUDE.md §1.7) **fails** on:
- L-shaped walls
- Stepped walls (different tile heights per segment)
- Curved walls
- **Niche internals** (1.5–3 m² per niche, **completely missed today**)

**Standard practice:**
- Each elevation wall = its own polygon
- Measure to **finished tile height**, not nominal 2.0m (varies 1.8–2.4m)
- Subtract fixture footprints visible in elevation
- Add niches: `niche_back + 4 niche sides` as additional area
- Schlüter trim profiles = linear meters at top of tile zone + inside corners

**Fix:** Replace `length × height` with polygon-based measurement in `extractor/wall_elevation.py`. Add separate line items for niches and trim profiles.

### A3. Q4 Thickness Underestimate (PREMIUM PROJECT GAP)

**Source:** Merkblatt Nr. 2 "Verspachtelung von Gipsplatten" (Bundesverband der Gipsindustrie), DIN 18181/18363

CLAUDE.md §1.11 says Q4 = 1.5–2 mm. **Wrong.** Q4 needs:
- **3–5 mm** full-surface skim minimum
- 80–120 grit sanding
- Sanding labor ~0.30 h/m² (not in CLAUDE.md)

**Why it matters:** Q4 is gloss-paint-ready surface. Every 0.1 mm imperfection shows under gloss. Premium residential (penthouse, salonai) projects routinely under-quote 30%+ on labor due to missing sanding.

**Fix:**
- Bump Q4 thickness to 3–5 mm in CLAUDE.md §1.11
- Add line item `glaistymo_šlifavimas_Q4` = `wall_area × 0.30 h/m²` in pozicijų generator
- Surface as warning when user selects Q4: "Q4 reikalauja 3–5 mm sluoksnio + šlifavimo"

### A4. Paint Class → Coats × Coverage (CONFIGURATION GAP)

**Source:** Tikkurila Optiva/Otex TI, Caparol CapaSol TI, Squote Paint Coverage Guide

CLAUDE.md hardcodes `1.8×` multiplier for "2 coats". Real coverage depends on paint class:
- **Class 1** (top opaque): 10 m²/L × **1 coat** sufficient
- **Class 2** (Sikkens Alpha Matt, Dulux Easycare): 9 m²/L × **2 coats** typical
- **Class 3** (rough/textured, fresh plaster): 7–8 m²/L × **3 coats** required

Tikkurila Optiva primer = 6–8 m²/L (CLAUDE.md says ~7, ✅), but Otex adhesion primer (tile/glass) = 8–10 m²/L (missing as option).

**Fix:** Add `paint_class` parameter to room rules. Default Class 2. Adjust `coats × coverage` formula accordingly.

### A5. Sloped Ceilings + Stairwells (SILENT 15–40% UNDERESTIMATE)

**Source:** painttalk.com, NKBA, hunker.com

CLAUDE.md §1.1 hardcodes `S_ceiling = floor_area` (flat ceilings only). LT pavienių namų projects frequently have:
- **Vaulted/sloped ceilings** (mansardiniai, klasikiniai dvišlaičiai stogų erdvės)
- **Stairwells** (multi-height walls + triangular subtractions)
- **Coffered ceilings** (kasetiniai, +15–25% over flat)

**Formulas:**
| Edge case | Formula |
|---|---|
| Sloped ceiling | `actual_area = base_area / cos(slope_angle)` (reuse §3 slope_factor table) |
| Stairwell wall | `S = perimeter × max_height − Σ(stair_triangles)` where triangle = `0.5 × run × rise × steps` |
| Curved wall | `length = π × radius × (angle°/180)` arc, `area = arc_length × height` |
| Coffered ceiling | `flat_area + Σ(coffer_perimeters × coffer_depth)` |

**Fix:** Add `ceiling_type` parameter (`flat` | `sloped` | `vaulted` | `coffered`) and `room_type` extension for `stairwell`. Reuse §3 slope_factor in interior context.

### A6. Common Mistakes Update (CLAUDE.md §8)

Four additions needed beyond current 10:

11. **Ceiling drywall counted with walls** — different thickness (9.5mm ceilings vs 12.5mm walls), often summed into one "drywall sheets" total.
12. **Sanding labor rushed/skipped** — represents 25–35% of drywall finishing labor, often only material costed.
13. **Touch-up buffer too low** — rough/textured walls need 10–20% extra paint, not just 5–8% waste factor.
14. **Inside vs outside corner bead split** — only outside corners need metal bead; inside use paper tape (cheaper). Estimators often spec metal everywhere.

---

## PART B — PDF Interactive Feature Gaps

### B1. Feature Matrix Summary

| Feature | Sąmatų AI today | Togal.AI | Bluebeam | Kreo | STACK | Best-in-class |
|---|---|---|---|---|---|---|
| Click-to-area | 🟡 rooms only | ✅ | ✅ | ✅ | ✅ | Bluebeam |
| AI auto-room polygons | ✅ Vision | ✅ Togal button | ❌ | ✅ Auto Measure 2.0 | ✅ Floor Plan AI | Togal/Kreo |
| **Editable polygons (cut/merge/split)** | ❌ | ✅ C/M/S hotkeys | ✅ Dynamic Fill | ✅ | ✅ | Togal |
| **Snap-to-edge / angle snap** | ❌ | ✅ 2025 | ✅ | ✅ | ✅ | Togal/Bluebeam |
| **Pattern / symbol search** | ❌ | ✅ Text/Image/Pattern | ✅ Visual Search | ✅ I-OCR+CV | 🟡 | Bluebeam |
| Scale calibration | ✅ ScaleCalibrationModal | ✅ | ✅ | ✅ | ✅ | Parity |
| Layer toggle | 🟡 source dots only | ✅ | ✅ | ✅ | ✅ | Behind |
| **Drawing-revision diff (blue/red)** | ❌ | ✅ | ❌ | ✅ | 🟡 | Togal/Kreo |
| Repeating/typical groups | ❌ | ✅ Repeating Groups | ✅ Sets | 🟡 | ✅ | Togal |
| **Confidence indicators visual** | 🟡 (data exists, weak UI) | 🟡 | ✅ | ✅ Assist | ✅ | STACK/Kreo |
| AI Chat grounded in plans | ✅ AiChat | ✅ Togal Chat | ❌ | 🟡 | 🟡 | Parity |
| 3D takeoff | ❌ | ✅ 2025 | ❌ | 🟡 | ❌ | Togal |
| Real-time multi-user collab | ❌ | ✅ | 🟡 Studio | ✅ | ✅ | Behind |
| Hover-highlight room↔table | ✅ Eksplikacija↔PDF | ✅ | 🟡 | ✅ | ✅ | Parity |

### B2. Togal.AI Detailed UX Pattern

Three primitive verbs with hotkeys:
- **C** — Cut/Subtract (draw region to subtract, double-click commit)
- **M** — Merge (draw extension into existing polygon)
- **S** — Split (click outside polygon, drag line through)

Side toolbar (left): Selection (Esc), 2D/3D toggle, pan, merge, cut, split, ruler, markup, undo/redo, settings, **Search Tools (Text/Image/Pattern)**, scale.

Right rail: Togal AI button, Togal Chat, Quantities, Breakdown, Export, Compare, PDF export.

**Drawing comparison UX:** Compare tab → "+" overlay sheet → algorithm auto-aligns → diff rendered as **blue=added, red=removed, grey=unchanged**.

### B3. Togal Pain Points (Per G2/Capterra/Trustpilot)

- High-resolution sheets lag, multi-tab opens trigger bugs
- Auto-takeoff over-captures (false positives) → forces rework, no efficient bulk-reject
- AI Chat "limited to plans" — does not reason about building process or local codes
- Civil/sitework/plumbing assemblies weak

**Implication for us:** Bulk-reject + grounded chat + LT codes (STR) are real openings.

### B4. Technical Implementation Patterns

**PDF.js layered model** (preferred for static overlays):
- Canvas (raster) → text-layer (selectable) → annotation-layer (HTML)
- Overlays via CSS positioning, native DOM clicks/taps

**Konva for editing only:**
- Move static overlays (room outlines, source dots) to plain SVG annotation-layer div
- Konva pays its cost only when user drags/edits
- One Konva layer per interaction mode + `.cache()` static layers
- Reference: [Konva FAQ](https://konvajs.org/docs/faq.html)

**Spatial index for hit-testing:**
- [rbush](https://github.com/mourner/rbush) — O(log n) bbox queries
- Bulk-load room polygons once after extraction
- Critical for ≥500 polygons (multi-floor commercial PDFs)

**Snap-to-edge:**
- Precompute pdfplumber line segments per page
- kdbush of endpoints + rbush of segment bboxes
- On cursor move: query within `snap_radius_px`, snap to nearest endpoint, then nearest line projection

**Reactive polygon editing:**
- Handle-per-vertex + mid-edge "phantom" handles for inserting points
- Commit on `dragend`
- Recompute area/perimeter via Shoelace formula
- Debounce recalc through `interiorCalc.js`

### B5. UX Patterns for AI-Extracted Overlays

**Confidence visualization:**
- Green ≥85%, yellow 60–84%, red <60%
- **Dashed border for AI-pending** vs solid for user-confirmed
- HIGH/MED/LOW already in our data — need polygon stroke-color + opacity surfacing

**Three-way bidirectional sync (table↔canvas):**
- Click row → scroll panel ✅ → jump page ✅ → **zoom-pan to polygon bbox with 600ms ease + 1.5s flash** ❌ (gap)

**Hover halo:**
- 4px outer-glow on polygon when hovering matching row
- Kreo/Togal both do this — dramatically improves wayfinding

**Industry keyboard convention:**
- `Esc` (select), `Space-drag` or middle-click (pan), `Ctrl+wheel` (zoom)
- `C/M/S` (cut/merge/split, Togal-style)
- `+/-` (zoom), `[/]` (prev/next page), `F` (fit page)

### B6. Sąmatų AI's Unique Leap-Frog Opportunities

1. **Eksplikacija-grounded HIGH confidence** — Togal/Kreo guess room names from OCR; we read from structured table. Display 🟢 "patvirtinta eksplikacijoje" lock badge on rooms with bbox-matched eksplikacija text. **Nobody else can do this.**
2. **STR/Sistela reasoning in AI Chat** — Togal Chat is "limited to plans". We can answer "ar šitam kambariui reikia hidroizoliacijos pagal STR?"
3. **F2/F3 export from canvas** — Mark polygons "atlikta", export F2 directly. LT-only, no Western tool competes.
4. **Sienų išklotinių auto-classifier** — Vision-classify each page (plan/pjūvis/fasadas/išklotinė/lubų) → route extraction per type. Ground truth: CLAUDE.md §4.
5. **"Praktinis vs tikslus" toggle** for GK/dažai — matches real LT pro workflow (CLAUDE.md §1.8).

---

## TOP 10 ACTIONABLE ADDITIONS (CONSOLIDATED RANKING)

Ranked by impact × feasibility, combining both parts:

| # | Item | Type | Impact | Effort | Differentiator? |
|---|---|---|---|---|---|
| 1 | Editable polygons (cut/merge/split + drag handles + C/M/S hotkeys) | UX | 🔥🔥🔥 | 3–5 d | Parity |
| 2 | Confidence Review Queue + 🟢 eksplikacija lock badge | UX | 🔥🔥🔥 | 1–2 d | **YES** (unique) |
| 3 | NRM2 tiered opening rule (3 m² threshold) | Accuracy | 🔥🔥 | 1 d | Quality |
| 4 | Polygon-based tile zones from išklotinės + niches + trim | Accuracy | 🔥🔥🔥 | 2 d | Quality |
| 5 | Symbol/pattern search ("find all door symbols") | UX | 🔥🔥 | 3–4 d | Parity |
| 6 | Sloped ceiling + stairwell modules | Accuracy | 🔥🔥 | 1–2 d | Quality |
| 7 | Drawing comparison (blue/red revision diff) | UX | 🔥🔥 | 4–6 d | Parity |
| 8 | Q4 thickness fix (3–5 mm) + sanding labor line item | Accuracy | 🔥 | 0.5 d | Quality |
| 9 | Snap-to-edge + scale auto-detect from text | UX | 🔥 | 2–3 d | Polish |
| 10 | Paint class (1/2/3) parameter → coats × coverage | Accuracy | 🔥 | 0.5 d | Quality |

**Bonus (low effort, high polish):**
- Three-way sync polish (zoom-pan-flash + hover halo) — 1 d
- Industry keyboard shortcuts — 0.5 d
- 4 new common mistakes → CLAUDE.md §8 + UI warnings — 0.5 d

---

## Full Source List

### Interior Finishing
- [RICS NRM 2: Detailed measurement for building works](https://www.rics.org/content/dam/ricsglobal/documents/standards/october_2021_nrm_2.pdf)
- [DIN 18363 — Painting and coating work](https://www.dinmedia.de/en/standard/din-18363/256187057)
- [Q1–Q4 Merkblatt 2 (Rigips DE)](https://www.rigips.de/loesungen-inspiration/oberflaechenqualitaet)
- [Tikkurila Optiva Primer TI](https://tikkurila.com/products/optiva-primer)
- [Caparol CapaSol LF technical](https://www.caparol.de/caparol_pim_import/caparol_de/products/ti/2869/TI_654.pdf)
- [theconstructor.org IS 1200 plastering deductions](https://theconstructor.org/practical-guide/deduction-plastering-painting-measurement-is-code/404476/)
- [Togal.AI Painting/Wallpaper trade page](https://www.togal.ai/trades/painting-wallpaper)
- [Bluebeam Wall Area methods](https://www.hagenbusiness.com/bluebeam-tip-of-the-week-3-wall-area-measurement-methods-for-estimators/)
- [NKBA Chapter 12 Interior Elevations](https://elearning.nkba.org/wp-content/uploads/2023/12/Chapter-12-Interior-Elevations-for-Kitchens-and-Baths-1.pdf)
- [MeasureSquare bathroom takeoff](https://measuresquare.com/use-case-bathroom-takeoff-software/)
- [Mexen LT plytelių kiekio skaičiavimas](https://mexen.lt/blog/naujienos-is-mexen-pasaulio/kaip-apskaiciuoti-plyteliu-kieki-sienai)

### PDF Interactive UX
- [Togal How it Works](https://www.togal.ai/how-it-works) · [2025 Features Roundup](https://www.togal.ai/blog/2025-features-roundup) · [Editor walkthrough](https://help.togal.ai/how-to-get-started-with-the-editor-mode) · [Editing Tools blog](https://www.togal.ai/blog/how-to-improve-the-efficiency-of-your-precon-workflow-using-the-editing-tools-in-togal-ai) · [Drawing Comparison](https://help.togal.ai/how-to-compare-drawings) · [Version History](https://help.togal.ai/version-history)
- [Bluebeam Dynamic Fill](https://support.bluebeam.com/online-help/revu20/Content/RevuHelp/Menus/Tools/Measure/Dynamic-Fill--T.htm) · [Bluebeam Count + Legend](https://support.bluebeam.com/revu/how-to/tips-and-tricks/boost-takeoff-workflows-with-count-tool.html)
- [Kreo Auto Measure 2.0](https://help-takeoff.kreo.net/en/articles/9722231-auto-measure-20) · [Kreo floor plan recognition](https://www.kreo.net/news-2d-takeoff/floor-plan-recognition-technologies)
- [STACK Assist](https://www.stackct.com/stack-assist/) · [STACK Floor Plan AI](https://www.stackct.com/floor-plan-ai/)
- [PDF.js layer architecture (react-pdf blog)](https://blog.react-pdf.dev/understanding-pdfjs-layers-and-how-to-use-them-in-reactjs)
- [Konva FAQ + performance](https://konvajs.org/docs/faq.html) · [rbush spatial index](https://github.com/mourner/rbush)
- [Confidence-based UI for AI takeoff](https://nedesestimating.com/how-ai-is-transforming-material-takeoffs-in-2026/)
- [Togal G2 Reviews](https://www.g2.com/products/togal-ai/reviews) · [Togal Capterra](https://www.capterra.com/p/10001876/Togal-AI/)
