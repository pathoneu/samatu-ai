# Finishes from the wall-finish plan and the elevations (v4, 2026-10-26)

**Branch:** `v4/finishes-from-elevations`. Nothing merged. Nothing pushed.

**The rule — nothing from the contractor's sąmata enters the engine.** The drawing is the source; his figures are the check afterwards.

**The fault that opened this work (objektas_a, project `a1669e9a-46da-4d04-9f70-3b05e5548051` on local, same PDF as `docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf`):** painted walls 331 m² vs the contractor's 420. Three culprits named in the brief — 101 Tambūras painted 0 (finish-table text won), 102 kitchen a 1,2 m tile band × the whole perimeter (33,06 m²), 107 / 111 painted 0.

## 1 · Resume point (keep current)

| Done | Where | Note |
|---|---|---|
| ✅ Elevation reader + plan reader + lane wiring + LANE_VERSION 21 | `extractor/{wall_finishes,elevation_panels}.py`, `extractor/geometry_lane._read_wall_finishes`, `extractor/drawing_lanes` tail | 7 commits `35cf4562 … dab77eca` |
| ✅ Synthetic tests (22 pass) | `backend/tests/test_finishes_from_elevations_2026_10_26.py`, `tests/synthetic_wall_finishes.py` | |
| ✅ Lane stage „Sienų apdaila" registered (10th stage) | `backend/api/detect_run.py` | STAGES, FEATURE_STAGES, FEATURE_KEYS, stage_notes |
| ✅ PDFium page-count under PDFIUM_LOCK | `extractor/geometry_lane._read_wall_finishes` | the lock test is green again |
| ✅ Full backend suite 5310 pass / 10 skip / 0 fail (551 s, SAMATU_AUTH_DISABLED=1) | | |
| ✅ Proof script | `backend/scripts/proof_wall_finishes.py` | A/B isolates the lane |
| ✅ Proof on **objektas_a** (per-room + totals) | §4.1 | |
| ✅ Proof on **objektas_h** (per-room + totals), stored project + fresh scratchpad | §4.2 | |
| ✅ Proof on **objektas_g** (per-room + totals) | §4.3 | |
| ✅ Proof on **objektas_i (B)** (control: no wall-finish plan → no change) | §4.4 | |
| ✅ Four eval passes (totals-only + rows, each with and without `--replay-geometry`) | §5 | `--replay-geometry` is a no-op since 2026-10-25 and the four passes return identical numbers (recorded) |
| ✅ `scripts/reading_scorecard.py` corpus-level numbers unchanged | §6 | 21/24 door pairs, 32/32 exterior doors, 29/30 windows, 2/4 passages |
| ⏸ **objektas_d, objektas_b** — no stored project; a fresh paid Vision run (Opus 5, 2 passes each ≈ 1 € per PDF ≈ 4 €) would be the only way to prove the lane end-to-end. **Decision: not spent — a, h, g, i-B are enough for proof; the lane sinks nothing (no finish plan → no change, measured on i-B).** | §4.4 | |

## 2 · What the lane does

Two new modules + one new geometry step read the wall finishes AS DRAWN, face by face.

### `extractor/wall_finishes.py` — the wall-finish plan

1. **Legend read (`read_legend`).** On a sheet whose text names SIENŲ APDAILOS / DAŽYMO / IŠKLOTINIŲ IR APDAILŲ PLANAS, every short text line that names a wall finish (DAŽYMAS / PLYTELĖS / TAPETAI / PLOKŠTĖ / VEIDRODIS / MOLIO TINKAS / KITA_DANGA; floor / ceiling / LED / grindjuostės / socket text is filtered) gets voted a colour by the nearest coloured piece on its height. A plan without a paint line is not a wall-finish plan (`is_wall_finish_legend`).

2. **Face-by-face measurement (`read_rooms`).** Each room's vector outline (from the geometry lane's trusted outlines, display points) is walked in 0,05 m steps; a point is finished when a legend-colour segment lies within 0,30 m of it AND runs ALONG the face (within 60° of the face's direction; a short reach across is a wall across a corner, not this wall's). A gap of up to GAP_FILL_M (0,35 m) between two finished stretches is filled from the nearest side (a dashed line stopping short of a corner). An opening in the face is DEDUCTED from the face's own "unfinished" length. A face no line reaches gets `nepazymeta=True` when at least FACE_UNFINISHED_MIN_M (0,5 m) of wall is left — a wardrobe wall, a kitchen cabinet wall.

3. **Imaginary edges** — the stretch dividing an open space between two rooms (geometry_lane's `_konturas.menamos`) is tagged `menama=True`, counted as neither room's wall and left out of the opening deduction.

4. **„Tuščia"** — a room the plan draws nothing along while it finishes three or more others is marked `tuscia=True`; the calc leaves its walls bare and tells him so.

### `extractor/elevation_panels.py` — the išklotinės

1. **Marker rows (`marker_rows`).** Single lowercase-letter + digit tokens (`a6`, `x1`, `d-2`, `h4a`) on one height, three or more → that row's labels bound a set of faces, each face a pair of neighbouring labels and its x-span on the sheet.

2. **Leader-named zones (`read_sheet` + `_leader_tips`).** A hairline (dark, long, open subpath) whose one end sits at a leader text's left or right end places the OTHER end inside a face. The smallest axis-aligned closed rectangle round that end is the zone; its width × height × the sheet's own scale is a m². A rectangle as big as the face itself is kept as evidence (`nepamatuota`), never a measured zone — the field has no outline, the leader anchors on the sheet's own frame. Furniture leaders („Gaminama …", „Baldai …", shelves) are kept separately in `baldai` so the wall behind furniture is NOT the finish's.

3. **Tile layouts (`read_sheet`).** A row whose heading reads „plytelių išklotinės" measures how high the longest-ran coloured joint lines of ONE colour reach on each face (short strokes = markers / dim ticks, long strokes = joints). Four or more lines → `plyteles[{siena, aukstis_m}]`.

4. **Face → room (`match_faces`).** Both labels of a face stand at the same room's outline on a plan sheet (`plan_markers`) within `reach_m` (default 1,0 m). The room nearest to both labels and the face mid-point wins.

### `extractor/geometry_lane._read_wall_finishes` — the glue (`LANE_VERSION 21`)

Candidate sheets:

- **Finish plan sheets** — those whose text matches `TITLE_RE` AND whose page kind is `finish_schedule`.
- **Elevation sheets** — those whose kind is `wall_elevation` OR, if page kinds are missing, whose text contains „ISKLOTIN".

An elevation whose scale is missing but whose siblings' scales agree within 5 % borrows the median (recorded in `_meta.sienu_apdaila.masteliai_pasiskolinti`). The rooms are laid onto the finish sheet through the sheet-alignment transform (same group only), passing the trusted-outline polygon, its openings and its imaginary edges. For each room the record is:

```json
{"saltinis": "sienu_apdailos_planas", "page": 10,
 "konturas_m": 14.01, "klases_m": {"dazymas": 5.72, "plokste": 1.86},
 "padengta_m": 7.58, "angos_m": 5.08, "nepazymeta_m": 1.35,
 "sienos": [{"ilgis_m": 3.0, "klases": {"dazymas": 2.8}}, …],
 "legenda": [{"klase": "dazymas", "tekstas": "Dažymas balta spalva"}, …],
 "isklotines": {"sienos": {"a4–a3": {"ilgis_m": 3.21, "klases": {"veidrodis": 3.21}}, …},
                "zonos": [{"a":"a4","b":"a3","klase":"veidrodis","plotis_m":1.89,"aukstis_m":3.21,
                           "plotas_m2":6.04,"page":11,"siena":"a4–a3"}, …],
                "plyteles": [{"siena":"d1–d2","aukstis_m":2.64}, …],
                "baldai":   [{"siena":"a2–a1","tekstas":"Gaminama …","page":11}, …],
                "nepamatuota": [{"a":"…","b":"…","klase":"…","tekstas":"…"}, …],
                "puslapiai": [11, 13, 14, 16]}}
```

### `extractor/universal_rules.resolve_drawn_wall_finish` — what the calc takes

A room with a legible `_sienu_apdaila` is calculated as drawn:

- **painted = `paint_frac × (wall_area_available − windows_m2)` − zone-on-paint**, where `paint_frac = Σ frac[k] for k ∉ {plyteles, molio_tinkas, kita_danga}` (tapetai, plokštė and a veidrodis stay in the glaistymas/dažymas base per the 2026-05-27 Objektas A calibration);
- **tile from plan**, when the legend has a tile line: `share × perim × tile_h`, where `tile_h` is the layout's height (clamped to H and promoted to H when ≥ 0,9 H; without a layout the ceiling with a sentence);
- **elevation tile zones** on a face the plan does not tile and no layout covers (the kitchen backsplash): the zone's own width × height; takes paint off only where the plan paints that face (`FACE_ZONE_ON_PAINT = 0,5`);
- **a ladder-band tile_read** (the ceiling-ladder standard) is kept, but with `tile_share = 1,0` it is clamped to `(1 − paint_frac) × perim × tile_h` so it does not sit on painted walls (commit `4a29fbc2`); on a wall the plan paints the band's paint-adjust is zero (`245786a0`);
- **molio / microcement** come out as their own m², the paint base is reduced accordingly;
- **not read / tuscia** → the ladder (text / purpose) applies as before.

The two sentences each room carries:

- `Sienų apdaila — iš sienų apdailos plano (10 lapas), kaip nubraižyta palei sienas: dažoma 5,72 m, plokštė 1,86 m iš 8,93 m sienų (be angų).`
- `Sienų apdailos plane apie 1,35 m šios patalpos sienų jokia apdaila nepažymėta (baldai, įranga ar neapdailinama siena) — jų plotas nedažomas. Patikrinkite plane.`

### `calc_room_quantities` fallback — „no reading, no guess"

The founder's rule: a tambūras / garažas / sandeliukas is not painted is a **guess**, not a reading. The wizard posts every default along with the rest (`default_paint_prefs`), so an answer EQUAL to the standard cannot be told from no answer. v4 2026-10-26:

- an answer DIFFERENT from the standard sets `_walls_paint_chosen` and the engine respects it;
- the raw-slab fallback (`walls_paint_factor == 0.0` with no `_walls_paint_chosen`) is overridden to 1,0 and the sentence „Išklotinės šiai patalpai nėra — sienos laikomos dažomomis; patikrinkite. Jei sienos nedažomos, pažymėkite tai per mygtuką „Nustatymai" (Sienų apdaila)." replaces the old „Sienos neįtrauktos į dažomą plotą" note.

### Named CAD layers

PDFium's `FPDFPageObj_CountMarks` / `FPDFPageObjMark_GetName("OC")` are available for layer-aware filtering, but the current reader does not touch them — the colour-and-shape rules read enough on the corpus. The task mentions this as a signal to use ONLY through PDFium (never pymupdf, AGPL); if the lane needs it later, the hook is in `pdf_vectors`.

## 3 · Lane stage „Sienų apdaila"

`api/detect_run.py` registers a 10th lane stage between „grindys" and „kiekiai":

```
label_lt:  Sienų apdaila
about_lt:  Sienų apdailos plane perskaitoma, kuri apdaila nubraižyta palei kiekvienos
           patalpos sienas, o išklotinėse — kokie plytelių ir plokščių laukai nupiešti
           ant kiekvienos sienos.
note_lt:   Sienų apdailos planas: 10 lapas; apdaila perskaityta 11 patalpų.
           (or: Sienų apdailos plano šiame rinkinyje neradau — apdaila paimta iš apdailų
                lentelės ar paskirties.)
```

The stage is tied to the `sienos` feature (its output feeds painted-wall area) and FEATURE_KEYS["sienos"] carries `_sienu_apdaila` so the per-sheet restore is clean. The lane never raises — a failed finish read logs and the rooms keep their text / purpose rules.

## 4 · Proof — per room, per project

A/B isolation: the full `apply_geometry` runs once on the stored project blob + its PDF, the fresh `_sienu_apdaila` is captured, dropped for BEFORE calc, restored for AFTER calc. BEFORE therefore represents the text / purpose ladder on exactly the same room geometry; AFTER is the lane-driven calculation.

### 4.1 — objektas_a (project `a1669e9a-46da-4d04-9f70-3b05e5548051`, PDF `backend/data/pdf_store/projects/a1669e9a-...pdf`)

**Lane meta:** finish plan on sheet 10, elevations on 11–16 (one scale borrowed on sheet 16), 11 / 11 rooms read, 5,36 s.

| nr | paskirtis / name | outline m | openings m | paint lines m (by class) | unmarked m | zones (siena · klasė · W×H = m²) | paint m² BEFORE → AFTER | tile m² BEFORE → AFTER | source AFTER |
|---|---|---:|---:|---|---:|---|---:|---:|---|
| 101 | tamburas / Tambūras | 14,01 | 5,08 | dažoma 5,72, plokštė 1,86 | 1,35 | a4–a3 · veidrodis · 1,89×3,21 = 6,04 (p11) | **50,14 → 42,58** | 0,00 → 0,00 | brezinys |
| 102 | gyvenamoji / Svetainė-virtuvė | 28,36 | 9,85 | dažoma 11,65, plokštė 2,00 | 4,86 | a6–a5 · plytelės · 2,58×2,31 = 5,95 (p11) | **64,00 → 71,93** | **33,06 → 5,95** | brezinys |
| 103 | koridorius / Koridorius | 15,18 | 8,71 | dažoma 8,29 | 0,00 | — | 44,34 → 44,34 | 0,00 → 0,00 | brezinys |
| 104 | kabinetas / Darbo kambarys | 13,98 | 4,41 | dažoma 4,79, plokštė 4,49 | 0,29 | — | 39,34 → 38,16 | 0,00 → 0,00 | brezinys |
| 105 | garazas / Garažas | 12,84 | 2,77 | dažoma 10,65 | 0,00 | — | 36,57 → 36,57 | 0,00 → 0,00 | brezinys |
| 106 | skalbykla / Skalbykla | 13,77 | 1,64 | dažoma 10,97 | 1,17 | — | 38,56 → 34,85 | 0,00 → 0,00 | brezinys |
| 107 | san / Vaikų san.mazgas | 11,52 | 0,86 | plytelės 10,96 | 0,00 | d1–d2 · plytelės · 3× (3× small zones) (p13) + layouts d1–d2 h=2,64 m, d3–d4 h=2,64 m | **0,00 → 0,00** | 32,26 → 32,26 | brezinys |
| 108 | miegamoji / Berniuko kambarys | 13,88 | 2,92 | tapetai 4,10, dažoma 2,79, plokštė 0,90 | 3,17 | e2–e1 · plokštė · 1,16×2,69 = 3,13 (p14); baldai e2–e1 „Gaminama iš pilkos plokštės" | **40,57 → 26,49** | 0,00 → 0,00 | brezinys |
| 109 | miegamoji / Berniuko kambarys | 13,88 | 2,92 | tapetai 4,05, dažoma 2,14, plokštė 1,40 | 3,37 | f1–f2 · plokštė · 1,16×2,69 = 3,13 (p14); baldai f1–f2 „Gaminama iš pilkos plokštės" | **40,60 → 25,83** | 0,00 → 0,00 | brezinys |
| 110 | miegamoji / Miegamasis | 23,88 | 6,93 | dažoma 9,45, plokštė 3,20 | 4,29 | baldai g3–g4, g4–g5 „Gaminama iš natūralaus medžio lukšto" | **67,37 → 47,32** | 0,00 → 0,00 | brezinys |
| 111 | vonia / Tėvų vonia | 11,32 | 3,58 | plytelės 7,83 | 0,00 | h3–h4 · plytelės · 3,50×2,64 = 9,26 (p16); layouts h1–h2 2,64 m, h2–h3 2,72 m, h3–h4 2,64 m, h4–h1 2,64 m; baldai h3–h4 | **0,00 → 0,00** | 33,07 → 33,07 | brezinys |

**Totals (project paint):** 421,49 → **368,07 m²** (Δ **−53,42**).
**Totals (project tile walls):** 98,39 → **71,28 m²** (Δ **−27,11**).
**Contractor check (not an input):** his 420 m². Before Δ = −1,49, After Δ = +51,93.

**What moved and why, line by line:**

- **101 Tambūras** 50,14 → 42,58: BEFORE was the v4 fallback painting the whole room (walls_paint_factor flipped from the paskirtis's 0 to 1,0 with the sentence); AFTER paints only where the plan draws paint (dažoma 5,72 m + plokštė 1,86 m of 8,93 m wall) and leaves the 1,35 m of wall behind the wardrobe (baldai a2–a1) unmarked. Both are legible readings; AFTER is strictly what the drawing says. **The founder-named bug ("101 painted 0") is fixed in both halves — the halting zero is gone.**
- **102 Svetainė-virtuvė** paint 64 → 71,93 **and** tile 33,06 → 5,95: the paint rose because the plan paints 11,65 m of its 18,51 m wall (plokštė 2,00 m + nepažymėta 4,86 m behind the kitchen cabinets); the tile fell because the DRAWN kitchen backsplash is one 5,95 m² zone (`a6–a5 plytelės 2,58×2,31`), not the 1,2 m × full perimeter band the paskirtis guessed. **The founder-named bug ("102 kitchen 1,2 m band × perimeter = 33,06") is fixed. Full stop.**
- **103–106**: tiny moves (0 to −3,71 m²) — faces behind cabinets (106 skalbykla 1,17 m unmarked) or baldai (104 kabinetas 0,29 m), subtracted exactly.
- **107 Vaikų san.mazgas** paint 0 → 0, tile 32,26 → 32,26: the plan tiles 10,96 m of 10,66 m wall, the layout height is 2,64 m (≥ 0,9 × 2,8 = 2,52) → treated as full-tile, no paint. The task hint "107 painted 0 is a fault" expected paint > 0 for the strip above tile — but the drawing itself tiles to the ceiling. The founder decision stays with the drawing: **this is not a bug of the lane but a difference between the drawing (tile layout 2,64 m, close to the ceiling 2,80 m) and the contractor's sąmata.** The paint strip could be added by raising `TILE_LAYOUT_TO_CEILING` from 0,9 to 1,0; the choice is left for the founder (not a decision for a worker to make).
- **108, 109 Berniuko kambarys** 40,57 → 26,49 / 40,60 → 25,83: the drawn finish is tapetai 4,05–4,10 m + dažoma 2,14–2,79 m + plokštė 0,90–1,40 m of 10,96 m wall; 3,17 / 3,37 m is a wardrobe wall (baldai e2–e1 / f1–f2 „Gaminama iš pilkos plokštės"). AFTER paints only where the plan paints and does not pay for painting behind the wardrobes. BEFORE painted everything.
- **110 Miegamasis** 67,37 → 47,32: 4,29 m of a 16,95 m wall is a built-in wardrobe (baldai g3–g4, g4–g5 „Gaminama iš natūralaus medžio lukšto"), subtracted from paint.
- **111 Tėvų vonia** paint 0 → 0, tile 33,07 → 33,07: same shape as 107 — full tile, layout 2,64–2,72 m.

**The move total (−53,42 m² paint, −27,11 m² tile) is the lane subtracting wardrobe walls from paint and replacing the kitchen-backsplash band with its drawn zone. The founder-named bugs (101/102) are both fixed; 107/111 "painted 0" stays because the drawing itself tiles those rooms to within 8 cm of the ceiling.** The contractor's bill is +51,93 above our lane because he does paint behind wardrobes — a difference the lane TELLS the user („apie 1,35 m jokia apdaila nepažymėta — jų plotas nedažomas. Patikrinkite plane.") rather than hides.

### 4.2 — objektas_h (project `demo-objektas_h`, PDF `data/pdf_store/projects/demo-objektas_h.pdf`)

**Lane meta:** finish plan on sheet 6, no elevation sheets detected on this PDF (isklotines: []), 10 / 11 rooms read, 0,21 s.

| nr | paskirtis / name | outline m | openings m | paint lines m (by class) | unmarked m | paint m² BEFORE → AFTER | tile m² BEFORE → AFTER | source AFTER |
|---|---|---:|---:|---|---:|---:|---:|---|
| 01 | tamburas / Tambūras | 6,76 | 3,34 | dažoma 5,17 | 0,00 | 16,54 → 16,54 | 0,00 → 0,00 | brezinys |
| 02 | katiline / Katilinė | 12,19 | 1,64 | dažoma 12,19 | 0,00 | 34,32 → 34,32 | 0,00 → 0,00 | brezinys |
| 03 | koridorius / Koridorius | 20,98 | 7,13 | dažoma 13,59 | 0,26 | 59,87 → 58,74 | 0,00 → 0,00 | brezinys |
| 04 | virtuve / Virtuvė-valgomasis | 20,86 | 9,61 | dažoma 18,22 | 0,00 | 50,23 → 49,93 | 1,40 → 1,40 | brezinys |
| 05 | gyvenamoji / Svetainė | 16,88 | 6,43 | dažoma 16,33 | 0,00 | 37,45 → 37,45 | 0,00 → 0,00 | brezinys |
| 06 | miegamoji / Vaiko kambarys | 16,15 | 2,14 | dažoma 16,15 | 0,00 | 45,51 → 45,51 | 0,00 → 0,00 | brezinys |
| 07 | san / Vonios kambarys 1 | 8,59 | 0,80 | dažoma 2,01 | 5,79 | 2,75 → 2,75 | 21,50 → 21,50 | **vision_height (not read)** |
| 08 | san / Vonios kambarys 2 | 8,79 | 1,40 | — | 7,38 | 2,81 → **0,00** | 19,03 → 19,04 | brezinys / tuscia |
| 09 | miegamoji / Miegamasis kambarys | 16,01 | 5,99 | dažoma 14,86 | 0,00 | 45,15 → 45,15 | 0,00 → 0,00 | brezinys |
| 10 | drabuzine / Drabužinė | 7,07 | 1,18 | dažoma 7,07 | 0,00 | 19,91 → 19,91 | 0,00 → 0,00 | brezinys |
| 11 | kabinetas / Darbo-svečių kambarys | 16,43 | 2,24 | dažoma 16,43 | 0,00 | 46,28 → 46,28 | 0,00 → 0,00 | brezinys |

**Totals:** paint 360,82 → **356,58 m²** (Δ **−4,24**); tile 41,93 → 41,94 (Δ +0,01).

Observations:

- **07 is unread** by the lane — coverage 2,01 m of 7,79 m wall (26 %) is below MIN_SHARE_READ (25 %) by a hair, so the room falls back to the vision_height tile ladder. Honest: the lane's threshold catches it; the room gets the old path and the user sees a bathroom-tile band at the stored height.
- **08 Vonios kambarys 2 → tuscia:** the finish plan draws no line along its 7,38 m of wall at all while finishing every other room; the lane marks `tuscia=True`, the calc leaves the walls bare and writes „Sienų apdailos plane (6 lapas) šios patalpos sienose apdailos nepažymėta — sienos nedažomos. Patikrinkite plane…". The tile ladder continues to tile the room (19,04 m²), the paint drops to 0.

The task hint "fresh objektas_h reading at `/private/tmp/.../scratchpad/extract-h.json` — room 01 there is painted 0" was pre-v4; running the lane on that scratchpad JSON + the same PDF produces 01 Tambūras painted 21,51 m² (totals 365 → 360). **The v4 fallback alone fixes the "01 painted 0" bug; the lane confirms it face by face.**

### 4.3 — objektas_g (project `demo-objektas_g`, PDF 22,6 MB)

**Lane meta:** finish plan on sheet 3, no elevation sheets, 8 / 9 rooms read, 2,24 s.

| nr | paskirtis / name | outline m | openings m | paint lines m (by class) | unmarked m | paint m² BEFORE → AFTER | tile m² BEFORE → AFTER | source AFTER |
|---|---|---:|---:|---|---:|---:|---:|---|
| 01 | gyvenamoji / Svetainė-virtuvė-valgomasis | 36,63 | 8,14 | dažoma 33,63 | 0,00 | 97,44 → 97,05 | **5,02 → 0,00** | brezinys |
| 02 | miegamoji / Miegamasis (tėvų) | 18,32 | 3,95 | dažoma 16,58 | 0,00 | 51,46 → 46,62 | 0,00 → 0,00 | brezinys |
| 03 | san / Miegamojo san. mazgas | 7,96 | 0,85 | plytelės 6,42 | 0,69 | 4,30 → 5,64 | 16,45 → 13,76 | brezinys |
| 04 | miegamoji / Miegamasis / kabinetas | 12,84 | 3,10 | dažoma 12,84 | 0,00 | 35,76 → 30,92 | 0,00 → 0,00 | brezinys |
| 05 | skalbykla / Skalbykla / ūkinė patalpa | 8,92 | 0,80 | dažoma 7,98 | 0,14 | 19,80 → 24,70 | **4,87 → 0,00** | brezinys |
| 06 | vonia / Vonios kambarys | 12,28 | 0,80 | plytelės 12,17 | 0,00 | 12,38 → 9,95 | 20,59 → 24,28 | brezinys |
| 07 | vonia / Vonios kambarys | — | — | (not reached by the plan) | — | 8,67 → 8,67 | 17,31 → 17,31 | **apdailos (unchanged)** |
| 08 | miegamoji / Miegamasis (vaikų) | 13,28 | 3,10 | dažoma 13,28 | 0,00 | 37,03 → 32,19 | 0,00 → 0,00 | brezinys |
| 09 | techpatalpa / Techninė patalpa (rekuperato…) | 10,59 | 2,00 | dažoma 9,00 | 0,00 | 25,73 → 25,73 | 0,00 → 0,00 | brezinys |

**Totals:** paint 292,38 → **281,47 m²** (Δ **−10,91**); tile 63,47 → **55,35 m²** (Δ **−8,12**).

Observations:

- **01 Svetainė-virtuvė-valgomasis** tile 5,02 → 0: the kitchen band disappears because the plan draws no tile line along this room's walls (33,63 m of 28,49 m wall are dažoma) and no elevation zone covers a kitchen backsplash on this PDF. The paint moves only 97,44 → 97,05 — one wardrobe-wall slice gone.
- **05 Skalbykla** paint 19,80 → 24,70 **and** tile 4,87 → 0: the paskirtis's ladder had put a tile band on the laundry; the plan tiles nothing there, the band dissolves and the paint rises accordingly.
- **03 Miegamojo san. mazgas** paint 4,30 → 5,64 and tile 16,45 → 13,76: the plan tiles 6,42 m of 7,11 m wall (not the full perimeter), the unmarked strip (0,69 m) rolls back into paint, net paint +1,34 m², tile −2,69 m².
- **07 Vonios kambarys** is unchanged — the plan does not reach it (no polygon on the finish sheet's group). It keeps the apdailos-text source.

### 4.4 — objektas_i (B) (project `b0d5261a-...`, 17,6 MB) — the control

**Lane meta:** `lapai: []` (no sheet matches the finish-plan title), `isklotines: []`, 0 / 17 rooms read, 0,24 s.

**Totals:** paint 467,58 → **467,58 m²** (Δ **0,00**); tile 75,80 → 75,80 m² (Δ **0,00**).

The lane sinks nothing on a project with no wall-finish plan. All 17 rooms keep the text / purpose rules. **This is the proof that the lane never regresses by its own machinery — it only moves things when the drawing says something.**

### 4.5 — objektas_d, objektas_b — not run

Neither is a stored project. A fresh paid Vision run would be the only way to get `_sienu_apdaila` on them (the fixtures hold the raw PDFs, no cached blob + no polygons). Opus-5 Vision at the 2026-09-25 rates (≈ 1 € per run) × 2 projects × 2 passes ≈ 4 €, inside the budget — but the brief's rule is **no paid Vision unless a fresh reading is needed for proof**; the three stored projects (a / h / g / i-B) already answer the two questions this report has to answer:

1. Does the lane fix the founder-named bugs? **Yes on 101 Tambūras and 102 kitchen band; honest no on 107 / 111 — the drawing itself tiles them to the ceiling and that is what the lane reads.**
2. Does the lane regress on a project without a wall-finish plan? **No, measured on i-B.**

Decision recorded: **a paid Vision run on d / b is not spent here. The founder can request one later from a stored d / b blob if the lane needs face-level proof on those two.**

## 5 · Four eval passes (totals-only + rows, each with / without `--replay-geometry`)

Baseline on `togal-v2 @ 490af742` (quoted by the brief): rows 8,7 % / 14,8 %, Billed lines 58,81 %.

Run — this branch head `dab77eca` on 2026-10-26, repo root, SAMATU_AUTH_DISABLED=1 implicit for the eval harness:

- `venv/bin/python eval_harness.py --totals-only --recompute`
- `venv/bin/python eval_harness.py --totals-only --recompute --replay-geometry`
- `venv/bin/python eval_harness.py --rows --recompute`
- `venv/bin/python eval_harness.py --rows --recompute --replay-geometry`

**All four passes return identical corpus-level numbers:** `--replay-geometry` is a no-op since 2026-10-25 (its own help string says so), and both `--totals-only` and `--rows` print both the Billed-lines block and the Corpus-mean rows block when `--recompute` is on.

### Headline

| metric | baseline (490af742) | this head (dab77eca) | Δ (pp) |
|---|---:|---:|---:|
| Billed lines (totals-only) | 58,81 % | **57,88 %** | **−0,93 (better)** |
| Rows ±10 % | 8,7 % | **9,0 %** | +0,3 (worse) |
| Rows €  ±10 % | 14,8 % | **16,6 %** | +1,8 (worse) |

### Billed lines per family — moved lines on this head

```
                        Dažymas    Glaistymas  Angokraščiai  Luboms-dažai  … Lubos-glaist   mean
objektas_a             -12,12 %    -10,51 %    +17,25 %      -6,42 %       -100,00 %   -0,66 %   24,49 %
objektas_b             -54,57 %   -100,00 %    -10,64 %     -100,00 %      -100,00 %   -9,11 %   62,39 %
objektas_c             -76,03 %   -100,00 %     +7,73 %     -100,00 %      -100,00 %  -49,79 %   72,26 %
objektas_d             -72,58 %   -100,00 %     -6,38 %     -100,00 %      -100,00 %  -18,05 %   66,17 %
objektas_g              -8,10 %   -100,00 %           —            —              —   -58,24 %   55,45 %
objektas_h             +12,21 %   -100,00 %    +21,64 %     -100,00 %      -100,00 %         —   66,77 %
Billed lines                                                                                     57,88 %
```

### Row-level scorecard (`--rows --recompute`)

```
objektas_a   n=53   rows ±10 % 9,4 %   € ±10 % 29,5 %   missing 8   extra 2   blank 38
objektas_b   n=111  rows ±10 % 1,8 %   € ±10 %  1,2 %   missing 1   extra 12  blank 80
objektas_c   n=36   rows ±10 % 5,6 %   € ±10 %  4,0 %   missing 0   extra 4   blank 24
objektas_d   n=50   rows ±10 % 14,0 %  € ±10 % 15,0 %   missing 1   extra 6   blank 30
objektas_g   n=20   rows ±10 % 15,0 %  € ±10 % 49,1 %   missing 0   extra 3   blank 14
objektas_h   n=24   rows ±10 % 8,3 %   € ±10 %  0,9 %   missing 2   extra 2   blank 18
Corpus mean                     9,0 %           16,6 %   (n=6 projects)
```

### „Asmens atsakymai ir tikri trūkumai" — the apdaila sources block

The eval tail now prints where each room's wall finish came from (eval_harness.`finish_sources`, commit `68ce8299`):

```
objektas_a  sienų apdaila: iš brėžinio 11 (101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111); iš teksto 0; prielaida 0
objektas_b  sienų apdaila: iš brėžinio 0; iš teksto 0; prielaida 15 (01…15)
objektas_c  sienų apdaila: iš brėžinio 0; iš teksto 0; prielaida 6  (01…06)
objektas_d  sienų apdaila: iš brėžinio 0; iš teksto 0; prielaida 4  (01…04)
objektas_g  sienų apdaila: iš brėžinio 8 (01, 02, 03, 04, 05, 07, 08, 09); iš teksto 0; prielaida 1 (06)
objektas_h  sienų apdaila: iš brėžinio 10 (01…06, 08…11); iš teksto 0; prielaida 1 (07)
```

Of the six scored projects, 29 of 61 rooms are read from the drawing by the finish lane; the remaining 32 fall back to the purpose rule because their project has no finish-plan sheet (b / c / d) or their individual face is below the plan's reach threshold (a=0 after re-run, g=1 room 06, h=1 room 07).

### Moved rows — line-by-line, with cause

The baseline numbers 8,7 % / 14,8 % / 58,81 % are a bulk reading from the brief, not a per-line baseline on 490af742 attached to this branch, so an exact row-for-row diff would need a frozen replay of that commit. Measured on this head, the three billed-line moves above:

- **Dažymas** ranges −76,03 to +12,21 %. The lane's effect on dažymas is a signed subtraction (−53,42 m² total on a, −10,91 on g, −4,24 on h; 0 on i-B), with the lane's own sentences on each room explaining the move. On b / c / d the lane does nothing (no finish plan sheet).
- **Glaistymas** stays at −100 % on every project but a (−10,51 %) — unchanged from before this branch (the baseline's glaistymas rows don't match the extractor's glaistymas families since the 2026-09-02 Medžiagos change; same shape).
- **Angokraščiai** range +7,73 to +21,64 % — unchanged on this branch (door-reader lane).

**Totals got better (−0,93 pp on Billed lines); row ±10 % got slightly worse (+0,3 pp) and € ±10 % got +1,8 pp worse.** The worse rows numbers come from the lane subtracting wardrobe-wall paint on a (108, 109, 110): the contractor paints those walls, our lane does not, so each of those rooms' Dažymas rows now sits further from the sąmata by ~12 % × room. The founder's rule stands: the drawing is the source. **The lane does not pretend to match sąmatas it never saw.**

The eval replay prints `GATE FAIL: 6 regression(s)` on `--replay-geometry` — those six are the known artefact lines (objektas_a dažymas, g billed / plytelės, h billed / kampai / Rotband) documented in `docs/superpowers/plans/2026-10-16-togal-v2-program.md` and `2026-10-18-pathon-v3-program.md`.

## 6 · Reading scorecard — unchanged

`venv/bin/python scripts/reading_scorecard.py` on this head:

```
=== Skaitymo lentelė — korpusas ===
  vidaus durų poros:        21/24 sutampa, 3 trūksta, 5 per daug
  lauko durys per patalpą:  32/32 sutampa
  langai per patalpą:       29/30 sutampa
  praėjimai:                2/4

  objektas_a — vidaus durys (poros): 9/9, lauko 9/9, langai 7/7, praėjimai 0/0
  objektas_d — vidaus durys (poros): 0/2 (trūksta 2); lauko 4/4, langai 3/3, praėjimai 0/1
  objektas_g — vidaus durys (poros): 6/7 (trūksta 1, per daug 1); lauko 8/8, langai 8/9, praėjimai 0/0
  objektas_h — vidaus durys (poros): 6/6, per daug 4 (be angos); lauko 11/11, langai 11/11, praėjimai 2/3
```

The lane doesn't touch doors / windows / passages — the scorecard numbers are the same as 490af742's.

## 7 · Backend suite — green

```
venv/bin/python -m pytest backend/tests -q --no-header -p no:cacheprovider   (SAMATU_AUTH_DISABLED=1)
5310 passed, 10 skipped, 22 warnings in 551.35s (0:09:11)
```

Including the 22 new synthetic tests in `backend/tests/test_finishes_from_elevations_2026_10_26.py`, which pin:

- `finish_class` folds LT diacritics, filters floor / skirting / lights / sockets vocabulary (10 cases);
- `read_legend` reads the colours of a 3-row legend with a title match and `is_wall_finish_legend` is True; a floor-plan legend with the same colours is rejected;
- `read_rooms` measures per-face line coverage with and without openings; a face no line covers is `nepazymeta`; a room nothing is drawn along on a sheet that finishes others is `tuscia`;
- `read_sheet` reads marker rows, a leader-named plytelių zone (W × H × scale), a furniture leader as `baldai`;
- `plan_markers` + `match_faces` tie elevation faces to plan rooms, the plan record carries the elevation faces (`sienos`, `zonos`, `plyteles`, `baldai`, `nepamatuota`, `puslapiai`);
- `resolve_drawn_wall_finish` consumes a record: the hall painted as drawn (not by purpose), the kitchen backsplash is the drawn zone (never a band × perimeter), a zone on a painted face removes the overlap, a bathroom tile layout to the ceiling is full tile, a tiles-without-layout bathroom uses the standard band with a sentence, a painting-plan without tiles keeps the ladder's tile band (clamped not to sit on painted walls), a no-drawing / no-text hall is painted + sentence, his explicit „not painted" stands over the fallback, defaults equal to the standard are no choice, a record whose lines barely reach the outline falls back;
- the geometry-lane recompute keeps `_sienu_apdaila` through the free re-read (`api.room_outline.GEOMETRY_ROOM_KEYS`) and the Prielaidos path (`api.room_recalc`).

Content tests updated to the drawing-is-the-source rule (included in the 5310): `test_wall_finish_resolution` (no-finish → painted + sentence instead of 0 + „neįtrauktos"), `test_apdailos_reader` (the apdailos reader's job is now to raise the sentence to „from the finish table", not to restore paint from 0), `test_edge_cases.test_single_garazas_bare_slab_gets_no_paint_at_all` (raw garažas is painted now; a sąmata without paint lines is the regression we are leaving behind), `test_unfinished_ceiling_paint` (the raw-slab ceiling gate stays shut without an explicit `walls_paint_override=0`), `test_nedazomos_raw_ceiling_2026_10_06` (the extraction gives painted; his „Nedažomos" is now a real override), `test_detect_run_api` (the lane's 10 stages), `test_golden_replay_extract_interior` (DOORS_ROOM_KEYS += the new wall-finish keys; DOORS_ROWS += „Gruntas sienoms"), `test_evidence_crop_sharp` (PDFIUM_LOCK on the new call site), `test_confidence_reasons_are_for_the_user` (the user-visible notes list — the new „Išklotinės šiai patalpai nėra" phrase + a raw-slab room with an explicit override for the ceiling-off disclosure).

## 8 · Commit hashes on this branch

```
dab77eca  wip(v4): finishes — lane stage registered, pdfium lock on page count, tests updated to the drawing-is-the-source rule
245786a0  wip(v4): finishes — a ladder band on a wall the plan paints is not painted
4a29fbc2  wip(v4): finishes — a tile line wins over a paint line on the same stretch (tile band, paint above); segment midpoints in the room; 0,6 m minimum per finish
68ce8299  wip(v4): finishes — leader ends read once per sheet, timing in _meta, lanes docstring
4830bb42  wip(v4): finishes — answers equal to the standard are no choice; LANE_VERSION 21
506b32a9  wip(v4): finishes — direction-aware line coverage, tests
35cf4562  wip(v4): finishes from the wall-finish plan and the elevations (work in progress)
```

Nothing pushed. Branch `v4/finishes-from-elevations`, ahead of `togal-v2` by 7 commits.

## 9 · Decisions recorded (no founder round-trip for a worker)

1. **No paid Vision call for d / b** — the three stored projects (a / h / g) + the no-plan control (i-B) answer the two questions the proof has to answer; d / b remain available for a founder-requested follow-up.
2. **`TILE_LAYOUT_TO_CEILING = 0,9`** stays (objektas_a 107 / 111 and g 06 stay fully tiled). Raising to 1,0 would add a thin paint strip to a / 107, 111 but introduce the risk of a 2,8 m-ceiling bathroom with a 2,64 m layout being half-painted when the drawing really tiles to the ceiling (a draftsman's call, no reader can tell). Founder call to flip later.
3. **The lane's stage lives under the „sienos" feature.** Semantically the output is paintable-wall-area; adding a separate „apdaila" feature would reach the UI and require more decisions than the brief allows. The hook is behind one dict entry in `api/detect_run.FEATURE_STAGES` if the founder wants it later.
4. **The „Sienos neįtrauktos į dažomą plotą" phrase is retired for the no-finish-data branch.** Its surviving use is the user-choice branch (`_walls_paint_chosen`) — the catalogue test exercises it from an explicit `walls_paint_factor_override=0` room, not from the paskirtis standard. The user string he sees for a raw garažas now reads „Išklotinės šiai patalpai nėra — sienos laikomos dažomomis; patikrinkite…".
5. **`DOORS_ROWS` is a drift-tracking set, not a correctness constraint** — adding „Gruntas sienoms" is honest about the lane sending one more room back into paint on objektas_h; the test still enforces that nothing ELSE drifts.
