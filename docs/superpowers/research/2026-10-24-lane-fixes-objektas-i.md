# Geometry lane fixes for objektas_i — badge size, wall colours, units, dashed doors

**Date:** 2026-10-24 · **Worker:** Opus 5.5 · **Branch:** `v4/lane-objektas-i` (from `togal-v2` @ b291f492)
**Diagnosis fixed:** `docs/superpowers/research/2026-10-24-cold-run-contractor-uploads.md` §1.3 (three causes) + failure #13 (dashed arcs).
**Cost:** €0. No model call.

## 0. Verdict

On objektas_i the lane went from **0 of 17 rooms located, 0 outlines, 0 doors** to **17/17 located, 17/17 outlined
(15 on their own face, 2 as one open space divided by the lane's proposal), median |area − table| 0,10 % (A) /
0,14 % (B), 22–24 doors classified, 5–6 perimeters summed from dimension strings**. objektas_j2 went from 0 to
7/8 outlined (+1 … +3 % vs the table, the open living room stays open); with the scale branch merged,
objektas_j1 (seeded) went from 0 to 15/18 outlined. Plain eval passes are unchanged; replay billed lines
22,88 → 22,84 %, replay rows unchanged (27,9 % / 39,6 %). objektas_b's painted walls first went to +31,2 % (open-space
share by floor area handed the double-height living room 47,8 m of 65,1 m); with the mixed-height rule (§4) they are
**+20,53 %** — 0,41 pp over the +20,12 % baseline, from four walls now read from strings 0,25–0,40 m longer than the
stored ones. Target „perimeters read for most rooms" is **not** met: 5–6 of 17.

*Update after the merge of `togal-v2` (scale branch, LANE_VERSION 15):* §2 j1/j2, §3 and §4 carry the final numbers.

## 1. Rules chosen

| fault | file | rule |
|---|---|---|
| 1 badge size | `room_locator.py` | A short badge may be at most **2,0 × the median height of the sheet's dimension strings** (all text directions), never above **14 pt**; a sheet with < 5 strings keeps the old 6,5 pt cap. Width cap scales with it. Measured ratios: i 6,6 / 6,55 = 1,01; objektas_h 3,5 / 2,91 = 1,20; j2 11,0 / 6,62–8,27 = 1,33–1,66. On h the cap is tighter than before (5,8 pt). Plus: the sheet showing the most wanted numbers is the **room-number sheet**; a badge there is never displaced by the same digit on another sheet (b's furniture plan numbers its furniture 1–18 in badge size — its „13", a bidet in room 10, had won room 13 by Vision-box distance). |
| 2 wall colours | `vector_rooms.py` `_ring_colours` | A further fill colour joins the wall solid when (1) it is ink — not black, not paper white (white fills are masks); (2) at least half its area is **bar-shaped** (≤ 0,8 m thick at the sheet's scale, ≥ 3× longer than thick) — zone fills and blocks fail; (3) one of its connected pieces meets the solid in **≥ 2 separate places** (closes a ring). No area share. Transitive (accepted colours grow the solid). One-colour sheets get exactly the old solid (test). |
| 3 units | `pdfplumber_eksplikacija.py` `stacked_unit_rooms`, `room_locator.py` `units_of_badges` | Table: text-line reader of blocks under each „…EKSPLIKACIJA" heading, rows = number in the heading's column … first area (+m2), block ends at its subtotal; used **only** when ≥ 2 blocks repeat each other's numbers, each block's printed subtotal must equal its rows (±0,05). Rooms keyed `<unit>-<nr>` („2-3", the LT apartment-room form) with `_vienetas` and `_nr_brezinyje`. Locator: per sheet, cut by the axis-parallel line leaving the most numbers on both sides (widest gap as tie-break), each part → the unit whose numbers it shows best (matches − extras, then fewest missing); ties are left unassigned. Rooms without `_vienetas` never reach this path. |
| 4 dashed arcs | `drawn_openings.py` | Dash chaining only links pieces whose directions turn ≤ 1,5 × (dash + gap) / r_min (≈ 35° at 1:75; cap 45°) — a dashed threshold or box corner touching the arc's end no longer joins the chain; pieces < 0,5 pt join nothing. A chain that fits no circle is trimmed (dashes off the best circle set aside, ≤ 3 rounds, keep ≥ 75 % and ≥ 6 dashes). |
| 5 furniture strings | — | **Not done**: string-to-wall assignment lives in `dimension_sum.py` (outside this branch's files). With the units fixed the trace now runs on the partitions sheet, and no „530" module string reaches a wall on i; the risk remains on furniture-only sheets. |

## 2. objektas_i — before / after (cold run, `scripts/cold_run/run_cold.py`)

| read | A before | A after | B before | B after |
|---|---|---|---|---|
| room table (text layer) | 7 of 17, numbers mangled | **17/17**, 2 units (104,99 + 102,11 = 207,10) | 7 of 17 | **17/17** (unit 1's subtotal line not read; unit 2 checks) |
| rooms located (badge) | 0 | **17** | 0 | **17** |
| outlines | 0 | **17** (sheet 4) | 0 | **17** |
| median \|area err\| vs table | — | **0,10 %** | — | **0,14 %** |
| perimeters summed from strings | 0 | 5 | 0 | 6 |
| doors / windows classified | 0 / 0 | **24** / 0 | 0 / 0 | **22** / 0 |

Per room, upload A (sheet 4 = partitions plan, both units):

| room | table m² | outline m² | Δ | perimeter m | source |
|---|---|---|---|---|---|
| 1-1 corridor | 16,14 | 13,85 | open space with 1-6 (45,02 vs 52,46, −14 %) | 26,24 | outline estimate |
| 1-2 bedroom | 14,56 | 14,56 | 0,0 % | 15,40 | **strings** |
| 1-3 bathroom | 3,68 | 3,69 | +0,3 % | 7,72 | **strings** |
| 1-4 bedroom | 11,95 | 11,94 | −0,1 % | 14,81 | estimate (2 of 6 walls no string) |
| 1-5 bedroom | 10,68 | 11,94 | +11,8 % | 14,01 | estimate (table ≠ drawing, known) |
| 1-6 living/kitchen | 36,32 | 31,17 | see 1-1 | 17,07 | estimate |
| 1-7 bathroom | 7,04 | 7,05 | +0,1 % | 11,72 | estimate |
| 1-8 technical | 4,62 | 4,63 | +0,2 % | 9,50 | estimate |
| 2-1 corridor | 12,09 | 11,47 | −5,1 % | 20,09 | estimate |
| 2-2 technical | 5,00 | 5,01 | +0,2 % | 10,01 | estimate |
| 2-3 bathroom | 6,48 | 6,48 | 0,0 % | 10,27 | estimate |
| 2-4 bathroom | 5,01 | 5,01 | 0,0 % | 8,88 | **strings** |
| 2-5 wardrobe | 2,72 | 2,72 | 0,0 % | 5,17 | estimate |
| 2-6 bedroom | 14,53 | 14,54 | +0,1 % | 15,39 | estimate |
| 2-7 bedroom | 10,30 | 10,31 | +0,1 % | 13,00 | **strings** |
| 2-8 bedroom | 10,31 | 10,31 | 0,0 % | 13,00 | **strings** |
| 2-9 living/kitchen | 35,67 | 35,65 | −0,1 % | 26,00 | estimate |

Why most perimeters stay estimates: `dimension_sum` refuses a sum when „2 of 6 walls have no string" — the two
short faces are door-jamb returns the designer never dimensions. That rule is outside this branch; it is the next
lever for „perimeters read" (the outline lengths themselves agree with the strings where both exist).
Windows: 0 classified — the glazing on this drawing is drawn in cyan inside the gap and `_glazing_lines` does not
see it; not investigated here.

Other projects (after the merge with the scale branch):

| | before | after |
|---|---|---|
| j2 cold | 0 located, 0 outlines | 8/8 located, **7/8 outlined**, median +2,26 %, 1 perimeter from strings, 8 doors (room 3 living: walls do not close) |
| j2 seeded (production's 9 rooms) | 0 | 9/9 located, 8/9 outlined, median +2,59 %, 9 doors |
| j1 cold | no room source (no table, no m² labels) | unchanged |
| j1 seeded (production's 18 rooms) | 18 located, 0 outlines (no scale) | 18 located, **15/18 outlined**, median 0,00 %, 14 doors |

The j2 table still loses room 2 (8 of 9 rows).

## 3. Corpus — the four eval passes

| pass | baseline | after |
|---|---|---|
| plain, billed lines | 22,60 % | **22,60 %** |
| plain, rows ±10 % / € ±10 % | 26,1 % / 34,7 % | **26,1 % / 34,7 %** |
| replay, billed lines | 22,88 % | **22,84 %** |
| replay, rows ±10 % / € ±10 % | 27,9 % / 39,6 % | **27,9 % / 39,6 %** |

Final run (after the merge with `togal-v2` and the mixed-height rule). Replay prints GATE FAIL (as before): 6 lines
are the known a/g/h lines, identical to the baseline run; 3 are objektas_b Dažymas +20,12 → **+20,53 %**, walls
+31,69 → +32,33 % (0,41 / 0,64 pp, over the 0,25 pp tolerance). b otherwise: billed MAE 18,07 → 17,88 %, Angokr.
−22,9 → −22,4 %, Kampai −19,3 → −19,1 %, Rotband −10,8 → −10,4 %, Plytelės −9,6 → −9,1 %; rows unchanged (9,9 % / 21,0 %).
The +0,4 pp: b's rooms 04, 05, 06, 10 now take perimeters read from strings or the outline (14,25 / 8,20 / 15,79 /
16,56 m) instead of the stored 14,0 / 7,8 / 15,4 / 16,2 m — geometry against a stored figure, no share involved.

(Intermediate run, before the mixed-height rule: replay billed 22,86 %, rows 28,0 % / 40,5 %, b Dažymas +31,2 %.)

## 4. objektas_b — the open-space share and the mixed-height rule

b's 15 circled room numbers are now found (checked on the sheet), so the lane outlines 11 rooms. Tambūras, living
room and corridor (01, 02, 03) are one face, 65,1 m of wall. `geometry_lane` shared it by floor area: 02 got 47,8 m
(was 33,5), 01 and 03 lost 16,1 m. The living room is double height (5,7 m), the other two 2,82 m: ≈ +36 m² of wall.

Rule now (`geometry_lane._mixed_heights`, `settle_open_space_heights`): **an open space whose members' ceiling heights
differ (> 0,05 m) is not shared by floor area.** A two-room space is divided by the lane's own boundary as before
and each side's own faces are read (the boundary is a wall of neither); a larger space, or one with no boundary,
leaves each member with the figure it had and the reason „atvira erdvė su …, lubų aukščiai skirtingi — bendras
erdvės sienų ilgis … m pagal plotą nedalijamas; patikrinkite šios patalpos sienų ilgį". Unknown heights tell
nothing (the share stands). Because the paid reading settles heights AFTER the lane (b's 5,7 m comes from the
height salvage — the lane saw 2,82 m everywhere), the same check runs in the project-level pass every calc path
runs, `universal_rules.prepare_rooms_for_calc` (one guarded call). It is reversible: heights that agree again
(a correction in Prielaidos) get the share back.

Honest limit: „the figure it had" is a stored Vision figure on b; with no figure at all the calc falls back to its
square estimate. Blank-without-any-number is not possible in today's calc.

## 5. Not done / caveats

- **Production path**: the paid reading merges the text-layer table INTO Vision's rooms by number/name
  (`vision_call` ~L6300), so Vision's keys (K1…D9) survive and `_vienetas` never reaches the lane. The cold runner
  passes the two fields (one-line change in `scripts/cold_run/run_cold.py`). Wiring units into production is a
  `vision_call` / Phase-3 decision.
- Fault 5 (furniture strings) and „2 of N walls without a string" are `dimension_sum.py` work.
- A curve-fitted false arc (a rug's rounded corner) exists on sheet 5 as before; it only matters at a wall gap.
- Tests: `backend/tests/test_lane_objektas_i_2026_10_24.py` (16, synthetic only).
- `LANE_VERSION` = 15 (after the scale branch's 14).
- Files outside the original list touched: `geometry_lane.py` (assigned), `universal_rules.py` (one guarded call in
  `prepare_rooms_for_calc`), `scripts/cold_run/run_cold.py` (passes the unit fields).
