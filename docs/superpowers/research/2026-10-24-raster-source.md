# Raster room source — frozen-constant test on unseen sheets (gate before wiring)

**Date:** 2026-10-24 · **Worker:** Opus 5.5 · **Branch:** `v4/raster-source` (not merged; togal-v2 @ f9d2ced6 merged in, LANE_VERSION 15 untouched) · **Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §3.1, §3.4, §9 (founder decision „ok, 5%") · **Follows:** `docs/superpowers/research/2026-10-24-raster-rooms-spike.md`

## Resume point

Done: step 1 of the task (frozen-constant test) — the spike's four inputs re-run unchanged (identical to the spike report), truth dumped for four unseen sheets, every sheet scored at 150 and 300 DPI under the restated clause, failure causes looked at on overlays. **Verdict FAIL on every truly unseen sheet → per the task, nothing is wired**: no `backend/geometry/raster_source.py`, no `SAMATU_RASTER_ROOMS` flag, no `outline-at` hook, no frontend change. Committed: the two test scripts (`spikes/raster_rooms/dump_unseen.py`, `run_unseen.py`) and this report. Nothing under `backend/` or `frontend/` changed, so the backend suite, frontend tests/lint/build and the four eval passes were **not run** (no code path they cover moved). If the founder wants the raster track to continue, the next step is in "What would have to change" — and it means new constants, so a fresh unseen sheet is needed afterwards (these four are now seen).

## The clause (as restated by the founder)

Per room: area within **5 %** of the vector outline (the designer's table where no vector truth exists), **IoU ≥ 0,9** against the vector outline (where there is one), **no leak** (status `open` / `outside` / no face, or > 1,3 × the table). A sheet passes when **≥ 80 %** of its rooms pass. Constants: exactly as committed in `spikes/raster_rooms/raster_rooms.py` on togal-v2 (imported, never overridden).

## Verdict

| sheet | never seen by the spike? | truth | 150 DPI | 300 DPI |
|---|---|---|---|---|
| **objektas_d** sheet 2 (rooms sheet, scale 1:40 borrowed from sheet 1 by `scale.py`) | yes | table (the vector lane has no walls here) | **FAIL 0/4** | **FAIL 0/4** |
| **objektas_b** sheet 1 (plan, 1:100 from dimension lines) | yes | vector 10 rooms (lane 9 + one click), table 5 | **FAIL 1/15** | **FAIL 6/15** |
| **objektas_i** sheet 4 (contractor's partitions plan, two units, 1:75) | yes | vector 17/17 (lane after the togal-v2 lane fixes) | **FAIL 6/17** | **FAIL 5/17** |
| objektas_a sheet 4 (another plan of the spike's project; same frame as the tuned sheet 2) | sheet yes, drawing no | vector 11 (the lane's sheet-2 outlines; badges on the same points) | FAIL 3/11 | PASS 9/11 |

**The unseen sheets FAIL. Not wired.** The only PASS is objektas_a sheet 4 at 300 DPI — the same building, the same pen and the same frame as the sheet the constants were tuned on, so it is in-sample in everything but the page number, and it fails at 150 DPI.

Reproducibility: the spike's own four inputs re-run unchanged give byte-for-byte the spike's table (`summarize.py` output identical row by row: a_flat150 2/11 · 1/11, h 0/11 · 3/11, g 3/8 · 1/8, j3 1/8 · 2/8 on the old §9 clause). Scored under the restated clause they are: objektas_a_flat150 **7/11 · 4/11**, objektas_h **0/11 · 5/11**, objektas_g **4/8 · 5/8**, objektas_j3 scan **8/9 PASS · 6/9** — so even in-sample only one input at one resolution meets the clause. The unseen numbers are identical under the backend venv (OpenCV 4.10) and the spike venv (OpenCV 5.0).

## Per room

Cells: raster m² (error vs truth %, IoU) — `L` = leak. 150 DPI | 300 DPI.

**objektas_d sheet 2** — every click `outside` at both resolutions: the wall mask is empty (0,05 % / 0 % of the sheet). Rooms 01–04 (table 4,05 / 4,00 / 10,21 / 23,02 m²).

**objektas_b sheet 1**

| nr | truth | truth m² | 150 DPI | 300 DPI |
|---|---|---|---|---|
| 01 | table | 7,36 | 991,9 L | outside L |
| 02 | vector (open space with 01, 03) | 84,68 | 61,2 (−27,7 %, 0,59) L | 85,3 (+0,7 %, 0,97) L (> 1,3 × table) |
| 03 | table | 15,25 | 991,9 L | outside L |
| 04 | vector | 12,15 | 14,9 (+22,9 %, 0,68) L | 12,7 (+4,6 %, 0,93) ✓ |
| 05 | vector | 3,76 | 14,9 L | 3,61 (−3,9 %, 0,96) ✓ |
| 06 | vector | 12,19 | 11,8 (−2,9 %, 0,65) | 15,2 (+24,7 %, 0,78) |
| 07 | vector | 3,81 | 2,57 (−32,5 %) | 3,63 (−4,8 %, 0,95) ✓ |
| 08 | vector | 6,77 | 7,44 (+9,9 %) | 6,68 (−1,3 %, 0,895) |
| 09 | table | 14,58 | 14,52 (−0,4 %) ✓ | 31,7 L |
| 10 | vector | 13,42 | 12,3 (−8,5 %, 0,81) | 31,7 L |
| 11 | vector | 5,73 | 4,88 (−14,7 %) | 5,55 (−3,1 %, 0,97) ✓ |
| 12 | table | 2,89 | 991,9 L | outside L |
| 13 | vector | 9,42 | 7,23 (−23,3 %) | 9,23 (−2,0 %, 0,97) ✓ |
| 14 | vector | 7,06 | 61,2 L | 6,88 (−2,6 %, 0,97) ✓ |
| 15 | table | 44,00 | 991,9 L | outside L |

**objektas_i sheet 4**

| nr | vector m² | 150 DPI | 300 DPI |
|---|---|---|---|
| 1-1 | 13,85 (open space with 1-6, lane's proposed split) | 85,0 L | 67,9 L |
| 1-2 | 14,56 | 85,0 L | 14,85 (+2,0 %, 0,95) ✓ |
| 1-3 | 3,69 | 85,0 L | 3,59 (−2,7 %, 0,97) ✓ |
| 1-4 | 11,94 | 12,27 (+2,8 %, 0,95) ✓ | 67,9 L |
| 1-5 | 11,94 | 85,0 L | 67,9 L |
| 1-6 | 31,17 | 85,0 L | 67,9 L |
| 1-7 | 7,05 | 85,0 L | 18,5 L |
| 1-8 | 4,63 | 85,0 L | 18,5 L |
| 2-1 | 11,47 | 8,95 (−22,0 %, 0,77) | 14,9 L |
| 2-2 | 5,01 | 4,99 (−0,4 %, 0,98) ✓ | 14,9 L |
| 2-3 | 6,48 | 5,51 (−15,0 %, 0,60) | 11,4 L |
| 2-4 | 5,01 | 4,89 (−2,4 %, 0,96) ✓ | 11,4 L |
| 2-5 | 2,72 | 1,60 (−41,0 %, 0,24) | 17,3 L |
| 2-6 | 14,54 | 14,22 (−2,2 %, 0,82) | 17,3 L |
| 2-7 | 10,31 | 10,13 (−1,8 %, 0,98) ✓ | 10,14 (−1,7 %, 0,98) ✓ |
| 2-8 | 10,31 | 10,09 (−2,2 %, 0,98) ✓ | 10,16 (−1,5 %, 0,99) ✓ |
| 2-9 | 35,65 | 35,94 (+0,8 %, 0,97) ✓ | 36,45 (+2,2 %, 0,98) ✓ |

**objektas_a sheet 4** — 150 DPI: 102, 108, 109 pass; 101 −19 %, 103/107 merged (11,8 L), 104 −48 %, 105 −14 %, 106 1,03 m² of 7,35, 110/111 merged (28,5 L). 300 DPI: 9/11 (101 −21,6 %, 103 −19,3 % — the same two rooms where the vector click itself disagrees with the lane outline; the rest within 4,1 %, IoU 0,92–0,98).

## Why it fails (looked at on the wall/bridge overlays)

1. **Walls drawn as two thin outlines with nothing between them (objektas_d).** The mask needs a wall to be ink at least 0,6 × 7 cm thick or a hatch whose cells are ≤ (6,5 cm)²; d draws its walls as a pair of 1-px lines around a white band 10–25 cm wide, so nothing survives the opening and every click floods the whole sheet. This is a drafting class the spike's five inputs did not contain (all had filled, hatched or very thick walls). The vector lane cannot read d either (`no_walls`), so this sheet has no automatic outline today from any source.
2. **Door bridges missing → rooms merge through their doors (objektas_i, objektas_b).** On i at 300 DPI the doors from rooms 1-4, 1-5, 2-1…2-6 into the corridors are left open (no bridge in the overlay at the 900 mm openings) and up to five rooms run together (67,9 / 18,5 / 17,3 m²); at 150 DPI a different set of doors is missed. Same pattern on b (09 + 10 = 31,7 m² at 300 DPI). The facing-edge rule depends on where a wall end lands to the pixel — exactly the 150-vs-300 brittleness the spike warned about, now out of sample.
3. **Spurious long bridges and lost thin partitions at 150 DPI on a 1:100 sheet (objektas_b).** At 59 px/m a 10 cm partition is 6 px — at the opening kernel's edge — so walls break and three rooms plus the outdoors become one 992 m² face; elsewhere bridges cut rooms (07 −32 %, 13 −23 %).
4. **Open-plan spaces.** b 01/02/03 and i 1-1/1-6 are one space on the drawing; the vector lane only separates them with a proposed line (or reports `open`). The raster click can never split them, so those rooms are structural fails under any constants — a smaller effect than 1–3.

Where the raster lane does find the room (status ok, no leak), it usually lands within 5 % and IoU ≥ 0,9: i at 300 DPI 5 of 5 such rooms, b at 300 DPI 6 of 8, i at 150 DPI 6 of 10 (the misses there are cut by spurious bridges: 2-1, 2-3, 2-5). The boundary is not the problem out of sample; **finding the room is** — the opposite of the spike's in-sample picture, and exactly the condition the spike report named for reconsidering the segmenter track ("only if (2) shows the deterministic lane failing on finding rooms, not on the last 2 cm").

## What would have to change before wiring (not done — new constants need a new unseen sheet)

- Outline-only walls: a second wall model — pairs of parallel strokes 7–50 cm apart filled between them — before the bar test (d).
- Door gaps from the door symbol, not wall-end geometry: swing arcs and leaf lines (thin, so the mask discards them today) used as gap markers; the bridge at the arc's chord. This is the plan's §9 fallback and would also make 150 vs 300 DPI stop flipping rooms.
- A resolution rule: render at a fixed px per metre (e.g. ≥ 110 px/m, i.e. a 10 cm partition ≥ 11 px), not a fixed DPI.
- Then freeze again and test on a sheet none of a, b, d, g, h, i, j has touched (these four are now seen).

## What was not done (by the task's rule)

Step 2 (port to `backend/geometry/raster_source.py`), step 3 (`outline-at` fallback, `source: "raster"`, `proposed: true`, dashed proposal in the viewer) and step 4's backend/frontend tests and the four eval passes. No file under `backend/` or `frontend/` changed on this branch beyond the togal-v2 merge.

## Reproduce

```bash
# worktree on v4/raster-source (togal-v2 merged in). Lane truth: PROJECT venv; writes spikes/raster_rooms/out/ (gitignored)
V=/Users/ignasgaldikas/samatu-ai/venv/bin/python
FIX=/Users/ignasgaldikas/samatu-ai/docs/superpowers/fixtures
GT=/Users/ignasgaldikas/samatu-ai/ground_truth
$V spikes/raster_rooms/dump_unseen.py objektas_d "$FIX/2026-06-01-batch-5/Nr. 5/objektas_d_TP_bundled.pdf" 2 spikes/raster_rooms/out/unseen_objektas_d.json --seed ground_truth/objektas_d
$V spikes/raster_rooms/dump_unseen.py objektas_b "/Users/ignasgaldikas/samatu-ai/$(python3 -c "import json;print(json.load(open('$GT/objektas_b/truth.json'))['pdf_path'])")" 1 spikes/raster_rooms/out/unseen_objektas_b.json --seed ground_truth/objektas_b
$V spikes/raster_rooms/dump_unseen.py objektas_a $FIX/2026-05-26-objektas-a/project.pdf 3,4 spikes/raster_rooms/out/unseen_objektas_a.json --seed ground_truth/objektas_a
$V spikes/raster_rooms/dump_unseen.py objektas_i <prod-pull>/559e17ce-e97c-4cd0-a768-5fbf202f7d72.pdf 4,5,7 spikes/raster_rooms/out/unseen_objektas_i.json
# frozen-constant scoring (spike venv or project venv — identical numbers)
$V spikes/raster_rooms/run_unseen.py            # -> out/unseen_results.json
# the spike's own inputs, unchanged (needs the spike's out/lane_*.json and out/sam/, copied from the spike worktree)
<spike venv>/bin/python spikes/raster_rooms/run_raster.py --no-overlays --runs objektas_a_flat150,objektas_h_render,objektas_g_render,objektas_j3_scan
python3 spikes/raster_rooms/summarize.py
```

objektas_i sheets 5 and 7 and objektas_a sheet 3 were dumped too: on i 5/7 the dumper found no vector truth (every click `open`: the text seats there are not reliable), so they are not scored; a sheet 3 duplicates sheet 4.
