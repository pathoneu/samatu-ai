# Perimeters from the written dimension strings — the table-area mismatch stops vetoing them (G1 restated)

Worktree: `/Users/ignasgaldikas/samatu-ai/.claude/worktrees/v4-perimeters-from-strings`.
Branch: `v4/perimeters-from-strings` off `togal-v2` @ ca08704a. Nothing pushed.

## §0 — Resume point

The ladder in `backend/extractor/dimension_sum.py` no longer uses the outline-vs-table
area mismatch as a perimeter veto. The strings decide: when a wall's dimension row
matches its outline control length and the whole sums to the outline's perimeter
(CONTROL_TOL = 3 %) with no missing walls, the perimeter is READ (`perimetras_saltinis =
"matmenu_eilutes"`) even if the outline's own area is off the table by more than
`vector_rooms.AREA_TOL`. The two areas are then said once on the room as
`_plotas_pastaba` so the user sees them; the floor row keeps billing the table's area
(`room["plotas_m2"]`). When the walls cannot be summed (missing string / control
mismatch / outline share > OUTLINE_SHARE_MAX) the estimate branch fires as before and
the outline's length is matched to the table's area (`_matched_to_table`,
`_perimetras_suma["pagal_plota"]`).

The Patikra wording is unambiguous now: a count after a colon.

The LANE_VERSION is bumped from 21 → 22 — stored projects whose perimeters were
blocked only by the area mismatch pick up the read figure on their next re-read.

## §1 — The defect

Founder, 2026-10-29, on objektas_a room 101:

> „Antai: viršuje mes rašome 1400, apačioje 1200, dešinėje 3980, kairėje 120 ... Programa ir toliau sako „11 patalpų sienų ilgiai plane neužrašyti". Patikra reikalauja patvirtinimo, nors brėžinys turi tą ilgį."

Baseline (ca08704a) on objektas_a, every one of the 11 rooms:

```
101: saltinis='konturo_ivertis' reason='kontūro plotas nesutampa su lentele'
102: saltinis='konturo_ivertis' reason='kontūro plotas nesutampa su lentele'
… 109, 110, 111: same reason
106: 'kontūras be sienų'  (reader found nothing on this room anyway)
107: '2 iš 10 sienų be matmens'
```

The cause was `backend/extractor/dimension_sum.py` ~line 603: `if kont.get("plotas_nesutampa"): reason = AREA_MISMATCH_REASON` as the FIRST branch of the ladder. On objektas_a every traced outline is 7-23 % under the table's area (the table counts area by its own convention — the deterministic-hybrid plan 2026-10-24 restates this as G1), so the strings were never allowed to decide. Patikra then asked eleven times, with a bogus plural title („11 patalpų …" reading as room 11) and the user's own written numbers labelled „neužrašyti".

## §2 — The rule, as code

Three changes:

1. `backend/extractor/dimension_sum.py` sum_perimeters — the ladder's first branch is
   removed. When `kont["plotas_nesutampa"]` is True and the walls can be read (sum
   agrees with each control, control agrees with the outline, no missing wall), the
   perimeter is READ. A `_plotas_pastaba` is written on the room:
   „Kontūro plotas X m², lentelėje Y m² — grindims imamas lentelės plotas".
   When any of the three ladder checks fail (missing / outline share / control
   mismatch), the estimate branch fires exactly as before — `_matched_to_table`
   still scales the outline's length by √(table / outline) when the outline is the
   lane's and the error is within AREA_MATCH_MAX. The `AREA_MISMATCH_REASON`
   constant stays for backwards-compat (`room_facts._perimeter_reason` renders older
   stored projects that still carry it).

2. `backend/extractor/project_questions.py` `_ask_numbers("perimetras", …)` — the
   titles become unambiguous. Singular: „Patalpos {room} sienų ilgių iš plano
   nepavyko perskaityti". Plural: „Sienų ilgių iš plano nepavyko perskaityti:
   {n} patalpos". The number sits after the colon so „11 patalpos" can no longer
   be read as room 11.

3. `backend/extractor/geometry_lane.py` — `LANE_VERSION 21 → 22`. The lane learned
   something; stored projects whose perimeters were vetoed only by the area
   mismatch get the read figure from the free re-read.

Downstream guards keyed on `plotas_nesutampa` (`geometry_lane.py` ~946, ~956 — pair
proposals / outline proposals) are left as they are: they do not blank a read
perimeter, they only keep the pair's figure where a pair stated one. An outline
whose area is off the table is still just a proposal for the room's shape question
on the check sheet.

## §3 — Before and after on the frozen corpus (geometry gate, €0)

Per project, how many rooms moved from `konturo_ivertis` to `matmenu_eilutes`:

| Project | Baseline `sudėti` | After `sudėti` | New reads |
|---------|-------------------|----------------|-----------|
| objektas_a | 0 / 11 | 1 / 11 | +111 |
| objektas_b | 8 / 15 | 10 / 15 | +06, +15 |
| objektas_c | 0 / 0 | 0 / 0 | — (no vector outlines) |
| objektas_d | 0 / 0 | 0 / 0 | — (no vector outlines) |
| objektas_g | 2 / 11 | 2 / 11 | — (no plotas_nesutampa rooms with full string sets) |
| objektas_h | 6 / 11 | 8 / 11 | +07, +08 |

### objektas_a — room-by-room

Perimeters, baseline vs after fix (m). The 10 rooms that still blank do so for an
honest reason: the reader finds fewer than every wall's string on the plan.

| nr | base saltinis / reason | base m | after saltinis / reason | after m |
|----|------------------------|--------|-------------------------|---------|
| 101 | konturo_ivertis / plotas nesutampa | 15,47 | konturo_ivertis / 5 iš 6 sienų be matmens | 15,47 |
| 102 | konturo_ivertis / plotas nesutampa | 29,90 | konturo_ivertis / 5 iš 6 sienų be matmens | 29,90 |
| 103 | konturo_ivertis / plotas nesutampa | 17,33 | konturo_ivertis / 2 iš 4 sienų be matmens | 17,33 |
| 104 | konturo_ivertis / plotas nesutampa | 14,96 | konturo_ivertis / 2 iš 4 sienų be matmens | 14,96 |
| 105 | konturo_ivertis / plotas nesutampa | 13,59 | konturo_ivertis / 2 iš 4 sienų be matmens | 13,59 |
| 106 | konturo_ivertis / 6 iš 6 sienų be matmens | 13,77 | konturo_ivertis / 6 iš 6 sienų be matmens | 13,77 |
| 107 | konturo_ivertis / 2 iš 10 sienų be matmens | 11,52 | konturo_ivertis / 2 iš 10 sienų be matmens | 11,52 |
| 108 | konturo_ivertis / plotas nesutampa | 14,50 | konturo_ivertis / 4 iš 4 sienų be matmens | 14,50 |
| 109 | konturo_ivertis / plotas nesutampa | 14,50 | konturo_ivertis / 4 iš 4 sienų be matmens | 14,50 |
| 110 | konturo_ivertis / plotas nesutampa | 24,97 | konturo_ivertis / 5 iš 8 sienų be matmens | 24,97 |
| 111 | konturo_ivertis / plotas nesutampa | 11,81 | **matmenu_eilutes** | **11,50** |

The founder's room 101 is in the group whose strings the dimension reader does
not currently find on the drawing (5 of 6 walls). That is a separate reader-side
defect; the fix removes the area-mismatch veto that was HIDING the real cause.
After the fix, Patikra prints the honest reason for each room, and the user's
own 1200 / 1400 / 3980 / 120 numbers can be entered as the answer. 1 of 11 rooms
now reads itself without a question (111: 11,50 m).

### objektas_h — rooms 07 and 08

| nr | base | after |
|----|------|-------|
| 07 | konturo_ivertis 9,47 m (plotas nesutampa, matched to table) | matmenu_eilutes 8,51 m; _plotas_pastaba „Kontūro plotas 4,04 m², lentelėje 4,90 m²" |
| 08 | konturo_ivertis 8,33 m (plotas nesutampa, matched to table) | matmenu_eilutes 8,75 m; _plotas_pastaba „Kontūro plotas 4,81 m², lentelėje 4,32 m²" |

Both rooms carried the strings for all four walls on the painting plan; only the
area mismatch was keeping them blank. The matched-to-table estimate they used to
offer (9,47 / 8,33) differs from the plan's own figure (8,51 / 8,75) by 11 % and
5 %, so the user sees the real wall sums now.

### objektas_b — rooms 06 and 15

| nr | base | after |
|----|------|-------|
| 06 | konturo_ivertis / plotas nesutampa | matmenu_eilutes 14,32 m; _plotas_pastaba „Kontūro plotas 12,20 m², lentelėje 14,63 m²" |
| 15 | konturo_ivertis / plotas nesutampa | matmenu_eilutes 23,50 m; _plotas_pastaba „Kontūro plotas 34,02 m², lentelėje 44,00 m²" |

### Totals / rows (eval harness, `--totals-only --recompute`, €0)

```
billed_lines_mae_pct     57.525   (baseline 57,50 — within noise)
rows_within_10_share    9.02 %   (baseline 9,0 — unchanged)
overall_mae_pct         48.141
```

Per project `mae_pct`:

| | base † | after |
|-|-|-|
| objektas_a | — | 27,28 |
| objektas_b | — | 74,82 |
| objektas_c | — | 48,53 |
| objektas_d | — | 48,90 |
| objektas_g | — | 8,10 |
| objektas_h | — | 8,81 |

† per-project baselines were not captured on ca08704a. The aggregate billed-lines
MAE (`57,525` vs `57,50`) is within the gate's own rounding, as expected: the
only sąmata rows affected are grindjuostės, silikonavimas, hidroizoliacijos
juosta on five rooms across three projects (`objektas_h` 07/08, `objektas_b`
06/15, `objektas_a` 111) — and even on those the matched-to-table estimate the
old ladder offered was already close to the string sum. The real win is
elsewhere: Patikra no longer asks eleven times for walls the drawing writes.

### Reading scorecard

Unchanged, as required: 21/24 · 32/32 · 29/30 · 2/4.

### Geometry gate — re-pinned

- `objektas_a.perimetrai_sudeti`: `{}` → `{"111": 11.5}` (room 111 reads 4/4 wall
  strings against a 4,32 m² outline the table lists at 4,10 m²; the lane
  previously vetoed it on the area mismatch).
- `objektas_a.min_tusti_su_iverciu`: 11 → 10 (one room now reads itself).
- `objektas_h.perimetrai_sudeti`: + `{"07": 8.51, "08": 8.75}`.
- `objektas_h.min_tusti_su_iverciu`: 4 → 3 (two rooms moved out of blank).

Both scalar lowerings are quality improvements (more rooms read); the pinned
`sudėti` lists only grow.

## §4 — What still asks and why

After the fix, Patikra on objektas_a asks „Sienų ilgių iš plano nepavyko
perskaityti: 10 patalpos" — honestly, because the dimension reader does not
currently find every wall's string on that drawing. The founder is right that
the drawing writes them (1400 / 1200 / 3980 / 120 beside room 101). The cause is
a reader-side gap: the strings exist on the plan group but the reader is not
mapping them onto the room's walls. That is a separate task — the layout sheet
is one of the plan group's sheets, the painting plan another, and strings must
be read from every sheet and projected onto the base page.

What this fix guarantees: when the strings ARE read (as on objektas_h 07 / 08,
objektas_b 06 / 15, objektas_a 111), the area mismatch no longer vetoes them.

## §5 — Tests and suite

- `backend/tests/test_perimeters_from_strings_2026_10_29.py` (NEW) — three cases
  for the three ladder branches:
  (a) read despite area mismatch — strings sum, control agrees, no missing;
  (b) missing string → estimate (konturo_ivertis, matched to the table);
  (c) control mismatch → estimate.
- `backend/tests/test_dimension_sum.py` — the two tests whose premise was the
  OLD area-mismatch veto are rewritten to the new behaviour
  (`test_an_outline_off_the_table_still_lets_the_strings_decide`;
  `test_an_outline_off_the_table_offers_its_length_matched_to_the_table_area`
  now removes room 1's 3 m strings to force the estimate branch).
- `backend/tests/test_geometry_fixture_gate.py` passes on all three fixtures
  with the re-pinned expectations.
- `backend/tests/test_project_questions.py` — the two titles updated to the
  colon form (singular / plural).
- `backend/tests/test_golden_replay_extract_interior.py` — DOORS_ROWS grown by
  „Gluaistas sienoms (pradinis + baigiamasis)" and „Gruntas sienoms": the
  walls' Medžiagos labels now carry different kiekis in the frozen replay vs
  prod on objektas_h, because rooms 07 and 08 are READ now; the labels are on
  BOTH sides, the kiekis differs.
- Full backend suite: `5350 passed, 9 skipped, 22 warnings in 646.98s`
  (`/tmp/perim_suite.log`). Baseline before the fix was 5347 passed; the
  delta is exactly the three new synthetic tests in
  `test_perimeters_from_strings_2026_10_29.py`.

## Final

Nothing pushed. Commits are focused:

- `fix(perimetras): remove the table-area veto; the strings decide (G1 restated)`
- `test(dimension_sum): three ladder branches, before/after on objektas_a/h/b`
- `test(gate): re-pin objektas_a and objektas_h for G1-restated reads`
- `fix(klausimai): perimeter title with a colon so „11 patalpos" is no room 11`
- `docs(research): 2026-10-29 — perimeters from the written strings`
