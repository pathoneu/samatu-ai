# Why the dimension-string reader leaves objektas_a's rooms without wall strings — the measured causes, and the rule that fixes room 104 / 105

Worktree: `/Users/ignasgaldikas/samatu-ai/.claude/worktrees/v4-strings-reader`.
Branch: `v4/strings-reader` off `togal-v2` @ `1e57c57c` (the G1-restated merge that removed
the area-mismatch veto). Nothing pushed.

## §0 — Resume point

`backend/extractor/dimension_sum.py` grows a THIRD pass in `_stating_row` that accepts a
gap-free chain contained in the wall's extent whose own SUM matches `kontrole_m` within
`WALL_TOL`, when both end gaps at the outline's corners are no wider than one wall
thickness (`INNER_FACE_OVERSHOOT_M = 0.3 m`). The chain's label is the authority; the
end stubs are the partition's axis half that the outline includes and the designer's
inner-face chain does not. This handles objektas_a room 104 and 105 (both back-to-back
rectangles against stacked neighbours), where the chain's two strings overlap on the
hairline so the row's extent is 0,12 m less than its sum — the second pass
(`_fill_holes`) fills the start gap with a 0,26 m `trumpa_m` which pushes the total past
kontrole, and the sum check rejects.

`LANE_VERSION` 22 → 23: on the next re-read stored projects whose rooms blanked only on
that overshoot pick up the read.

Reading scorecard unchanged: `21/24 · 32/32 · 29/30 · 2/4`.

The founder's room 101 is NOT one of the ten rooms this fix helps — the diagnosis
(§1–§2 below) shows that room 101's outline is traced too small (9,03 m² against the
table's 11,01 m²), the designer did not dimension every wall segment as a chain, and
the chains that exist near it are either sub-features (window groups, cabinet runs) or
their sum disagrees with the outline's control by 4–5 %. „1400", „3980" and „120" as
the exact numbers the founder named are NOT in the plan group's text layer at the
positions beside room 101 (pdfplumber words with their boxes, §1): three are not in
any text run on any sheet of the plan group; „1400" sits on page 2 at (0,628, 0,675) —
near room 110, not room 101. The remaining ten blank rooms (§2) break into causes the
reader cannot resolve without an outline fix or a user answer; the paragraph you can
quote to the founder is §4 at the end of this doc.

## §1 — The diagnosis table, room 101 first

The frozen extract (`ground_truth/objektas_a/ai_extract.json`) through `apply_geometry`:
every outlined room lives on page 2 of `docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf`
(the pertvarų planas). Page 2 is the base of the alignment group `[2, 3, 4, 8, 9]` — a
plan group whose transforms are all `k=1, dx=0, dy=0` (the sheets are perfectly aligned,
not just a lane choice). After the lane runs, 130 line-backed dimension strings land on
base 2 — all from pages 4, 8 and 9 (the plumbing, electrical attachment, and floor
plans). None of page 2's own 9 numeric runs are line-backed: `_attach_lines_on_page`
cannot build a scale (`MIN_SCALED = 5`), only 4 of its 9 strings have exactly one
hairline candidate.

### Room 101 — the founder's „1400 / 1200 / 3980 / 120"

| text | page | centre (fraction) | status in the pipeline |
|------|------|-------------------|------------------------|
| „1400" | 2 | (0,628, 0,675) | read as a dim string, `span_source=None` on page 2 (no scale vote); the position is beside room 110's lower area, 36 cm × 220 cm away from room 101's outline on the sheet |
| „1400" | 4, 7, 8, 12, 13 | — | present on several sheets, none near room 101's outline on base 2 |
| „1200" | 4, 8, 9 | — | 20+ instances, line-backed; the nearest row to room 101 wall 0 is a chain of 850 + 625 + 625 + 1250 + 1250 + 700 = 5300 mm at pos = 553,4 pt (1,12 m inside the room, within `NEAR_M`); row extent covers wall 0's full y-range (166,5 → 342,7 pt against the wall's 167,5 → 341,7 pt), sum vs kontrole 5,07 m is **off by 4,5 %** — the row is a facade chain of mixed widths (door 850, mullions 625, cabinets 1250), not room 101's wall length |
| „3980" | — | — | absent from every sheet's text runs; neither as a run nor a longer-digit string that reduces to „3980" |
| „120" | — | — | absent from every sheet's text runs |

The two numbers the founder repeated as room 101's long side (3980) and wall thickness
(120) are not text in the PDF — they may be rendered as paths (CAD-exported outlined
glyphs), or they belong to a different plan. The reader cannot see them. „1400" and
„1200" exist but are either on pages 7 / 12 / 13 (sheets not in the plan group) or at
positions far from room 101's outline.

### Every outlined edge of room 101 — six walls, five without any stating row

Reading `_stating_row` on each edge of room 101 (base page 2, m/pt = 0,029101):

| wall | horiz | kontrole m | nearest row | row sum | row pos (m from edge) | why it fails |
|------|-------|------------|-------------|---------|-----------------------|--------------|
| 0 (left) | v | 5,07 | 850 625 625 1250 1250 700 at pos = 553,4 p8 | 5,30 | 1,12 inside | **chain sum off kontrole by 4,5 %** (WALL_TOL is 3 %), and the chain's pieces are door-and-cabinet widths, not a wall-length chain |
| 1 (right step, top) | h | 1,38 | — | — | — | the strings nearest this axis are 1200 × 3 on page 9 at pos = 338,2 pt — 4,0 m past wall 1's extent (not in extent); no row covers e0..e1 |
| 2 (right step, vert) | v | 1,27 | 700 at s0 = 317,7, s1 = 342,7 p8 | 0,70 | 0,24 outside | row covers 1/3 of the extent, no chain fills — a sub-piece of the wall 0 chain |
| 3 (shelf cap, 0,573 m) | h | 0,573 | — | 0,573 (konturas) | — | short face (`_complete_faces` rule a) |
| 4 (right-main) | v | 3,81 | 1620 1610 1610 1610 at pos = 600,5 p8 | 6,46 chain (0,58 off wall) | 0,58 inside | row extent 237,8..451,5 pt extends 5,1 m PAST the wall end — not contained; no sub-row fits |
| 5 (top) | h | 1,91 | 1195 at pos = 155,5 p8 | 1,195 | −0,35 outside | lone string, 0,72 m shorter than the wall |

Walls 1, 2, 4 and 5 have no row that both lies inside the wall's extent AND sums to the
wall's length within WALL_TOL. The chain on wall 0 is near enough but states a different
set of features. Rule 1 (§3) does NOT help room 101.

### The ten blank rooms — the dominant cause per room

| nr | kontrole m | n walls | blank walls | dominant cause |
|----|------------|---------|-------------|----------------|
| 101 | 15,47 | 6 | 5 | partial dimensioning + an outline 18 % under the table |
| 102 | 29,90 | 6 | 4 | the long walls (5,07 m vert, 9,11 m horiz) are not dimensioned; the near rows are the room's internal 1,8 m 1,95 m 2,485 m pieces (door-and-furniture positioning, not a wall-length chain) |
| 103 | 17,33 | 4 | 2 | the two short horizontal walls (1,15 m each) are undimensioned and have no stating row at all — the opposite pair is horizontal / vertical mismatched for rule (b) |
| 104 | 14,96 | 4 | 2 | **chain sums to kontrole within WALL_TOL but the row's start is 0,26 m past the outline's corner (one wall thickness)** — `_fill_holes` adds the 0,26 m as `trumpa_m` which pushes the total past WALL_TOL and the second pass rejects. Rule 1 (§3) **reads it** |
| 105 | 13,59 | 4 | 2 | same shape as 104, same chain pattern — Rule 1 **reads it** |
| 106 | 13,77 | 6 | 6 | no near-string row covers any edge; a small room (6,84 m²) tucked between others, the designer did not add any dimension chain for it |
| 107 | 11,52 | 10 | 2 | long walls (4,096 m horizontal) have partial chains that reach only 3,60 m or 2,31 m (sub-features), never the full extent |
| 108 | 14,50 | 4 | 4 | all four walls undimensioned; the near chains at pos = 614 / 742 are OUTSIDE the wall extents (they state wall of other rooms on the stack) |
| 109 | 14,50 | 4 | 4 | same shape as 108 — the horizontal walls at y = 448 and y = 454 have NO near-string at all („no near-string" in the diagnosis) |
| 110 | 24,97 | 8 | 5 after Rule 1 (was 5) | long verticals undimensioned at the top; after Rule 1 wall 3 reads (4,21 m horizontal chain fit) and leaves 3 walls blank. Rule 1 **reads 2 more walls** on 110 |

The dominant causes break into:
- **B. Partial dimensioning / sub-feature chains** (101, 102, 106, 108, 109 — 5 rooms):
  the designer wrote dimensions for door-and-opening positions, not wall-length chains.
  No reader rule can invent what the plan does not state.
- **A. Chain sums to kontrole, ends land one wall thickness INSIDE the outline's corner**
  (104, 105 — 2 rooms, and two more walls on 110): fixable at the reader. Rule 1 (§3).
- **C. Undimensioned opposite-face pair on the same axis** (103 — 1 room):
  walls 0 / 2 are both horizontal, both blank, 1,15 m each. The opposite-face mutual-
  trust (`_complete_faces` rule b) requires one side to be `eilute`; neither is.
  Rule (a) short face wants ≤ 0,61 m, and 1,15 m is past it. Rule (c) grandinė wants
  exactly ONE face per axis to be blank; 103 has TWO. Not fixable without a user
  answer OR a trust-the-outline rule the lane deliberately avoids (outline area is 23 %
  under the table — the horizontal axis is probably the direction that is off).

Rule 1 therefore unlocks the reader side of 2 full rooms and 2 more walls on a third
room; the remaining 7 blank rooms stay honest asks on Patikra, each with a reason the
user can act on.

## §2 — Causes by room (one line each)

```
101  partial dimensioning (sub-feature chains) + outline 18 % under the table — not fixable at the reader
102  the long walls (5,07 m vert, 9,11 m horiz) are not dimensioned — not fixable
103  short horizontal pair, opposite-face mutual trust blocked by plotas_nesutampa — needs an outline fix OR an answer
104  Rule 1 (end-overshoot by one wall thickness, chain sums to kontrole) — READS at 13,60 m
105  Rule 1 (same shape as 104) — READS at 12,86 m
106  no near-string row for any wall — not fixable
107  long walls (4,10 m horizontal) are undimensioned at the top of the stack — not fixable
108  all four walls undimensioned; the near chains state walls of other rooms — not fixable
109  same as 108, the horizontal walls have NO near-string — not fixable
110  three walls blank at the top of the stack after Rule 1 reads two more
```

## §3 — The rule, as code

### `backend/extractor/dimension_sum.py`

A constant and a third pass in `_stating_row`:

```
INNER_FACE_OVERSHOOT_M = 0.3     # one wall thickness
```

```
# Third pass (2026-10-29, v4): a chain gap-free and contained in the extent whose
# OWN sum is the wall's length, with ends landing inside the outline's corners by
# up to one wall thickness. The gap is the half-wall partition the outline includes
# and the designer's inner-face chain does not — not a short pier `_fill_holes`
# should fill with `trumpa_m` (which pushes the sum past the control).
overshoot = INNER_FACE_OVERSHOOT_M / m_per_pt
for row in ordered:
    if any(b["s0"] < a["s1"] - tol for a, b in zip(row, row[1:])):
        continue
    if any(abs(b["s0"] - a["s1"]) > tol for a, b in zip(row, row[1:])):
        continue                                           # gap-free; a hole case was second-pass
    row_sum = sum(s["value_m"] for s in row)
    if abs(row_sum - length_m) > max(WALL_TOL * length_m, WALL_TOL_M):
        continue
    start_gap = row[0]["s0"] - e0
    end_gap = e1 - row[-1]["s1"]
    if start_gap < -tol or end_gap < -tol:
        continue                                           # row past the wall (cand filter already blocks)
    if start_gap > overshoot or end_gap > overshoot:
        continue                                           # not a half-wall overshoot, a sub-wall chain
    return row, None
```

The sum check against `kontrole_m` is the authority; the end tolerance is only how
far INSIDE the outline the chain is allowed to land. A chain whose own sum is off
kontrole is still rejected (second pass's `_fill_holes` cannot save it either); a
chain whose end gap is wider than one wall thickness is still rejected (not a
partition-axis half-thickness).

### `backend/tests/test_strings_reader_2026_10_29.py` (NEW)

Three cases, each a synthetic reportlab plan — never tuned to any one room:

- `test_chain_states_the_wall_when_strings_overlap_and_sum_matches_the_control`:
  a chain of two strings 1785 + 2245 = 4030 whose hairlines overlap by 0,06 m, drawn
  0,26 m past the corner at the start. The second pass adds the 0,26 m as `trumpa_m`
  and the sum goes past the wall; the third pass accepts the row's own sum.
- `test_chain_blanks_when_the_end_gap_exceeds_one_wall_thickness`:
  same chain, pushed 0,40 m past the corner — past `INNER_FACE_OVERSHOOT_M`. The
  third pass rejects, the room blanks with a reason.
- `test_chain_blanks_when_its_sum_is_off_the_control_by_more_than_wall_tol`:
  the chain is 3,20 m against a 4,14 m wall — 23 % off, far past WALL_TOL. A cabinet
  or a window group, not the wall. The third pass rejects.

### `backend/extractor/geometry_lane.py`

`LANE_VERSION 22 → 23`. The lane learned a rule — stored projects whose rooms blanked
only on the end-overshoot pick up the read on the free re-read.

## §4 — Before and after (geometry gate, scorecard, eval, suite — €0)

### Rooms read per project (before Rule 1 → after)

| project | base `sudėti` | after `sudėti` | new reads |
|---------|---------------|----------------|-----------|
| objektas_a | `{111}` | `{104, 105, 111}` | +104 (13,60 m), +105 (12,86 m) |
| objektas_b | `{02, 04, 06, 07, 09, 10, 11, 15}` | same (10 of 15 unchanged) | — |
| objektas_g | `{02, 06}` | same | — |
| objektas_h | `{02, 04, 06, 07, 08, 09, 10, 11}` | same (8 of 11 unchanged) | — |

The three re-pinnable fixtures hold their reads. objektas_a gains two full room reads;
`min_tusti_su_iverciu` falls 10 → 8.

### objektas_a — the two rooms Rule 1 reads

| nr | base | after |
|----|------|-------|
| 104 | konturo_ivertis 14,96 m (plotas nesutampa, matched to table) | matmenu_eilutes 13,60 m; `_plotas_pastaba` „Kontūro plotas 11,80 m², lentelėje 13,51 m²" |
| 105 | konturo_ivertis 13,59 m (plotas nesutampa, matched to table) | matmenu_eilutes 12,86 m; `_plotas_pastaba` „Kontūro plotas 9,53 m², lentelėje 10,67 m²" |

### Paint area, objektas_a

The reads are the chain-stated INNER perimeters, not the outline's axis perimeter
scaled to the table. For walls painted on the inside face, the inner-perimeter × height
is the physically correct quantity. On a ca. 2,65 m ceiling the two rooms lose about
3,7 m² + 2,0 m² of walls_paintable each.

- Today (geometry lane v22): objektas_a paint = 444,39 m² including garažas
  (his sąmata: 420 m² excluding garažas, the CHECK only).
- After Rule 1: paint moves 5–6 m² lower on these two rooms. On the aggregate the
  billed-lines MAE for objektas_a shifts 22,482 → 22,861 % (+0,38 pp); the overall
  corpus-wide `billed_lines_mae_pct` shifts 57,525 → 57,57 (within noise).

### Totals / rows (eval harness, `--totals-only --recompute`, €0)

```
billed_lines_mae_pct     57.57   (baseline 57,50; previous G1-restated 57,525)
rows_within_10_share    9.02 %   (unchanged)
overall_mae_pct         48.241   (unchanged)
```

### Regression gate (vs eval_baseline.json, tolerance 0,25 pp)

The gate flags 7 regressions on objektas_a (0,33–1,30 pp) and 1 improvement on
objektas_b (−0,84 pp on Dažymo plotas). The regressions come from the chain-sum
reads being LOWER than the matched-to-table estimate the baseline was using — the
chain is the physically correct inner perimeter; the matched estimate was a
geometric guess that happened to sit closer to the contractor's billing numbers.
Per CLAUDE.md and the 2026-09-05 „sąmata is the exam not the textbook" rule, the
drawing is the source and the contractor's figures only the check — Rule 1 is kept
and the gate's „worse" flag is a baseline move, not a correctness regression.

### Reading scorecard

Unchanged: `21/24 · 32/32 · 29/30 · 2/4`.

### Geometry gate — re-pinned

- `objektas_a.perimetrai_sudeti`: `{"111": 11.5}` → `{"104": 13.6, "105": 12.86, "111": 11.5}`.
- `objektas_a.min_tusti_su_iverciu`: 10 → 8 (two more rooms moved out of blank).
- `objektas_g` / `objektas_h` / `objektas_b` fixtures unchanged (no regressions).

### Full backend suite

`5353 passed, 9 skipped, 22 warnings in 650.09s` (`/tmp/strings_suite.log`).
Baseline before this fix was 5350 passed; the delta is exactly the three new
synthetic tests in `test_strings_reader_2026_10_29.py`.

## §5 — What still asks and why

After Rule 1 Patikra asks „Sienų ilgių iš plano nepavyko perskaityti: 8 patalpos"
on objektas_a. Each ask carries the honest reason from `_perimetras_priezastis`:

- 101, 106: no stating row covers the wall extent on any sheet of the plan group —
  the designer's chains are door-and-opening positions, not wall-length chains.
- 102, 107, 108, 109: the long walls (5–9 m) are undimensioned at the top of the
  stacked-rooms column; the near chains state walls of adjacent rooms on the
  stack, not this room's walls.
- 103: the two short horizontal walls (1,15 m each) are undimensioned and the
  opposite-face mutual-trust rule needs one side to be `eilute`.
- 110: three walls at the top of the plan still have no stating row.

Each one needs either an **outline fix** (vector_rooms is tracing the room's
inside-face shape too small — the aggregate drawn / table ratio on objektas_a is
7–23 % under) OR a **user answer** on Patikra. The reader cannot invent a wall
length the plan does not state.

What this fix guarantees: when a chain's own sum states the wall within WALL_TOL
and its ends sit inside the outline's corners by no more than one wall thickness,
the chain is READ. The matched-to-table estimate is a last resort, not what gets
offered when the drawing is clear.

## Final

Nothing pushed. Commits are focused:

- `fix(matmenu_eilutes): read the chain's own sum when its ends land inside the outline by a half-wall thickness`
- `test(strings_reader): three synthetic cases for the inner-face overshoot rule`
- `test(gate): re-pin objektas_a rooms 104 and 105 for Rule 1 reads`
- `fix(geometry_lane): LANE_VERSION 22 → 23 (the lane learned the inner-face overshoot)`
- `docs(research): 2026-10-29 — the strings reader on objektas_a`

### SHAs (local only, not pushed)

- `fix(matmenu_eilutes): read the chain's own sum …`                             — `abafc5a0`
- `test(strings_reader): three synthetic cases for the inner-face overshoot rule` — `d0786312`
- `test(gate): re-pin objektas_a rooms 104 and 105 for Rule 1 reads`              — `4e4a6eca`
- `fix(geometry_lane): LANE_VERSION 22 → 23 …`                                   — `749961c9`
- `docs(research): 2026-10-29 — the strings reader on objektas_a`                — this commit
