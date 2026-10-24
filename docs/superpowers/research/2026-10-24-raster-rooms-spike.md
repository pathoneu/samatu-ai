# Deterministic raster room spike — gate G0 (raster path after SAM 2)

**Date:** 2026-10-24 · **Worker:** Opus 5.5 · **Branch:** `spike/raster-rooms` (not merged) · **Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §3.1, §4 Phase 0, §9 · **Follows:** `docs/superpowers/research/2026-10-24-sam2-room-mask-spike.md` ("Is the fallback right?")

Founder decision being tested: *"deterministic raster spike: wall mask + door-gap bridging + the existing room logic, same gate G0; trained segmenter only if it fails"*. No model of any kind: OpenCV, numpy, shapely, pypdfium2.

## Resume point

Done: code (`spikes/raster_rooms/`), all runs (5 inputs × 150/300 DPI, furniture on/off, 4 sensitivity variants), tables below, report. Committed on `spike/raster-rooms`. Nothing under `backend/` touched. If picked up again: the next experiment is listed under "If the raster track continues" — do not tune constants further on these same 50 rooms (see "Overfitting warning").

## Verdict

**G0 FAILS on every project and every clause except "no leak" on three runs.** The deterministic pipeline is nevertheless a different class of result from SAM 2: on the sheets where its wall mask is clean it finds the right room almost every time (IoU 0,94–0,98 against the vector outline), but it does **not** place the boundary to 2 %.

| G0 clause (bar) | objektas_a raster (flat150) | objektas_h render | objektas_g render | objektas_j3 scan |
|---|---|---|---|---|
| ≤ 2 % of table on ≥ 80 % | **FAIL** 0/11 (150 & 300 DPI) | **FAIL** 1/11 · 0/11 | **FAIL** 4/8 · 6/8 | **FAIL** 3/9 · 2/9 |
| no leak on ≥ 90 % | **PASS** 11/11 (150) · FAIL 8/11 (300) | **FAIL** 8/11 · 9/11 | FAIL 5/8 · **PASS** 8/8 | **PASS** 9/9 · FAIL 8/9 |
| §9: ≤ 2 % of vector outline AND IoU ≥ 0,95 on ≥ 80 % | **FAIL** 2/11 · 1/11 | **FAIL** 0/11 · 3/11 | **FAIL** 3/8 · 1/8 | **FAIL** 1/8 · 2/8 |
| (context) ≤ 5 % of vector outline | 7/11 · 4/11 | 1/11 · 5/11 | 4/8 · 5/8 | 7/8 · 6/8 |
| (context) median IoU vs vector | 0,945 · 0,915 | 0,370 · 0,870 | 0,946 · 0,972 | 0,962 · 0,968 |
| SAM 2 best honest variant, same rooms (≤ 2 % table / median IoU) | A: 0/11 · 0,11 | A: 0/11 · 0,30 | A: 0/9 · 0,48 | not run |

Cells are "150 DPI · 300 DPI". The table clause is unreachable on objektas_a for **any** geometry source (the vector outlines themselves are 7–23 % under the table — the SAM report's caveat, re-confirmed: vector median |err| vs table 8,4 %).

**Is the trained-segmenter track needed?** Not for the reason the plan gave. What fails here is not *finding* the room (the raster lane finds it on 4 of 5 inputs with median IoU 0,92–0,97, SAM did not), it is (1) the 2 % boundary bar, which a segmenter trained on our ~1 confirmed polygon cannot be expected to meet either, and (2) furnished sheets whose furniture is drawn with the same pen as the walls (objektas_h at 150 DPI). My recommendation, stated as a disagreement with the gate rather than a pass: **do not start a trained segmenter now.** Restate the raster clause the way §9 restated G1 (the outline against the drawing, ≤ 5 %, plus a leak clause), and treat the raster lane as a *proposal* the user confirms — exactly how the vector `outline_at` result is used today. If the founder keeps 2 %, then nothing raster passes, trained or not, and the honest product answer for raster sheets is manual polygon + the raster proposal as a starting shape.

## Setup

| | |
|---|---|
| Code | `spikes/raster_rooms/raster_rooms.py` (`wall_mask_raster`, `wall_solid`, `bridge_door_gaps`, `RasterPage`, `room_at_click`, `snap_to_axes`, `face_stroke_px`); runner `run_raster.py`; tables `summarize.py`; j2 truth `dump_j2.py` |
| Reused (imported, not copied) | `spikes/sam2/sam_source.py`: `render_page` (PDFium, display space, pixel ↔ PDF-point frame), `largest_component`, `mask_to_polygon`, `polygon_metrics`; `spikes/sam2/run_spike.py`: `ref_outline`, `iou`, `pct_err` (so the reference outline is chosen exactly as in the SAM spike) |
| venv | `spikes/raster_rooms/.venv` (Python 3.14, opencv-python-headless 5.0, numpy, shapely 2.x, pypdfium2, pymupdf for optional-content layers, scikit-image unused). `spikes/sam2/.venv` did not exist in the main checkout. |
| Truth, objektas_a / h / g | `spikes/sam2/dump_lane.py` (project venv, read-only import of `backend/`) on the **vector originals**: seats (printed badge / area label from `room_locator`), table m² (cached extraction), sheet scale (`plan_dimensions`), reference outline (lane `_konturas` on the same page, else the one-click `outline_at` face) — identical to the SAM spike. |
| Truth, objektas_j3 | `spikes/raster_rooms/dump_j2.py` on the vector original objektas_j2 sheet 1. **The lane is blind on this sheet** (plan §9 causes 1 and 5: badges 11,7 pt > the 6,5 pt cap; no scale). Seats = the badge digits from the text layer; table = the sheet's eksplikacija; scale: the stated „M 1:40" is wrong for this A3 print (outlines came out 18–31 % under the table) — matched by hand to dimension strings on wall faces (room 9: 3200 mm / 203,1 pt, 3790 / 240,3; room 7: 3570 / 226,4) → **0,01576 m/pt (≈ 1:44,7)**; reference = vector `outline_at` at each seat (8/9 ok; room 3 "outside" — no vector truth for it). The scan is registered to j2 by SIFT + RANSAC homography on the two renders (475 inliers at 150 DPI, scale 1,420 vector-pt per scan-pt, rotation 0,003°); seats go j2 → scan, the raster polygon goes scan → j2 for IoU and m² (scale cancels). |
| Inputs | objektas_a: the flattened raster `objektas_a_flat150.pdf` p.2 (150 DPI raster inside; 300 DPI = upsampled) and the vector original p.2 rasterised by PDFium; objektas_h p.1 and objektas_g p.4 rasterised by PDFium (glyphs stay as pixels; nothing reads text); objektas_j3 the contractor's scan (native ≈ 213 DPI). Rendered at 150 and 300 DPI. |
| Furniture off | `pymupdf` switches every optional-content layer named like furniture (`baldai`, `Furniture`) OFF, PDFium renders the copy. **Not testable on these sheets:** the layers exist (objektas_a: 6 furniture layers, objektas_g: „Interior - Furniture") but the plan pages' furniture is not drawn in them — the render differs by 0,01 % (a) / 0 % (g) of pixels and every number is identical. objektas_h has no optional content. |
| Hardware | Apple M4 Pro, single process, no GPU |

### The pipeline (what each function does, and which vector rule it ports)

1. **`wall_mask_raster`** — the thickness band comes from the sheet scale. Ink = dark (< 170) strokes ∪ light-grey fill (< 240) that is at least 6 cm wide (a line's anti-aliased halo never is); coloured pixels ((max−min)/max > 0,2 and not dark) are never wall — blue dimensions, red leaders, cyan radiators and the contractor's pen on j3 drop out here. Hatch/cross-hatch/honeycomb: enclosed white cells ≤ (6,5 cm)² are filled (text is not made solid by this). Then a wall must be a **bar**: union of openings with a k × 25 cm rectangle at 0°/90° and a k-wide diagonal at 45°/135°, k = 0,6 × 7 cm (thinnest wall); isolated pieces < 40 cm and < 0,06 m² are dropped.
2. **`wall_solid`** — contours → polygons, edges within 12° of an axis snapped onto it, a vector opening by 8 cm cuts off knobs (window-frame stubs, ticks), 1-px steps simplified away. This is the raster twin of the vector lane's merged wall-colour solid.
3. **`bridge_door_gaps`** — `vector_rooms._bridge_records` ported verbatim to pixels (DOOR_SWEEP 1,25 → 1,6 m, LONG_MAX 6,5 m, STRIP_MAX 0,75 m, MIN_OVERLAP 5 cm, antiparallel 6°, "something stands in the gap", both sides free). **One raster change:** a gap beyond the door limit (windows, glazed walls) is bridged only between two real **wall end caps** (`_is_end`: behind the edge the solid runs on ≥ 15 cm and on at least one side there is free space just beyond the edge) — on raster a short edge is far more often a bump left by a crossing dimension line than a wall end, and the unmodified rule drew 4 m strips across rooms (objektas_a 107). Requiring an end cap for *doors* too was measured (`--door-needs-end`) and is worse on the vector-rendered objektas_a (median IoU 0,917 → 0,769).
4. **`room_at_click`** — the vector lane's `outline_at` decisions: free face under the click (a click on the badge ink moves to the nearest free pixel); door sweep 1,25 → 1,6 m when the face reaches the sheet frame; a face that is too small takes in a seat-less neighbour across a bridge while that brings the area closer to the table (`_match` "grow", AREA_TOL 8 %, kept only if it ends within 8 %); another seat inside, or > 1,6 × table → `open`. Polygon via `mask_to_polygon` (ε 2 cm), half-pixel correction, `snap_to_axes` (≤ 3°), holes filled, then grown by half the measured outline-stroke width (`face_stroke_px`: CAD draws the hatch boundary on the wall line's centre).
5. **Scoring** — area vs the vector outline (primary, scale cancels), IoU vs the vector outline, area vs the table (secondary), leak = `open` / reaches the frame / > 1,3 × table, ms per click (per-sheet preprocessing reported separately, like SAM's encoder).

## Results — all runs (default parameters)

| run | DPI | rooms | ≤2 % table | no leak | ≤2 % vector & IoU≥0,95 | ≤2 % vector | ≤5 % vector | IoU≥0,95 | median \|err\| vector | median \|err\| table | median IoU | failed (no outline) | ms/click | G0 table | G0 leak | G0 §9 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| objektas_a_flat150 | 150 | 11 | 0/11 | 11/11 | 2/11 | 4/11 | 7/11 | 4/11 | 2.6 % | 8.3 % | 0.945 | 0 | 15 | FAIL | PASS | FAIL |
| objektas_a_flat150 | 300 | 11 | 0/11 | 8/11 | 1/11 | 2/11 | 4/11 | 2/11 | 6.2 % | 15.3 % | 0.915 | 0 | 56 | FAIL | FAIL | FAIL |
| objektas_a_render | 150 | 11 | 0/11 | 8/11 | 0/11 | 4/11 | 6/11 | 1/11 | 2.5 % | 8.0 % | 0.917 | 0 | 15 | FAIL | FAIL | FAIL |
| objektas_a_render | 300 | 11 | 0/11 | 8/11 | 0/11 | 0/11 | 6/11 | 4/11 | 3.8 % | 14.4 % | 0.923 | 0 | 56 | FAIL | FAIL | FAIL |
| objektas_a_render_nofurn | 150 | 11 | 0/11 | 8/11 | 0/11 | 4/11 | 6/11 | 1/11 | 2.5 % | 8.0 % | 0.917 | 0 | 15 | FAIL | FAIL | FAIL |
| objektas_a_render_nofurn | 300 | 11 | 0/11 | 8/11 | 0/11 | 0/11 | 6/11 | 4/11 | 3.8 % | 14.4 % | 0.923 | 0 | 56 | FAIL | FAIL | FAIL |
| objektas_h_render | 150 | 11 | 1/11 | 8/11 | 0/11 | 0/11 | 1/11 | 0/11 | 54.0 % | 51.2 % | 0.370 | 0 | 8 | FAIL | FAIL | FAIL |
| objektas_h_render | 300 | 11 | 0/11 | 9/11 | 3/11 | 3/11 | 5/11 | 3/11 | 9.9 % | 9.0 % | 0.870 | 0 | 27 | FAIL | FAIL | FAIL |
| objektas_g_render | 150 | 8 | 4/8 | 5/8 | 3/8 | 3/8 | 4/8 | 4/8 | 5.4 % | 2.5 % | 0.946 | 0 | 15 | FAIL | FAIL | FAIL |
| objektas_g_render | 300 | 8 | 6/8 | 8/8 | 1/8 | 1/8 | 5/8 | 5/8 | 2.6 % | 1.1 % | 0.972 | 0 | 54 | FAIL | PASS | FAIL |
| objektas_g_render_nofurn | 150 | 8 | 4/8 | 5/8 | 3/8 | 3/8 | 4/8 | 4/8 | 5.4 % | 2.5 % | 0.946 | 0 | 15 | FAIL | FAIL | FAIL |
| objektas_g_render_nofurn | 300 | 8 | 6/8 | 8/8 | 1/8 | 1/8 | 5/8 | 5/8 | 2.6 % | 1.1 % | 0.972 | 0 | 54 | FAIL | PASS | FAIL |
| objektas_j3_scan | 150 | 9 | 3/9 | 9/9 | 1/8 | 1/8 | 7/8 | 7/8 | 3.4 % | 2.1 % | 0.962 | 0 | 8 | FAIL | PASS | FAIL |
| objektas_j3_scan | 300 | 9 | 2/9 | 8/9 | 2/8 | 2/8 | 6/8 | 6/8 | 3.2 % | 2.7 % | 0.968 | 1 | 28 | FAIL | FAIL | FAIL |

`ms/click` is `room_at_click` alone (walls, solid, edges and bridges are built once per sheet: 0,1–0,3 s at 150 DPI, 0,3–0,55 s at 300 DPI; render 0,06–0,2 s). Half of the per-click time is `face_stroke_px`; without it a click is 5–25 ms. objektas_g has 8 rooms here (room 07's seat lies on another page; the SAM table has 9).

### Sensitivity (cells: `≤2 % vector & IoU≥0,95` / `≤5 % vector` / `no leak` · median IoU, for 150 — 300 DPI)

| variant | a_flat150 150 / 300 | a_render 150 / 300 | h_render 150 / 300 | g_render 150 / 300 | j3_scan 150 / 300 |
|---|---|---|---|---|---|
| default (min wall 7 cm, k=0,6×, knob 8 cm) | 2/7/11 · 0.94 — 1/4/8 · 0.92 | 0/6/8 · 0.92 — 0/6/8 · 0.92 | 0/1/8 · 0.37 — 3/5/9 · 0.87 | 3/4/5 · 0.95 — 1/5/8 · 0.97 | 1/7/9 · 0.96 — 2/6/8 · 0.97 |
| thinnest wall 5 cm | 3/7/11 · 0.94 — 0/4/9 · 0.92 | 0/5/9 · 0.89 — 0/6/8 · 0.93 | 0/1/8 · 0.37 — 0/2/11 · 0.70 | 2/3/5 · 0.70 — 3/6/8 · 0.97 | 0/4/6 · 0.81 — 2/5/9 · 0.96 |
| thinnest wall 9 cm (= open share 0,8 — same kernel) | 2/6/11 · 0.92 — 1/5/8 · 0.92 | 0/6/9 · 0.89 — 0/6/8 · 0.92 | 0/1/9 · 0.53 — 1/4/6 · 0.56 | 3/6/6 · 0.96 — 3/7/8 · 0.97 | 1/5/9 · 0.95 — 2/7/8 · 0.97 |
| knob opening 6 cm | 3/7/11 · 0.94 — 0/3/7 · 0.74 | 1/6/9 · 0.92 — 0/5/7 · 0.80 | 0/0/8 · 0.37 — 2/4/9 · 0.75 | 3/4/5 · 0.95 — 3/5/8 · 0.97 | 2/7/9 · 0.96 — 2/7/8 · 0.97 |
| doors must start at a wall end | 3/7/11 · 0.94 — 1/4/8 · 0.92 | 1/4/6 · 0.77 — 0/6/8 · 0.92 | 0/1/6 · 0.45 — 3/5/9 · 0.88 | 3/4/5 · 0.95 — 1/5/8 · 0.97 | 1/7/9 · 0.96 — 2/6/8 · 0.97 |

Read across a row and down a column: **no setting is best everywhere, and 150 vs 300 DPI flips individual rooms** (objektas_a: 11/11 no-leak at 150, 8/11 at 300; objektas_g the reverse). A 1-px change in where a wall end lands decides whether a 1,25 m door limit is met. That is the brittleness the founder should weigh, not any single cell.

### Overfitting warning

The constants above were tuned by looking at overlays of these same five sheets (≈ 50 rooms); objektas_j3 was looked at last and least. The numbers are an in-sample upper bound for this pipeline. Out-of-sample raster plans would be expected to score lower, not higher.

## Per-room tables (selected; all runs in `spikes/raster_rooms/out/results.json` after a run)

"vector click m²" is the vector lane's own one-click answer (`outline_at`) at the same seat — the like-for-like vector baseline. SAM columns are the SAM 2.1 base rows from the SAM spike (A = honest click, C = box from the vector outline, i.e. cheating); for objektas_h and objektas_g SAM ran on the vector sheet, here the raster lane runs on a render of it.

#### objektas_a_flat150 — 150 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 11.01 | 9.014 | 7.28 | 4.853 | -55.9 | -46.2 | 0.538 | – | ok |  | 15.2 | -37.4 % / 0.762 | -9.9 % / 0.83 |
| 102 | 50.54 | 45.503 | 45.47 | 46.63 | -7.7 | +2.5 | 0.96 | 1.4 | ok |  | 14.8 | +5.0 % / 0.782 | -88.0 % / 0.011 |
| 103 | 9.64 | 7.405 | 6.06 | 6.129 | -36.4 | -17.2 | 0.754 | 1.4 | ok |  | 14.2 | 2406.28 % / 0.03 | -28.3 % / 0.776 |
| 104 | 13.51 | 11.812 | 11.8 | 12.138 | -10.2 | +2.8 | 0.94 | 1.4 | ok |  | 14.9 | -71.6 % / 0.325 | -17.7 % / 0.861 |
| 105 | 10.67 | 9.538 | 9.53 | 7.461 | -30.1 | -21.8 | 0.782 | 1.4 | ok |  | 15.3 | -53.7 % / 0.518 | -13.8 % / 0.86 |
| 106 | 6.84 | 7.354 | 7.35 | 7.166 | +4.8 | -2.6 | 0.956 | 1.4 | ok |  | 14.1 | +176.2 % / 0.325 | -20.1 % / 0.744 |
| 107 | 6.59 | 6.108 | 6.1 | 3.914 | -40.6 | -35.9 | 0.641 | 1.4 | ok |  | 14.4 | 2908.71 % / 0.031 | -1.3 % / 0.899 |
| 108 | 12.71 | 11.652 | 11.64 | 11.712 | -7.8 | +0.5 | 0.948 | 1.4 | ok |  | 14.6 | -94.3 % / 0.06 | -12.9 % / 0.902 |
| 109 | 12.71 | 11.652 | 11.64 | 11.828 | -6.9 | +1.5 | 0.956 | 1.4 | ok |  | 14.3 | -31.6 % / 0.0 | -4.6 % / 0.888 |
| 110 | 23.97 | 21.948 | 28.97 | 21.988 | -8.3 | +0.2 | 0.961 | 1.4 | ok |  | 14.6 | +955.7 % / 0.087 | -65.1 % / 0.036 |
| 111 | 7.45 | 6.851 | – | 6.935 | -6.9 | +1.2 | 0.945 | 1.4 | ok |  | 14.4 | +760.2 % / 0.107 | +7.4 % / 0.759 |

#### objektas_a_flat150 — 300 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 11.01 | 9.009 | 7.28 | 6.823 | -38.0 | -24.3 | 0.718 | – | ok |  | 59.3 | -37.4 % / 0.762 | -9.9 % / 0.83 |
| 102 | 50.54 | 45.481 | 45.47 | 44.669 | -11.6 | -1.8 | 0.915 | 2.1 | ok |  | 60.0 | +5.0 % / 0.782 | -88.0 % / 0.011 |
| 103 | 9.64 | 7.401 | 6.06 | 5.867 | -39.1 | -20.7 | 0.793 | – | ok |  | 55.0 | 2406.28 % / 0.03 | -28.3 % / 0.776 |
| 104 | 13.51 | 11.806 | 11.8 | 11.59 | -14.2 | -1.8 | 0.982 | 1.4 | ok |  | 55.3 | -71.6 % / 0.325 | -17.7 % / 0.861 |
| 105 | 10.67 | 9.533 | 9.53 | 9.033 | -15.3 | -5.2 | 0.947 | 1.4 | ok |  | 53.9 | -53.7 % / 0.518 | -13.8 % / 0.86 |
| 106 | 6.84 | 7.35 | 7.35 | 7.142 | +4.4 | -2.8 | 0.962 | 1.4 | ok |  | 56.2 | +176.2 % / 0.325 | -20.1 % / 0.744 |
| 107 | 6.59 | 6.105 | 6.1 | 5.725 | -13.1 | -6.2 | 0.937 | 1.4 | ok |  | 53.8 | 2908.71 % / 0.031 | -1.3 % / 0.899 |
| 108 | 12.71 | 11.647 | 11.64 | 12.073 | -5.0 | +3.6 | 0.936 | 2.1 | ok |  | 55.5 | -94.3 % / 0.06 | -12.9 % / 0.902 |
| 109 | 12.71 | 11.647 | 11.64 | 40.747 | +220.6 | +249.8 | 0.281 | 1.4 | open | L | 56.8 | -31.6 % / 0.0 | -4.6 % / 0.888 |
| 110 | 23.97 | 21.937 | 28.97 | 40.747 | +70.0 | +85.8 | 0.528 | 1.4 | open | L | 57.5 | +955.7 % / 0.087 | -65.1 % / 0.036 |
| 111 | 7.45 | 6.848 | – | 40.747 | +446.9 | +495.0 | 0.165 | 1.4 | open | L | 55.7 | +760.2 % / 0.107 | +7.4 % / 0.759 |

#### objektas_h_render — 150 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 4.48 | 4.311 | 2.86 | 2.846 | -36.5 | -34.0 | 0.37 | 1.9 | ok |  | 7.6 | -18.6 % / 0.298 | -67.8 % / 0.274 |
| 02 | 6.9 | 7.162 | 7.16 | 44.932 | +551.2 | +527.4 | 0.133 | 3.9 | open | L | 7.9 | +7.8 % / 0.932 | -7.5 % / 0.884 |
| 03 | 10.12 | 9.738 | – | 3.178 | -68.6 | -67.4 | 0.215 | 1.9 | ok |  | 8.1 | 2471.77 % / 0.037 | +85.6 % / 0.317 |
| 04 | 26.31 | 25.758 | – | 53.66 | +104.0 | +108.3 | 0.366 | 1.9 | open | L | 8.9 | +8.0 % / 0.796 | +13.7 % / 0.761 |
| 05 | 35.5 | 34.839 | – | 53.66 | +51.2 | +54.0 | 0.569 | 1.9 | open | L | 9.1 | +119.8 % / 0.444 | +9.8 % / 0.858 |
| 06 | 15.29 | 14.679 | 14.67 | 15.065 | -1.5 | +2.6 | 0.406 | 1.9 | ok |  | 8.8 | -24.0 % / 0.784 | +5.0 % / 0.846 |
| 07 | 4.9 | 4.049 | 4.04 | 1.414 | -71.1 | -65.1 | 0.349 | 1.9 | ok |  | 7.8 | -52.6 % / 0.27 | -3.0 % / 0.768 |
| 08 | 4.32 | 4.817 | – | 2.779 | -35.7 | -42.3 | 0.545 | 1.9 | ok |  | 7.9 | -91.9 % / 0.058 | +13.6 % / 0.957 |
| 09 | 16.84 | 16.35 | 21.36 | 12.015 | -28.6 | -26.5 | 0.7 | 1.9 | ok |  | 8.3 | -36.1 % / 0.658 | -12.2 % / 0.768 |
| 10 | 2.72 | 2.666 | 2.66 | 0.629 | -76.9 | -76.4 | 0.198 | 1.9 | ok |  | 7.9 | 7909.93 % / 0.012 | -16.4 % / 0.822 |
| 11 | 15.89 | 15.302 | 15.29 | 10.894 | -31.4 | -28.8 | 0.712 | 1.9 | ok |  | 8.2 | -83.5 % / 0.171 | -23.1 % / 0.795 |

#### objektas_h_render — 300 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 4.48 | 4.31 | 2.86 | 2.28 | -49.1 | -47.1 | 0.429 | 2.9 | ok |  | 27.6 | -18.6 % / 0.298 | -67.8 % / 0.274 |
| 02 | 6.9 | 7.16 | 7.16 | 7.051 | +2.2 | -1.5 | 0.973 | 2.9 | ok |  | 27.4 | +7.8 % / 0.932 | -7.5 % / 0.884 |
| 03 | 10.12 | 9.735 | – | 10.698 | +5.7 | +9.9 | 0.87 | 2.9 | ok |  | 26.8 | 2471.77 % / 0.037 | +85.6 % / 0.317 |
| 04 | 26.31 | 25.751 | – | 61.31 | +133.0 | +138.1 | 0.401 | 2.9 | open | L | 27.7 | +8.0 % / 0.796 | +13.7 % / 0.761 |
| 05 | 35.5 | 34.829 | – | 61.31 | +72.7 | +76.0 | 0.556 | 2.9 | open | L | 28.4 | +119.8 % / 0.444 | +9.8 % / 0.858 |
| 06 | 15.29 | 14.675 | 14.67 | 14.025 | -8.3 | -4.4 | 0.941 | 2.9 | ok |  | 27.0 | -24.0 % / 0.784 | +5.0 % / 0.846 |
| 07 | 4.9 | 4.048 | 4.04 | 2.839 | -42.1 | -29.9 | 0.701 | 2.9 | ok |  | 26.1 | -52.6 % / 0.27 | -3.0 % / 0.768 |
| 08 | 4.32 | 4.815 | – | 4.708 | +9.0 | -2.2 | 0.924 | 2.9 | ok |  | 27.0 | -91.9 % / 0.058 | +13.6 % / 0.957 |
| 09 | 16.84 | 16.346 | 21.36 | 16.353 | -2.9 | +0.0 | 0.957 | 2.9 | ok |  | 27.5 | -36.1 % / 0.658 | -12.2 % / 0.768 |
| 10 | 2.72 | 2.665 | 2.66 | 1.496 | -45.0 | -43.9 | 0.504 | 2.9 | ok |  | 26.8 | 7909.93 % / 0.012 | -16.4 % / 0.822 |
| 11 | 15.89 | 15.297 | 15.29 | 15.059 | -5.2 | -1.6 | 0.981 | 2.9 | ok |  | 27.1 | -83.5 % / 0.171 | -23.1 % / 0.795 |

#### objektas_g_render — 150 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 37.86 | 39.264 | 39.25 | 54.31 | +43.5 | +38.3 | 0.521 | 2.5 | open | L | 15.1 | +110.1 % / 0.483 | +107.9 % / 0.494 |
| 02 | 14.26 | 15.125 | 15.17 | 54.31 | +280.9 | +259.1 | 0.276 | 2.5 | open | L | 15.9 | +136.9 % / 0.447 | +38.9 % / 0.757 |
| 03 | 3.52 | 3.841 | 3.84 | 3.532 | +0.3 | -8.1 | 0.919 | 2.5 | ok |  | 13.6 | -42.2 % / 0.529 | +24.6 % / 0.865 |
| 04 | 10.05 | 10.299 | 10.3 | 10.139 | +0.9 | -1.6 | 0.983 | 2.5 | ok |  | 14.6 | -9.4 % / 0.884 | -2.8 % / 0.94 |
| 05 | 3.76 | 3.904 | 3.95 | 3.916 | +4.1 | +0.3 | 0.98 | 2.5 | ok |  | 14.7 | 1946.12 % / 0.0 | +14.9 % / 0.862 |
| 06 | 7.25 | 7.562 | 7.56 | 54.31 | +649.1 | +618.2 | 0.127 | 2.5 | open | L | 16.0 | +690.9 % / 0.0 | +4.1 % / 0.958 |
| 08 | 10.55 | 10.812 | 10.81 | 10.509 | -0.4 | -2.8 | 0.972 | 0.9 | ok |  | 14.5 | -4.8 % / 0.928 | +5.5 % / 0.957 |
| 09 | 6.78 | 6.881 | 6.91 | 6.816 | +0.5 | -0.9 | 0.987 | 1.7 | ok |  | 14.6 | 1211.31 % / 0.0 | +1.2 % / 0.967 |

#### objektas_g_render — 300 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 37.86 | 39.256 | 39.25 | 38.46 | +1.6 | -2.0 | 0.979 | 0.4 | ok |  | 56.6 | +110.1 % / 0.483 | +107.9 % / 0.494 |
| 02 | 14.26 | 15.122 | 15.17 | 14.804 | +3.8 | -2.1 | 0.979 | 0.9 | ok |  | 55.6 | +136.9 % / 0.447 | +38.9 % / 0.757 |
| 03 | 3.52 | 3.84 | 3.84 | 3.5 | -0.6 | -8.8 | 0.911 | 1.3 | ok |  | 53.5 | -42.2 % / 0.529 | +24.6 % / 0.865 |
| 04 | 10.05 | 10.297 | 10.3 | 9.992 | -0.6 | -3.0 | 0.97 | 0.4 | ok |  | 54.1 | -9.4 % / 0.884 | -2.8 % / 0.94 |
| 05 | 3.76 | 3.903 | 3.95 | 3.701 | -1.6 | -5.2 | 0.948 | 0.4 | ok |  | 52.6 | 1946.12 % / 0.0 | +14.9 % / 0.862 |
| 06 | 7.25 | 7.56 | 7.56 | 7.102 | -2.0 | -6.0 | 0.939 | 1.3 | ok |  | 53.8 | +690.9 % / 0.0 | +4.1 % / 0.958 |
| 08 | 10.55 | 10.81 | 10.81 | 10.575 | +0.2 | -2.2 | 0.977 | 1.3 | ok |  | 53.1 | -4.8 % / 0.928 | +5.5 % / 0.957 |
| 09 | 6.78 | 6.879 | 6.91 | 6.769 | -0.2 | -1.6 | 0.975 | 1.3 | ok |  | 53.0 | 1211.31 % / 0.0 | +1.2 % / 0.967 |

#### objektas_j3_scan — 150 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3.14 | 2.696 | 2.69 | 1.503 | -52.1 | -44.3 | 0.539 | 1.1 | ok |  | 7.5 | – | – |
| 2 | 5.47 | 5.555 | 5.55 | 5.424 | -0.8 | -2.4 | 0.961 | 3.2 | ok |  | 7.8 | – | – |
| 3 | 35.86 | – | – | 36.409 | +1.5 | – | – | 3.2 | ok |  | 8.1 | – | – |
| 4 | 15.27 | 15.242 | 15.23 | 15.025 | -1.6 | -1.4 | 0.97 | 3.2 | ok |  | 7.9 | – | – |
| 5 | 3.99 | 4.029 | 4.03 | 3.878 | -2.8 | -3.7 | 0.959 | 3.2 | ok |  | 7.7 | – | – |
| 6 | 3.69 | 3.75 | 3.74 | 3.613 | -2.1 | -3.6 | 0.964 | 3.2 | ok |  | 7.7 | – | – |
| 7 | 11.42 | 11.429 | 11.42 | 11.181 | -2.1 | -2.2 | 0.977 | 3.2 | ok |  | 7.8 | – | – |
| 8 | 5.57 | 5.685 | 5.68 | 5.402 | -3.0 | -5.0 | 0.95 | 2.1 | ok |  | 7.6 | – | – |
| 9 | 12.13 | 12.085 | 12.1 | 11.708 | -3.5 | -3.1 | 0.969 | 2.1 | ok |  | 7.9 | – | – |

#### objektas_j3_scan — 300 DPI

| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3.14 | 2.695 | 2.69 | 2.603 | -17.1 | -3.4 | 0.966 | 3.2 | ok |  | 28.5 | – | – |
| 2 | 5.47 | 5.552 | 5.55 | 5.216 | -4.6 | -6.0 | 0.939 | – | ok |  | 28.7 | – | – |
| 3 | 35.86 | – | – | – | – | – | – | – | outside | L | 1.0 | – | – |
| 4 | 15.27 | 15.234 | 15.23 | 15.094 | -1.1 | -0.9 | 0.982 | 2.7 | ok |  | 29.4 | – | – |
| 5 | 3.99 | 4.027 | 4.03 | 3.906 | -2.1 | -3.0 | 0.97 | 2.7 | ok |  | 27.2 | – | – |
| 6 | 3.69 | 3.748 | 3.74 | 3.517 | -4.7 | -6.2 | 0.938 | – | ok |  | 28.1 | – | – |
| 7 | 11.42 | 11.423 | 11.42 | 11.222 | -1.7 | -1.8 | 0.982 | 2.7 | ok |  | 28.6 | – | – |
| 8 | 5.57 | 5.683 | 5.68 | 5.405 | -3.0 | -4.9 | 0.951 | 1.6 | ok |  | 28.2 | – | – |
| 9 | 12.13 | 12.079 | 12.1 | 11.824 | -2.5 | -2.1 | 0.979 | 1.6 | ok |  | 28.5 | – | – |

## Failure modes (in order of damage)

1. **Boundary noise of ±1–2 cm, systematically inward — the 2 % bar is below what a raster face can hold.** Where the right room is found (IoU ≥ 0,9), the raster face sits inside the vector face by a median 1,7–2,2 cm at 300 DPI (objektas_g 2,2; j3 1,7; a 2,1; h 0,9) with a per-room spread of ±1–1,5 cm — and the offset changes with DPI (objektas_a: −0,7 cm at 150, +2,1 cm at 300). On a 3,5 m² bathroom (perimeter 7,5 m) 2 cm is already 4 %. Causes: the wall's outline stroke (often coloured or merged with the hatch, so `face_stroke_px` cannot measure it), anti-aliasing, and the vector lane's own convention (its face is the fill edge). This one cause alone keeps every project below the §9 clause; the share within 5 % of the vector outline is 5/8–7/8 where the mask is clean.
2. **Furniture and fixtures drawn with the wall pen become walls (furnished sheets).** objektas_h at 150 DPI (median IoU 0,37): wardrobe zig-zag and kitchen-unit cross-hatch are enclosed cells, so the hatch fill makes them solid; thin (0,1 m at 1:115 ≈ 5 px) partitions in light grey are lost, so rooms leak into neighbours (02 → 44,9 m², 04/05 merged) or shrink to a cabinet-bounded fragment (10: 0,63 of 2,72 m²). At 300 DPI it recovers to 0,87 median IoU. This is the case the plan reserved for a trained segmenter — but note the vector lane already solves objektas_h, so it only matters for furnished sheets that arrive as raster.
3. **Door-gap bridging is right most of the time and catastrophically wrong when it is not.** The facing-edge rule needs clean wall ends; on raster, a dimension line crossing a wall, a door leaf stub or a frame tick changes an end into a bump (or the reverse). Results: a spurious bridge cuts a room in two (objektas_a 101: 4,9 of 9,0 m²; 107 at some settings; j3 room 1: the tambūras halved by a strip between the entrance door's frame and the inner door), or a missing window bridge lets the room run out of the building (objektas_g 01/02/06 at 150 DPI → 54 m² "open"). The rule cannot tell a 1,2 m door from a 1,2 m-wide corridor recess either (objektas_a 103, same as the vector lane's own click: 6,1 vs 6,06 m²). Door-swing arcs as gap markers were **not** implemented: on these sheets the arcs are thin strokes the mask already removes, and every missed bridge I inspected was a window or a frame stub, not a door without an arc.

Secondary: contractor pen markup on objektas_j3 is coloured (blue/red) and drops out of the mask with no visible damage — a black-pen markup would not; the table clause is meaningless on objektas_a (vector itself 8,4 % median under the table); objektas_j3 room 3 (35,86 m² open-plan living room with a glazed wall) is found by the raster lane within 1,5 % of the table at 150 DPI while the vector lane returns "outside".

## What wiring `backend/geometry/raster_source.py` would take

The seed is `spikes/raster_rooms/raster_rooms.py`; the functions are pure (image + scale in, GeoJSON in PDF points out).

- **Inputs the spike got for free.** Seats, table areas and the scale came from the vector original. A raster-only upload has none of them: seat = the user's click (fine — that is the product gesture), scale = the calibration-line gesture or OCR of a dimension string (plan §9 cause 5/7), table = OCR. Without a table, `grow` and the `open` factor switch off (both are optional in `room_at_click`).
- **Module shape.** `RasterPage` per (pdf, page, dpi) cached next to `page_raster_cache` (prep 0,1–0,5 s, a few MB per sheet: walls mask + shapely solid + bridge lists for 1,25/1,6 m); `room_at_click(page, x_pt→px, …)` per click (8–60 ms). PDFium render under `PDFIUM_LOCK`; no torch, no new heavy dependency (opencv-python-headless and shapely are already in the backend venv; pymupdf only for the furniture-layer experiment, not needed).
- **Endpoint.** Behind the existing `rooms/{nr}/outline-at` when the page has no vector walls (`status: "no_walls"` today), returning the polygon with `source="raster"` — plan §1 R1 lists `vector | sam2 | manual`; it would need `raster` added as a legal source with its own provenance (dpi, constants version, bridges used). Always presented as a **proposal the user confirms**, the same way a vector click is, with `paklaida` against the table when one exists.
- **Don't share code with `vector_rooms.py` yet.** The bridge rule is a verbatim port today with one deliberate difference (window bridges need end caps). If it ships, factor `_bridge_records` into a geometry-agnostic helper both lanes call, so a fix to one is a fix to both.
- **Tests before wiring:** the four inputs here as fixtures (codenames only, renders outside the repo), the j3 registration as the one real-scan case, and at least one *unseen* raster plan — the in-sample numbers above are not evidence enough.

## If the raster track continues (cheapest next experiments, in order)

1. **Restate the raster clause, then re-score unchanged:** ≤ 5 % vs the vector outline + IoU ≥ 0,9 + no leak. Today the ≤ 5 % share alone reads objektas_j3 7/8 (150), objektas_g 5/8 (300), objektas_a 7/11 (150 flat), objektas_h 1/11 · 5/11 — still a FAIL on h and a, which is the honest picture.
2. **One unseen raster sheet** (any contractor scan with a vector sibling, like j2/j3) run with the constants frozen as committed.
3. Only then: furnished-sheet handling (symbol cells excluded from the hatch fill when they are not bounded by a wall-thick outline), and an explicit door/window detector instead of geometry-only end caps. A trained segmenter is the step after that, and only if (2) shows the deterministic lane failing on *finding* rooms, not on the last 2 cm.

## Reproduce

```bash
# 0. worktree on togal-v2, branch spike/raster-rooms
# 1. spike venv (once)
python3 -m venv spikes/raster_rooms/.venv
spikes/raster_rooms/.venv/bin/pip install opencv-python-headless pypdfium2 numpy shapely pillow pymupdf

# 2. vector truth (PROJECT venv; reads ground_truth/ + fixtures from the main checkout, imports backend/ read-only)
for s in objektas_a objektas_h objektas_g; do
  /Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/sam2/dump_lane.py $s spikes/raster_rooms/out/lane_$s.json
done
/Users/ignasgaldikas/samatu-ai/venv/bin/python spikes/raster_rooms/dump_j2.py \
  /private/tmp/claude-501/-Users-ignasgaldikas-samatu-ai/17639f50-ffef-49b5-8063-bb81f19b2420/scratchpad/prod-pull/pdfs/5cdaa3a1-0fd8-4a03-9d26-f0464e9f060b.pdf \
  spikes/raster_rooms/out/lane_objektas_j2.json

# 3. SAM rows for the comparison columns (from the sam2 spike's out/, any checkout that ran it)
mkdir -p spikes/raster_rooms/out/sam && cp <sam2 checkout>/spikes/sam2/out/results_objektas_{a_raster,g,h}.json spikes/raster_rooms/out/sam/

# 4. raster runs (spike venv; ~15 s for all 7 inputs × 2 DPI) + tables
spikes/raster_rooms/.venv/bin/python spikes/raster_rooms/run_raster.py                 # overlays in out/<run>_<dpi>/
spikes/raster_rooms/.venv/bin/python spikes/raster_rooms/run_raster.py --no-overlays --min-wall-m 0.05 --tag _mw05
spikes/raster_rooms/.venv/bin/python spikes/raster_rooms/run_raster.py --no-overlays --min-wall-m 0.09 --tag _mw09
spikes/raster_rooms/.venv/bin/python spikes/raster_rooms/run_raster.py --no-overlays --door-needs-end --tag _doorend
# knob 6 cm: set KNOB_M = 0.06 in raster_rooms.py, run with --tag _knob06, set it back
python3 spikes/raster_rooms/summarize.py --rooms          # add --tag _mw05 etc.
```

Overlays (`spikes/raster_rooms/out/<run>_<dpi>/<nr>.png`, gitignored): red tint = raster room, magenta = vector reference outline, dark green = wall mask, green boxes = bridges, red dot = seat; `_walls_bridges.png` = the whole sheet's mask (black) with door bridges (green) and window bridges (orange). Fixture PDFs, the prod-pull PDFs and the lane dumps are read by absolute path and never copied into the repo; the furniture-off copies live in `out/_pdfs/` (gitignored).
