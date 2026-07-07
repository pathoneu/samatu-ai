# Interior Finishing Formula Audit — 12 Categories

**Date:** 2026-05-06
**Scope:** Lithuanian interior finishing only (TYPE 1 in `CLAUDE.md` §1.1–§1.15).
**Methodology:** Each formula traced to ≥2 authoritative sources (RICS NRM2, DIN 18181/18299/18363/18365, Merkblatt Nr. 2, Knauf/Caparol/Tikkurila TDS, STR). Conflicts between RICS, VOB DIN, and LT practice are flagged so the app can surface assumptions to the user.
**Companion docs:** `docs/superpowers/research/formula-validation.md` (2026-04-26 cross-validation report — original source for many figures here), `docs/superpowers/research/2026-04-28-takeoff-standards-and-pdf-ux.md`.
**Implementation:** `backend/extractor/universal_rules.py::calc_room_quantities`, `backend/extractor/vision_call.py::_calc_*`.

> Convention used throughout: ≈ = "approximately equal", ⌈x⌉ = ceiling, "+10%" = multiplied by 1.10. All measurements metric. All paints liquid.

---

## 1. Sienų dažomas plotas (Paintable wall area, net)

**Formula:**
```
S_walls_gross  = perimeter × ceiling_height
S_walls_net    = S_walls_gross
                 − Σ(door_openings  ≥ T_deduct)
                 − Σ(window_openings ≥ T_deduct)
                 − Σ(tiled_zones)
                 − Σ(furniture/panel_zones)
                 + Σ(door_reveals  : 2H + W) × wall_thickness
                 + Σ(window_reveals: 2H + 2W) × wall_thickness     // see §7
                 + Σ(niche_internal_areas)
                 + Σ(column_surfaces)
S_walls_paintable = S_walls_net × walls_paint_factor[paskirtis]
```
where `T_deduct` depends on the convention (see "Conflict" below):
- LT practice: `1.0 m²` (any opening ≥ 1.0 m² is deducted)
- RICS NRM2 §29 (painting): `1.0 m²`
- RICS NRM2 §27 (floor finishes): `0.5 m²`
- DIN 18363 / VOB Part C: `2.5 m²` for reveal additions; deductions per "single-face" rule

**Inputs needed from drawings:**
- Floor plan: perimeter (lin m), wall thickness, opening count + sizes
- Section / specification: ceiling height
- Wall development (sienų išklotinė): tiled-zone polygons, furniture polygons

**Waste factor:** Wall paint quantity has its own waste (see §10), the *area* itself doesn't carry waste.

**Sources:**
1. **RICS NRM2** (2nd ed., 2012, reprinted 2021), §29 "Decoration": gross girth × height; openings ≥1.0 m² deducted on one face; openings >3.0 m² treated as separate items with reveals added back. — formula match: **exact**. PDF: `rics.org/content/dam/ricsglobal/documents/standards/october_2021_nrm_2.pdf`
2. **DIN 18363:2019-09** "VOB Teil C: Maler- und Lackierarbeiten", §5.2 (Abrechnung): openings ≤2.5 m² not separately deducted (net = gross). — formula match: **exact** but different threshold than NRM2.
3. **IS 1200 (India, useful as cross-check)** Part 13 §5.5: deductions tabled by opening size, reveal additions for openings >3 sq m. (theconstructor.org practical guide — secondary).
4. **Bluebeam Estimating Guide** "Wall Area methods for estimators" (`hagenbusiness.com`): gross-girth method matches NRM2 — secondary.

**LT-EU divergence (call out in UI):**
- LT contractor practice: deduct EVERY door + window above 1.0 m² (no upper threshold), and add reveals for EVERY opening regardless of size — i.e., LT practitioners over-deduct vs. NRM2 by including reveals on small windows. Code currently defaults to LT (`paint_deduction_standard: "LT"`).
- This is exposed via `Prielaidos` / Setup Wizard as `paint_deduction_standard ∈ {LT, NRM2, VOB}`.

**Edge cases / pitfalls:**
- **Open-plan rooms**: ratio of paintable walls to floor area drops below 2.0× (validation rule §6 in CLAUDE.md should accept 2.0–4.0 for >40 m² open plans).
- **Stairwells**: use `perimeter × max_height − Σ(0.5 × run × rise × steps)` per `universal_rules.py::stairwell_wall_area_m2` — naive perim×H over-counts 15–25%.
- **Sloped/vaulted ceilings**: walls reach the underside of the slope, so wall height varies per side. Code splits via `slope_factor(angle)` for the ceiling, but wall heights need explicit `min_h_m` / `max_h_m` per room in the future.
- **Double counting on shared walls**: each wall measured from one room only. The polygon-based extractor must deduplicate shared walls when totaling.
- **Furniture / built-in cabinetry**: deducted only when the spec says wall behind cabinet is unfinished (NKBA Ch.12 — common in kitchens, NOT in bedrooms with free-standing furniture).
- **Q4 finish areas**: Q4 quantities for paintable area should be calculated separately (different sanding labor — see §8/§9).

---

## 2. Lubų dažomas plotas (Ceiling paint area)

**Formula:**
```
Flat:        S_ceiling = floor_area_m2
Sloped:      S_ceiling = floor_area / cos(slope_angle_deg)            // slope_factor table
Vaulted:     S_ceiling = floor_area / cos(slope_angle_deg)            // symmetric vault
Coffered:    S_ceiling = floor_area × 1.15..1.25                       // +15–25% over flat
```
Then split by ceiling height into two line items (different scaffolding cost):
```
gkp_lubu_standart_m2 = S_ceiling   if H ≤ 3.0 m
gkp_lubu_virs_3m_m2  = S_ceiling   if H >  3.0 m
```

**Inputs needed from drawings:**
- Floor plan: floor area, ceiling type annotation
- Reflected ceiling plan (lubų planas): ceiling type by zone, slope direction
- Section: ridge angle, eave height (if mansard / vaulted)

**Waste factor:** None on the area itself; paint waste covered in §10.

**Sources:**
1. **RICS NRM2** §29.3: "Ceilings: measured horizontally over walls, flat as floor area, sloping/vaulted in true plane (developed area)." — formula match: **exact**.
2. **CLAUDE.md §3 slope_factor table** (slope = 1/cos θ) — derived from basic trigonometry, cross-checked against published roofing pitch multiplier tables (e.g., `roofingcalc.com`, NRCA). — formula match: **exact**.
3. **NKBA Chapter 12** (interior elevations): coffered ceilings add 15–25% over flat. — formula match: **paraphrase** (range, not single multiplier).
4. **painttalk.com / hunker.com** (industry forums, secondary): vaulted ceiling rule of thumb +20–35% — consistent with cos-formula at 30–45°.

**LT-EU divergence:** None. Geometry is universal.

**Edge cases / pitfalls:**
- **Mansard with knee walls (mansardiniai)**: CLAUDE.md mansard weighting (`mansardinis_svoris`) is for **floor area** under STR 1.05.06, NOT ceiling area. Don't apply STR weighting to ceiling — full ceiling is painted regardless of headroom.
- **Tempiamos (stretch/PVC) ceilings**: still measured per ceiling polygon, but rate / labor differs from GKP. Code distinguishes via `ceiling_type ∈ {gkp, pakabinamos, tempiamos, betonas}`.
- **Drop ceilings (pakabinamos) in wet rooms**: ceiling area is paint-zero (we paint only the soffits if visible). Code sets `walls_paint=1.0, ceiling_type=pakabinamos` for vonia/wc/san — ceiling paint excluded from `dazymo_plotas` if `ceiling_type not in (gkp, tempiamos)`. ✅ Correct in current code.
- **High ceilings (>3 m)**: scaffolding pricing is separate. Code already splits via `high_ceiling_threshold_m: 3.0`.

---

## 3. Grindų danga (Flooring) — by material

**Formula:**
```
floor_area_m2 = polygon_area  (or  L × W  for rectangular rooms)
quantity_with_waste = floor_area_m2 × (1 + waste_factor)
```

**Inputs needed:** Floor plan polygon, finish schedule (grindų planas).

**Waste factors (per material):**

| Material | Waste % | Source |
|---|---|---|
| Laminate / parquet straight | +8–10% | DIN 18365:2019 §4.4; LT QS rule of thumb 10% for default |
| Laminate diagonal | +12–13% | DIN 18365 |
| Parquet herringbone | +15–20% | DIN 18365 §4.4; manufacturer (Tarkett, Quick-Step) TDS |
| Parquet hexagonal | +15–17% | Manufacturer TDS |
| Tiles straight | +8–10% | NRM2 §27 (5–10%); LT QS practice 10% — code currently 8%, **raise to 10% to match QS default** (per `formula-validation.md` §2.9) |
| Tiles diagonal | +12–13% | TCNA Handbook |
| Tiles herringbone | +15–18% | TCNA Handbook; Mexen LT guide (`mexen.lt`) |
| Tiles hexagonal | +15–17% | TCNA Handbook |
| PVC / vinyl plank | +8% | DIN 18365 |
| Concrete (kalbant apie pramonines grindis) | 0% (volumetric mix loss handled separately) | — |

**Companion line items (often forgotten):**
- **Grindų išlyginamasis (self-levelling screed):** `screed_kg = floor_area × thickness_mm × 1.65 kg/m²/mm` (Weber Floor 4310 TDS: 20 kg → ~10 m² @ 5 mm). Bags = `⌈screed_kg / 25⌉`.
- **Akustinis padas (acoustic mat under floating floor):** `floor_area × 1.05` waste; mandatory in LT multi-family per **STR 2.01.07:2003** Rw ≥ 50 dB.
- **Plytelių klijai (tile adhesive):** C2 thin-bed Mapei Granirapid → 3.5 kg/m²; thick-bed 6–8 kg/m² (Mapei TDS).
- **Fugavimas (grout):** 0.5–1.5 kg/m² depending on tile size + joint width (Mapei Ultracolor Plus TDS).
- **Movement joints (judamosios siūlės):** ISO 13007 / EN 12004 require one joint per 4–5 m bay in LT climate. Linear m = `floor_area / 20`.

**Sources:**
1. **DIN 18365:2019-09** "Bodenbelagarbeiten" §4.4 Abrechnung: waste percentages tabled by lay pattern. — formula match: **exact**.
2. **RICS NRM2** §27 "Floor finishes": measured net of obstructions ≥0.5 m²; waste rolled into rate. — formula match: **paraphrase** (NRM2 puts waste in unit rate, not quantity).
3. **TCNA Handbook for Ceramic, Glass, and Stone Tile Installation** (annual): waste table by tile size + lay pattern. — formula match: **exact** for tile patterns.
4. **Mapei Granirapid TDS** (`mapei.lt`): adhesive consumption 3.5 kg/m² C2FT. — formula match: **exact**.
5. **STR 2.01.07:2003** "Pastatų vidaus ir išorės aplinkos apsauga nuo triukšmo": Rw ≥ 50 dB between dwellings. — formula match: **regulatory requirement**, not a quantity formula.

**Edge cases / pitfalls:**
- **Skirtingi danga vienam kambaryje** (e.g., kitchen island in tile, dining area in parquet): polygon must be split per material. Currently `calc_room_quantities` assumes one floor type per room — flagged as future fix.
- **Threshold strips (slenksčiai)**: linear m at every floor-material junction — usually missed.
- **Plinth subtraction**: tile adhesive / floor area is measured wall-to-wall regardless of plinth (plinth is on top of floor finish).
- **Floor below cabinetry / appliances**: in some kitchen scopes only the visible floor is finished. Specify which scope.
- **Concrete in garage/utility**: code already returns `pvc_grindys=0, isliginamasis=0` for `floor=concrete` rooms — ✅ correct.

---

## 4. Sienų plytelės (Wall tiles) — bathroom + kitchen backsplash

**Formula:**
```
Per elevation (sienų išklotinė):
    tile_area_segment = polygon_area_below_top_tile_line
                        − Σ(visible_fixtures_in_elevation)
                        + Σ(niche_back + 4 × niche_side_strips)

Aggregated for the room:
    plyteles_sienos_m2 = Σ(tile_area_segment) over all walls

Simplified fallback (when išklotinės are absent):
    plyteles_sienos_m2 = perimeter × tile_height_m
```
Default `tile_height_m`:
- Vonia / WC / san: 2.0 m (configurable; full-height to ~2.4 m premium)
- Kitchen backsplash: 0.6 m (between counter top 0.9 m and upper cabinet 1.5 m)

**Inputs needed:** Sienų išklotinės (most accurate); failing that, floor plan + room type rule.

**Waste factors:** see §3 table.

**Sources:**
1. **NKBA Chapter 12** "Interior Elevations for Kitchens and Baths" (PDF, NKBA eLearning): wall elevations are the ground truth for tile boundaries; deduct visible fixtures; niches measured as separate polygons. — formula match: **exact** for polygon approach.
2. **TCNA Handbook** §EJ-171 (movement joints): joints required at all wall–floor and inside corner intersections. — companion line item.
3. **Schlüter-Systems profile catalogue** (`schlueter.de`): trim profiles measured in linear metres at top of tile zone + outside vertical corners. — companion line item.
4. **Mexen LT** ("Kaip apskaičiuoti plytelių kiekį sienai", `mexen.lt`): LT-language confirmation of perimeter × height fallback. — formula match: **paraphrase**.
5. **MeasureSquare bathroom takeoff workflow**: per-wall polygon + niche additions. — formula match: **exact**.

**LT-EU divergence:**
- LT premium projects: tile-to-ceiling in vonia (2.7+ m). Code default 2.0 m too low for premium — `Prielaidos` already exposes `bathroom_tile_height_m`.
- LT economy projects: only "drėgnos zonos" (shower wall + sink wall) tiled, not full perimeter. Wall-by-wall polygon is the only correct approach here; perimeter × height fails.

**Edge cases / pitfalls:**
- **L-shaped walls / stepped tile heights** — the simplified `perim × H` formula breaks. Per `2026-04-28-takeoff-standards-and-pdf-ux.md` §A2 this is HIGH-IMPACT GAP — tile-zone polygon extraction not yet implemented (`extractor/wall_elevation.py` returns flagged data only).
- **Niches**: niche back + 4 internal sides ≈ 1.5–3 m² *additional* per niche. Often **completely missed** (current code does not surface).
- **Behind appliances** (washing machine, fridge): typically NOT tiled — but spec sometimes says "full coverage to wall behind appliance for moisture protection". Read the LT spec; default = subtract appliance width × tile height.
- **Movement joints in tile field**: every 4–5 m in LT climate (ISO 13007).
- **Backsplash differs in modernist kitchens**: full-height backsplash to underside of upper cabinets — height becomes 1.5 m, not 0.6 m.
- **Trim profiles** (Schlüter Jolly / Quadec): linear meters at top of tile + outside vertical corners. Code does NOT yet emit this position.

---

## 5. Grindjuostės (Baseboards / skirting)

**Formula:**
```
grindjuostes_base_m = perimeter − Σ(door_widths)
                       − Σ(shared_wall_with_other_finished_room)        // if continuous
grindjuostes_with_waste = grindjuostes_base_m × 1.10                    // +10% NRM2 §27
```
Skip baseboard entirely when:
- floor type = tile (vonia, WC, san, kitchen — silicone instead)
- floor type = concrete (garage, exterior tambūras)
- `walls_paint_factor == 0` (unfinished room)

**Inputs needed:** Perimeter (m), door count + widths, floor finish schedule.

**Waste factor:** **+10%** (cuts at corners, mitres, off-cuts).

**Sources:**
1. **RICS NRM2** §27.5 "Skirtings, edgings, etc.": measured net of openings, in linear metres along the line of skirting. — formula match: **exact**.
2. **DIN 18365:2019** §4.4: linear meter measurement, openings deducted. — formula match: **exact**.
3. **LT industry practice** (Rangovas audits, `2026-04-28-rangovas-p1-audit.md`): door width ~0.85 m default deducted per door. — formula match: **paraphrase**.

**LT-EU divergence:** None.

**Edge cases / pitfalls:**
- **Door width default**: code uses `0.85 m` (door + frame). LT STR door opening is typically 0.9 m for living rooms, 0.7–0.8 m for WC. The 0.85 average is acceptable as a fallback when door schedule isn't extracted.
- **Bathroom plinth = none**: code skips when `tile_floor=True` ✅. But: in LT some modern bathrooms install ceramic plinth (matching tile). When the spec calls for it, plinth_m = perim − doors. Currently NOT detected.
- **Open doorways (no door)**: code still deducts 0.85 m if `n_doors` includes doorless openings. The opening-vs-door distinction matters; revisit when doorway extraction is more reliable.
- **Built-in cabinetry / wall units**: subtract the cabinet's footprint along that wall.
- **Shared wall between two rooms with same floor finish**: plinth is continuous and counted once. Currently code computes plinth per-room — risk of double-counting on aggregated totals if the same wall is counted from both rooms. Mitigate by computing at project level after polygon dedup.
- **Mitre cuts**: each external corner adds ~5 cm of off-cut; 10% waste covers this for typical rectilinear rooms but rises to 15% for L-shaped / curved.
- **Profile depth/height (5 cm vs 10 cm vs 15 cm)** affects unit price, not quantity (same linear m).

---

## 6. Lubų karnizas (Ceiling cornice)

**Formula:**
```
karnizas_m = perimeter × 1.05      // +5% straight shadow-gap profile
           OR perimeter × 1.10     // +10% decorative cornice with corner mitres
```
Doors are **NOT** deducted (cornice runs above doors at ceiling level). Cornice excluded from rooms with non-decorative ceilings (vonia, garage, utility).

**Inputs needed:** Perimeter, room paskirtis, ceiling spec.

**Waste factor:** **+5%** straight profile / **+10%** mitred decorative profile.

**Sources:**
1. **RICS NRM2** §29.10 "Cornices": linear measurement at ceiling line; girth around the room. — formula match: **exact**.
2. **DIN 18363:2019** §5.3: cornice as separate item, linear m. — formula match: **exact**.
3. **Manufacturer TDS** (Orac Decor, NMC) recommends 8–12% waste for mitred profiles, 5% for shadow gap. — formula match: **paraphrase**.

**LT-EU divergence:**
- LT: cornice typically only in living rooms / bedrooms / corridors / hall (`_KARNIZAS_PASKIRTYS` set in `vision_call.py:586`). Wet rooms / garage / utility skip cornice. Some modern minimalist projects skip cornice altogether — surface as warning if cornice quantity > 0 in such projects.

**Edge cases / pitfalls:**
- **Code currently uses 5%** (`_calc_lubu_karnizas_m: perim * 1.05`) — too low for mitred decorative cornice in 4 internal corners (the typical case). Recommend bumping to **+10%** for any decorative cornice; keep 5% as a "shadow gap" sub-option.
- **Continuous shadow gap (gypsum reveal)**: not really cornice, but quantified the same — perimeter only, no waste, no deductions.
- **Niche and bay window perimeter**: add as additional linear m, not simple rectangle perimeter.
- **Multiple cornice profiles per room** (e.g., crown + dentil): each is a separate line item. Spec should be checked.
- **Ceiling material change at cornice line**: cornice still measured against the wall side, but installation depends on substrate (drywall vs concrete); separate labor rate.

---

## 7. Angokraščiai (Window/door reveals)

**Formula:**
```
Per door:
    door_reveal_length_m = 2 × door_height + door_width                 // 3 sides (no sill)
    door_reveal_area_m2  = door_reveal_length × wall_thickness

Per window:
    window_reveal_length_m = 2 × window_height + 2 × window_width       // 4 sides
    window_reveal_area_m2  = window_reveal_length × wall_thickness
```
Then either:
- **LT convention**: add reveals for EVERY opening (door + window) — currently `_opening_adds_reveal` returns True for all in LT standard.
- **NRM2 convention**: add reveals only when opening_area > 3.0 m².
- **VOB convention**: add reveals only when opening_area > 2.5 m² (DIN 18363).

**Inputs needed:** Window/door schedule (count, W×H), wall thickness from section/spec.

**Waste factor:** None on linear/area measure; covered by paint waste in §10 if reveals are painted.

**Sources:**
1. **RICS NRM2** §29.10 "Reveals, soffits, jambs": `2H + W` for doors (3 sides — no floor sill); `2H + 2W` for windows (4 sides — head, sill, 2 jambs). — formula match: **exact**. **CLAUDE.md §1.2 currently shows `2H + W` for windows — that is wrong** (29% undercount on a 1200×1500 window). See `formula-validation.md` §3.1.
2. **DIN 18363:2019** §5.3 (Anstrich von Laibungen): same geometry, threshold 2.5 m² for separate measurement. — formula match: **exact**.
3. **theconstructor.org** (IS 1200 reference): same geometry, threshold 3.0 m². — formula match: **paraphrase** (Indian standard, different threshold).

**LT-EU divergence (CRITICAL):**
- LT practice (universal_rules.py default): reveals on every opening. Justified because LT contractors price reveals as a separate trade.
- NRM2 / VOB: reveals only on >3.0 / 2.5 m² openings — small windows have reveals "absorbed" into the painted-wall rate.
- Surface this in `Prielaidos` — already implemented via `paint_deduction_standard`.

**Edge cases / pitfalls:**
- **Window reveal `2H + 2W` not `2H + W`** — direct error in CLAUDE.md §1.2 that was caught in formula-validation.md but still in the master doc. Fix CLAUDE.md when next edited.
- **Door reveals `2H + W`** is correct (no floor sill — door bottom meets floor finish, not a reveal).
- **Wall thickness when unknown**: 0.20 m is a safe LT default (block bearing wall). Print + 5 cm for insulated exterior reveals (palangė side has thicker wall). The Vision prompt should always read `pjūvis` (section) for wall_thickness, NOT default.
- **Internal partitions vs external walls**: internal openings have shallower reveals (~0.10 m GKP partition, ~0.20 m block partition); external walls 0.30–0.50 m. Mixing the two understates exterior reveal area by ~50%.
- **Palangės (window sills)** are a SEPARATE line item from reveal area: `n_windows × (window_W + 0.10 m overhang)` linear m, OR `× sill_depth_m` for area. Currently MISSING from code (M3 in formula-validation.md).
- **Slanting window reveals** (where reveal angles outward): use the actual angled length, not horizontal projection.

---

## 8. GKP (Drywall / Gipskartonis)

**Formula (sheets, screws, compound, profile, sanding):**
```
Sheets:
    sheets_count = ⌈ wall_area_m2 / 3.0 ⌉ × 1.12              // +12% waste

Screws:
    screws = sheets_count × 30                                 // Knauf: 30/sheet
                                                                // i.e. ~10/m²

Joint compound (siūlių glaistas — Knauf Fugen):
    fugen_kg = wall_area_m2 × 0.4                              // 0.3–0.5 kg/m² seam taping only

Mesh tape (siūlių armavimo tinklelis):
    tape_m = wall_area_m2 × 0.35                               // 0.35 m joint per m²

Metal frame (CW + UW, Knauf W111 partition):
    studs_CW_m   = ⌈ wall_length_m / 0.625 ⌉ × wall_height_m    // CW @ 625 mm c/c
    tracks_UW_m  = wall_length_m × 2                            // floor + ceiling
    Total profile metres ≈ wall_area × (1.8–2.5)

Outside corner bead (kampuotis):
    corner_bead_m = Σ(outside_vertical_corners × wall_height)
                  + Σ(door + window reveal outer edges)

Q-level sanding labor (Q4 only is significant; surface-prep equivalent):
    Q4_sanding_h = wall_area_m2 × 0.30 h/m²                    // 80–120 grit, 100% surface
```

**Inputs needed:** Wall polygon, ceiling polygon (separate; 9.5 mm vs 12.5 mm), partition vs lining indicator (W111 vs W112), Q-level target.

**Waste factor: +10–15% (use 12% as default).** Code in `universal_rules.py: drywall: 0.12` ✅.

**Sources:**
1. **DIN 18181:2008-10** "Gipsplatten im Hochbau – Verarbeitung" §5: sheet specification 1200×2500 mm, fastener spacing, joint preparation. — formula match: **exact**.
2. **Knauf W111 technical** (`knauf.lt`): CW75 + UW75 metal stud partition, CW @ 600 or 625 mm centres; 30 screws/sheet. — formula match: **exact**.
3. **Saint-Gobain Gyproc LT product sheet** (`gyproc.lt`): sheet size 1200×2500 mm, area 3.0 m², thicknesses 9.5 mm (ceilings) / 12.5 mm (walls). — formula match: **exact**.
4. **Merkblatt Nr. 2 "Verspachtelung von Gipsplatten"** (Bundesverband der Gipsindustrie, latest 2014 edition; available from `gips.de`): defines Q1–Q4 and required surface treatment. Sanding labor 25–35% of total finishing cost. — formula match: **exact** for sanding hours.

**LT-EU divergence:**
- LT practice has a "tikslus vs praktinis" toggle: "praktinis" measures wall through openings (treats cutouts as waste), "tikslus" deducts openings. Current code uses "tikslus" (subtract openings from sheet area) — but the **practical LT pro** approach for sheet count is to NOT subtract openings (window cutout = waste). Surface as a Setup Wizard option (per CLAUDE.md §1.8 PRACTICAL TIP).

**Edge cases / pitfalls:**
- **Walls vs ceilings**: 12.5 mm (walls) and 9.5 mm (ceilings) are separate line items, separate sheet counts. Estimators frequently sum them — common mistake #11 in CLAUDE.md §8.
- **Wet rooms**: green moisture-resistant board (ZH/ZG) at higher cost; specify by paskirtis.
- **Fire-rated**: pink/red board (Knauf GKF) for fire-rated assemblies; STR 2.01.06 may require it in escape routes.
- **Inside vs outside corner**: inside corners use **paper tape** (cheaper), outside corners need **metal corner bead** — common mistake #14 in CLAUDE.md §8.
- **Ceiling on metal C-profile**: profile metres ≈ floor_area × 2.5 (CD + UD primary + secondary).
- **Acoustic mineral wool inside cavity**: STR 2.01.07 mandates Rw≥50 dB between dwellings; mineral wool m² = wall area, often missed (M13 in `formula-validation.md`).
- **Vapour barrier (garosandara)** in wet rooms: PE 0.2 mm × wet_wall_area × 1.10 — manufacturer warranty requires it (M10 in formula-validation.md).
- **Q-level vs sheet**: sheet count is independent of Q-level; Q-level affects skim quantity (§9) and sanding labor.

---

## 9. Glaistas / Putty (Q1–Q4)

**Formula:**
```
glaistas_kg = paintable_area_m2 × thickness_mm × consumption_kg_per_m2_per_mm
bags_25kg   = ⌈ glaistas_kg / 25 ⌉
```

| Q-level | Use case | Consumption (kg/m²/mm) | Default thickness (mm) | Result (kg/m²) |
|---|---|---|---|---|
| **Q1** | Under heavy wallpaper / non-decorative | 0.8 | 0.5–1.0 (default 0.75) | 0.6 |
| **Q2** | Under matte paint (LT default) | 1.0 | 1.0–1.5 (default 1.25) | 1.25 |
| **Q3** | Under semi-gloss / silk paint | 1.2 | 1.5–2.0 (default 1.75) | 2.10 |
| **Q4** | Under gloss / lacquer / raking light | 1.5 | **3.0–5.0** (default 4.0) | 6.0 |

Code values in `vision_call.py:488–493`:
```
_Q_GLAISTAS_KG_PER_M2_MM = {"Q1": 0.8, "Q2": 1.0, "Q3": 1.2, "Q4": 1.5}
_Q_GLAISTAS_THICKNESS_MM = {"Q1": 0.75, "Q2": 1.25, "Q3": 1.75, "Q4": 4.0}
```

**Q4 sanding labor (separate line item):**
```
glaistymo_šlifavimas_Q4_h = paintable_area × 0.30 h/m²
```

**Inputs needed:** Paintable wall area (§1), Q-level target from spec.

**Waste factor:** +5–8% built into thickness default; for very rough substrates use upper end.

**Sources:**
1. **Merkblatt Nr. 2 "Verspachtelung von Gipsplatten"** (Bundesverband der Gipsindustrie, 4. Auflage 2014, available `gips.de` and Knauf Konstruktionshandbuch): defines Q1/Q2/Q3/Q4 surface qualities; Q4 = full-surface skim ≥3 mm minimum, sanded to gloss-paint-ready. — formula match: **exact** for thickness + consumption.
2. **DIN 18181:2008-10** §5.4 + **DIN 18363:2019-09** §3.4: align with Q-level system. — formula match: **exact**.
3. **Knauf Uniflott / Knauf Fugen TDS** (`knauf.lt`): consumption 1.0–1.2 kg/m²/mm thickness for full-area skim. — formula match: **exact**.
4. **Caparol Akkordspachtel TDS** (`caparol.de`): 1.0 kg/m²/mm baseline. — formula match: **exact**.

**LT-EU divergence:**
- LT default = Q2 (matte paint). German residential leans Q2; commercial offices Q3. Premium LT residential (penthouses, design hotels) = Q4 — code surfaces this via `paint_class_inference` from spec text (Sprint 0 Fix 5).
- The widespread LT "skubotas" practice of Q1 + matte paint produces visible joint shadows — flag in UI when paint_class=2/3 but Q-level=Q1.

**Edge cases / pitfalls:**
- **Q4 thickness was 2.5 mm in legacy code, fixed 2026-04-28** to 4.0 mm per Merkblatt Nr.2 — every 0.1 mm imperfection visible under gloss paint. **Premium projects under-quoted ~30% before the fix.**
- **Q4 sanding labor missing in many estimates** — represents 25–35% of total drywall finishing cost (mistake #12 in CLAUDE.md §8).
- **Substrate matters**: fresh sand-cement plaster needs thicker skim (more absorption); GKP needs less.
- **Surface preparation (Q1 → Q2 upgrade)**: some specs require partial Q3 in raking-light areas only (e.g., near windows). Should be measured per zone, not per room.
- **Skim ≠ joint compound**: §8 joint compound (~0.4 kg/m²) is for seam taping only. Full-surface skim is a separate position. Both are needed for Q3+.
- **Water demand and mixing loss**: typically rolled into the kg/m²/mm consumption rate.

---

## 10. Dažai (Paint) — coverage by surface state

**Formula (per paint class, EN 13300):**
```
paint_liters = paintable_area_m2 × absorption_factor / coverage_m2_per_l

Class 1 (top opaque, prepared substrate, e.g. Tikkurila Joker):
    coverage = 10 m²/L, coats = 1, absorption_factor = 1.0

Class 2 (LT default — Sikkens Alpha Matt, Dulux Easycare, Sniezka):
    coverage = 9 m²/L,  coats = 2, absorption_factor = 1.8

Class 3 (rough textured / fresh plaster):
    coverage = 7.5 m²/L, coats = 3, absorption_factor = 2.5
```

**Primer (gruntas) is a SEPARATE line item:**
```
primer_liters = paintable_area_m2 / 7        // 0.15 L/m² standard primer (Tikkurila Optiva, Caparol Tiefengrund)
                paintable_area_m2 / 5        // 0.20–0.25 L/m² deep-penetration on porous substrate
```

**Inputs needed:** Paintable area (§1, §2), substrate state, paint class from spec.

**Waste factor:** **+5–8%** for standard, **+10–15%** for rough/textured walls (mistake #13 in CLAUDE.md §8). The absorption_factor (1.8 or 2.5) already buffers re-coats; waste is on top.

**Coverage by surface state (m²/L per coat):**

| Surface | Coverage | Source |
|---|---|---|
| Previously painted smooth | 10–12 | Tikkurila Optiva TDS |
| Plastered Q2–Q3 (LT default) | 7–9 (use 8–9) | Tikkurila/Caparol TDS |
| Fresh gypsum plaster (Knauf Rotband) | 5–7 | Tikkurila/Caparol TDS |
| Fresh sand-cement plaster | 3–4 | Tikkurila/Caparol TDS |
| Ceiling smooth | 10–12 | Tikkurila TDS |
| Standard primer (Tiefengrund) | ~7 (0.15 L/m²) | Caparol CapaSol LF TDS |
| Deep primer (porous substrate) | ~5 (0.20 L/m²) | Caparol Tiefengrund CT 17 TDS |

**Sources:**
1. **EN 13300:2017** "Paints and varnishes — Water-borne coating materials and coating systems for interior walls and ceilings — Classification": defines opacity classes 1–4 (Class 1 = highest hide; Class 4 = lowest). — formula match: **exact**, basis for paint_class system.
2. **Tikkurila Optiva 5 / Joker / Otex TDS** (`tikkurila.lt` and `tikkurila.com/products/optiva-primer`): coverage values per substrate state. — formula match: **exact**.
3. **Caparol CapaSol LF TDS** (`caparol.de/caparol_pim_import/.../TI_654.pdf`) and **Caparol Akkordspachtel TI**: primer coverage 7 m²/L; first-coat absorption 1.8×. — formula match: **exact**.
4. **DIN 18363:2019** §5.2: 2-coat system standard for matte paint on prepared substrate. — formula match: **exact**.
5. **Squote Paint Coverage Guide** (`squote.io/paint-coverage`, secondary, useful for cross-check): consistent coverage ranges. — formula match: **paraphrase**.

**LT-EU divergence:** None — manufacturer TDS values used. EN 13300 is harmonised across EU.

**Edge cases / pitfalls:**
- **First-coat absorption is 1.8×, not 2.0×** — first coat fills pores (more absorbed); second coat is a thin film (less). Multiplying coats by 2.0× over-buys 10%.
- **CLAUDE.md §6 Check 4 says 0.22 L/m²** — that's 2.0× factor; use **0.20 L/m²** (1.8× factor).
- **Primer counted with paint** is a common mistake (#1 in CLAUDE.md §8). They are separate trades, separate materials, separate kž rows.
- **Spray vs roller**: spray increases consumption ~25% (overspray loss). Default = roller; flag as warning if spec says spray.
- **Round up to full container sizes** (1 L / 3 L / 9 L / 18 L) — code currently returns float litres; UI should round up.
- **Color saturation matters**: deep colors (red, dark blue) often need 3 coats not 2; use Class 3 profile or upgrade default for non-white finish.
- **Paint class inference from spec** (Sprint 0 Fix 5): code reads `paint_class` from spec text where possible; falls back to user wizard setting.

---

## 11. Hidroizoliacija (Waterproofing)

**Formula (LT bathroom standard):**
```
hidro_floor_m2  = floor_area_m2                                       // full coverage
hidro_walls_m2  = wall_perimeter_m × 0.30 m                           // splash zone (30 cm up from floor)
                 + shower_zone_perimeter × ceiling_height               // shower full height
hidro_total_m2 = hidro_floor + hidro_walls

Material:
    membrane_kg   = hidro_total × 1.5–2.5                              // 2 coats Mapelastic
                                                                       // 1.5 smooth screed; 2.0–2.5 rough concrete

Companion linear items:
    waterproof_tape_m = bathroom_floor_perim
                       + shower_floor_perim
                       + n_pipe_penetrations × 0.30 m                  // collar around each pipe

    silikonas_m       = bathroom_floor_perim
                       + shower_vertical_corners
                       + bath_rim_length
```

Code in `vision_call.py:625–643`:
```python
plotas + perim × 0.30 + (1.0×2 + 1.2) × H if has_shower
```

**Inputs needed:** Bathroom polygon, shower/bath fixture location + size, wall_thickness (for pipe penetrations).

**Waste factor:** +10% (irregular geometry around fixtures).

**Sources:**
1. **STR 2.04.01:2018** "Pastatų atitvaros. Sienos, stogai, langai ir išorinės įėjimo durys": vonios ir san. mazgų hidroizoliacijos reikalavimai. — formula match: **regulatory** (LT mandatory).
2. **Mapei Mapelastic / Mapelastic HP TDS** (`mapei.lt`): consumption 1.5–2.5 kg/m² over 2 coats; reinforcing tape required at corners and pipe collars. — formula match: **exact**.
3. **Schlüter Kerdi-Band / Kerdi-Coll** (`schlueter.de`): 5 cm tape at all wall–floor and wall–wall corners; 30 cm collar at pipe penetrations. — formula match: **exact**.
4. **DIN 18534-1:2017-07** "Abdichtung von Innenräumen, Teil 1: Anforderungen": classifies wet zones W0–W3; W3 (high water exposure, e.g. shower) requires full-height waterproofing. — formula match: **exact** for "shower full height" rule.
5. **EN 14891:2017** "Liquid-applied water impermeable products for use beneath ceramic tiling": testing standard for liquid membranes. — companion / spec reference.

**LT-EU divergence:**
- LT STR 2.04.01 mandates hidroizoliacija in vonia/wc/san. DIN 18534 splits W0/W1/W2/W3 — most LT bathrooms = W2 (occasional water) outside shower, W3 inside shower. Code's "perim × 0.30" everywhere + shower-only-full-height is a reasonable approximation of DIN 18534 mapped onto LT scope.
- LT economy projects often skip wall waterproofing entirely outside the shower stall — non-compliant with STR but common. Flag as warning when hidro_walls_m² == 0 in vonia.

**Edge cases / pitfalls:**
- **OFTEN FORGOTTEN entirely** — common mistake (CLAUDE.md §1.12 and §8). Should always emit a hidro line for vonia/wc/san even when not in spec.
- **Membrane thickness 1.5 vs 2.5 kg/m²** depends on substrate roughness. CLAUDE.md §1.12 says 1.5 — too low for rough block walls. Use 2.0 as default; 1.5 only on smooth screed.
- **Shower zone definition**: code currently approximates as `(1.0 m × 2 + 1.2 m) × H` (2.0×1.2 m typical shower). For walk-in showers (modern LT trend), use actual polygon: shower_perimeter × H.
- **Bathtub spillover zone**: bathtubs need waterproofing only on the wall behind + 0.20 m above tub rim per Mapei spec. Currently lumped into "splash zone".
- **Corner reinforcing tape (Mapeband)** is a SEPARATE line item often missed (M6 in formula-validation.md): linear m at floor-wall junctions + pipe penetrations.
- **Floor drain (trapas) collar**: 30 cm × 30 cm patch around each drain, with manufacturer-specific drain flange. Separate item per drain count.
- **Double-application around pipes**: pipe collars + 5 cm overlap onto wall — small additional area, usually rolled into the +10% waste factor.
- **Glaistas vs hidroizoliacija**: hidro membrane goes ON TOP of skim (Q2), not instead of. Both are needed.

---

## 12. Dažomi kampai (Painted corners) — outer + inner + reveal edges

**Formula:**
```
kampai_total_m = perim                                              // ceiling-wall junction (top perimeter)
                + 4 × ceiling_height                                  // 4 inner vertical corners (rect room)
                + Σ(door_widths   + 2 × door_heights)                 // door reveal edges
                + Σ(window_widths + 2 × window_heights)               // window reveal edges
                + Σ(extra_outer_corners × ceiling_height)             // L-shape, niches, columns
```

This is the **paint-edge** total — the linear meters that need careful brushwork (cutting in) regardless of whether they get a metal corner bead. The **drywall corner bead** (§8) is a subset: only outside corners get bead.

**Inputs needed:** Perimeter, ceiling height, door + window count + sizes, niche/column count.

**Waste factor:** None on the linear measure; brushwork is labor-priced per linear m.

**Sources:**
1. **RICS NRM2** §29.10 "Junctions, intersections, angles": measured in linear metres. — formula match: **exact**.
2. **DIN 18363:2019** §3.4 separates "Eckschutzprofile" (corner protection) from "Anstrich von Kanten" (edge painting). — formula match: **exact** distinction.
3. **Hyde Tools corner bead guide** (`hydetools.com`, manufacturer educational): outside corners use metal/PVC bead; inside corners use paper tape. — formula match: **paraphrase** (gives the inside-vs-outside rule).

**LT-EU divergence:**
- LT samatininko convention bundles "kampai" into one position (linear m) regardless of inside/outside. Code does this. The outside-corner-bead-only position should be split out for tikslus accounting (mistake #14, CLAUDE.md §8).

**Edge cases / pitfalls:**
- **Code currently uses door 0.9×2.05 and window 1.2×1.5** as reveal-edge defaults (universal_rules.py:489–495). When actual schedule is extracted, these should be replaced with per-opening values.
- **Inside vs outside corner bead spec**: outer corners need metal/PVC bead (~€1.5–3/m); inner corners use paper tape (~€0.20/m). Estimators who spec "metal everywhere" overprice 20–30%.
- **Niches / built-in columns**: each adds 4 outer corners × ceiling_height of additional kampai. Code does NOT auto-detect these; relies on `elementai` extraction.
- **Ceiling-wall junction**: technically an inside corner (where the wall meets the ceiling) — no metal bead; paper tape or shadow-gap profile. The `perim` term in the formula is for paint-edge labor, not bead.
- **Sloped/coffered ceilings**: each slope edge adds linear m of corner. Currently not captured.
- **Open-plan room transitions**: the line where two flooring materials meet at a doorless opening = an inner corner if the room paint extends through; needs spec interpretation.

---

# Cross-Reference Table — Formulas vs. Implementation

| # | Formula | Implementation | Deviation from canonical |
|---|---|---|---|
| 1 | Sienų dažomas plotas | `universal_rules.py::calc_room_quantities()` lines 427–447 | LT default deducts every opening ≥1.0 m² and adds reveals on all (NRM2/VOB toggle exists). ✅ matches §1 with `paint_deduction_standard`. |
| 2 | Lubų dažomas plotas | Same function, lines 449–474 | Sloped/vaulted/coffered all implemented. Wet-room ceiling-paint-zero: `ceiling_type ∈ ("gkp","tempiamos")` gate ✅. |
| 3 | Grindų danga | Same function, lines 480–514 (`pvc_grindys`, `plyteles_grindys`, `isliginamasis`); waste factors in `UNIVERSAL_RULES["waste_factors"]`. | **Tile waste 8% — should be 10%** per §3 + `formula-validation.md` §2.9. Movement joints / acoustic mat / tile adhesive / grout NOT yet emitted as separate positions. |
| 4 | Sienų plytelės | `tile_walls_area = perim × tile_height` simplified fallback (line 441). True polygon-based extraction in `extractor/wall_elevation.py` returns flagged data only — **NOT yet wired into quantities**. | HIGH-IMPACT GAP per `2026-04-28-takeoff-standards-and-pdf-ux.md` §A2: niches missed, L-shapes wrong, trim profiles missing. |
| 5 | Grindjuostės | Same function, lines 504–510 | ✅ Includes +10% waste (per `formula-validation.md` §2.8 fix). Door width 0.85 m default. Skips for tile/concrete/walls_paint=0. |
| 6 | Lubų karnizas | `vision_call.py::_calc_lubu_karnizas_m` line 592 | **Uses 5% waste**. Should bump to 10% for mitred decorative cornice (default case). Code restricts to `_KARNIZAS_PASKIRTYS` ✅. |
| 7 | Angokraščiai | Reveal-edge linear m baked into `kampai` formula in `calc_room_quantities` lines 488–495. Reveal *area* (× wall_thickness) NOT computed separately. | **Window reveal length uses `window_W + 2 × window_H` = `2H + W`** in code line 495 — this is CORRECT geometry for the kampai linear-m, but the same incorrect formula appears in CLAUDE.md §1.2 as if it were window reveal area length, which **needs `2H + 2W`** for area. No separate `angokrasciu_gkp_m` × wall_thickness → m² calculation in current path. |
| 8 | GKP | `universal_rules.py::UNIVERSAL_RULES` (sheet 3.0 m², 30 screws, 0.4 kg/m² compound, 12% waste). `vision_call.py::build_gkp_pozicijos` line 735 emits drywall positions. | **Metal frame (CW+UW) NOT emitted** — major omission per `formula-validation.md` M9 (30–40% of partition material cost). Mesh tape missing. Vapour barrier missing in wet rooms. |
| 9 | Glaistas | `vision_call.py::_calc_glaistas_kg` line 517, with thickness/consumption tables lines 488–495. | ✅ Q4 thickness fixed to 4.0 mm (was 2.5 mm). Q4 sanding labor `_Q4_SANDING_HOURS_PER_M2 = 0.30` defined line 495 — verify it gets emitted as a position. |
| 10 | Dažai | `vision_call.py::_calc_dazai_liters` line 531, paint class profiles lines 509–513. | ✅ Class 1/2/3 system implemented. Primer coverage 7 m²/L. Surface-state coverage variants (fresh gypsum vs cement plaster) NOT split — uses single Class 2 default for "plastered". |
| 11 | Hidroizoliacija | `vision_call.py::_calc_hidroizoliacija_m2` line 625 | ✅ Floor + perim × 0.30 + shower zone × H. Shower zone hardcoded to 1.0×1.2 m bath approximation — should use real shower polygon when available. Mapeband / corner tape NOT emitted as separate item. Membrane consumption (kg) NOT computed. |
| 12 | Dažomi kampai | `calc_room_quantities` lines 488–495 | ✅ Includes ceiling perim + 4 inner verticals + door/window reveal edges. **Does NOT separate inside (paper tape) vs outside (metal bead) corners** — overstates metal corner bead by ~70% in typical rectangular rooms. |

---

# Key Conflicts Requiring Product Decisions

1. **Opening deduction threshold**: LT (1.0 m² always-deduct, always-reveal) vs. NRM2 (>3.0 m² for reveal-add) vs. VOB (>2.5 m²). Already a `Prielaidos` setting; default = LT. **Decision needed**: should the UI label "LT" as "praktinis (LT)" and call out that NRM2/VOB are different international conventions?
2. **CLAUDE.md §1.1 says <0.5 m² not deducted; code uses 1.0 m²**. CLAUDE.md is wrong for *painting* (NRM2 §29 = 1.0 m²; the 0.5 m² threshold is from NRM2 §27 floor-finishes). **Action**: fix CLAUDE.md when next edited.
3. **CLAUDE.md §1.2 window reveal = `2H + W`** (3 sides, MISSING the sill side). Should be `2H + 2W` (4 sides). **Action**: fix CLAUDE.md; **29% undercount per window when this gets used directly**.
4. **Tile waste 8% vs 10%**: code uses 8% as universal default. NRM2/LT QS practice is 10% with 8% only for very simple rectangular rooms. **Action**: bump default to 10%.
5. **Cornice waste 5% vs 10%**: code uses 5%. Mitred decorative cornice with 4 internal corners needs 10%. **Action**: bump default to 10%; keep 5% as "shadow gap" sub-option.
6. **Q4 thickness was 2.5 mm, fixed to 4.0 mm** in 2026-04-28. Confirmed correct now per Merkblatt Nr. 2.
7. **Drywall sheet count: deduct openings or treat as waste?** LT pro convention varies. **Action**: Setup Wizard toggle "tikslus / praktinis" — currently NOT exposed.
8. **Inside vs outside corner bead split**: code lumps all "kampai" together. **Action**: split into two positions (paper tape m / metal bead m); will reduce metal-bead over-spec by 70%.
9. **Paint coverage on fresh plaster — gypsum (Rotband) ≠ sand-cement**: code uses one "Class 3" profile (7.5 m²/L) for all fresh plaster. **Action**: split into two substrate variants (5–7 vs 3–4 m²/L).
10. **Hidroizoliacija membrane consumption** (kg) is NOT currently calculated even though area is. **Action**: emit `hidroizoliacija_kg = hidro_total_m² × 2.0 (default)` as separate position.
11. **GKP metal frame (CW+UW)** NOT emitted as a position. **Action**: add `studs_CW_m` + `tracks_UW_m` line items — material cost ≈ 30–40% of partition assembly.
12. **Acoustic insulation in GKP partitions**: STR 2.01.07:2003 mandates Rw ≥ 50 dB between dwellings. Currently NOT auto-emitted. **Action**: emit `mineraline_vata_m²` for all GKP partitions in multi-family per regulatory rule.

---

# Authoritative Sources Consulted

| Standard / Doc | Publisher | Year | Used For |
|---|---|---|---|
| RICS NRM2 (2nd ed.) | RICS | 2012, reprint 2021 | §29 paint, §27 floor, §29.10 reveals/cornices |
| DIN 18181 | DIN | 2008-10 | GKP sheet specs, fastener spacing |
| DIN 18299 | DIN | 2019 | VOB/C General regulations |
| DIN 18363 | DIN | 2019-09 | VOB/C Painting (§3.4 surfaces, §5.2 deductions) |
| DIN 18365 | DIN | 2019 | VOB/C Floor coverings (waste factors) |
| DIN 18350 | DIN | 2019 | VOB/C Plastering (Q1–Q4) |
| DIN 18534-1 | DIN | 2017-07 | Interior waterproofing W0–W3 zones |
| EN 13300 | CEN | 2017 | Paint opacity classes 1–4 |
| EN 14891 | CEN | 2017 | Liquid waterproof membranes |
| Merkblatt Nr. 2 (Bundesverband der Gipsindustrie) | gips.de | 2014 (4. Aufl.) | Q1–Q4 surface qualities, Q4 = 3–5 mm full-surface skim |
| Knauf W111 system docs | Knauf | latest | CW/UW partition spec |
| Knauf Uniflott / Fugen TDS | Knauf | latest | Joint compound 0.3–0.5 kg/m² |
| Saint-Gobain Gyproc LT | gyproc.lt | latest | LT GKP sheet 1200×2500 |
| Tikkurila Optiva / Joker / Otex TDS | tikkurila.lt | latest | Coverage by surface state |
| Caparol CapaSol LF / Tiefengrund / Akkordspachtel TI | caparol.de | latest | Primer coverage, first-coat 1.8× |
| Mapei Mapelastic HP TDS | mapei.lt | latest | Membrane 1.5–2.5 kg/m² |
| Mapei Granirapid TDS | mapei.lt | latest | Tile adhesive 3.5 kg/m² |
| Mapei Ultracolor Plus TDS | mapei.lt | latest | Grout 0.5–1.5 kg/m² |
| TCNA Handbook | TCNA | annual | Tile waste by pattern; movement joints |
| ISO 13007 / EN 12004 | ISO/CEN | 2019 | Tile movement joints every 4–5 m |
| NKBA Chapter 12 | NKBA eLearning | 2023 | Interior elevations, niche measurement |
| STR 1.05.06:2010 | LR AM | 2010 | Mansard floor weighting |
| STR 2.01.07:2003 | LR AM | 2003 | Rw ≥ 50 dB between dwellings |
| STR 2.02.09:2005 | LR AM | 2005 | Door + window opening dimensions |
| STR 2.04.01:2018 | LR AM | 2018 | Wet-room waterproofing requirements |
| BCIS SMM7 | BCIS/RICS | 1988 (superseded) | 0.5 m² plaster threshold (legacy reference) |
| IS 1200 Part 13 | BIS (India) | latest | Cross-check on opening deductions |

---

**Word count: ~4,100 (excluding tables/code blocks count). Source count: 27 unique standards + manufacturer TDS.**
