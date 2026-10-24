# Phase 0 (a) baseline — frozen numbers before the v4 pipeline changes

**Date:** 2026-10-24 · **Worker:** Opus 5.5 (manager review: Fable 5.1) · **Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §4 Phase 0 (a), groundwork for Phase 2.
**Zero API spend.** Every number below comes from cached extracts + fixture PDFs, run through the live engine with the Anthropic key replaced by a dead one and the client constructor patched to raise (`scripts/method_reconstruction/common.py`). No call was attempted.
**Codenames only.** The two truth folders not named `objektas_*` are `objektas_r1` and `objektas_r2` (sorted folder order). Quantities only — no prices anywhere in this file.

## 0. What was measured, on what

- **Code measured:** `togal-v2` @ **`d63cc06a`** (the main checkout's `HEAD` is `refs/heads/togal-v2`; `diff -rq` of `backend/extractor`, `backend/api` and `eval_harness.py` between the main checkout and a clean `togal-v2` worktree is empty — no uncommitted code was measured). `d63cc06a` only adds the plan doc on top of the code commit before it.
- **Commands** (run from `/Users/ignasgaldikas/samatu-ai`, `ANTHROPIC_API_KEY` set to a dead value):
  ```
  venv/bin/python eval_harness.py --rows --recompute --detailed
  venv/bin/python eval_harness.py --rows --recompute --replay-geometry --detailed
  METHOD_OUT=<scratch> venv/bin/python <worktree>/scripts/method_reconstruction/run_engine.py \
        --modes plain,replay --variants today,open05,open30,open_inf
  METHOD_OUT=<scratch> venv/bin/python <worktree>/scripts/method_reconstruction/outline_errors.py
  METHOD_OUT=<scratch> venv/bin/python <worktree>/scripts/method_reconstruction/scale_check.py objektas_a   # also _h, _g
  METHOD_OUT=<scratch> venv/bin/python <worktree>/scripts/method_reconstruction/analyze.py --mode replay
  ```
  `run_engine.py` reproduces the harness numbers exactly (same `_rerun_deterministic_tail` + `_score_rows_of`); it only adds the dumps the analysis needs. No GATE line was printed (no `--gate` was passed).
- **Wall time:** plain rows pass 1 min 53 s, replay pass 2 min 49 s; all eight engine variants ≈ 25 min.

## 1. Baseline table (eight projects)

"his rows" = his priced lines without subtotal lines (scored = lines that carry a quantity). "±10 %" = share of his scored rows our engine reproduces within ±10 % (`row_scorecard`). Outline columns = the **vector lane alone** (`outline_errors.py`: every earlier lane taken back with `eval_harness._undo_lane_state`, then `geometry_lane.apply_geometry` from scratch; LANE_VERSION 13), area of the outline vs the designer's area (room table, or for objektas_g the area labels on the plan), perimeter of the outline vs the perimeter added from the plan's dimension strings (`perimetras_saltinis = matmenu_eilutes`).

| project | his rows (scored) | ±10 % plain | ±10 % replay-geometry | rooms / with designer area | outlined (with area) / designer-area rooms w/o outline | area \|err\| median / p90 | perimeter pairs: \|err\| median / p90 |
|---|---|---|---|---|---|---|---|
| objektas_a | 53 (53) | 37,7 % | 43,4 % | 11 / 11 | 11 (11) / 0 | **8,51 % / 17,98 %** (all 11 under the table but 106) | 0 pairs (no string sums attach) |
| objektas_b | 113 (111) | 9,9 % | 9,9 % | 15 / 15 | 0 / 15 | — | — |
| objektas_c | 37 (36) | 22,2 % | 22,2 % | 6 / 0 (no table; 2 rooms are default guesses) | 0 / — | — | — |
| objektas_d | 50 (50) | 36,0 % | 36,0 % | 4 / 4 | 0 / 4 | — | — |
| objektas_g | 20 (20) | 30,0 % | 35,0 % | 9 / 8 (plan labels) | 6 (6) / 2 | 3,08 % / 5,71 % (all over, +1,9…+6,4 %) | 4 pairs: 0,94 % / 1,10 % |
| objektas_h | 35 (24) | 20,8 % | 20,8 % | 11 / 11 | 11 (11) / 0 — 4 of them in two open spaces divided by the lane | 3,78 % / 11,34 % (9 of 11 under) | 6 pairs: 0,16 % / 0,22 % |
| objektas_r1 | 15 (15) | 6,7 % | 6,7 % | 20 / 20 | 0 / 20 | — | — |
| objektas_r2 | 29 | — no extract | — no extract | no floor plan in the bundle | — | — | — |

Corpus mean as the harness prints it (six projects; r1 excluded as scope mismatch, r2 has no extract): **26,1 % plain, 27,9 % replay-geometry**. The plan's "≈ 26 %" is confirmed. Note the harness's holdout banner: nothing is held out — every number above is in-sample.

Open spaces (objektas_h): 01+03 outline 14,04 m² vs table 14,60 (−3,8 %); 04+05 outline 60,55 vs 61,81 (−2,0 %).

**Why the vector lane outlines nothing on four projects** (a one-off diagnostic over `geometry_dimension_strings` and the extracts' page classification; recorded here because it decides where G1 can even be measured):
- objektas_b: 1 202 dimension strings, sheets at 1:100 / 1:50 — scale exists — but the rooms are located only by the model's boxes (`vietos: bbox 15`) and the walls never close around any of them ("sienos neuždaro patalpos").
- objektas_c: 4 dimension strings, none line-backed → no scale on any sheet.
- objektas_d: rooms on sheet 2, the only line-backed strings on sheet 1 (1:40); the lane traces no sheet.
- objektas_r1: 270 strings, none line-backed → no scale.

So the G1 gate ("per-room area vs table ≤ 1 % median on all eight projects where a table exists") is today measurable on **three** projects (a, g, h), and failing on all three.

### 1.1 objektas_a: is the −8,5 % the sheet scale or the table? (manager's added check)

`scale_check.py objektas_a`:
- **Sheet 2 has no line-backed dimension strings of its own** (9 strings, 0 on a dimension line) and writes no scale ("M 1:xx" absent from its text). Its scale 0,029101 m/pt (1:82,5 — an odd ratio; most likely a reduced print, no written scale to compare against) is **borrowed from sheets 4, 8, 9**, laid over sheet 2 at identity (k = 1,0, no offset); those sheets carry 130 line-backed strings and their own lane scales agree with each other (0,029101 / 0,029226 / 0,029155 — within 0,4 %).
- **Outline edges vs the strings that run along them:** only 8 edges match a string end-to-end (≤ 0,30 m at both ends): signed median **+2,3 %** (outline edges slightly *longer*), |median| 5,7 %. A scale short enough to explain −8,5 % area would make edges ≈ −4,3 % short. The sign is the opposite; the sample is small and noisy.
- **Box sides vs the nearest written string** (sides with a string within 5 %): as traced 14 sides, median +0,8 %; scaled up to the table area 12 sides, median +0,5 %. The strings are dense (109 distinct values) — this test does not discriminate; I report it only so nobody reads it as evidence either way.
- **The table is internally consistent:** room areas sum to 165,64 m² against the stated total 165,61 (0,02 %).
- **The gap is not a uniform boundary offset:** (table − outline) / outline perimeter runs from 0,04 m (107) to 0,18 m (102), and room 106 is *over* the table (+7,5 %). A finishing layer or a half-wall convention would give a near-constant offset.
- Contrast: on objektas_h 39 outline edges match strings with signed median **+0,1 %** (|0,12 %|), yet areas are still −3,8 % median under the table; on objektas_g 23 edges +0,8 %, areas +3,1 %. There too the walls match the strings and the area does not match the table.

**Verdict:** the evidence points away from the scale (edges are not short; the borrowed scale is consistent across three sheets) and toward the table measuring something other than the room the lane traces — on objektas_a by a varying amount per room (consistent with a table that belongs to an earlier layout than sheet 2's partitions, or that measures to other faces; I could not verify which). It is not proven: sheet 2's own strings are not line-backed, and only 8 edges could be checked. **Consequence for the gates:** a "within 2 % of the table" area gate on objektas_a (and arguably on h and g, where the table differs by ±3 % while walls match strings to 0,1–0,8 %) would measure the designer's table convention, not the lane. The honest G1 metric is **outline edges / perimeters vs the dimension strings** (h 0,1 %, g 0,8 %), with table area as a secondary, convention-dependent check.

## 2. Phase 2 inventory — his families vs ours

Every row (his and ours) goes into one family by the ordered regex list in `analyze.py` (`FAMILIES`); our rows in the „Medžiagos" section are one family of their own. Ours = replay-geometry engine, committed constants. Units normalised (b/m → m, kompl → vnt); "be kiekio" = row present, no quantity.

| family | a | b | c | d | g | h | r1 | r2 |
|---|---|---|---|---|---|---|---|---|
| dažymas sienos+lubos (his one row) vs ours walls + ceilings | 584,81 / 602,75 | 493,03 / 592,23 | 388,01 / 312,27 | 150,57 / 136,28 | walls only 239,40 / 220,00 | 412,88 / 463,27 | 420,08 / 992,33 (scope) | 461,31 / — |
| rotband m² | 138,69 / 131,14 | 138,69 / 123,67 | 37,00 / 65,78 | 32,41 / 28,50 | — / 84,53 | 168,83 / 89,44 | 95,00 / 228,17 | 132,36 / — |
| dažymo kampai m | 493,35 / 463,19 | 580,54 / 468,70 | 201,86 / 266,89 | 123,59 / 131,87 | 134,72 / 317,33 | 412,94 / 473,12 | 329,77 / 852,14 | 303,25 / — |
| GKP lubos m² | 165,60 / 154,97 | 143,19 / 180,00 | 111,84 / 93,00 | 41,28 / 41,28 | — / 76,48 | 137,71 / 136,37 | — / 231,77 | — |
| GKP / LED nišų formavimas m | 42,30 / 41,88 | 54,98 / 26,61 | 16,84 / 15,50 | 10,58 / 5,64 | — / 6,20 | 44,99 (2 rows) / 27,70 | — / be kiekio | — |
| LED nišų glaistymas-dažymas m | 42,30 / 41,88 | 54,98 / 26,61 | 16,84 / 15,50 | 10,68 / 5,64 | — / 6,20 | 33,19 / 27,70 | 34,54 / — | — |
| angokraščiai m | 178,78 (2 rows) / 180,20 (2) | 94,02 / 198,06 (2) | 34,53 / 74,40 (2) | 31,80 / 59,54 (2) | — / 97,48 (2) | 63,23 / 153,82 (2) | 23,80 / 159,76 (2) | 85,45 / — |
| durų angos beapvadinėms / staktos m | 39,20 / 48,13 | 55,52 / 70,60 | — / — | 20,44 (2) / 10,22 | — / 5,70 | 40,94 / 41,47 | 28,92 (2) / 34,90 | 33,97 / — |
| plytelės sienų+grindų (his one row) m² | 55,62 | 209,93 (2) | 55,27 | 32,97 | — | be kiekio | — | 101,57 |
| plytelės sienų m² (ours) | his 28,80 / 69,14 | — / 131,04 | — / 62,70 | — / 21,27 | 46,06 / 64,76 | — / 43,05 | — / 246,93 | — |
| plytelės grindų m² (ours) | his 16,99 / 42,56 | — / 75,12 | — / 27,75 | — / 27,02 | 21,50 / 28,21 | — / 42,43 | — / 86,87 | — |
| plytelės kita (didžiaformatės, mozaika, apsiuvimas) | 4,48 m² / — | 7,52 m², 26,77 m / — | — | — | 1 vnt / — | be kiekio / — | — | — |
| plytelių angokraščiai / nišos | 8,70 m² / — | 34,49 m + 10,49 m² / — | — | — | — | — | — | 25,74 m / — |
| plytelių fugavimas m² | — / 111,70 | — / 206,16 | 37,11 (epoksidas) / 90,45 | — / 48,29 | 67,56 („siūlių glaistas + silikonas") / 92,97 | — / 85,48 | — / 333,80 | — |
| silikonavimas m | 50,14 / 85,33 | 128,97 / 79,12 | 38,15 / 59,22 | 25,36 / 18,86 | — / 68,58 | be kiekio / 40,94 | — / 60,72 | 60,54 / — |
| plytelių 45° pjovimas m | 9,70 / 11,20 | 45,72 / 16,80 | 18,60 / 10,30 | 5,91 / 4,78 | 12,08 / 14,40 | be kiekio / 10,00 | — / 16,96 | 32,52 / — |
| skylės plytelėse vnt | 56 / 40 | 109 / 80 | 21 / 12 | 17 / 21 | 32 / 59 | be kiekio / 48 | — / 61 | 49 / — |
| hidroizoliacija | 2 vnt / 2 vnt | 3 vnt / 3 vnt | 2 vnt / 2 vnt | 1 vnt / 1 vnt | **39,50 m²** / 3 vnt | be kiekio vnt / 2 vnt | — / 3 vnt | 2 vnt / — |
| dušo įrengimas (nuolydis, lentynėlės, latakai, trapai) vnt | 9 / 8 | 4 / 8 | 1 / 8 | 2 / 4 | 6 / 8 | be kiekio / 8 | — / 12 | 5 / — |
| grindjuostės medinės / PVC m | — / 56,00 | 93,80 (2: įleistos 63,0 + paprastos 30,8) / 138,56 | — / 64,96 | 23,07 / 19,86 | — / 53,69 | — / 91,90 | — / 213,35 | — |
| grindjuostės plytelių m | 22,72 / 42,43 | — / 39,44 | — | — / 20,52 | 26,87 / 24,97 | — / 29,37 | — / 70,18 | 8,33 / — |
| grindų danga m² | — / 135,00 | 118,88 (parketas 108,08 + guma garaže 10,80) / 148,88 | 98,00 / 65,25 | 36,99 / 14,26 | — / 76,65 | — / 100,84 | — / 180,84 | — |
| išlyginamasis m² | — / 154,97 | 182,62 (2) / 180,00 | — / 93,00 | — / 41,28 | 2 vnt / 100,93 | — / 143,27 | — / 231,77 | — |
| priglaistomi elementai (šviestuvai, difūzoriai, profiliai, durelės) | 112 vnt + 40,12 m / 70 vnt + m be kiekio | 192 vnt / 132 vnt | 1 / 56 | 32 vnt + 13,70 m / 34 vnt | — / 68 | 56 vnt + 31,26 m / 69 vnt | 37 vnt + 5,50 m / 124 vnt | 12 vnt / — |
| GKP kita (pertvaros, dėžutės, apsiuvimai) | 20,27 m, 15,88 m², 3 vnt / m² be kiekio, 2 vnt (+ 232 m GKP siūlių) | 26,57 m/m², 4 vnt / 3 vnt | 2 vnt / 2 vnt | 9,94 m, 11,14 m², 20 vnt / 1 vnt | 2 vnt / 2 vnt | 44,94 m, 19,35 m², 2 vnt / 2 vnt | 1 vnt / 3 vnt | 19 m, 1 vnt / — |
| santechnikos taškai vnt | 32 (15 rows) / 22 (15) | 39 (19) / 33 (15) | 7 (6) / 19 (13) | 9 (9) / 13 (17) | 3 (2) / 26 (17) | 6 (3) / 23 (17) | — / 32 (17) | — |
| elektros taškai | — / 105 vnt + 42 m | 1 vnt / 166 vnt + 48 m | 134 vnt + 16,7 m / 91 vnt + 22 m | 52 vnt + 268,53 m / 26 vnt + 12 m | — / 87 vnt | — / 110 vnt | — / 174 vnt | — |
| vėdinimas / kondicionavimas | — / be kiekio | 140 vnt + 102,5 m (36 rows) / 87 vnt + 170 m | 4 vnt / be kiekio | 3 vnt / 26 vnt + 51 m | — / 35 vnt + 68 m | — / 39 vnt + 76,5 m | — / 35 vnt + 68 m | 1 vnt / — |
| statybvietė | 12 m³ / 12,4 m³ … | 12 m³, 90 d.d. / 13,5 m³, 4 d.d. | 10 m³, 25 d.d. / 6,9 m³ | 8 m³ / 3,1 m³ | — / 7,6 m³ | be kiekio / 10,7 m³ | — / 20,1 m³ | 25 d.d., 1 vnt / — |
| glaistymas atskirai | — | — | 5 m (durų anga į rūbinę) / — | — | — | — | — | **395,19 m² „Papildomas sienų glaistymas"** / — |
| tapetai / stiklo audinys m² | — | — | — | — | — | — | 134,79 / — | — |
| demontavimas | — | 1 vnt / — | — | — | — | — | — | — |
| gruntas | never written by him | | | | | | | |
| kita (one-off lines) | 1 vnt | molio tinkas 160 m², 6 vnt | palangės 4,94 m, 2 vnt | 1 vnt | 1 vnt | langų rėmų sandarinimas 74,95 m + grindų betonavimas prie langų 11,72 m, 1 vnt | moldingų dažymas 27,1 m, durų varčia 1 vnt | 25,88 m, 7 vnt |

**Families he writes that we never emit (as a row with a quantity):**
1. *Granularity only — we have the quantity, split differently:* dažymas sienos+lubos as ONE row (a b c d h r1 r2: he writes walls+ceilings together on every project except g, which bills walls only); plytelės sienų+grindų as ONE row (a b c d h r2; only g splits walls / floors).
2. *Real gaps:* plytelių angokraščiai / nišos (a, b, r2); plytelės kita — didžiaformatės, mozaika, vonios apsiuvimas (a, b, g, h); papildomas / atskiras glaistymas (r2 395,19 m², c); stiklo audinys / tapetai (r1); demontavimas (b); and the one-off „kita" lines (molio tinkas 160 m² b, langų rėmų sandarinimas h, palangės c, moldingai r1, …).
3. *We emit the row but blank* („suveskite patys"): TRACK / magnetiniai profiliai m (a, h), GKP pertvarų / storinimo m² (a, d, h), GKP dėžutės m (a, d).

**Families we emit that he never writes:** every material quantity („Medžiagos": kg, l, m, m², vnt — 30–60 rows per project); „Grindjuosčių dažymas" (a 56, b 138,56, c 64,96 … m). Families we emit on every project but he writes only on some: grindjuostės medinės (he: b, d), grindų danga (b, c, d), išlyginamasis (b; g as 2 vnt), plytelių fugavimas (c, g), elektros taškai (c, d), vėdinimas (b, c, d, r2). He never writes gruntas or glaistymas by Q-level as rows; neither do we as work rows (gruntas / glaistas appear only in our „Medžiagos").

## 3. Hypotheses (i)–(iv)

### (i) Openings ≤ 3,0 m² not deducted vs today's threshold

First, a correction to the plan's §1: the engine's default is **not** the NRM2 0,5 m² rule. `paint_deduction_standard` defaults to `"LT"`, which deducts every opening ≥ `openings_threshold_m2` = **1,0 m²**, doors net of their jambs (`_door_net_deduction_m2`), windows only in the legacy (no-apdailos) branch. The NRM2 0,5 m² path is reachable only if a user picks NRM2. I ran four in-process variants of `openings_threshold_m2`: 0,5 / 1,0 (today) / 3,0 / ∞.

- **0,5 ≡ 1,0 on every project, both modes** — no drawn door or window in the corpus is between 0,5 and 1,0 m². The NRM2-vs-LT distinction is moot on this data.
- Paint m² (his combined row vs our walls + ceilings), replay-geometry mode:

| project | his | today (1,0) | 3,0 | ∞ (nothing deducted) | m² at stake 1,0 → 3,0 |
|---|---|---|---|---|---|
| objektas_a | 584,81 | 602,75 (+3,1 %) | 621,47 (+6,3 %) | 636,24 (+8,8 %) | 18,7 |
| objektas_b | 493,03 | 592,23 (+20,1 %) | 610,79 (+23,9 %) | 662,83 (+34,4 %) | 18,6 |
| objektas_c | 388,01 | 312,27 (−19,5 %) | 330,32 (−14,9 %) | 330,32 | 18,1 |
| objektas_d | 150,57 | 136,28 (−9,5 %) | 143,46 (−4,7 %) | 158,49 (+5,3 %) | 7,2 |
| objektas_g (walls only) | 239,40 | 220,00 (−8,1 %) | 220,00 | 220,00 | 0 — walls anchored to the designer's legend figure |
| objektas_h | 412,88 | 463,27 (+12,2 %) | 463,27 | 463,27 | 0 — walls anchored to the designer's legend (320) |
| objektas_r1 | 420,08 | 992,33 | 1 008,24 | 1 040,51 | scope mismatch — ignore |

  Plain mode, objektas_a: 574,59 (−1,7 %) today, 590,20 (+0,9 %) at 3,0. Rows ±10 % move only marginally: a plain 37,7 → 41,5 %, b 9,9 → 10,8 %, d 36,0 → 38,0 % at 3,0 (replay: b, d same gains; a unchanged at 43,4 %).
- **Reading:** 3,0 m² is closer on the two projects where we under-read (c, d) and further on the two where we over-read (a replay, b). Mean |error| over a, b, c, d: 13,1 % today vs 12,4 % at 3,0 — no real difference. The threshold moves the paint total by 7–19 m² (1–5 %), while the residual on b and c is 75–100 m² (15–20 %) from other causes (perimeters, heights, which rooms are painted). **The data cannot identify the threshold.** It does not contradict 3,0; it does not support it either. Two projects (g, h) cannot test it at all because their wall paint is pinned to the designer's figure. If the founder makes 3,0 the profile default, the fit should report it as a founder convention, not a fitted one — until the other residuals are an order of magnitude smaller.

### (ii) Grindjuostės: perimeter − 0,90 m × doors vs perimeter − drawn widths, ± 10 %

He bills wooden / PVC skirting on b and d only, tile skirting on a, g, r2. Door counts from `reading_truth.json` (counted by eye from the drawing, both sides of an interior door) where it exists (a, d, g, h), else the model's element list (b). Perimeters are what the engine uses in replay mode. Room set = the rooms our engine skirts (wood/PVC), or tile-floored rooms that are not fully tiled.

| project | his | rooms used | P | doors | P − 0,90 n | P − drawn | (P − 0,90 n) × 1,10 | (P − drawn) × 1,10 |
|---|---|---|---|---|---|---|---|---|
| objektas_d wood | 23,07 | 01, 03 | 21,45 | 4 | 17,85 (−23 %) | 18,14 (−21 %) | 19,63 (−15 %) | 19,95 (−14 %) |
| objektas_d if kitchen 04 added | 23,07 | 01, 03, 04 | 40,95 | 5 | 36,45 (+58 %) | 36,27 | 40,10 | 39,90 |
| objektas_b wood (63,0 + 30,8) | 93,80 | 9 non-tiled rooms | 137,00 | 13 | 125,30 (+34 %) | 124,00 (+32 %) | 137,83 | 136,40 |
| objektas_a tile | 22,72 | 101, 105, 106 | 42,83 | 6 | 37,43 (+65 %) | 35,46 | 41,17 | 39,01 |
| objektas_g tile | 26,87 | 05, 09 | 19,38 | 2 | 17,58 (−35 %) | 16,58 | 19,34 | 18,24 |

- **Fixed 0,90 vs drawn widths differs by 1–4 m (1–5 %)** on these sets, because most drawn doors are 0,8–0,9 m. **Which rooms he skirts is unknown and moves the total by 20–60 %.** The comparison cannot pick a formula.
- One room-level data point does discriminate: objektas_a's notes give garage 105 skirting 10,92 m; its perimeter 13,59 m (outline estimate) minus the drawn 2,50 m garage door = 11,09 (+1,6 %), while 13,59 − 0,90 = 12,69 (+16 %) and either ×1,10 is worse. That favours **drawn width, no waste** for a wide opening — one room, and the notes' per-room skirting (33,04 m over three rooms) does not even sum to his sąmata row (22,72 m), so this is weak.
- Waste: on objektas_d, the only clean wood case, his 23,07 is above both net formulas for the two obvious rooms and far below them with the kitchen; ×1,10 lands closer (−14/−15 %) only because the room set is short. **Undetermined.**

### (iii) Wet rooms: one hidroizoliacija row or two?

| project | his row(s) | wet rooms (vonia / san / wc) | our row |
|---|---|---|---|
| objektas_a | 1 row, **2 vnt** | 2 (107, 111) | 2 vnt |
| objektas_b | 1 row, **3 vnt** | 3 (08, 10, 12 = WC) | 3 vnt |
| objektas_c | 1 row, **2 vnt** | 2 | 2 vnt |
| objektas_d | 1 row, **1 vnt** | 1 | 1 vnt |
| objektas_g | 1 row, **39,50 m²** | 3 (03, 06, 07) + skalbykla 05 | 3 vnt |
| objektas_h | 1 row, vnt, no quantity | 2 | 2 vnt |
| objektas_r1 | none (scope: paint only) | 3 | 3 vnt |
| objektas_r2 | 1 row, **2 vnt** | (no extract) | — |

- He writes **one** row on every project that bills waterproofing, never the founder's two (floor m² + corner tape m). On six of seven it is **vnt = number of vonia / san / WC rooms**; a laundry („Skalbykla", a, b, g, r1) is never counted. Our engine already reproduces this exactly on a, b, c, d.
- The single m² case, objektas_g (an *atliktų darbų aktas*, a different document kind): wet floors 17,67 m² (+ laundry 3,76 = 21,43, which equals his floor-tile total 21,50 within 0,3 %); the remaining 18,07 m² would be a 0,47 m wall band over all four rooms' perimeters (38,71 m), or 21,83 m² = 0,73 m over the three wet rooms only. One number, two unknowns — **not identifiable**.
- Name markers: the core markers (vonia / vonios / WC / san. mazgas) find exactly the wet rooms on every project; of the candidates only „Skalbykla" ever occurs, and he does not count it. „Dušas", „Tualetas" never occur in the corpus.
- **Conclusion:** the founder's two-row rule is not what this contractor writes. Implementing it as the default would move a reproduced row (4 of 4 today) to two rows he does not bill. Founder decision; I recommend keeping one vnt row as the `lt_rangovas` default and offering the two-row form as an option.

### (iv) Waste factors on grindų danga and plytelės

| check | his | designer's net area | ratio |
|---|---|---|---|
| objektas_d PVC | 36,99 m² | all non-wet rooms 37,28 (incl. kitchen) | 0,992 |
| objektas_g floor tiles (2 rows) | 21,50 m² | 3 wet rooms + laundry 21,43 | 1,003 |
| objektas_a floor tiles, per room (his notes) | 101: 8,54 · 105: 10,10 · 106: 6,89 · 107: 6,52 · 111: 7,83 | 11,01 · 10,67 · 6,84 · 6,59 · 7,45 | 0,78 · 0,95 · 1,01 · 0,99 · 1,05 (median 0,99) |
| objektas_b parquet | 108,08 m² | no floor-covering read; rooms 02+04+05+06+09 = 107,52 | 1,005 (room set chosen to fit — circular, weak) |
| objektas_c PVC | 98,00 m² | no designer table (areas computed) | — |

- Where it can be checked, **he bills net area — no 1,08 / 1,10 factor** on labour rows. Waste belongs in material quantities, which he never writes. Our engine already writes labour rows net and puts +10 % only in „Medžiagos" („Grindų danga (m² + 10 % atliekų)"), which matches. Do not put 1,08 / 1,10 into the row generators for his profile.
- Thin: three clean cases (d, g, a per-room), one circular (b).

## 4. What this means for Phase 2 (my reading, for the manager)

1. The biggest row-level losses are not conventions but **scope and granularity**: which rooms he paints/skirts/tiles, one combined paint row, one combined tile row, and blanks for GKP extras. A conventions fit over thresholds will move the ±10 % share by a few points at most on this data (best single change seen: +4 pp on a at 3,0 m²).
2. Two of the four founder rules are contradicted or untestable here: hidro two-rows is contradicted (6/7 one vnt row); waste factors on labour rows are contradicted (net, 3 clean cases). The aperture 3,0 rule and the fixed 0,90 skirting deduction are **untestable** at today's residuals.
3. The vector lane outlines rooms on 3 of 7 projects; G1 as written ("≤ 1 % vs table on all eight") cannot pass on table area even where the walls match the strings to 0,1 % (h). Recommend G1 be stated against dimension strings, with table area as a convention-dependent secondary.
4. objektas_r2 has no floor plan and no extract; objektas_r1 is a scope-mismatched paint-only quote. Leave-one-out over "eight" is really over six usable projects (a, b, c, d, g, h), two of which (g, h) have designer-anchored wall paint and one (c) no designer table.

## 5. Reproduce

All code is in `scripts/method_reconstruction/` (reads the main checkout's gitignored ground truth / fixtures / cached extracts by absolute path, writes only to `$METHOD_OUT`, never into the repo; codenames only):
- `common.py` — paths, codename mapping, paid-call block, harness import.
- `run_engine.py` — live engine per mode × variant → `engine_<mode>_<variant>.json` (rooms, our rows, scorecard).
- `outline_errors.py` — vector lane alone, per-room area / perimeter errors → `outline_errors.json`.
- `scale_check.py` — scale vs table diagnosis for one project → `scale_check_<code>.json`.
- `analyze.py` — families inventory and hypotheses (i)–(iv) → `analysis_<mode>.json`.
