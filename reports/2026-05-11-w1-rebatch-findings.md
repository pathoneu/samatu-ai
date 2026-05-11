# W1 re-batch findings — mixed result, honest writeup

**Date:** 2026-05-11 (afternoon, after the first 2026-05-11-w1-baseline.md)
**Cost:** ~$5 (second batch) + ~$2 prior single-extraction tests = **~$12 total session API spend**

## What changed since first batch

Two prompt fixes shipped between batches:
1. **plotas_m2 fallback chain non-skippable** — fail-soft default ≥ 15 m² beats silent zero.
2. **Broader ceiling-height format table** in the lubu_aukstis_m section
   (listed 7 explicit formats: `+X.XXX`, `H2400`, "Svarus lubų aukštis: 300cm", etc.)

## Re-batch result

| PDF | Rooms | Plotas (was) | Plotas (now) | `by_nr` (was) | `by_nr` (now) | Δ |
|-----|------:|------:|------:|------:|------:|---|
| projektas_1_breziniai | 15 | 180.0 | 180.0 | 0 | 0 | — |
| projektas_3_breziniai | 20 | 267.7 | 267.7 | 0 | 0 | — |
| projektas_4(1)_breziniai | 13 | **0.0** | **245.0** | 0 | 0 | ✅ plotas fixed |
| projektas_4(2)_breziniai | 3 | 18.5 | 16.5 | 0 | 0 | — |
| vidaus_apdaila | 11 | 165.6 | 165.6 | **11** | **0** | ❌ REGRESSION |

## Verdict

- ✅ `plotas_m2 = 0` bug **fixed across the corpus** — projektas_4(1)
  jumped from 0 m² → 245 m² (the actual sum of room areas). Backend
  no longer outputs zero-quantity pozicijos.
- ❌ **The ceiling-format table iteration caused regression on the
  previously-working case (vidaus_apdaila).** The verbose 7-row table
  appears to have signalled "describe in detail" to Vision, which then
  reverted to narrating heights in `warnings[]` text instead of
  structuring them.

Vision IS still seeing the heights — every PDF now has a clear warning
line:
- vidaus_apdaila: "Svetainė/virtuvė 102 turi aukštas lubas +3400mm; garažas 105 +3000mm"
- projektas_1: "Lubų aukštis ~2.80m bazinis, svetainėje/valgomajame ~3.00m"
- projektas_3: "aukštos lubos +3.00m 1 aukšte"
- projektas_4(1): "Pjūvis (sekcija) nerasta — lubų aukščiai defaultinti į 2.82m"
- projektas_4(2): "Brėžinių komplekte nėra eksplikacijos lentelės"

The signal IS there, it's just not structured.

## Action taken (this commit)

Partial revert: kept the **non-skippable plotas_m2 fallback** (clear win)
+ reverted the verbose 7-row ceiling-format table back to a short
"apply same rule to ALL height formats" instruction (less likely to
suggest a "describe in detail" response style).

**Did NOT re-batch a third time** — credits hit zero during the second
batch (projektas_1 zoom-pass calls failed mid-run with "credit balance
too low"). User must refill before next API spend. Net session API
spend: ~$12.

## Honest open issues

1. **Vision narrates instead of structures** for ceiling info on 4/5
   PDFs. The structural prompt phrasing that works (vidaus_apdaila pre-iteration)
   has a narrow window — too forceful and Vision describes; too soft
   and Vision skips. Need a third iteration that emphasises STRUCTURE
   without prescribing format permutations. Defer until next API budget.

2. **`projektas_1` zoom-pass crashed** after credit exhaustion. Result
   includes per-room data but no zoom-corrected dimensions for the
   last 5 rooms. Re-running once credits refill should fix.

3. **A Python-side warning parser** could catch the structured-looking
   tokens in narration ("Svetainė/virtuvė 102 +3400mm" matches a
   regex). Deferred — adds complexity, brittle to LLM phrasing
   changes. Better: get the prompt right.

## Recommended next steps

Before any more API spend:
1. Refill Anthropic credits.
2. Take one PDF (vidaus_apdaila) and iterate the ceiling prompt on it
   alone (~$1 per attempt vs ~$5 for full batch). Once it consistently
   structures `lubu_auksciai_by_nr` across 3 consecutive runs, run the
   full batch once for verification.
3. Add a guardrail: post-Vision parser scans `warnings[]` for known
   marker patterns; if found, raises a `data_in_warning_text` lint
   error so we catch this regression deterministically in tests.

## What stayed clean

- Tests: 480 passed, 0 regressions.
- `plotas_m2 = 0` fixed for projektas_4(1).
- vidaus_apdaila first-run capture (11/11 per-room ceilings) is
  preserved in `reports/baseline-pre-revert/` — sanity check the
  partial revert against next single-PDF run.
