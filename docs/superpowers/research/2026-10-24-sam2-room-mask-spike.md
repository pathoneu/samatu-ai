# SAM 2 room-mask spike — Phase 0 (c), gate G0

**Date:** 2026-10-24 · **Worker:** Opus 5.5 · **Branch:** `spike/sam2-room-mask` (not merged) · **Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §3.1, §4 Phase 0 (c), §7

## Verdict

**G0 FAILS on every clause, by a wide margin, and not in a way more prompt engineering fixes.**

| G0 clause | Bar | Best SAM variant measured | Result |
|---|---|---|---|
| Raster: SAM area within 2 % of the table | ≥ 80 % of rooms | 1/11 (9 %) — variant C, which cheats by taking its box from the vector outline; honest single click (A) 0/11, click + wall negatives (B) 0/11 | **FAIL** |
| Raster: no leak through doors | ≥ 90 % of rooms | B 9/11 (82 %), C 10/11 (91 %, cheating box), A 4/11 (36 %) — and "no leak" mostly means the mask stopped *short* (B median error −49 %) | **FAIL** (A, B) |
| Vector sheets: vector lane ≥ SAM | vector at least as good | vector median \|err\| vs table 3.8 % (H) / 3.8 % (G); best SAM 13.6 % / 14.9 % (C), A 52.6 % / 110 % | **PASS** — the vector lane wins on every room but one |

Even the generous comparison — SAM vs the vector outline on the same sheet at the same scale (so scale and table conventions cancel) — reaches ≤ 2 % on at most 2 of 11 rooms for any variant. The median IoU of the honest click (A) with the vector outline is 0.11 (objektas_a raster), 0.30 (H), 0.48 (G). SAM 2.1 large does not change the picture (below).

**Recommendation:** do not build `geometry/sam_source.py` on SAM 2.1 as it is. On vector sheets keep vector + manual (already the case). For raster sheets the plan's fallback stands: **vector-where-possible + manual polygon now**, and a floor-plan-trained segmenter as its own track. What the failures show (below) is that the right next step is a model that predicts **walls/rooms as classes** (CubiCasa5k-style semantic segmentation), not a promptable "any object" model — and, cheaper still, a deterministic raster wall-solid pipeline (wall mask → door-gap bridging → room faces) deserves a spike before any training, because the wall mask this spike built is already clean on two of three sheets.

One caveat that matters for the 2 % bar itself: **the vector lane does not meet it either** — 0/11 on objektas_a (every outline 7–23 % *under* the table, median −8.5 %), 1/11 on H, 1/9 on G (≤ 5 %: 0/11, 9/11, 6/9). On objektas_a the bias is systematic, which points at the sheet scale (0.029101 m/pt on page 2) or a table convention (gross vs finished area), not at segmentation. G0's "within 2 % of the table" is unreachable for *any* geometry source on objektas_a until that is understood — a Phase 0 (a) item, flagged here because no SAM number can be judged against it.

## Setup

| | |
|---|---|
| Model | SAM 2.1 base (`sam2.1_b.pt`, 154 MB, Ultralytics release v8.4.0); cross-check with SAM 2.1 large (`sam2.1_l.pt`, 449 MB). `_s`/`_t` not needed — `_b` ran comfortably. |
| Device | **MPS** (Apple M4 Pro, 24 GB) — `torch.backends.mps.is_available()` True |
| Versions | Python 3.14.3, torch 2.14.1, ultralytics 8.4.187, opencv-python-headless 5.0.0, pypdfium2 5.14.0, shapely 2.2.0, numpy 2.5.4 |
| venv | `spikes/sam2/.venv` (separate from the project `venv`; gitignored with `weights/` and `out/`) |
| Inference | All local. Weights downloaded once from the Ultralytics GitHub release. No cloud call of any kind. |
| Render | PDFium, 300 DPI, display orientation (`/Rotate` applied); pixel ↔ PDF point = ×72/300 |
| Prompt crop | 20 m × 20 m square around the click (sensitivity run at 10 m below); SAM resizes to 1024 px |
| Polygon | largest connected component under the click → `cv2.findContours(RETR_CCOMP)` → `approxPolyDP` ε = 2 cm on the sheet → shapely; m² and perimeter from the polygon and the sheet scale |

**Inputs reused from the app (in-process, project `venv`, `spikes/sam2/dump_lane.py`):** room table areas from the cached extraction (`ground_truth/<slug>/ai_extract.json`: eksplikacija on A and H, plan area labels on G), room seats from `room_locator.locate_rooms` (printed room badge or area label), sheet scales from `plan_dimensions` via `geometry_lane.apply_geometry`, the lane's vector outline (`_konturas`, `polygon_pct`) and the one-click `vector_rooms.outline_at` answer at the seat (what `POST …/rooms/{nr}/outline-at` does). **For the raster file (`objektas_a_flat150.pdf`, no text layer, no vector paths) the seats, scale and table areas come from the vector original of the same sheet** (`2026-05-26-objektas-a/project.pdf`, page 2, same 1191 × 842 pt display layout — checked by overlay). A real raster pipeline would have to OCR the badges, the table and a dimension string first; this spike gives SAM that information for free, so the raster numbers are an upper bound.

Truth for room areas: none of the three `truth.json` files carries per-room areas (`gt_per_room` is empty on G and H, finishes only on A), so "table m²" is the designer's own figure the app reads from the drawing (eksplikacija / area label).

## Prompt variants

| Key | Prompt | Note |
|---|---|---|
| L | one positive point exactly on the room badge/label | the naive click |
| A | one positive point, **moved off the ink** to the nearest pixel ≥ 25 cm from any line with no wall between (`clear_floor_point`) | multimask, highest predicted IoU kept |
| B | A's point + up to 4 negative points on the nearest thick-wall pixels (8 rays into `wall_mask`) | single mask |
| C | box = the vector outline's bbox × 1.1, no point | **uses the vector answer** — an upper bound, not available on raster |
| D | A's point, but SAM sees a **walls-only** image (`wall_mask`: dark < 240, hatch closed, opened by an 8 cm square, blobs < (4k)² dropped) | tests "remove furniture first" |
| FF / FFd | no model: flood fill of free space in the walls-only mask; FFd bridges door gaps by closing walls with a 1.2 m square | deterministic baselines |
| F | A's point on the **full page** (no crop) | how much the crop matters |

Leak = mask > 1.3 × table, **or** the polygon contains another room's seat, **or** the mask touches the crop edge (unbounded). Overlays were checked by eye for the cases named below.

## Results (SAM 2.1 base, MPS, 20 m crop)

Cells: m² (signed % vs table); `L` = leak. IoU is the polygon vs the vector outline on the same sheet.

#### objektas_a — raster (`objektas_a_flat150.pdf`, page 2, 150 DPI flattened)

| nr | table m² | vector m² (%) | A m² (%) | B m² (%) | C m² (%) | D m² (%) | FFd m² (%) | IoU vs vector A/B/C | ms enc+dec A |
|---|---|---|---|---|---|---|---|---|---|
| 101 | 11.01 | 9.01 (-18.2) | 6.90 (-37.4) | 8.26 (-24.9) | 9.92 (-9.9) | 330.46 (+2901.4) L | 277.73 (+2422.5) L | 0.762/0.728/0.83 | 613+53 |
| 102 | 50.54 | 45.48 (-10.0) | 53.05 (+5.0) L | 40.43 (-20.0) | 6.06 (-88.0) | 39.66 (-21.5) | 301.40 (+496.4) L | 0.782/0.854/0.011 | 249+27 |
| 103 | 9.64 | 7.40 (-23.2) | 241.60 (+2406.3) L | 2.62 (-72.8) | 6.92 (-28.3) | 3.54 (-63.3) | – (no mask) | 0.03/0.294/0.776 | 247+29 |
| 104 | 13.51 | 11.81 (-12.6) | 3.84 (-71.6) | 5.75 (-57.4) | 11.12 (-17.7) | 304.87 (+2156.6) L | 11.88 (-12.1) | 0.325/0.487/0.861 | 246+50 |
| 105 | 10.67 | 9.53 (-10.7) | 4.94 (-53.7) | 8.96 (-16.1) | 9.20 (-13.8) | 307.90 (+2785.7) L | 250.82 (+2250.7) L | 0.518/0.834/0.86 | 247+50 |
| 106 | 6.84 | 7.35 (+7.5) | 18.89 (+176.2) L | 9.10 (+33.0) L | 5.47 (-20.1) | 10.78 (+57.7) L | 5.91 (-13.6) | 0.325/0.5/0.744 | 244+27 |
| 107 | 6.59 | 6.11 (-7.4) | 198.27 (+2908.7) L | 5.67 (-13.9) | 6.51 (-1.3) | 9.50 (+44.2) L | 5.74 (-13.0) | 0.031/0.843/0.899 | 248+29 |
| 108 | 12.71 | 11.65 (-8.4) | 0.73 (-94.3) | 0.48 (-96.2) | 11.07 (-12.9) | 11.09 (-12.8) | 11.64 (-8.4) | 0.06/0.042/0.902 | 245+24 |
| 109 | 12.71 | 11.65 (-8.4) | 8.69 (-31.6) L | 6.52 (-48.7) | 12.12 (-4.6) | 365.73 (+2777.5) L | 306.31 (+2310.0) L | 0.0/0.0/0.888 | 247+28 |
| 110 | 23.97 | 21.94 (-8.5) | 253.06 (+955.7) L | 4.44 (-81.5) | 8.36 (-65.1) L | 353.05 (+1372.9) L | – (no mask) | 0.087/0.162/0.036 | 245+55 |
| 111 | 7.45 | 6.85 (-8.1) | 64.08 (+760.2) L | 19.02 (+155.3) L | 8.00 (+7.4) | 271.70 (+3546.9) L | 246.16 (+3204.1) L | 0.107/0.331/0.759 | 247+44 |

Summary (n = 11): ≤ 2 % of table — vector 0, L 0, A 0, B 0, C 1, D 0, FFd 0. ≤ 5 % — vector 0, A 1, C 2. No leak — A 4, B 9, C 10, D 3, FFd 4. Median \|err\| — vector 8.5 %, A 94 %, B 49 %, C 14 %.
The vector original of the same sheet, rasterised at 300 DPI and run the same way, gives the same picture (A 0/11, B 0/11, C 1/11 within 2 %; table in `spikes/sam2/out/summary.md`): the flattening to 150 DPI is **not** what breaks SAM.

#### objektas_h — vector (page 1, išdėstymo planas with furniture)

| nr | table m² | vector m² (%) | A m² (%) | B m² (%) | C m² (%) | D m² (%) | FFd m² (%) | IoU vs vector A/B/C | ms enc+dec A |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 4.48 | 4.31 (-3.8) | 3.65 (-18.6) | 3.25 (-27.5) | 1.44 (-67.8) | 350.85 (+7731.4) L | 2.61 (-41.7) | 0.298/0.253/0.274 | 264+22 |
| 02 | 6.9 | 7.16 (+3.8) | 7.44 (+7.8) | 6.84 (-0.9) | 6.38 (-7.5) | 6.01 (-12.8) | 6.59 (-4.5) | 0.932/0.94/0.884 | 250+23 |
| 03 | 10.12 | 9.73 (-3.8) | 260.26 (+2471.8) L | 8.19 (-19.1) | 18.79 (+85.6) L | 345.53 (+3314.4) L | 67.43 (+566.3) L | 0.037/0.341/0.317 | 246+23 |
| 04 | 26.31 | 25.75 (-2.1) | 28.42 (+8.0) | 19.74 (-25.0) | 29.90 (+13.7) | 363.30 (+1280.8) L | 67.43 (+156.3) L | 0.796/0.765/0.761 | 243+25 |
| 05 | 35.5 | 34.83 (-1.9) | 78.03 (+119.8) L | 25.38 (-28.5) | 38.97 (+9.8) | 284.70 (+702.0) L | 67.43 (+90.0) L | 0.444/0.706/0.858 | 247+45 |
| 06 | 15.29 | 14.68 (-4.0) | 11.62 (-24.0) | 14.41 (-5.8) | 16.05 (+5.0) | 12.45 (-18.6) | 13.52 (-11.6) | 0.784/0.841/0.846 | 248+44 |
| 07 | 4.9 | 4.05 (-17.4) | 2.32 (-52.6) | 3.99 (-18.5) | 4.75 (-3.0) | 341.29 (+6865.1) L | 1.71 (-65.1) | 0.27/0.678/0.768 | 249+40 |
| 08 | 4.32 | 4.82 (+11.5) | 0.35 (-91.9) | 0.05 (-98.9) | 4.91 (+13.6) | 346.30 (+7916.1) L | 142.19 (+3191.5) L | 0.058/0.01/0.957 | 247+22 |
| 09 | 16.84 | 16.35 (-2.9) | 10.76 (-36.1) | 6.71 (-60.2) | 14.78 (-12.2) | 340.51 (+1922.0) L | 196.65 (+1067.7) L | 0.658/0.41/0.768 | 244+35 |
| 10 | 2.72 | 2.67 (-2.0) | 217.87 (+7909.9) L | 100.17 (+3582.9) L | 2.27 (-16.4) | 310.51 (+11315.9) L | 190.53 (+6904.9) L | 0.012/0.0/0.822 | 247+23 |
| 11 | 15.89 | 15.30 (-3.7) | 2.62 (-83.5) | 2.48 (-84.4) | 12.23 (-23.1) | 267.04 (+1580.5) L | 15.12 (-4.8) | 0.171/0.162/0.795 | 249+24 |

Summary (n = 11): ≤ 2 % — vector 1, A 0, B 1, C 0. ≤ 5 % — vector 9, A 0, B 1, C 2. Median \|err\| — vector 3.8 %, A 52.6 %, B 27.5 %, C 13.6 %. Rooms 01/03 and 04/05 are open spaces the lane divides by its own boundary; no SAM variant can know that boundary.

#### objektas_g — vector (page 4, lubų planas: area labels, stipple hatch, diffuser symbols)

| nr | table m² | vector m² (%) | A m² (%) | B m² (%) | C m² (%) | D m² (%) | FFd m² (%) | IoU vs vector A/B/C | ms enc+dec A |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 37.86 | 39.26 (+3.7) | 79.53 (+110.1) L | 0.06 (-99.8) | 78.73 (+107.9) L | 221.47 (+485.0) L | 205.10 (+441.7) L | 0.483/0.002/0.494 | 250+75 |
| 02 | 14.26 | 15.12 (+6.0) | 33.78 (+136.9) L | 14.19 (-0.5) | 19.80 (+38.9) L | 12.38 (-13.2) | 166.38 (+1066.8) L | 0.447/0.892/0.757 | 261+82 |
| 03 | 3.52 | 3.84 (+9.1) | 2.03 (-42.2) | 1.81 (-48.7) | 4.38 (+24.6) | 3.60 (+2.3) | 3.56 (+1.3) | 0.529/0.47/0.865 | 249+77 |
| 04 | 10.05 | 10.30 (+2.5) | 9.11 (-9.4) | 0.28 (-97.2) | 9.77 (-2.8) | 266.44 (+2551.1) L | 250.33 (+2390.9) L | 0.884/0.027/0.94 | 245+32 |
| 05 | 3.76 | 3.90 (+3.8) | 76.93 (+1946.1) L | 21.33 (+467.4) L | 4.32 (+14.9) | 224.41 (+5868.5) L | 153.39 (+3979.5) L | 0.0/0.0/0.862 | 266+77 |
| 06 | 7.25 | 7.56 (+4.3) | 57.34 (+690.9) L | 11.07 (+52.7) L | 7.55 (+4.1) | 207.61 (+2763.6) L | 159.59 (+2101.2) L | 0.0/0.0/0.958 | 262+75 |
| 07 | 5.64 | 7.56 (+34.0) | 10.15 (+80.0) L | 1.51 (-73.2) | 8.69 (+54.1) L | 6.29 (+11.5) | 5.40 (-4.3) | 0.652/0.2/0.818 | 267+73 |
| 08 | 10.55 | 10.81 (+2.5) | 10.04 (-4.8) | 10.59 (+0.4) | 11.13 (+5.5) | 9.78 (-7.3) | 173.33 (+1542.9) L | 0.928/0.948/0.957 | 247+30 |
| 09 | 6.78 | 6.88 (+1.5) | 88.91 (+1211.3) L | 10.54 (+55.5) L | 6.86 (+1.2) | 176.82 (+2507.9) L | 149.28 (+2101.8) L | 0.0/0.0/0.967 | 246+64 |

"vector" on G is the one-click `outline_at` face on page 4 (the lane's stored outlines live on other sheets of the same plan; their areas agree within 1 %). Room 07's seat is a guessed bbox and lands in room 06 — the vector click takes 06's face too (+34 %). Summary (n = 9): ≤ 2 % — vector 1, A 0, B 2, C 1. ≤ 5 % — vector 6, A 1, C 3. Median \|err\| — vector 3.8 %, A 110 %, B 55.5 %, C 14.9 %.

### Sensitivity

| Change | Effect |
|---|---|
| SAM 2.1 **large** (A raster / H) | ≤ 2 % of table: A 0/11 / 0/11, B 0/11 / 1/11, C 0/11 / 1/11. Encode 411 ms instead of 247 ms. No improvement. |
| **10 m** crop instead of 20 m | A ≤ 2 %: 0/11 (raster), 1/11 (H), 0/9 (G); C 1/11, 2/11, 1/9. No improvement. |
| **Full page** (F) instead of a crop | worse: no-leak 1/11, 3/11, 3/9 |
| **Oracle** — best of A's three multimask hypotheses chosen with the table in hand | ≤ 2 % of table: 1/11 (raster), 0/11 (H), 0/9 (G). The right mask is usually *not among* SAM's hypotheses at all. |

## Timing (M4 Pro, MPS, `sam2.1_b`)

| Step | Time |
|---|---|
| Model load | 0.7 s (once per process) |
| First encode (warm-up) | 0.6 s |
| Encode, 20 m crop (~2000–2900 px square → 1024) | **median 247 ms** |
| Decode + mask upscale per prompt | 22–75 ms (median 25–74 ms per sheet) |
| Polygonize | 15–25 ms |
| Render a page at 300 DPI | 60–200 ms (once per page) |
| Vector `outline_at` for comparison | 22–65 ms |

A click would cost ~0.3–0.4 s end to end — fast enough. Speed is not the problem.

## Failure modes (in order of damage)

1. **SAM segments the drawing's line-art, not the room.** Every thin line is an edge to SAM: dimension lines and construction lines crossing the room, door-swing arcs, furniture outlines, the printed badge itself. A click on the label returns the badge glyph (L: 0.03–0.8 m² on 25 of 31 rooms); a click beside it returns the cell between the badge, the door arc and a dimension line (objektas_a 108: A 0.73 m² vs 11.65 m² — `spikes/sam2/out/objektas_a_raster/108.png`); in furnished plans the mask follows the bed and wardrobe (objektas_h 06: A 11.6 vs 14.7 — `spikes/sam2/out/objektas_h/06.png`). Negative points on the walls (B) make masks *smaller*, not tighter (B median −49 % on objektas_a).
2. **"Paper" wins over "room".** On a white sheet the most object-like region around a point in white space is the white paper. With one point SAM's top-scoring hypothesis is often the entire sheet background across all rooms (objektas_a 103/107/109/110: 200–340 m² — `spikes/sam2/out/objektas_a_raster/110.png`; objektas_h 10: 218 m² for a 2.7 m² room). With a box (C) it sometimes picks the **wall ring** instead of the interior (objektas_a 110: 8.4 m², mostly the hatched wall ring; 102: a 6.1 m² fragment).
3. **Doors and open plans are invisible boundaries.** A door opening is a gap in the walls; SAM, flood fill and the walls-only image all run through it (D: 8/11 leaks on the raster, FF 11/11, FFd still 7/11 with a 1.2 m bridge). Rooms with no wall between them (objektas_g 01 + hall: `spikes/sam2/out/objektas_g/01.png`, A/C ≈ 79 m² vs 37.9; objektas_h 01/03, 04/05) cannot be separated by any mask — only by the table's areas and a proposed boundary, which the vector lane already does.

Secondary: stipple hatching on ceiling plans (G) makes mask edges jagged (C polygons with 24–370 vertices at ε = 2 cm); seats from `room_locator` that are guessed (`bbox`, G 07) put the click in the wrong room.

## Is the fallback right?

**Partly.** "Vector + manual polygons now" is right, and it is what the app already has (`outline_at`, `outline-set`, `OutlineEditLayer`). On the segmenter track, two observations:

- What is missing is **class knowledge** (this is a wall, this is a door leaf, this is furniture, this is floor), not boundary quality. A promptable class-agnostic model cannot be prompted into it. A semantic floor-plan segmenter (rooms/walls/doors/windows — CubiCasa5k-style, later fine-tuned on our `room_geometry` rows) attacks failure modes 1 and 2 directly; failure mode 3 (doors, open plans) needs the room/door classes *and* the table logic the vector lane already has.
- Before training anything, a **deterministic raster wall-solid spike** is cheaper and may cover the honest raster case: `wall_mask` here is already clean on G and on the objektas_a raster (black hatched walls), the remaining work is door-gap bridging by detected wall ends (not a blind 1.2 m closing, which merged rooms and stripped corridors: FFd 4/11 no-leak), i.e. the raster twin of `vector_rooms._bridges`. That reuses the vector lane's room logic unchanged. Only if that fails on furnished/greyscale sheets (H) is the trained segmenter the next step.

Either way G0's 2 % bar needs fixing first on objektas_a: the vector outlines are 8.5 % under the table there, so the bar measures the scale or the table convention, not the segmentation.

## What wiring `sam_source.py` (plan §3.1) would take — if a later model passes

The code under `spikes/sam2/` is shaped as the seed:

- `spikes/sam2/sam_source.py` — `render_page(pdf, page, dpi) -> (img, PageFrame)` (pixel ↔ PDF-point matrix), `load_model(weights, device)` → `SamModel.set_image()` / `.segment(points, neg_points, box, multimask) -> [(mask, score)]`, `wall_mask`, `clear_floor_point`, `negative_points_on_walls`, `largest_component`, `mask_to_polygon(mask, frame, eps_m, m_per_pt, offset_px) -> GeoJSON` (PDF points, display space), `polygon_metrics`. The model is an implementation detail behind `SamModel`; a floor-plan segmenter would drop in behind the same `segment()` and the rest stays.
- To ship: move to `backend/geometry/` (render via `page_raster_cache`, scale via `scale.py`), weights under `backend/data/models/` (gitignored), model loaded once per process behind a lock (MPS/PDFium are not thread-safe — see `PDFIUM_LOCK`), `torch` + `ultralytics` as an optional extra (≈ 1 GB of wheels; Railway image size and CPU-only latency need a measurement — CPU encode was not measured here), `POST /api/geometry/segment` returning the polygon with `source="sam2"`, model version and prompt points for `provenance.py`. Snapping vertices to vector walls (`polygonize.py`) would not rescue failure modes 1–3.
- Do **not** wire it now: it would put a geometry source that is wrong by > 10 % on most rooms behind the same button as a vector outline that is within 5 % on most rooms.

## Reproduce

```bash
# 1. spike venv (once)
python3 -m venv spikes/sam2/.venv
spikes/sam2/.venv/bin/pip install ultralytics opencv-python-headless pypdfium2 numpy shapely pillow
mkdir -p spikes/sam2/weights spikes/sam2/out
(cd spikes/sam2/weights && ../.venv/bin/python -c "from ultralytics import SAM; SAM('sam2.1_b.pt'); SAM('sam2.1_l.pt')")

# 2. the app's readers on the vector drawings (PROJECT venv; reads ground_truth/ + fixtures from the main checkout)
/Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/sam2/dump_lane.py objektas_a spikes/sam2/out/lane_objektas_a.json
/Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/sam2/dump_lane.py objektas_h spikes/sam2/out/lane_objektas_h.json
/Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/sam2/dump_lane.py objektas_g spikes/sam2/out/lane_objektas_g.json

# 3. SAM runs (spike venv) + tables
spikes/sam2/.venv/bin/python spikes/sam2/run_spike.py                       # base, 20 m crop, all four runs (~80 s)
spikes/sam2/.venv/bin/python spikes/sam2/run_spike.py --weights spikes/sam2/weights/sam2.1_l.pt --runs objektas_a_raster,objektas_h --tag _large
spikes/sam2/.venv/bin/python spikes/sam2/run_spike.py --side-m 10 --runs objektas_a_raster,objektas_h,objektas_g --tag _crop10
python3 spikes/sam2/summarize.py > spikes/sam2/out/summary.md                # and --tag _large / --tag _crop10
```

Overlays: `spikes/sam2/out/<run>/<nr>.png` (red A, green B, blue C, yellow D, magenta = vector outline, red dot = click, black crosses = B's negatives) — written by the **last** run, so re-run the base command last before looking at them. Fixture PDFs and truth are read from the main checkout by absolute path; nothing from them is copied into the repo.
