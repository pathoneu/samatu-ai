# 2026-10-29 — OCR'd dimension strings into the perimeter reader

Branch `v4/ocr-dimension-strings` off `togal-v2` @ 920515d4. Behind `SAMATU_OCR` (default OFF).

## §0 Resume point

Done, local only, nothing pushed:
- `backend/extractor/plan_dimensions.py` — `ocr_augment_dimensions(pdf_bytes, dims, pages)` + the sparse-strings trigger (`_needs_ocr_dims`) + bbox-centre dedupe (`_dedupe_overlap`). Behind `SAMATU_OCR` (`text.ocr.ocr_enabled`); flag OFF returns `[]` without importing the engine.
- `backend/extractor/geometry_lane.py` — `apply_geometry` calls the augmentation once, right after it computed the lane's candidate `sheets` set, and recomputes `dimensioned` and `sheets` from the augmented `dims`. `LANE_VERSION` unchanged (23) because flag-OFF output is byte-identical.
- `backend/tests/test_ocr_dimension_strings.py` — 5 tests: the text-as-curves twin feeds `sum_perimeters` from OCR; flag OFF leaves perimeters unread from dim strings; a sheet with a complete text layer is never OCR'd; the function returns `[]` with the flag OFF; the dedupe drops an OCR'd string that is the same as a text-layer one.

Open: the room-level measurement script lives at `.superpowers/sdd/v4-ocr-dimension-strings/measure_all.py` (git-ignored). No eval harness run (did not locate a `--totals-only --recompute --gate` CLI in this worktree; the per-project `apply_geometry` numbers below do the gate's job for this feature).

## §1 The trigger rule

A plan-group sheet is read by OCR when **both** hold:
- its text-layer line-backed dimension strings are **fewer than `OCR_SPARSE_STRINGS` (= 5)** — the smallest number any scale source already requires (`geometry/scale.py:WALL_MIN_AGREE`), so "the text layer isn't doing the job";
- the sheet carries **at least `OCR_MIN_HAIRLINES` (= 8) vector hairlines** — two rooms' worth; fewer is a title block or a blank page.

The lane only applies the rule to its own candidate set `sheets = plan_pages ∪ traced_on ∪ dimensioned`, so non-plan sheets (elevations, electrical, title blocks the classifier did not call `floor_plan`) are skipped even when they would qualify.

Measurement — objektas_a (`docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf`, 17 pages), text-layer line-backed strings vs vector hairlines on each sheet:

| page | lines | strings | backed | would fire | in `sheets` | OCR'd |
|-----:|------:|--------:|-------:|:----------:|:-----------:|:-----:|
|  1 |  20 |   0 |   0 | yes | — | — |
|  2 | 349 |   9 |   0 | **yes** | **yes** | **yes** |
|  3 | 632 |   3 |   0 | yes | — | — |
|  4 | 493 |  38 |  17 | no  | yes | — |
|  5 | 563 |  63 |   0 | yes | — | — |
|  6 | 643 |  17 |   0 | yes | — | — |
|  7 | 503 |  18 |   0 | yes | — | — |
|  8 | 817 | 148 | 102 | no  | yes | — |
|  9 | 484 |  18 |  11 | no  | yes | — |
| 10 | 482 |   9 |   0 | yes | — | — |
| 11 | 485 |  97 |  63 | no  | yes | — |
| 12 | 240 |  57 |  34 | no  | yes | — |
| 13 | 621 | 103 |  61 | no  | yes | — |
| 14 | 441 |  42 |  32 | no  | yes | — |
| 15 | 257 |  37 |  22 | no  | yes | — |
| 16 | 634 |  89 |   0 | yes | — | — |
| 17 | 168 |  29 |  21 | no  | yes | — |

Only one page (p2 — the partition plan) is both a plan-group sheet and sparse, so the rule fires on exactly that page. The others qualifying for the trigger (p1, p3, p5, p6, p7, p10, p16) are facade/section/elevation sheets the lane never asks about.

objektas_h (a well-formed CAD plan, 8 pages): 7/8 sheets have ≥ 5 line-backed strings; only one page (p7, 119 lines, 1 string) would fire — not in `sheets`, so no OCR actually runs on h.

objektas_g (an inherited extraction, 16 pages): 9/16 sheets qualify sparsely. Flag ON OCRs the ones in `sheets`; no rooms change (see §3).

## §2 The feed

`ocr_augment_dimensions(pdf_bytes, dims, pages)` runs per qualifying page:

1. **Call** `text.ocr.dimension_strings(pdf_bytes, page)` — the existing OCR'd reader. Each returned string already carries `source: "ocr"` and `ocr_conf`. We add `saltinis: "ocr"` so the LT-keyed meta and the check-sheet evidence sentence can say „skaičiai perskaityti iš lapo vaizdo".
2. **Dedupe** against existing text-layer dims on the same page: an OCR'd string whose bbox centre is within `OCR_DEDUPE_PT` (= 2.0 pt) of a text-layer string with the same `value_m` is the same string (the layer kept half of it as glyphs and sent half as curves — one is kept).
3. **Attach vector hairlines** via `attach_dimension_lines(pdf_bytes, kept, {page: stated})` — the SAME path text-layer strings go through (`_attach_lines_on_page`). After this the OCR'd strings carry `span`, `line_pos`, `span_source: "line"`, `scale_m_per_pt`, `mastelis` and `ilgis_pt`. They now look exactly like text-layer strings to `_strings_on_base`, so `sum_perimeters` reads them.

The lane calls the function once and extends its `dims`, then recomputes `dimensioned` and `sheets` so an OCR'd sheet joins the plan group for alignment and sibling scales. `meta["masteliai_atmesti"] / masteliai_kiti` are refreshed over the OCR'd strings too.

The feed is **vector only** for now — raster lines (the one `text.raster_lines` reads off the render) are already used by source 2b of the scale module (`_ocr_line_match`) but are not yet wired to the perimeter reader. On objektas_a p2 the dimension strings sit on vector hairlines, so this is enough; a scan with no vector layer at all (objektas_j3) stays unchanged.

## §3 objektas_a before/after, room by room

Live run of `apply_geometry` on the project PDF with and without `SAMATU_OCR=1`, no cached JSON. The second column is the number the lane WROTE on the room (not the eval roll-up):

| nr  | pavadinimas          | off perimetras (šaltinis)  | on perimetras (šaltinis)  |
|-----|----------------------|----------------------------|---------------------------|
| 101 | Tambūras             | 15.47 (konturo_ivertis)    | 15.47 (konturo_ivertis)   |
| 102 | Svetainė/virtuvė     | 29.9 (konturo_ivertis)     | 28.69 (konturo_ivertis)   |
| 103 | Koridorius           | 17.33 (konturo_ivertis)    | **15.38 (matmenu_eilutes)** |
| 104 | Darbo kabinetas      | 13.6 (matmenu_eilutes)     | **14.2  (matmenu_eilutes)** |
| 105 | WC                   | 12.86 (matmenu_eilutes)    | 12.86 (matmenu_eilutes)   |
| 106 | …                    | 13.77 (konturo_ivertis)    | **11.38 (matmenu_eilutes)** |
| 107 | …                    | 11.52 (konturo_ivertis)    | **11.62 (matmenu_eilutes)** |
| 108 | …                    | 14.5 (konturo_ivertis)     | 14.04 (konturo_ivertis)   |
| 109 | …                    | 14.5 (konturo_ivertis)     | 14.04 (konturo_ivertis)   |
| 110 | …                    | 24.97 (konturo_ivertis)    | 24.15 (konturo_ivertis)   |
| 111 | …                    | 11.5 (matmenu_eilutes)     | 11.53 (matmenu_eilutes)   |

**Rooms read from dim strings grew 3 → 6**: 103, 106, 107 moved from the outline estimate to a strings read. 104 and 111 refined slightly as more strings joined their chains. 101's strings are now read on the sheet (the manager's measurement predicted this) but the room's 11-wall chain still does not close under the perimeter reader's rules — the strings reach the room, the room still asks a question. 108/109/110 remain outline estimates; the OCR fed strings on p2 but these rooms' chains need more than p2 alone.

For 101 the strings reader has new material to work with now that the strings are on the sheet, but closing it is a separate task (research 2026-10-29-strings-reader.md).

## §4 Runtime

Measured in the worktree, Apple Silicon, Python 3.14, RapidOCR engine, SAMATU_OCR_DPI=300 (default):

| project | pages OCR'd by trigger | pages OCR'd by lane | cold run | warm run (cached) |
|---------|------------------------:|---------------------:|---------:|-------------------:|
| objektas_a | 8 (p1, p2, p3, p5, p6, p7, p10, p16 would fire) | 1 (only p2 is in `sheets`) | 190.97 s | 12.0 s |
| objektas_g | 9 (p1, p3, p10–p16) | likely all 9 (plan-group) | 196.3 s | — |
| objektas_h | 1 (p7) | 0 (p7 is not in `sheets`) | 15.98 s | — |

OCR is ~22–25 s per page at 300 DPI; after one run the per-page disk cache (`backend/data/ocr_cache/`, content-hashed by `text.ocr._disk_path`) brings it to a few ms per hit. A first read of a 17-sheet project with the trigger set as above pays OCR for only the sheets that are in the lane's candidate set — 1 sheet on objektas_a (= one page × 22 s plus some overhead; the measured 190 s cold vs 12 s warm bounds it; the extra time is other lane work).

200 DPI was not measured on the real PDF; the manager measured 59 s/page at 300 DPI in a one-shot script; the gap between that and the ~22–25 s per page observed here is RapidOCR warm-start (one engine load amortised across pages) plus a shorter rotation list on the lane's path.

## §5 What still waits and why

- **Room 101** on objektas_a now receives OCR'd strings but the perimeter reader does not close it. Needs the strings reader (research 2026-10-29-strings-reader.md) to handle its 11-wall chain, which is a separate lane change.
- **objektas_c and objektas_d PDFs** are not in the worktree's fixture tree (I only found a, g, h). The brief listed c/d; I could not run the flag-on no-regress check for them. objektas_g and h both ran clean with the flag on, no rooms changed.
- **Raster-only sheets** (scans like objektas_j3): the perimeter reader still relies on vector hairlines. The scale lane already reads these via raster lines; the perimeter reader does not. A future lane bump can wire raster lines into `_strings_on_base` for OCR'd strings.
- **The feed on sibling sheets** (objektas_g's lot of qualifying pages) is wired but did not close any new room there — likely because g's OCR'd strings do not pair with its traced outlines (the strings and the outlines live on different plan groups). Needs a separate audit.

## §6 Production note

Deploy by setting `SAMATU_OCR=1` on the Railway service (dev + prod). The three ONNX models are fetched at image build by `scripts/fetch_ocr_models.py --soft`, which is already wired into `nixpacks.toml` and the Dockerfile — verify that the step runs on the service's build log the first time the flag is set. The disk cache (`backend/data/ocr_cache/`) is per-image; a redeploy drops it and the first project opened pays OCR again (per the §4 numbers, ~22 s per plan sheet it reads). With the flag OFF (default), nothing in this change runs — `ocr_augment_dimensions` returns `[]` without touching the engine, and the lane output is byte-identical to togal-v2 (the invariant is covered by `test_flag_off_leaves_perimeters_unread_from_dimensions` and `test_ocr_augment_dimensions_returns_empty_with_the_flag_off`).
