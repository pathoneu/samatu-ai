# Precise room geometry from floor-plan PDFs — research + probe (2026-09-13)

Trigger: founder's review note on the room sheet — the room frame (Vision `bbox_pct`) is off
by a wall thickness or more; „prieš darydamas pakeitimus padaryk research… ir tada daryk verdiktą".

## Probe on objektas_g, 3rd run, page 2 (the pertvarų planas), 200 dpi, 1:50

Seeds = the plan's own area labels (text layer). Scale = the dimension lane's page scale.

| Variant | Result |
|---|---|
| Existing `auto_room_polygon` (adaptive threshold, 15–40 px door closing) on the raw page | 0/9 (one low-confidence fragment: 09 at −38 %). Interior dimension lines and furniture cut the rooms; grey wall fills vanish under adaptive thresholding. |
| Thin ink removed by morphological opening (5/7 px) | 0/9 |
| **Vector filter** (drop text objects and stroke-only paths < 1 pt) → walls-only render → grey = wall → **door gaps bridged along the wall direction (150 px = 0,95 m)** → **window gaps bridged in thick walls only (open 30 px, close 500 px)** → label-seeded fill | **7/9 within ±5 % of the label area**; 02 at +5,3 %; 07 (holas) leaks. |

Perimeters where the dimension lane also has an answer: 04 12,80 vs 12,68; 08 13,23 vs 13,13;
09 10,54 vs 10,49 (all < 1 %). New figures the drawing gives: 01 36,48 m (read 27,5), 02 18,25
(read 15,27), 03 7,92 (read 7,37), 05 8,65 (8,1), 06 12,40 (9,63). Extra guard that worked: „exactly
one area label inside the polygon". Sensitivity: door closing 120 px breaks most rooms (leaks),
190 px eats the WCs — the per-room sweep + area gate (already the engine's design) is the answer,
not one kernel.

Consequence: painted-wall total would rise ≈ +36 m² (≈ 302 m² vs 265,91), i.e. further ABOVE the
contractor's act (239,4). The drawing is the reference; what his 239,4 excludes is his to say.

## External state of practice (research agent, 2026-09-13, sources in the brief below)

- Nobody reaches 1–2 % room geometry from a learned model or a vision LLM; the systems that do
  read the wall vectors, or flood-fill a clean raster and snap the result to linework.
- Vector-first: PyMuPDF `get_drawings` (elevait production pipeline; clip paths the one hard
  pitfall); Esri ArcGIS Pro vector-PDF → units with min-width/min-area filters and a door
  identifier, manual inspection still required; ResPlan (2025) cleanup: snap colinear walls,
  delete slivers, seal door gaps. VectorFloorSeg (CVPR 2023) needs roughcast (walls-only) input.
- Raster fill: ICDAR 2011 baseline 79 % correct rooms; OGA-Net: any break in the boundary is a
  room-level failure; Bluebeam Dynamic Fill is interactive (edge sensitivity, add boundary).
  1 px bias at 150 dpi / 1:100 ≈ 2 % of a small room's area → snap to vector faces.
- Learned models: CubiCasa5K room mIoU 57,5 %, best 2024 IoU 0,76; Raster-to-Vector ~90 % on its
  own benchmark; FloorplanVLM IoU 0,89 on its own data with 1024-grid quantization. No CAD-export
  PDF evidence, GPU-bound.
- Vision LLMs: COCO detection AP GPT-4o 31,9 / Claude 3.5 Sonnet 14,8 vs specialist 80; on
  architectural drawings best VLM 77,9 % vs trained humans 89,2 %, weakest on walls/doors;
  Anthropic docs: coordinates are approximate, images downscaled to 1568 px (an A1 sheet → a
  wall is 2–5 px — exactly our „off by a wall thickness"). Grid overlays / set-of-marks help
  selection, not measurement.
- Commercial: Kreo Auto Measure 3.0 — outline accuracy 72 → 94 % after a snap-to-linework pass,
  99,3 % of area captured; Togal „98 %" self-reported; Procore 3-model fusion patent; STACK /
  ConstructConnect: user must verify; Bluebeam: no auto rooms; Beam AI: human QA service.

## Verdict

Build the **wall-outline lane** (deterministic, €0): vector walls → walls-only raster → gap
bridging → label-seeded fill → snap edges to vector wall faces + orthogonalize → validate
against the printed m² (≤ 2–3 %, one label inside) → the polygon becomes the room's frame on the
sheet and its perimeter where the dimension lane has none (the lane keeps priority when both
exist); rooms that fail stay „kontūro neradau" with a manual close. Do NOT: train CubiCasa /
YOLO / SAM, polygonize the whole vector layer, or ask the model for coordinates.
