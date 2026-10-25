# Eval re-base: the person's answers — 2026-10-25

Branch `v4/eval-answers` from `togal-v2` @ 94528f65 (Phase 3b, LANE_VERSION 18). Worker: Sonnet 5.5. Not merged. No paid
call. `--accept-baseline` was NOT run. Codenames only; no € figures.

## Verdict in one paragraph

The layer is built and wired through the app's own path (below). **It recovers nothing**, and that is the finding: the
truth files hold exactly one legitimate ceiling-height answer (objektas_a, the contractor's own row labels), and even
giving EVERY room of EVERY project a 2,8 m answer (a sensitivity run, not a baseline) leaves the plain-pass rows ±10 %
at 10,8 %. After Phase 3b the wall/corner/skirting/tile rows are blocked by **perimeters first** (and GKP ceilings by a
ceiling-plan altitude); a height answer unblocks a row only when its perimeters are already drawn, which on the frozen
extracts is rare (plain pass) or has no height to answer (replay pass: the plan-text lane already reads objektas_a's
heights). The instrument now reports the real gaps by cause; the number that fell (26 % → 11–12 %) is mostly
perimeters (Phase 3c), GKP altitudes, and counts nobody has read — not heights.

## 1. Inventory — what the truth files hold that a person would type

Read: `truth.json`, `reading_truth.json`, `contractor_samata_parsed.json` (all six corpus projects).
Not read, by rule: `ai_extract.json`, `truth.json › gt_dimensions` (objektas_a's only per-room heights/perimeters; its
own `notes_for_evaluator` says they are "Vision-derived, not contractor-validated").

| project | ceiling height (project) | per room | room perimeters | other typed-in answers |
|---|---|---|---|---|
| objektas_a | **2,8 m** — his row labels „GKP … karkasą 2,8m aukštis“ (row 1); a second label states 3,4 m (row 2) with 62,82 m² of ceilings but **no rooms** → recorded, not applied | none | only `gt_dimensions` (Vision-derived → excluded) | per-room tile/skirting areas and `walls_paintable_m2` for room 105 (`gt_per_room`) are **outputs** (rows of his sąmata), not inputs → excluded |
| objektas_b | none (only the threshold „virš 3m“) | none | none (`gt_dimensions` empty) | outputs only |
| objektas_c | none | none | none | outputs only |
| objektas_d | none in the truth files (the drawing prints 2820 / 2390 / 2510 — that is the app's own reading, not an answer) | none | none | outputs only |
| objektas_g | none | none | none | the drawing's legend states 220 m² of walls (an output) |
| objektas_h | none | none | none | the designer's „Sienų dažai 320 m²“ (an output) |
| `reading_truth.json` (a, d, g, h) | — | — | — | doors, windows, passages per room: counts the app reads itself; not a number a person types when asked, and they feed the openings, which are not blocked |

What was rejected and why: a Rotband share, a rubbish volume, a fixture count, a tile area — each is itself a row (or
an aggregate of rows) of his sąmata; supplying it as an "answer" makes the row a copy of the answer key (the harness
already prints "copied, not measured" for those). Perimeters exist per room only in `gt_dimensions` (model-derived).

So `scripts/eval_answers_from_truth.py` writes: a → `lubu_aukstis_m: 2.8`; b, c, d, g, h → `null` (no answer: what
stays blank is a real gap, as the founder asked). Files: `ground_truth/objektas_*/answers.json`.

## 2. What was built

- `eval_harness.py`: `load_answers`, `apply_person_answers`, `_record_gaps`, `print_answers_block`, `--no-answers`.
  Applied in `_rerun_deterministic_tail` (so in the plain and the `--replay-geometry` pass, under `--recompute`),
  after every height producer and before the per-room recompute.
- **Same path as the app:** `api.recompute_quantities._apply_assumption_edits(rooms, {"lubu_auksciai": {nr: m}})` (what
  the Prielaidos per-room edit posts to `/api/recompute-quantities`; room height with source `user_override`) and
  `_overrides.lubu_auksciai[nr]` (what the endpoint stores and `row_provenance.own_heights` reads, so the rows class the
  height `drawing` = „the person's entry“). Applied only to rooms whose height is not `drawing` class by the rows' own
  test; a per-room entry wins over the project value; values outside 1,5–8 m are ignored (the panel's range).
- New output block „Asmens atsakymai ir tikri trūkumai“ after the rows table (both `--rows` and `--totals-only`, under
  `--recompute`): per project answers supplied, blank rows by cause, and his `missing` rows by reason class.
- `ground_truth/_schema_v2.md` documents `answers.json`.
- Not applied to the frozen (non-`--recompute`) pass: it has no tail to apply it to.

## 3. The four passes, before → after

(`--rows --recompute --gate` and `--totals-only --recompute --gate`, plain and `--replay-geometry`. "Before" = this
branch's base, run without the layer; "after" = with it. Gate output unchanged: rows 5 regressions beyond 1 pp,
totals 36 plain / 37 replay beyond 0,25 pp — all the Phase 3b blanks plus, on replay, the known false-FAIL lines.)

| pass | metric | before | after |
|---|---|---|---|
| rows plain | corpus mean ±10 % (n=6) | 10,8 % | 10,8 % |
| rows plain | € ±10 % | 15,0 % | 15,0 % |
| rows replay | corpus mean ±10 % | 12,1 % | 12,1 % |
| rows replay | € ±10 % | 19,6 % | 19,6 % |
| totals plain | billed MAE (32 observations) | 69,48 % | 69,48 % |
| totals plain | legacy MAE a–d / g,h | 40,32 % / 8,67 % | 40,32 % / 8,67 % |
| totals replay | billed MAE | 57,77 % | 57,77 % |
| totals replay | legacy MAE a–d / g,h | 46,01 % / 8,67 % | 46,01 % / 8,67 % |

Note: the Phase 3b hand-off quotes rows 12,0 % and totals 69,5 %; this worktree reproduces 12,1 % on the replay pass
and 10,8 % on the plain rows pass (totals 69,48 % matches). The plain-pass difference is not explained by the layer
(the layer supplies nothing that changes a row).

Per project, rows ±10 % (identical before and after, plain | replay):

| project | answers supplied (plain / replay) | rows ±10 % plain | rows ±10 % replay |
|---|---|---|---|
| objektas_a | 6 / 0 (the plan-text lane reads a's heights on replay) | 3,8 % | 7,5 % |
| objektas_b | 0 / 0 | 2,7 % | 1,8 % |
| objektas_c | 0 / 0 | 5,6 % | 5,6 % |
| objektas_d | 0 / 0 | 10,0 % | 10,0 % |
| objektas_g | 0 / 0 | 30,0 % | 35,0 % |
| objektas_h | 0 / 0 | 12,5 % | 12,5 % |

**Sensitivity (an upper bound, not a baseline, nothing committed):** every project given a project height of 2,8 m
as if a person had typed it (6 / 15 / 6 / 2 / 9 / 11 rooms answered on the plain pass):
plain pass rows ±10 % per project a–h 3,8 / 2,7 / 5,6 / 10,0 / 30,0 / 12,5 %, mean 10,8 % — **unchanged**; replay
pass 7,5 / 1,8 / 5,6 / 10,0 / 35,0 / 16,7 %, mean 12,8 % against 12,1 % — **one row** (objektas_h, +4,2 pp, € ±10 %
2,0 → 8,6 %). Heights are not what blocks the rows; even invented for every room they buy +0,7 pp.

## 4. The blank rows that remain, by cause (after answers)

Blank rows per project (rows with `_kilme == blank`; plain | replay) and the cause the reason sentence names:

| project | blank plain / replay | no drawn perimeter | no written height | no ceiling-plan altitude | plumbing / electrical counts not read | work in text/elevations, no reader | ventilation | shares/counts the drawing does not state | LED length | doors frame type | site items |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a | 55 / 38 | 12 / 0 | 0 / 0 | 3 / 0 | 24 / 24 | 7 / 7 | 2 / 2 | 2 / 2 | 2 / 0 | 1 / 1 | 2 / 2 |
| b | 59 / 48 | 11 / 2 | 3 / 3 | 3 / 3 | 24 / 24 | 7 / 7 | 4 / 4 | 2 / 2 | 2 / 0 | 1 / 1 | 2 / 2 |
| c | 48 / 48 | 8 / 8 | 2 / 2 | 2 / 2 | 22 / 22 | 7 / 7 | 1 / 1 | 2 / 2 | 2 / 2 | 0 / 0 | 2 / 2 |
| d | 55 / 55 | 13 / 11 | 0 / 2 | 2 / 2 | 25 / 25 | 7 / 7 | 4 / 4 | 2 / 2 | 0 / 0 | 0 / 0 | 2 / 2 |
| g | 36 / 36 | 6 / 6 | 1 / 1 | 2 / 2 | 9 / 9 | 7 / 7 | 4 / 4 | 2 / 2 | 2 / 2 | 1 / 1 | 2 / 2 |
| h | 43 / 32 | 11 / 0 | 1 / 1 | 2 / 2 | 11 / 11 | 7 / 7 | 4 / 4 | 2 / 2 | 2 / 2 | 1 / 1 | 2 / 2 |

(Counts parsed from the harness block of the four `after` runs; 0 where a cause is absent. "other" is empty on the corpus.)

His rows that are `missing`, by reason class (plain | replay):

| project | our row is blank | admitted gap (no family emits it) | granularity | no row of ours |
|---|---|---|---|---|
| a | 39 / 31 | 4 / 4 | 1 / 0 | 4 / 6 |
| b | 32 / 28 | 36 / 36 | 10 / 10 | 5 / 7 |
| c | 18 / 18 | 4 / 4 | 0 / 0 | 2 / 2 |
| d | 23 / 23 | 4 / 4 | 1 / 1 | 2 / 2 |
| g | 2 / 2 | 5 / 5 | 1 / 1 | 1 / 1 |
| h | 10 / 10 | 5 / 5 | 1 / 1 | 0 / 0 |

Reading it: the dominant cause of "our row is blank" is **no drawn perimeter** on the plain pass (frozen extracts hold
only Pass-1 perimeters) — the replay pass removes it for a and h (outlines from the geometry lane) and the rows then
move (a 3,8 → 7,5 %, a billed Kampai −100 → −20,6 %). The cause that survives on every project and both passes is
**plumbing / electrical counts not read** (22–26 blank rows per project, Phase 3c readers) and the 7 rows that describe
work written in text or elevations with no reader. Heights as a cause: 0–3 rows per project, none answerable from the
truth files except objektas_a's.

## 5. Tests

`backend/tests/test_eval_person_answers.py` (7): the answer goes through `_apply_assumption_edits` with exactly the
endpoint's edit shape (spy) and lands in `_overrides.lubu_auksciai`; read-from-drawing rooms are untouched, a model
figure is replaced; the answer makes the height `drawing` class; a per-room entry wins and an out-of-range value falls
back; a project without the file is byte-identical; a file with no height supplies nothing; gaps are recorded by cause;
the generator ignores `ai_extract.json` and `gt_dimensions`. With the existing eval and golden-replay tests
(`test_eval_gate`, `test_eval_harness`, `_experiments`, `_honesty_2026_10_05`, `_drift_row`, `_replay_geometry`,
`test_golden_replay_extract_interior`, `_stub`): 93 passed.

## 6. For the manager

1. **Do not read the instrument's silence as "the re-base worked".** With the only truth-supplied answer the numbers do
   not move; the 26 % → 11–12 % drop is not a height artefact. The honest baseline today is the Phase 3b number plus
   the new gap block. Accept it (or not) knowing that.
2. If a real person's answers are wanted for b, c, d, g, h, they must be typed by one (the contractor, or the
   founder reading each drawing): add them to `answers.json` (`lubu_aukstis_m`, `lubu_auksciai`) with a `saltiniai`
   line saying where. The harness already applies and reports them. Nothing in the truth files can stand in.
3. The binding gap is Phase 3c: perimeters on the plain pass (outline reader/strings), GKP ceiling-plan altitudes,
   plumbing/electrical counts. A height answer then matters for 1–3 rows per project (the replay sensitivity shows
   +0,7 pp at most on today's lanes).
4. `answers.json` is **tracked** (not gitignored): `truth.json`, `ai_extract.json` and `contractor_samata_parsed.json`
   are tracked too (only `*_priced.json` and `results_rescored*.json` are ignored), the file holds a codename and a
   height, and a fresh checkout needs it for the gate. One line in `.gitignore` flips this if you prefer.
5. Worktree setup note: the `ground_truth/*/ai_extract.json` etc. are tracked; the gitignored pieces the eval needs
   (`contractor_samata_priced.json`, the fixture PDFs, `.confidential-terms`) were copied from the main checkout.
