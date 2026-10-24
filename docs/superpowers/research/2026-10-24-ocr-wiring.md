# OCR wired into the readers — scale, room badges, room table for sheets with no text layer

**Date:** 2026-10-24 · **Worker:** Opus 5.5 (manager: Fable 5.1) · **Branch:** `v4/ocr-wiring` (from `togal-v2` @ 187ef70b)
**Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §3.2, §9 Phase 1 cause 7; follows
`2026-10-24-text-ocr.md` (its §4 and §6 were the wiring notes) and `2026-10-24-geometry-scale.md`.
**Cost:** €0 — local OCR only. Codenames only; every test sheet is synthetic. Everything is behind `SAMATU_OCR` (default OFF).

> **Resume point:** DONE — code (75c9d9cf deps + models, 51aa0c7c wiring, 9a38d665 tests + box fix), cold runs (§1),
> four passes + full suite flag OFF (§5) all final; report committed, togal-v2 merged in. Not merged anywhere else.

## 0. What changed

| piece | what |
|---|---|
| `backend/requirements.txt` / `.lock` / `-dev.lock` | `rapidocr==3.10.0` + `onnxruntime==1.31.0` and their closure (colorlog, flatbuffers, omegaconf, protobuf, pyclipper, tqdm; `packaging` moved from the dev lock to the production lock, same version). Resolved with the existing pins as constraints: **no existing version moved**. Both locks dry-run clean on cp312 and cp314 manylinux, wheels only (67 / 74 packages). **Deviation from the brief:** the brief named `rapidocr-onnxruntime`; that is the legacy 1.x package, which has neither PP-OCRv6 nor the `lt` recogniser that `text/ocr.py` uses and was measured with. `rapidocr` 3.x is the same project's current package (onnxruntime is its engine). |
| `scripts/fetch_ocr_models.py` (new) | downloads the 3 ONNX models (PP-OCRv6 medium det, PP-OCRv6 medium rec with `lt`, the direction classifier; ~140 MB) into `backend/data/models/ocr/` (gitignored), names/URLs/SHA-256 from RapidOCR's own model table (`text.ocr.model_files()`), 3 attempts per file, keeps a present file whose hash matches. `--soft` = warn and exit 0. |
| `backend/Dockerfile`, `nixpacks.toml`, `.dockerignore` | build step `python scripts/fetch_ocr_models.py --soft` (both builds: Docker for Render/dev, nixpacks for Railway). `backend/data/models` and `backend/data/ocr_cache` kept out of the Docker context. **Manager decision needed:** `--soft` means a model-host outage at build does not fail the deploy (OCR then reports itself unavailable on first use) — the flag is off, so failing the deploy for it seemed wrong; drop `--soft` if you want the build strict. |
| `backend/text/ocr.py` | `RapidEngine` loads from `model_dir()` (`SAMATU_OCR_MODEL_DIR`, default `backend/data/models/ocr`); files missing → **production (`ENV=prod/production`) refuses** (`OcrUnavailable`, „run scripts/fetch_ocr_models.py"); elsewhere RapidOCR downloads into that same dir. **Disk cache** (§4). **Word boxes cut to their ink** (§2.3). `dimension_strings(..., units="mm"|"cm")`, drops strings starting with 0 (the upside-down misread). `detail_scales()` (1:5 / 1:10 written on a sheet). |
| `backend/text/raster_lines.py` (new) | dimension lines read off the RENDER next to each OCR'd string (§2.1) — the only lines a scan has; same shape as `plan_dimensions._page_lines_pdfium`. Cached on disk with the OCR. |
| `backend/geometry/scale.py` | source **2b** `_ocr_line_match` (§2): OCR'd strings matched to vector + raster lines; mm/cm readings; the contradicted-written-scale rule. `measured_scale` = user → lines → **OCR lines** → walls. |
| `backend/extractor/plan_dimensions.py` | `_value_cm` + `_dimensions_on_page(..., units="cm")` — only when a caller asks; default unchanged. |
| `backend/extractor/room_locator.py` | reads `text.layer.page_items` (flag off = `_iter_pages`, call for call). |
| `backend/extractor/pdfplumber_eksplikacija.py` | `_unit_tables_on_page` split into `_unit_tables_from_words`; `_ocr_room_table` when the text layer gave no table and the flag is on (§2.4). |
| tests | `tests/test_ocr_wiring.py` (20, new) + `test_text_ocr.py` (cache isolated, two call-count asserts now count both readings). |
| `LANE_VERSION` | unchanged (15): with the flag off the lane's output cannot change; with it on, stored projects are not re-read automatically. |

## 1. Results per sheet (cold runner from this branch, `scripts/cold_run/run_cold.py` unedited, `SAMATU_OCR` unset vs `=1`)

| sheet | scale before → after | badges located (of table) | room table | outlines |
|---|---|---|---|---|
| **objektas_c** p1 | — (blank) → **1:59,9** `dimension_lines` MEDIUM — „10 matmenų eilutės ant matmenų linijų …; skaičiai perskaityti iš lapo vaizdo; užrašytas mastelis neatitinka matmenų (≈ 1:60)" | c has no badges | c has none | 0 (no badges; walls are strokes) |
| objektas_c p2 | — → **1:59,9** `sibling` from p1 (walls coincide, k = 1); note „užrašytas M 1:50 … 1 lapo matmenys atitinka 1:60" | | | |
| objektas_c p3 | — → **1:60,0** `dimension_lines` MEDIUM, 13 strings, same mismatch mark | | | |
| **objektas_j4** p1 | — → **1:87,2** `dimension_lines` MEDIUM, 28 strings agree, „matmenys centimetrais" | 0 → **9 / 9** | none on the sheet | 0 → **5** (102 5,47 · 105 4,75 · 106 2,92 · 107 11,42 · 108 5,56 m²) |
| **objektas_j3** p1 (scan) | — → **1:64,2** `dimension_lines` **LOW**, 10 strings; „užrašytas mastelis neatitinka matmenų (≈ 1:64)", pastaba says check with a line | 0 → **8 / 9** (room 1's badge is not read by OCR) | 0 → **9 rooms with areas** (sum 96,54 vs its own „Bendras plotas 96.53") | 0 — raster, no vector walls (raster track parked) |
| objektas_j1 p1 | 1:100 stated HIGH → identical | 18 / 18 → identical | — | 15 → identical (text layer: OCR never runs) |

Before = the same branch with the flag off (= togal-v2 behaviour; the flag-off identity is shown by the passes, §5).

**Is 1:87 right for j4?** j4 and j1 are the same house (rooms 102, 105–108 have the same numbers and areas). j4's five
outlines at 1:87,2 against j1's outlines at its confirmed 1:100: 102 5,47 / 5,47, 105 4,75 / 4,75, 106 2,92 / 2,93,
107 11,42 / 11,43, 108 5,56 / 5,57 m² — **within 0,4 %**. (Production's stored j4 table says 4,47 and 11,04 for 105 /
107 — its own model reads, not the drawing.) The vector hairlines alone measure 1:84,6 (they overshoot the ticks); the
raster lines, cut at the ticks, measure 1:87,2 — the one the areas confirm.

**Is 1:60 right for c?** The earlier worker measured 1:58,7–1:59,8 by hand on three vector lines; here 10 / 13 strings
per sheet agree at 1:59,9 / 1:60,0, and the two sheets measure independently. c is printed ≈ 83 % (written 1:50).

**j3 ≈ 1:64:** expected from its vector twin j2 (1:44,9 on A3) printed on A4: 44,9 × 1191 / 839 = 1:63,7 — 0,8 % off.
Its numbers are the contractor's tape readings; they scatter ±4 %, so no peak has twice its rival: the scale stands
only because the written 1:40 is contradicted (§2.2) and is marked LOW with „patikrinkite mastelį".

## 2. The rules

### 2.1 Lines under OCR'd strings (`text/raster_lines.py`)
For each string: rows within 14 pt across (`LINE_NEAR_PT`) whose ink passes under the string's middle; the run is
followed both ways (gaps ≤ 0,6 pt allowed); ≤ 2,5 pt thick (thicker = wall); cut at the nearest **mark of the line's
own colour** (RGB distance ≤ 45) outside the string — a narrow mark at its middle (a tick), a wide one (> 2 pt) at its
near face (a wall); else where the ink stops (light grey wall fills are not ink, darkest channel ≥ 150). Colour matters
on j3: dark-red reference lines cross every blue dimension line (first try without colour: „3290" cut to 121,8 pt,
ratio 1:76,6; with it 142,1 pt, 1:65,7).

### 2.2 The scale (`geometry/scale.py` source 2b, after source 2, before source 3)
Every (string, candidate line) pair proposes value / length (vector hairlines, raster lines, and their union are tried
separately). The densest proposal (`_peak`, ±1 %) is accepted — **strong** — by source 3's own rules: ≥ 5 strings
(`WALL_MIN_AGREE`), ≥ 4 values, ≥ 2× the best rival ≥ 4 % away; a scale no drawing is made at needs ≥ 10 strings and
3× the rival. `plan_dimensions`' 40 %-of-strings rule is not used: OCR returns every room number and furniture size too.
- **mm first; cm** only when no millimetre peak is a plan scale with ≥ 5 strings (j4 as mm: 1:8,5) and the sheet writes
  no detail scale (1:5, 1:10 — a 1:10 detail in mm looks exactly like 1:100 in cm). Provenance „matmenys centimetrais".
  **Deviation:** the brief said „the ×10 reading fits a standard scale"; j4's real scale (1:87, a reduced print) fits
  none, so the test is „mm gives no plan scale (1:20–1:500), cm does, with the strong rule". 
- **Written scale:** within 2 % → the written one exactly („sutampa su užrašytu"); 2–5 % → measured, with a note;
  **> 5 % → „užrašytas mastelis neatitinka matmenų (≈ 1:N)"** and the measurement wins.
- **Contradiction rule (weak, LOW):** when exactly one scale is written and no strong peak exists, the densest peak is
  taken if it has ≥ 5 strings / ≥ 4 values, more strings than any rival, is > 5 % off the written scale, and has ≥ 2×
  as many strings as propose the written one. **Deviation:** the brief said „≥ 3 measured strings"; with raster lines
  c has 10–13 strings anyway, and **3–4 agreeing strings were chance on c p2** (its furniture/electrical numbers gave a
  peak of 1:42,8 with 4 strings, rival 3) — at ≥ 3 c p2 would have got a wrong 1:43. c p2 now borrows p1's 1:60.
- Confidence: strong MEDIUM, weak LOW; provenance always has „skaičiai perskaityti iš lapo vaizdo".

### 2.3 OCR boxes cut to their ink (`text/ocr.py::_tighten`)
Measured on the renders: the ink inside a PP-OCR box is only **0,59 (j3) / 0,64 (j4) / 0,66 (c)** of its height
(median; ~1,9 pt padding above, 1,2–1,7 pt below). Every text-layer rule is tuned in points on tight boxes — so instead of
re-tuning room_locator for OCR, each word is cut to the ink it covers; a row/column inked across the box that continues
outside it on both sides is a line through the padding, not the word. After: tight / box **0,95–1,00**. Effect: j3 room
6's badge was rejected as „touching" the dimension „4250" 9,9 pt away (padded boxes) → found; j4's dimension-height
median 10,8 → 6,7 pt, badge cap 14 → 13,4 pt (the 2× rule from the lane fixes, unchanged); j4 cm support 18 → 28 strings.
The first version also cut columns inked across the box, which clipped the stroke of a „1" in tight boxes and made j4's
„102" a table-column cell (8/9) — fixed (9/9).

### 2.4 Badges and the room table
- `room_locator` takes `text.layer.page_items`: OCR only for a requested plan page whose text layer has < 8 characters.
- Room table: only when the text layer gave no table; OCR of the sheets with < 8 layer characters (≤ 12 sheets). Rows by
  the stacked-unit reader (heading „…EKSPLIKACIJA", number column, first area), OCR mode: lines by their middles
  (capital and lower-case ink boxes differ in top), only words on the table's side of the sheet (the drawing beside it
  writes numbers at the same heights), the number column searched as far left of the heading as the heading is wide
  (j3's heading is centred over a wide table), column headings count for the gap rule, a sum line without its unit
  („Bendras plotas 96.53") — rows that do not add up to it within 0,05 m² refuse the table. Single characters of any
  reading angle count (OCR called j3's row „3" vertical). Decimal comma or point; trailing „," dropped; **Ú → Ų at a
  word's end, Ū inside** (PATALPÚ → PATALPŲ). Rooms carry `_row_source: ocr_table`, `plotas_m2_raw`, `_is_vaizdo`;
  `_meta.ocr_table.pastaba` „lentelė perskaityta iš lapo vaizdo — patikrinkite plotus".

## 3. Timing and the cache
- First OCR per sheet (300 DPI, 0°+90°, M4 Pro CPU, other workers running): j4 10,6–16 s, j3 12–19 s, c 24–44 s.
- Disk cache `backend/data/ocr_cache/<sha1[:2]>/<sha1[:16]>-p<page>-<key>.json`, key = PDF content hash + page + DPI +
  engine/library/model versions + rotations + format (3); raster lines beside it. **Cached read: 1–3 ms per sheet.**
  The content hash is the drawing itself: a re-upload of the same PDF reuses it, any changed PDF never does (stronger
  than a project id). Only the built-in engines are cached on disk.
- With a warm cache the cold runner's totals: j3 0,28 → 0,47 s, j4 1,2 → 1,9 s (lane 0,05 → 0,77 s: it now outlines),
  c 9,0 → 8,8 s, j1 9,8 → 9,6 s (noise).

## 4. Not done / open
- j3 room 1: its badge is not in the OCR output (missed by the engine, as in the OCR report) — 8 / 9.
- j3 and all raster sheets: no outlines (no vector walls; the raster track is parked by the founder).
- c: no outlines — c has no room badges and its plan text is outlines; the scale is now there for the person's tools.
- The lane asks only plan/anchor sheets, so c p2's scale appears only when asked (`GET …/geometry/scale?page=2`).
- `scan_text_layer` (m² labels inside rooms) does not use OCR — j4's cold variant still has no rooms (no table, no
  text-layer labels); its seeded variant shows the outlines.

## 5. Flag OFF: passes and suite (on 9a38d665, dead API key, `SAMATU_OCR` unset)

| pass | expected (togal-v2) | v4/ocr-wiring |
|---|---|---|
| totals plain — billed lines MAE | 22,60 % · GATE OK | **22,60 %** · GATE OK |
| rows plain — ±10 % / €±10 | 26,1 % / 34,7 % | **26,1 % / 34,7 %** · GATE OK |
| totals replay — billed lines MAE | 22,84 %, 6 known false-FAIL lines + 3 objektas_b lines | **22,84 %**, the same 9 lines (a Dažymas; b ×3; g MAE, Plytelės; h MAE, kampai, Rotband) |
| rows replay — ±10 % / €±10 | 27,9 % / 39,6 % | **27,9 % / 39,6 %** · GATE OK |

(€ column needs the gitignored priced parses, copied from the main checkout for the rows passes.)
Full backend suite, `SAMATU_AUTH_DISABLED=1`: **5530 passed, 57 skipped, 0 failed** (8 min 25 s); includes the real-engine
OCR test, which now runs in the project venv (rapidocr installed there from the lock pins).

## 6. Reproduce
Scratch (outside the repo, `scratchpad/ocrw/`): `warm.py` (OCR + cache timing), `scale_on.py`, `locate.py`,
`badgedbg.py`, `pad.py` (box padding), `peak2.py` / `perstr.py` (per-string ratios by line source), `cold.sh` + `cmp.py`
(cold runner off/on), `passes.sh`.
