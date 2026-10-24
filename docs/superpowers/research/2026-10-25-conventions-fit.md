# Phase 2 — the conventions profile fitted to his sąmatos (rows ±10 %, in-sample and leave-one-out)

**Date:** 2026-10-25 · **Worker:** Opus 5.5 (manager review: Fable 5.1) · **Branch:** `v4/rules-fit` · **Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §1 R4/R5, §3.3, §4 Phase 2, §9 · **Baseline:** `2026-10-24-phase0-baseline.md`
**Zero API spend.** Cached extracts replayed through the live engine (`backend/rules/fit.py`, dead key, client constructor raises). **Codenames only; quantities only** — his prices are never read.
**Data:** `conventions_fitted.json` (replay-geometry mode, the headline) and `conventions_fitted_plain.json` next to this file. Reproduce: `venv/bin/python backend/rules/fit.py --mode replay` (≈ 3 min) and `--mode plain` (≈ 2 min).

## 0. Verdict

**Gate G2 is not reached and cannot be reached by conventions.** Rows within ±10 % (corpus mean of six projects, replay-geometry):

| | mean | a | b | c | d | g | h |
|---|---|---|---|---|---|---|---|
| engine before Phase 2 (one hidro row, legacy rounding) | **27,4 %** | 41,5 | 9,0 | 22,2 | 36,0 | 35,0 | 20,8 |
| profile defaults (two hidro rows — founder) | **26,2 %** | 39,6 | 8,1 | 19,4 | 34,0 | 35,0 | 20,8 |
| best in-sample profile (coordinate descent) | **27,9 %** | 37,7 | 9,0 | 22,2 | 34,0 | 35,0 | 29,2 |
| leave-one-out (fit on five, score the sixth) | **25,2 %** | 35,8 | 8,1 | 19,4 | 32,0 | 35,0 | 20,8 |
| per-project scope oracle (on top of the in-sample profile) | **28,0 %** | 37,7 | 9,9 | 22,2 | 34,0 | 35,0 | 29,2 |
| G2 target | ≥ 50 % in-sample, ≥ 40 % LOO | | | | | | |

Plain mode (no geometry replay): before 26,1 % · defaults 24,8 % · in-sample 26,0 % · LOO 23,7 % · scope oracle 28,6 %.

The leave-one-out number is **below the defaults** in both modes: the combination the descent finds on five projects (kampai `vertikalus_lubos`, Rotband 50 %, reveals without passages) does not carry to the sixth. No parameter except the aperture threshold shows a held-out gain (§2). The profile defaults are therefore **left as they were** (plus the two founder decisions); nothing in this branch changes a default on the strength of the fit.

**Why G2 is out of reach here (the blocker, measured, engine before Phase 2):** of his 294 scored rows, **138 (47 %)** are rows for which we emit no comparable quantity at all — `missing` (no app family / blank checklist row / unit mismatch / he splits finer) or `unmapped` (no concept covers his wording). Per project the share of his rows we can even compare: a 64 %, b 32 %, c 69 %, d 66 %, g 70 %, h 63 % (mean ≈ 61 % — the ceiling of the corpus-mean metric if every comparable row were exact). Reaching 50 % would need ≈ 82 % of the rows we do emit to land within ±10 %; today 70 of 156 (45 %) do. The plan's expectation that scope and granularity carry most of the gain does not hold on this instrument, for two measured reasons: (1) **granularity is invisible to the scorecard by construction** — `row_scorecard` already sums our wall + ceiling paint rows (and all our tile rows) against his single row, so merging them cannot add a hit, and under the frozen concept table a merged paint label is even read as unmapped (b −1, g −1); (2) **scope switches only remove quantity** — the greedy per-room oracle (room × {apdaila, grindys, plyteles}, ceilings „ne mūsų", corner bead) finds +1 row on b and +2 on h (replay), +2 on a and +1 on c, g, h (plain). His misses are rows we do not produce (tile-clad reveals and niches, large-format / mosaic, extra skim coat, demolition, GKP extras left blank, 36 ventilation lines on b), plus way-off counts (fixtures, diffusers, lights) — neither a threshold nor a scope switch moves those.

## 1. What was built (four commits)

1. `e8a27c64` — **mechanical split, zero behaviour.** `backend/rules/conventions.py` (every named constant + a `CONVENTIONS` registry with `source` / `fitted_on`), `rules/rows.py` (paint litres, GKP sheets, slope factor, stairwell walls, `calc_totals`, paint coverage), `rules/rounding.py` (R4). `universal_rules` re-exports every name as the same object. Proof: suite green, the four eval passes and `reading_scorecard` byte-identical to `togal-v2` (97f8a9d5); re-proven on the merged head with 18a99a8a + f1fb65a3 (passes identical; step 3c untouched — the merge did not touch `universal_rules.py` after the split base).
2. `8615040e` — **the `lt_rangovas` profile** (`LT_RANGOVAS`, Prielaidos override `_overrides.profilis`, accepted by `/api/recompute-quantities` and `/recompute-interior`): `aperture_no_deduct_max_m2`, `skirting_door_deduct_m`, `skirting_waste`, `wet_room_markers`, `hidro_rows` (**two by default — founder**), `rounding` (R4 at the row boundary), `kampai` (manager's addition, §4).
3. `ec1869ca` — **scope + granularity**: `reveals_scope` (the `_angokrasciu_apimtis` lever as a profile default; his Prielaidos choice wins), `scope_defaults` (the `_apimtis` shape; `scope.with_profile_defaults` fills the keys the project did not choose at all three entry points), `paint_rows` / `tile_rows` (`split` default | `merged`, applied at row generation, ledgers carried). Built on `extractor/scope.py` and the existing reveals choice; `samata_template.py` (his layout, „Jūsų eilutės") untouched.
4. this commit — `backend/rules/fit.py` + this report + `conventions_fitted*.json`.

## 2. Each parameter: chosen value, LOO, projects that disagree

Replay-geometry mode unless noted. „±10 % per project" = share of his scored rows within ±10 % with only that parameter changed (others at the defaults).

| parameter | default (kept) | in-sample best | LOO (one parameter at a time): folds choosing / held-out vs default | projects that disagree | data can decide? |
|---|---|---|---|---|---|
| `aperture_no_deduct_max_m2` | 1,0 | **3,0** (b +1 row, d +1; plain also a +2) | 6/6 folds choose 3,0; held-out never worse, better on b, d (plain: a, b, d) | none | **weakly yes — 3,0** (≤ 2 rows per project; see note) |
| `skirting_door_deduct_m` | 0,85 | tie (0,85 / 0,90 / drawn identical buckets) | default kept 6/6 | — | no — 1–5 % moves, never crosses a ±10 % bucket |
| `skirting_waste` | 1,10 | tie | default kept 6/6 | — | no — d's row is −14 % gross, −22 % net; b's +121 % is room scope |
| `kampai` | visi | `vertikalus_lubos` (c +1, h +1, a −1, d −1) | 4/6 folds pick a vertical convention; held-out: a −1, d −1, others equal | a, d against c, h | **no — and today's `visi` is what he writes (§4)** |
| `reveals_scope` | windows + ext. doors + passages | windows + ext. doors (h +1) | 5/6 choose that; held-out equal everywhere | none on the bucket | no (§5) |
| `rotband_dalis` (scope default, 30 %) | 30 % | 30 % (every other share loses a's row) | plain: 5/6 folds choose 50 %, held-out equal | — | no — at 30 % his Rotband rows sit from −47 % (h) to +78 % (c): no single share fits |
| `hidro_rows` | **two (founder)** | one (+1 row on a, b, c, d) | not fitted (founder decision) | — | yes — the data say one (§3) |
| `rounding` | row_boundary | tie | not fitted | — | n/a — changes 0 of 583 corpus row quantities |
| `paint_rows` | split | split (merged: b −1, g −1) | not fitted | — | the instrument cannot see it (§0) |
| `tile_rows` | split | split (merged: a −1, b −1, g −2) | not fitted | — | the instrument cannot see it |

**Note on the aperture threshold.** 3,0 m² is the founder's own default in plan §1 and the only parameter whose held-out effect is never negative. The gain is small (b and d one row each; plain a two rows) and comes from wall paint moving 1–5 % across the ±10 % edge, so it is exactly the kind of signal phase 0 warned about (residuals on b and c are still 15–20 % from other causes). Brief: the default stays 1,0 with 3,0 documented; **recommendation to the founder: flip to 3,0** if he wants the default to follow his own rule — the data do not contradict it on any project.

## 3. Waterproofing under the two-row default (founder override, cost made visible)

| project | his row | one-row form (`hidro_rows = one`) | two-row default |
|---|---|---|---|
| objektas_a | 2 vnt | 2 vnt ✓ | floor m² + tape m — his vnt row **missing** |
| objektas_b | 3 vnt | 3 vnt ✓ | missing |
| objektas_c | 2 vnt | 2 vnt ✓ | missing |
| objektas_d | 1 vnt | 1 vnt ✓ | missing |
| objektas_g | 39,50 m² | 51,09 m² (vnt row's m² detail) way off | missing (our rows are named as the founder named them, which the frozen concept table does not map; floor-only m² would be 17,67 + no shower walls — way off anyway) |
| objektas_h | vnt, no quantity | — | — |

Cost: **−4 rows**, rows ±10 % corpus −1,3 pp (replay 27,4 → 26,2 %, plain 26,1 → 24,9 %); € share −0,7 pp. Gate lines moved by commit 2 and attributable only to this row: plain rows a 37,7 → 35,8, b 9,9 → 9,0, c 22,2 → 19,4, d 36,0 → 34,0; replay a 41,5 → 39,6, b 9,0 → 8,1, c 22,2 → 19,4, d 36,0 → 34,0 (`--rows --gate` prints WORSE on a, c, d). The totals headline (22,60 % plain / 22,92 % replay) is unchanged — waterproofing is not a headline family. Also a consequence to know: the shower-zone wall m² that the one-row form carried (`_detail_m2`) is not in the two-row form; the founder's rule bills floor + corner tape only.

## 4. Kampai — which convention reproduces him (manager's addition)

His „Dažymo kampų montavimas" row against Σ room perimeter: **a 2,71×, b 2,60×, c 2,27×, d 2,51×, h 2,75×** — and **g 1,04×** (an *atliktų darbų aktas*, „Glaistymo kampų statymas"). So the 2,5–3,4× seen on the contractor's own projects is **his convention, not our error**: on the five sąmatos he bills ≈ 2,6× the perimeter too.

Residuals per convention (ours vs his, replay; vertical conventions count corners off the wall outline where one exists — a, g, h):

| convention | terms | a | b | c | d | g | h |
|---|---|---|---|---|---|---|---|
| **visi** (today) | perimeter + inner vertical + outer + opening edges + partition junctions | **−3,6 %** | −19,1 % | +32,2 % | **+6,7 %** | +135,5 % | +14,6 % |
| vertikalus_lubos | perimeter + vertical corners | −23,0 % | −36,8 % | **+2,8 %** | −23,7 % | +105,2 % | **−4,2 %** |
| vertikalus | vertical corners only | −55,2 % | −60,6 % | −41,3 % | −63,5 % | **+8,8 %** | −38,5 % |
| isoriniai_angos | outer corners + opening edges | −71,3 % | −82,3 % | −70,6 % | −69,6 % | −19,4 % | −65,5 % |
| isoriniai | outer vertical corners only | −96,9 % | — | — | — | −83,3 % | −95,2 % |
| tik_lubos | wall–ceiling junction only | −67,8 % | −76,3 % | −55,9 % | −60,2 % | **−3,6 %** | −65,7 % |

Plain mode gives the same picture (visi: a −10,4, b −19,3, c +32,2, d +6,7, g +135,7, h +6,0 %). **Today's `visi` reproduces his sąmatos best** (a, d within ±10 %, h within 15 %); the outer-corners-only convention is 75–97 % under him everywhere. g is the outlier and is matched by `tik_lubos` (−3,6 %) or `vertikalus` (+8,8 %) — a different document kind for a different crew; the profile parameter lets that project say so. Outer corners from the outline are few (a 15,2 m in total) — the drawings here are mostly convex rooms. Default kept at `visi`; the parameter is ready for a contractor who bills bead on outer corners only, and the evidence sentence (`confidence.KAMPAI_REASON`) still describes the default formula — it should name the convention once one is chosen (follow-up).

## 5. Reveals scope — which openings he bills

His „Angokraščių apdirbimas GKP" (a 89,39 · b 94,02 · c 34,53 · d 31,80 · h 63,23 m) against each scope (W = windows, E = exterior doors, P = passages, I = interior doors):

| scope | a | b | c | d | h |
|---|---|---|---|---|---|
| W E P (default) | +17,3 | +22,1 | +7,7 | −6,4 | +21,6 |
| W E | +17,3 | +22,1 | +7,7 | −6,4 | **+2,5** |
| W P | −18,5 | **−0,8** | −7,0 | −39,7 | −18,9 |
| E P I | −10,4 | −7,3 | −13,1 | −34,6 | +25,2 |
| W E P I | +71,1 | +91,9 | +79,8 | +25,8 | +87,2 |

No scope reproduces all five; interior doors are clearly not in his row (+26…+92 % with them). a's +17,3 % (the perimeters-merge move from +0,79 %) is not passages (a has none) — it sits between „windows + exterior doors" (+17,3 %) and „windows only" (−18,5 %): either he bills only some of a's exterior doors or the drawn windows are wider than his. **The data cannot decide** between „with exterior doors" and „without" (a, c, d prefer with; b prefers without); the default stays.

## 6. Per-project scope (the oracle — his choices on one job, not a default)

Greedy room × family switches that raise that project's own ±10 % count, on top of the in-sample profile:

| project | replay: rows ±10 % → with oracle scope | switches | plain: → | switches |
|---|---|---|---|---|
| objektas_a | 20 → 20 | — | 21 → 23 | tiles off in 105 (garage) and 111 |
| objektas_b | 10 → 11 | finishing off in 15 | 11 → 11 | — |
| objektas_c | 8 → 8 | — | 7 → 8 | corner bead outer only |
| objektas_d | 17 → 17 | — | 18 → 18 | — |
| objektas_g | 7 → 7 | — | 6 → 7 | tiles off in 07 |
| objektas_h | 7 → 7 | — | 5 → 6 | finishing off in 02 |

These are what `_apimtis` already lets him set per project; they cannot be validated leave-one-out and are not written into any default.

## 7. What the data cannot decide (frank list)

- **Aperture threshold:** 3,0 is never worse and slightly better, but by one or two rows on two or three projects whose wall paint still carries 15–20 % residuals from heights, perimeters and room scope. A weak signal, not a fit.
- **Skirting:** fixed 0,85 / 0,90 / drawn widths and net vs +10 % never move a row across ±10 %; which rooms he skirts (20–60 %) dominates and is not identifiable without his per-room notes.
- **Rotband share:** at the 30 % default his rows sit −47 % (h) … +78 % (c) from ours; one global share cannot fit and LOO shows no held-out gain.
- **Reveals scope:** b disagrees with a, c, d on exterior doors.
- **Kampai on g:** one *aktas* bills the wall–ceiling junction only; one document is not a convention.
- **Waterproofing:** decided by the founder against the data (6/7 one vnt row).
- **Granularity:** invisible to the row scorecard; only a founder/contractor walk can say whether merged rows read better (his layout already exists in „Jūsų eilutės").
- **G2 itself:** six projects, all in-sample for months of engine work, one contractor. The LOO numbers are the only out-of-sample statement in this report and they say the profile, beyond its defaults, does not generalise yet.

## 8. Checks (merged head)

- Backend suite (`SAMATU_AUTH_DISABLED=1`), 0 failures on every commit: commit 1 5556 passed / 57 skipped (baseline 5543); commit 2 5582; merged head 5604; commit 3 5613; commit 4 see the commit message.
- Four eval passes: commit 1 and the merge byte-identical; commit 2 moves only the rows listed in §3; commit 3 identical.
- `scripts/reading_scorecard.py`: identical on every commit (vidaus durų poros 21/24, lauko durys 32/32, langai 29/30, praėjimai 2/4).
