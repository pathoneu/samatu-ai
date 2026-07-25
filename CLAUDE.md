# PATHON — Master Knowledge Base

> **Naming:** the product is **Pathon**. "Sąmatų AI" is the pre-2026-07-03 name — it should not appear in UI, exports or marketing. Code identifiers keep the old prefix on purpose: env vars (`SAMATU_*`), the SQLite file (`samatu.db`), localStorage keys (`samatu_projects`), the session cookie (`samatu_session`) and Render service names. Don't "fix" those — renaming them breaks live sessions and prod config.

**What this is:** A Lithuanian construction cost-estimation web app. It reads project PDFs, extracts quantities, calculates areas/volumes/lengths, and generates kiekių žiniaraščiai (quantity schedules). Replaces manual estimator (samatininko) work for construction company owners.

**Stack:** Python FastAPI backend + React/Vite/Tailwind/shadcn frontend. Anthropic Claude for vision + extraction. PDF→PNG via pdfplumber/pdf2image. Run `ls backend/`, `ls frontend/src/`, or `git log` to discover current code layout — don't trust a stale file tree here.

**Start-here manuals** (read before touching code): [`docs/DEVELOPING.md`](docs/DEVELOPING.md) — how to run/test/debug/ship + the gotchas that waste an hour (no-`--reload` backend, auth-on testing, which test runner). [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — real data flow + the **CANONICAL-vs-stale file map** (the LT formula engine is `backend/extractor/universal_rules.py` — canonical, backend is source of truth; `frontend/src/lib/interiorCalc.js` is **live**, not dead: `InteriorProject.jsx` still calls it as the fallback for legacy project blobs that carry no `skaiciavimai`, so never extend it and never delete it) + known fragilities + accuracy reality. [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — production launch/DNS/hosting.

---

## How to work with me

I do not want a yes-man. The single most valuable thing you can do is push back when I'm wrong.

- **Stress-test every proposal.** Before you say "yes, let's build that," ask out loud: *what's the worst case? what does this lock us into? where do the numbers stop working? what's the cheaper / smaller / dumber version that gets 80% of the value?* If you can't poke holes, you haven't thought hard enough.
- **Argue, with reasons.** If I propose something that conflicts with the research below, with the bake-off results, or with what we already learned — say so directly and explain the tradeoff. "I disagree because X" beats "sure, I'll do it" every time.
- **Don't preserve my ego over accuracy.** If a feature I love is empirically a dead end, say it. Cite the file/number.
- **Research before committing.** When facing a non-trivial decision (new library, new pipeline, new pricing approach, new UX pattern), dispatch an Explore or research subagent first. Don't guess from training data — the answer often already exists in `docs/superpowers/research/`.
- **Accuracy > code beauty.** Never refactor "for cleanliness" if the new pipeline scores below the existing one on real PDFs. Refactoring is allowed only when the new approach is at least as accurate.
- **Verify before claiming success.** Type-check ≠ feature works. For UI changes, open a browser. For pipelines, run on real PDFs. Say "I couldn't test X" rather than implying you did.
- **Honest disclosure beats clever fixes.** If something is brittle, AI-seeded, or measured against itself — flag it explicitly in the UI / report.

---

## What we built (working today on `viewer-rebuild` — the active branch; `main` is behind)

- **KŽ extraction** (`/extract`) — Claude reads construction PDF → rows (nr, description, unit, quantity, section). User enters prices. 21% PVM. Excel/PDF export.
- **Interior analysis** (`/extract-interior`) — Claude Vision reads interior design PDFs → dažomas plotas, angokraščiai, glaistymo kampai, lubų perimetras, užuolaidų nišos, grindjuostės, dažų kiekis, GK lapai, glaistas.
- **Assumptions panel** — `AssumptionsPanel`, opened from the **Prielaidos** button in `ProjectTopBar` (it is not a TabBar tab); live recalculation via `POST /api/recompute-quantities` (`frontend/src/lib/recomputeApi.js`) when user edits sienos storis, Q lygis, langai, durys per kambarį. The math runs **backend-side** — `frontend/src/lib/interiorCalc.js` is only the legacy-blob fallback.
- **Window fallback** — when Vision returns 0 windows, warns + suggests standard sizes per room type.
- **PDF viewer Phase C-1 / C-2 / C-4** — polygon editor (sienos/grindys redagavimas), trust signals (provenance popovers), visual polish (theme tokens, toolbar grouping, thumbnails, status bar).
- **AI Takeoff Viewer** — `TakeoffViewer` on **EmbedPDF/PDFium** is the DEFAULT viewer; room zones (red-ring model), measurement tools (distance/perimeter/area/count + calibration), click-to-fill. The old react-pdf `PlanViewer` survives behind `?viewer=legacy`. See `docs/ARCHITECTURE.md` § "The viewer stack".
- **Project type selection** — **Interjero projektas is the only default choice**; Automatinis / KŽ / Fasadai / Stogas / Žemės / Betonas sit behind the "kitas tipas" advanced disclosure in `NewProject.jsx`.

## What we tried — worked

- **Deterministic refactor (2026-04-27)** — backend simplified, code audit passed (`docs/superpowers/research/2026-04-29-code-audit.md`).
- **LT-pro pozicijų coverage** — Rangovo audits + follow-up done (`docs/superpowers/research/2026-04-2[89]-rangovas-*`).
- **Sonnet 4.6 vision for legend extraction** — clean per-symbol JSON; powers `detector_bench/core/legend_extractor.py`.
- **Pipeline 1 (Claude Vision direct)** — 49.3% mean accuracy, $0.10/page, ~3s/symbol. Best of the 6 we tested.
- **Pipeline 2 (pdfplumber regex)** — 41.8% accuracy, **$0**, fast. Solid free fallback for text-annotated PDFs.

## What we tried — didn't work

- **V1 isolated Vision calls** — ~30% accuracy, replaced.
- **V2.1 prompts** (`docs/VISION_PROMPTS_V2_1_updated.md`) — superseded by deterministic refactor.
- **Path A: XObject vector parsing** — all 3 LT test PDFs are flattened raster (Ghostscript / iLovePDF re-exports), no Form XObjects. Dead end (`docs/superpowers/research/2026-04-28-pdf-spike-findings.md`).
- **Pipeline 3 (cv2.matchTemplate)** — over-counts 100× on busy drawings (1772 dvigubas_jungtukas where truth=5). Tiny ~30 px legend glyphs match anywhere.
- **Pipeline 4 (hybrid text+template)** — 0% on P1: `pdfplumber.extract_words()` tokenization differs from `extract_text()`, no anchors found.
- **Pipeline 5 (GroundingDINO via Replicate)** — credit ran out after 1 call, 60/72 returned `402 Insufficient Credit`. Inconclusive, retest pending.
- **Pipeline 6 (Claude tool-orch)** — 23.3% accuracy at $1.20 (2× p1 cost). Inherits p3's fragility under expensive orchestration.
- **Window detection** — still unreliable across drafting styles. Fallback warns, but root cause unsolved.

Full bake-off: `detector_bench/README.md` + `results/2026-05-03-bakeoff.md`.

⚠️ **The bake-off harness no longer runs.** `detector_bench/benchmark.py` still imports `p3_template_match`, `p4_hybrid`, `p5_grounding_dino` and `p6_claude_tool_orch`, but only `p1_baseline_vision.py` and `p2_text_driven.py` remain in `detector_bench/detectors/` — the import fails at module load. The numbers above are historical; fix the imports (or drop the dead detectors) before quoting any *new* number from it.

## Open / next

- **Ground truth is still mostly AI-seeded.** The tooling question is *solved*: `scripts/build_ground_truth.py` exists and harvests **human-confirmed** signals straight out of the project blobs in SQLite (polygons with `polygon_source ∈ {corrected, manual}`, quantities with `manual_override` / `user_verified`). No separate 1-hour interactive flow — the corrections *are* the corpus. **The corpus is nearly empty** (~1 confirmed polygon + 1 confirmed quantity across the 21 dev projects), so accuracy numbers still largely measure agreement-with-Claude. The highest-leverage act is therefore **using the correction workspace on real projects**, not writing more harness code. (The old `detector_bench/build_ground_truth.py` referenced by `detector_bench/README.md` was never written and is superseded — ignore it.)
- **Count-correction UI — SHIPPED.** Viewer count tool with user-defined types + `CountLegendPanel` (`frontend/src/components/viewer/`) + the **Matavimai** list in `WorkspacePanel.jsx` (CSV/JSON export). The bake-off conclusion (ship 50% AI + a fast manual-correction tool, don't chase a perfect detector) is implemented; what's missing is *usage volume*, see the ground-truth bullet above.
- **Phase C-3 click-to-fill walls — SHIPPED and maintained.** `POST /api/click-to-fill` + the label-seeded auto-polygon path in `backend/main.py`, driven by the viewer's **Taisyti zoną** flow (`TakeoffViewer.jsx`, `PlanViewer.jsx`). The plan doc (`docs/superpowers/plans/2026-05-02-phase-c-3-click-to-fill.md`) is history, not a TODO.
- **Auth + DB exist.** Session auth (email + password via bcrypt work-factor 12, plus Google OAuth) and SQLite (`backend/db.py`, 10 tables: users, projects, extractions, usage_events, corrections, consumed_trials, billing_usage, webhook_events, invoices, admin_audit_log). `localStorage` is a **write-through cache** — the backend is source of truth (`frontend/src/lib/projectStore.js`).
- **Facade / roof / earthworks / concrete — endpoints exist but are thin.** `/extract-facade`, `/extract-roof`, `/extract-earthworks`, `/extract-concrete` in `main.py` run a single Vision pass + a small formula block. They are **not** at interior-module quality: e.g. `_calculate_roof_quantities` silently falls back to `pitch_degrees = 30` when the drawing gives no pitch, which quietly fabricates the slope factor. **2026-07-25 founder decision: all four are hidden from the launch UI** (`NewProject.jsx` keeps them in `ADVANCED_PROJECT_TYPES`, behind the "kitas tipas" disclosure). The validated `backend/extractor/roof/` package (geometry, evidence, page_authority, constraint_check, strategies) exists but **is not wired to `/extract-roof`** — wiring it is the real roof-module task.
- **F2/F3 export: backend-only, no UI by choice.** `backend/extractor/f2_export.py` + `backend/api/exports_v2.py` serve `/f2/{id}.json|.csv` and `/f3/{id}.json` and work. The UI buttons were **removed 2026-04-29 per founder feedback** (`ExportDropdown.jsx` §FIX-9) — absence of a button is a product decision, not a missing feature.
- **No Sistela integration.**

## Research index — read before re-googling

`docs/superpowers/research/` (21 files, all kept):
- **PDF feasibility & vision:** `2026-04-28-pdf-spike-findings`, `2026-04-29-phase-c-{libraries,opencv-feasibility,competitor-tech}`, `vision-prompting-techniques`
- **Competitor UX:** `2026-05-02-competitor-viewer-ui-deep-dive`, `auto-count-{ux-patterns,clickcount-ux}`, `industry-takeoff-tools`
- **LT specifics:** `lt-drawing-conventions`, `2026-04-28-takeoff-standards-and-pdf-ux`, `rangovo-p1-position-analysis`, `2026-04-2{8,9}-rangovas-*`
- **Polygon UX:** `2026-04-29-phase-c-polygon-ux`, `2026-04-29-isklotines-quality`
- **Validation / formulas:** `formula-validation`, `2026-04-28-accuracy-priorities`
- **Code state:** `2026-04-29-code-audit`

`docs/superpowers/plans/` — implementation history (backend simplification, deterministic refactor, Phase C-1/C-2/C-3, bake-off).

`docs/superpowers/specs/` — design docs (bidirectional plan traceability, PDF viewer trust).

---

## Operational rules

- All **UI text in Lithuanian**. Code identifiers and comments in English.
- shadcn/ui, **light "Nordic Slate" theme** — parchment page + white panels + slate ink + ONE muted evergreen accent, sharp 2px radius, IBM Plex Sans/Mono. Tokens live in `:root` in `frontend/src/index.css`; there is **no `dark` class on `<html>`** (the `.dark` block there is inert compat). Never reach for `bg-gray-900/950` — use the theme tokens.
- Currency **EUR €**, always **21% PVM**. Renovation: reverse VAT.
- Metric only: **m, m², m³, kg, l, vnt.**
- Every calculation must show its assumptions to the user (and let them override → recalc live).
- Every external API call: retry logic, max 3 retries.
- Every endpoint: explicit error handling.
- Confidence indicators on every quantity: 🟢 read directly, 🟡 partial+assumption, 🔴 fallback default.

---

# ═══════════════════════════════════════════════
# SECTION 1: ALL CONSTRUCTION TYPES & FORMULAS
# ═══════════════════════════════════════════════

## TYPE 1: VIDAUS APDAILA (Interior Finishing)

### 1.1 Dažomas plotas (Paintable Wall Area)
```
S_walls_gross = perimeter × ceiling_height
S_walls_net = S_walls_gross − Σ(window_openings) − Σ(door_openings) − Σ(tiled_zones) − Σ(furniture_zones) − Σ(panel_zones) + Σ(window_reveals) + Σ(door_reveals) + Σ(niches) + Σ(column_surfaces)
S_ceiling = floor_area (flat ceilings) OR from reflected ceiling plan
S_total_paintable = S_walls_net + S_ceiling
```
- Openings < 0.5 m² are NOT deducted (RICS NRM2 rule)
- Walls and ceilings are SEPARATE line items (different paint)
- Primer is a SEPARATE line item
- Each coat is a SEPARATE quantity line

### 1.2 Angokraščiai (Window/Door Reveals)
```
Per window: reveal_length = (2 × window_height + window_width)
Per door:   reveal_length = (2 × door_height + door_width)
reveal_area = reveal_length × wall_thickness
```

### 1.3 Glaistymo kampai (Plastering Corners)
```
corner_length = number_of_outer_corners × ceiling_height
```
- Count outer corners from floor plan
- Inner corners typically don't need corner bead

### 1.4 Grindjuostės / Lubų perimetras
```
baseboard = room_perimeter − Σ(door_widths) + 10% waste
ceiling_cornice = room_perimeter (no deductions) + 5% waste
```

### 1.5 Užuolaidų nišos (Curtain Niches)
```
niche_length = window_width + 2 × 0.20 (overhang each side)
niche_paintable_area = niche_length × niche_depth × 3 (top + 2 sides)
```

### 1.6 Grindų danga (Flooring)
```
floor_area = from plan polygon or length × width
```
Waste: straight +8%, herringbone +12%, hexagonal +16%, diagonal +12%

### 1.7 Sienų plytelės (Wall Tiles)
```
tile_area = tiled_wall_length × tile_height (from sienų išklotinės!)
```
- Bathroom: tiles to 2.0-2.4m height
- Kitchen backsplash: 0.6m between counter and cabinets
- Waste: straight +8%, herringbone +12%, hexagonal +16%

### 1.8 Gipskartonis (Drywall)
```
sheets = CEILING(wall_area / 3.0) × 1.10   // 1 sheet = 1.2×2.5m = 3.0 m², +10% waste
```
- Walls: 12.5mm, Ceilings: 9.5mm, Wet rooms: moisture-resistant (green), Fire: pink/red
- Per sheet: ~30 screws, joint compound ~12 m²/5kg bucket
- Corner bead: linear meters of outside corners

**PRACTICAL TIP from pros:** Many drywall estimators do NOT deduct window/door openings — they measure straight through because cutouts = waste material + cutting labor. Your app should offer BOTH options: "tikslus" (deducting openings) and "praktinis" (no deductions, openings = waste).

### 1.9 Tapetai (Wallpaper)
```
rolls = CEILING(wall_area / usable_area_per_roll)
```
- Standard roll: 0.53m × 10.05m = ~5.3 m² gross
- With pattern repeat: usable 3.5-5.0 m²/roll depending on repeat size

### 1.10 Dažų kiekis (Paint Quantity)
```
paint_liters = (paintable_area × coats) / coverage_rate
```
| Surface | Coverage (m²/l per coat) |
|---------|------------------------|
| Previously painted smooth | 10-12 |
| Plastered Q2-Q3 | 7-9 |
| Fresh plaster | 3-5 |
| Ceiling smooth | 10-12 |
| Primer | ~7 (0.15 l/m²) |

- First coat absorbs more — for 2 coats multiply by 1.8× (not 2.0×)
- Round up to full containers

### 1.11 Glaistymas (Skimming/Putty)
| Q-level | Use | Consumption | Typical thickness |
|---------|-----|------------|------------------|
| Q1 | Under heavy wallpaper | 0.8 kg/m²/mm | 0.5-1mm |
| Q2 | Under matte paint | 1.0 kg/m²/mm | 1-1.5mm |
| Q3 | Under semi-gloss | 1.2 kg/m²/mm | 1.5-2mm |
| Q4 | Under gloss/lacquer | 1.5 kg/m²/mm | **3-5mm** (full-surface skim) |
```
putty_kg = area × thickness_mm × consumption_rate
bags_25kg = CEILING(putty_kg / 25)
```

**Q4 sanding labor — SEPARATE LINE ITEM, often missed:**
```
glaistymo_šlifavimas_Q4 = wall_area × 0.30 h/m²    // 80-120 grit, 100% surface
```
Q4 = gloss/lacquer-ready surface. Every 0.1mm imperfection shows under gloss paint.
Source: Merkblatt Nr. 2 "Verspachtelung von Gipsplatten" (Bundesverband der Gipsindustrie),
DIN 18181/18363. Sanding labor alone is ~25-35% of total drywall finishing cost.

### 1.12 Hidroizoliacija (Waterproofing) — OFTEN FORGOTTEN!
```
bathroom_floor = floor_area (full coverage)
bathroom_walls = wall_perimeter × 0.30m (splash zone) + shower_zone_to_ceiling
shower_zone = shower_perimeter × ceiling_height (full height)
```
- This is a SEPARATE line item that most estimators forget
- Material: ~1.5 kg/m² liquid membrane, 2 coats
- Include waterproofing tape for corners: linear meters of floor-wall junctions

### 1.13 Elektros taškai (from rozečių planas)
```
outlets_count = count from electrical plan symbols
switches_count = count from electrical plan symbols  
data_outlets_count = count internet/antenna symbols
```

### 1.14 Santechnikos taškai (from santechnikos planas)
```
fixtures = count: toilets, sinks, showers, bathtubs, washing_machine_connections
drain_points = count: floor drains (trapai), linear drains
```

### 1.15 LED juostos (from lubų planas)
```
led_strip_length = sum of all LED niche lengths from ceiling plan
led_niche_length = measured from ceiling plan details
```

---

## TYPE 2: FASADŲ DARBAI (Facade Works)

### 2.1 ETICS System
```
facade_area_bruto = elevation_width × elevation_height (per side: N,S,E,W)
facade_area_neto = bruto − Σ(windows) − Σ(doors) − Σ(balconies)
```
Gable end (trikampis): area = 0.5 × base × height

**ETICS components per m² of insulation area:**
| Component | Quantity per m² |
|-----------|----------------|
| Adhesive (klijai) | 5.5 kg |
| Mechanical anchors (smeigės) | 7 vnt. |
| Reinforcement mesh | 1.1 m² (10% overlap) |
| Base coat (armavimo mišinys) | 4.5 kg |
| Primer (gruntas) | 0.25 l |
| Decorative render | 3.0 kg |

**Linear components:**
| Component | How to measure |
|-----------|---------------|
| Cokolinis profilis | Building perimeter (in 2.5m lengths) |
| Corner profiles | All building corners + window/door corner lengths |
| Window sill (palangės) | Σ(window widths + 2×5cm overhang) |
| Drip edge profiles | Σ(window top widths) |

### 2.2 Ventilated Facade
```
brackets = facade_area × 2.5 vnt./m²
vertical_profiles = facade_height × (facade_width / spacing)
insulation = facade_area_neto
wind_barrier = facade_area × 1.1
cladding = facade_area_neto / panel_area + 8% waste
```

---

## TYPE 3: STOGŲ DARBAI (Roofing)

### CRITICAL: Slope Factor
```
actual_roof_area = plan_area × slope_factor
slope_factor = 1 / cos(pitch_angle_in_radians)
```
| Pitch | Factor |
|-------|--------|
| Flat (1-3°) | 1.00 |
| 15° | 1.035 |
| 20° | 1.064 |
| 25° | 1.103 |
| 30° | 1.155 |
| 35° | 1.221 |
| 40° | 1.305 |
| 45° | 1.414 |

### Roofing components:
```
roof_covering = actual_area + 8% waste
ridge_tiles = ridge_length / tile_length
underlayment = actual_area × 1.10
battens (latai) = actual_area / batten_spacing (0.30-0.35m)
snow_guards = roof_length × rows_per_slope
gutters = eaves_perimeter
downpipes = every 10-12m + at corners
```

### Flat Roof:
```
membrane = roof_area × 1.15 (overlaps + upstands)
insulation = roof_area
vapor_barrier = roof_area × 1.10
parapet_flashing = parapet_perimeter
```

---

## TYPE 4: DAUGIABUČIŲ MODERNIZAVIMAS (Renovation)
Combines: facade ETICS (Type 2) + roof (Type 3) + window replacement + balcony glazing + stairwell finishing + basement insulation + heating/plumbing pipes
- Reverse VAT mechanism applies
- Energy class B minimum (≥40% savings)
- APVA/BETA investment plan format
- Max subsidy: 14,500 €/apartment

---

## TYPE 5: ŽEMĖS DARBAI (Earthworks)
```
pit_volume = length × width × depth
trench_volume = ((bottom_w + top_w) / 2) × depth × length
  where top_w = bottom_w + 2 × depth × slope_ratio
backfill = excavation − structure_volume
hauling = in_situ_volume × (1 + swell_factor)
```
Swell: sand 12%, clay 25%, rock 50%
Shrinkage on compaction: sand 8%, clay 12%

---

## TYPE 6: BETONAVIMO DARBAI (Concrete)
```
slab = L × W × thickness          (+6% waste)
beam = width × height × length
column = cross_section × height
footing = L × W × H (sum steps for stepped footings)
```
Formwork = all surfaces touching concrete (m²)
Rebar: slabs 80-120 kg/m³, beams/columns 150-250 kg/m³

---

## TYPE 7: MŪRO DARBAI (Masonry)
```
blocks = wall_area_neto / (block_L + joint) × (block_H + joint)
```
Common LT blocks: Keramzitbetonis 490×190×240mm, Aeroc/Bauroc 600×200×300mm
Lintels: opening_width + 2 × bearing (min 150mm each side)

---

## TYPE 8: PASTOLIAI (Scaffolding)
```
scaffolding_area = facade_length × (building_height + 2m safety)
```
Measured in m² face area. Setup/teardown = separate items.

---

## TYPE 9: GRIOVIMO DARBAI (Demolition)
```
waste_volume = structure_volume × expansion_factor (1.5-2.0)
hauling_trips = waste_volume / truck_capacity
```
Waste removal = ~80% of demolition cost. Separate hazardous (asbestos).

---

## TYPE 10: MEP (Inžineriniai tinklai)

### Electrical:
```
cable = Σ(panel→device runs) + 10% routing + 0.3m/connection
```
Count: outlets, switches, data points, light fixtures, circuit breakers

### Plumbing:
```
pipe = Σ(runs by diameter) + 10% fittings
```
Count: toilets, sinks, showers, bathtubs, valves, drains

### HVAC:
```
duct_area = duct_perimeter × length (for insulation)
radiators = from heating plan (count + kW capacity)
```

---

## TYPE 11: KELIŲ STATYBA (Roads)
```
asphalt = road_area × layer_thickness (2-3 layers)
base_course = road_area × base_thickness
curbs = 2 × road_length + intersections
drainage = pipe_length + manholes + catch_basins
```

---

# ═══════════════════════════════════════════════
# SECTION 2: STANDARD LITHUANIAN DIMENSIONS
# ═══════════════════════════════════════════════

## Windows (Langai)
| Type | Width×Height | Area |
|------|-------------|------|
| Small | 900×1500mm | 1.35 m² |
| Standard | 1200×1500mm | 1.80 m² |
| Large | 1500×1500mm | 2.25 m² |
| Panoramic | 2100×1500mm | 3.15 m² |

## Interior Doors (Vidaus durys)
| Room | Width×Height | Opening |
|------|-------------|---------|
| Living/Bedroom | 800×2000mm | 900×2100mm |
| Bathroom | 700×2000mm | 800×2100mm |
| WC | 600×2000mm | 700×2100mm |

## Ceiling Heights
- Soviet-era (1960-1990): 2.50m
- Modern (post-2000): 2.65-2.75m
- Commercial: 2.70-3.30m

## Wall Thicknesses
- GK partition: 0.075-0.10m
- Block bearing wall: 0.20-0.25m
- Exterior insulated: 0.30-0.50m

## Drywall
- Standard: 1200×2500mm = 3.0 m²
- Walls: 12.5mm, Ceilings: 9.5mm

---

# ═══════════════════════════════════════════════
# SECTION 3: WASTE FACTORS (add to net quantities)
# ═══════════════════════════════════════════════

| Material | Waste % |
|----------|---------|
| Concrete | 5-8% |
| Rebar | 2-4% |
| Bricks/blocks | 3-5% |
| Tiles straight | 5-10% |
| Tiles herringbone | 10-15% |
| Tiles hexagonal | 15-17% |
| Drywall | 10-15% |
| Paint | 5-8% |
| Insulation EPS/MW | 3-5% |
| Roofing | 5-10% |
| Laminate flooring | 5-10% |
| Wallpaper | 10-15% |
| Pipe/cable | 5-10% |
| Reinforcement mesh | 10-15% |

---

# ═══════════════════════════════════════════════
# SECTION 4: DRAWING TYPES — WHAT TO EXTRACT
# ═══════════════════════════════════════════════

| Drawing Type | Lithuanian Name | Extract |
|-------------|----------------|---------|
| Floor Plan | Aukšto/pertvarų planas | Room dimensions, walls, doors, windows, areas, perimeters |
| Section | Pjūvis | Ceiling heights, wall thickness, slab thickness, roof pitch |
| Elevation | Fasadas | Window/door positions+sizes, building height, facade area |
| Wall Development | Sienų išklotinės | **MOST IMPORTANT FOR INTERIOR** — tile zones, paint zones, furniture, niches, exact boundaries |
| Ceiling Plan | Lubų planas | Ceiling type, light fixtures, curtain niches, LED niche positions, height annotations (+2800 etc.) |
| Electrical Plan | Rozečių/apšvietimo planas | Outlet count, switch count, data points, fixture count |
| Plumbing Plan | Santechnikos planas | Fixture count, pipe routes, drain positions |
| Floor Plan | Grindų planas | Flooring materials per room, material quantities, baseboard lengths |
| Furniture Plan | Baldų planas | Built-in furniture zones (for paint deductions), appliance positions |
| Specification | Specifikacija | Door/window/finish schedules with exact sizes and types |

**AI should classify each PDF page** into one of these types and extract the relevant data. This page classification is a killer feature that competitors don't have for Lithuanian projects.

---

# ═══════════════════════════════════════════════
# SECTION 5: KŽ EXTRACTION RULES
# ═══════════════════════════════════════════════

1. Each row: eilės_nr, aprašymas, mato_vienetas, kiekis, skyrius
2. Missing quantity → null (user fills in)
3. Item with 2 units (m² AND m³) → two separate rows
4. Preserve section hierarchy
5. Lithuanian characters (ąčęėįšųūž) MUST be preserved
6. Common units: m², m³, m, vnt., kg, t, l, kompl., d.d.
7. Auto-detect construction type from content
8. Group by categories: žemės darbai, konstrukcijos, mechanika, elektra, apdaila
9. Filter duplicates across pages

---

# ═══════════════════════════════════════════════
# SECTION 6: VALIDATION CHECKS
# ═══════════════════════════════════════════════

Run these BEFORE presenting results:
1. Paintable wall area should be 2.5-4× floor area
2. Ceiling area ≈ floor area (flat ceilings)
3. Baseboard ≈ perimeter − 0.8m per door
4. Paint ≈ 0.22 l/m² (2 coats, 9 m²/l avg)
5. GK sheets = wall_area / 3.0 × 1.1
6. Insulation anchors = 6-8 per m² (if <5 or >10, wrong)
7. Facade area ≈ perimeter × height − 15-25%
8. Roof area > plan area if pitched
9. Concrete 100mm slab on 100m² = 10 m³
10. Window reveals ≈ 5m per standard window

If any check fails → show warning to user, don't hide it.

---

# ═══════════════════════════════════════════════
# SECTION 7: CONFIDENCE LEVELS
# ═══════════════════════════════════════════════

Every calculated quantity should have a confidence indicator:
- 🟢 HIGH: Value read directly from dimensions on drawing
- 🟡 MEDIUM: Value calculated from partial data + assumptions
- 🔴 LOW: Value estimated from room type defaults (fallback)

Show these in UI so user knows what to double-check.

---

# ═══════════════════════════════════════════════
# SECTION 8: COMMON ESTIMATOR MISTAKES TO PREVENT
# ═══════════════════════════════════════════════

1. Forgetting surface preparation (gruntas, glaistymas) as separate items
2. Not counting primer separately from paint
3. Missing waterproofing in wet rooms (hidroizoliacija)
4. Wrong PDF scale — ALWAYS verify scale before measuring
5. Counting same wall from both sides (double counting)
6. Forgetting deformation joints in long walls
7. Missing corner bead, sealing tapes, edge profiles
8. Not accounting for different ceiling heights per room
9. Forgetting fire-rated assemblies where required
10. Missing MEP penetration sealing (firestops)
11. Mixing ceiling drywall (9.5mm) with wall drywall (12.5mm) in one total — different thickness, different sheet counts; estimators often sum into one number
12. Skipping sanding labor — represents 25-35% of drywall finishing cost; rushed estimates count only material
13. Touch-up buffer too low on rough/textured walls — needs 10-20% extra paint, not just 5-8% standard waste factor
14. Specifying metal corner bead everywhere — only outside corners need metal; inside corners use cheaper paper tape

The app should WARN users about these commonly missed items.

> **Sources for #11-14:** RICS NRM2, Merkblatt Nr. 2 (Bundesverband der Gipsindustrie), DIN 18363, Tikkurila/Caparol TI sheets, Hyde Tools corner bead guide. Full research: `docs/superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md`

---

# ═══════════════════════════════════════════════
# SECTION 9: LT DOCUMENTS & FORMS
# ═══════════════════════════════════════════════

Document hierarchy: KŽ → Lokalinė sąmata → Objektinė sąmata → Suvestinė sąmata
- Forma F2: Atliktų darbų aktas (work done report)
- Forma F3: Pažyma apie atliktų darbų vertę (value certificate)
- Defektinis aktas: For additional/unforeseen works

Cost structure: Medžiagos ~60%, DU ~25%, Mechanizmai ~7%, Statybvietės iki 10%
Always: + pridėtinės išlaidos + pelnas + 21% PVM
Renovation: reverse VAT mechanism (atvirkštinis PVM)

---

# Standard pipeline for a new project PDF

1. Identify construction type from title/contents
2. Classify each page (plan, section, elevation, išklotinė, etc. — see Section 4)
3. Find and verify scale
4. Extract room data (name, dimensions, area, ceiling height)
5. Count openings (windows from elevations, doors from plans/schedules)
6. Read finishes from wall developments (išklotinės) or finish schedule
7. Calculate quantities using formulas from Section 1
8. Apply waste factors (Section 3)
9. Run validation checks (Section 6) — surface failures to the user, don't hide them
10. Present results WITH assumptions and confidence levels
11. Let user override any assumption → recalculate live
