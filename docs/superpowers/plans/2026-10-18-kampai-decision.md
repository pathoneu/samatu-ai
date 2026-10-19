# Kampai — two decisions for the founder (v3 W5-E, E10)

Nothing here changes a default. Two choices decide how many metres the „Dažymo kampų montavimas" row bills,
and both are conventions of the contractor, not standards we can pick for him. The numbers below were
measured before (sources at the end); the „today" column is the plain eval of 2026-10-18 on togal-v2 @
bce583c. Codenames only. Every percentage is the engine's row against the contractor's own kampai row.

## Decision 1 — the default: „su vidiniais" or „tik išoriniai"

What it means (CLAUDE.md §1.3 and §8.14):
- **su vidiniais** (today's default) — every room's concave corners get bead too (4 × room height for a
  room without a read outline), plus opening reveals, partition ends and outer corners.
- **tik išoriniai** — only outer corners, opening reveals and partition ends. §8.14 says metal bead belongs on
  outside corners only and inside corners take cheaper paper tape; §1.3 says inner corners typically need
  no bead.

He can already choose per project („Ką skaičiuoti" → kampai, stored as `_apimtis.kampai`). The question is
only what a NEW project starts with.

| objektas | his m | su vidiniais (2026-09-10) | tik išoriniai (2026-09-10) | today, su vidiniais (plain eval) |
|---|---:|---:|---:|---:|
| a | 493,35 | 437,70 (−11 %) | 333,70 (−32 %) | −10,43 % |
| b | 580,54 | 445,66 (−23 %) | 344,14 (−41 %) | −19,27 % |
| c | 201,86 | 266,89 (+32 %) | 199,21 (−1 %) | +32,22 % |
| d | 123,59 | 131,87 (+7 %) | 86,75 (−30 %) | +6,70 % |
| g | 134,72 | 299,78 (+122 %) | 198,26 (+47 %) | +135,73 % |
| h | 412,94 | 437,78 (+6 %) | 324,98 (−21 %) | +6,01 % |

Summary of the 2026-09-10 run: „su vidiniais" median |error| 17 %, 2 of 6 within ±10 %, 4 of 6 within
±25 %; „tik išoriniai" median 31 %, 1 of 6 within ±10 %, 2 of 6 within ±25 %. A later H-only measurement
(2026-10-16): `tik_isoriniai` takes H from 485,6 to 372,8 m, −9,7 % against his 412,94.

Reading: on these six contractors' rows „su vidiniais" is closer more often; objektas_c is the one project
whose contractor clearly bills outer corners only, and the per-project choice covers it. objektas_g's
overshoot is its own problem (a duplicate room alone is about 26 m), not a reason to flip the default.

**Options**
1. Keep „su vidiniais" (recommended by the numbers above; nothing to do).
2. Flip to „tik išoriniai" (matches §1.3/§8.14 literally; worse on 4 of the 6 rows measured). Needs one
   engine change behind the eval gate.
3. Ask once per project in Patikra („Ar kampų profiliai statomi ir vidiniuose kampuose?") with the
   current default as the proposal — no default decided, one more question for him.

## Decision 2 — corners counted from the room outline

An experiment (`eval_harness.py --experiment outline-corners`, recompute only, not shipped; env
`SAMATU_EXPERIMENT_CORNERS_FROM_OUTLINE`) counts every outlined room's corners off its outline instead of
the 4-corner default.

| objektas | kampai error, off (replay geometry) | on | corner metres off → on |
|---|---:|---:|---|
| a | −6,11 % | +0,05 % | 463,19 → 493,59 m |
| g | +135,55 % | +169,04 % | 317,33 → 362,45 m |
| h | +14,57 % | +25,50 % | 473,12 → 518,24 m |
| b, c, d | unchanged | unchanged | no wall outlines |

Billed-lines headline (replay) 22,88 % → 24,12 %. Reading: the outline rule closes objektas_a exactly and
makes g and h worse, so it is not the lever for the kampai gap. It also counts more corners than the
4-corner default on every outlined room, which only moves the number further from a contractor who
bills outer corners only.

**Options**
1. Leave the experiment off (recommended by the numbers above).
2. Ship it only together with „tik išoriniai" (Decision 1, option 2) — never measured as a pair; would need
   a fresh €0 run of the four eval passes before anyone decides.

## Sources

- `docs/superpowers/plans/2026-09-05-generalization-plan.md` § „Kampai default — measured 2026-09-10".
- `docs/superpowers/plans/2026-10-16-togal-v2-program.md`, open decision „corners from outlines".
- Today's column: `eval_harness.py --totals-only --recompute --gate` on togal-v2 @ bce583c (billed lines
  22,60 %, GATE OK).
