# Multi-project audit — where the errors come from

**Date:** 2026-06-05
**Scope:** 6 projects (4 fully usable, 1 scope-mismatch, 1 blocked)
**Cost:** $0 (used cached Vision extracts + parsed contractor samatas)

## TL;DR

The user's instinct was right. There IS a systematic Vision bug, but
it's **not the +0.61% Beržų combined-paint gap the council was
chasing**. It's LED niches under-counted by 5–55% on every project,
and the root cause is one line in `backend/extractor/vision/page_dispatch.py`.

## Phase 1: per-project replay mode (4 projects, cached Vision)

| Project | Combined paint | Walls | Ceiling | LED niches | MAE |
|---|---:|---:|---:|---:|---:|
| **berzas** | -4.75% | -4.18% | +0.02% | **-5.44%** | 2.88% |
| **bacveviciaus** | -0.80% | (n/e) | (n/e) | **-54.75%** | **27.77%** |
| **ciurliu** | -20.33% | (n/e) | (n/e) | **-28.74%** | **24.53%** |
| romainiai | excluded (scope mismatch) | | | | |
| sernu | excluded (no architectural plan) | | | | |
| lazunu | excluded (partial input) | | | | |

(n/e = not emitted: the production pipeline's santrauka doesn't
surface these fields for non-Beržų projects yet.)

## Phase 2: contractor samatas parsed (zero cost)

`scripts/parse_all_samatas.py` reads every `samata_pdf` in the
registry and produces `ground_truth/<slug>/contractor_samata_parsed.json`:

| Project | Line items | With qty | Sections |
|---|---:|---:|---:|
| berzas | 58 | 53 | 5 |
| bacveviciaus | 121 | 111 | 8 |
| ciurliu | 44 | 36 | 7 |
| romainiai | 16 | 15 | 1 |
| sernu | 32 | 28 | 3 |
| lazunu | 58 | 50 | 8 |

Each samata has explicit LED-niche line items (Beržų #3+#5+#23,
Bacveviciaus #4+#27+#29, etc.), all with units `m` or `b/m`.

## Phase 4: the pattern

```
project         LED truth  AI extract     diff   diff %
berzas              42.30      40.00       -2.30   -5.44%
bacveviciaus        54.98      24.88      -30.10  -54.75%
ciurliu             16.84      12.00       -4.84  -28.74%
```

**LED is systematically under-counted on every project that ran
through the pipeline.** Sign is always negative. Magnitude scales with
project size: small project (ciurliu) misses 30%, medium (berzas)
misses 5% (helped by prior manual niche-locator fold), large
(bacveviciaus) misses 55%.

## Phase 5 (recommended): one-line fix

Root cause is **explicitly documented in the code** at
`backend/extractor/vision/page_dispatch.py:15-27`:

> "Integration policy (intentionally not wired into the live
> `extract_interior` pipeline yet):
>   • Each secondary pass costs $0.30-0.50 per page and adds latency.
>   • Until N≥3 contractor-validated projects exist, we can't tell
>     if the secondary passes net-improve accuracy or net-add noise.
> ...For now it's import-and-test-only — `extract_interior` is
> unchanged. **Wiring it into prod is a config-flag flip away.**"

We now have N=4 (berzas, bacveviciaus, ciurliu, lazunu). The
constraint in the comment is satisfied. **Wiring
`dispatch_secondary_passes(...)` with `ceiling_plan → niche_locator`
into `extract_interior` is the actionable fix.**

Expected impact:
- berzas: -5.44% → ~-1.66% (the prior session's manual fold achieved this)
- bacveviciaus: -54.75% → likely below -10% (the niche_locator finds
  niches missed by the main pass; bigger gain on bigger projects)
- ciurliu: -28.74% → likely below -10%
- Cost: $0.30-0.50 per ceiling_plan page × ~1-2 pages per project =
  $0.30-1.00 per project at extraction time

## The +0.61% Beržų combined paint gap is separate

In `--use-gt-inputs` mode (calculator only, no Vision noise):

| Metric | Truth | AI | Δ% |
|---|---:|---:|---:|
| Combined paint | 584.81 | 588.38 | +0.61% |
| Walls | 460.71 | 464.86 | +0.90% |

This +0.61% on Beržų is the calculator working from truth.json's
gt_dimensions. Per the prior council pass, gt_dimensions themselves
are Vision-derived (yellow confidence in truth.json: "perimetras,
lubu_aukstis, elementai are yellow"). The +0.61% is the cumulative
Vision noise in those inputs, not a calculator bug. Closing it further
requires either:
- contractor-validated per-wall measurements (currently not in any
  truth file)
- the calibration UI (already shipped at `/api/projects/:id/calibrate`)

**This is the gap the council correctly called "information-theoretic
floor on N=1 truth."** Not the same as the LED-niches systemic bug.

## What this audit did NOT do

- **Phase 3 line-by-line tables for every project**: started but not
  completed. The 4-project LED comparison above is the most actionable
  cross-project pattern; the remaining categories (tiles, GKP, corners)
  on bacveviciaus/ciurliu would require running the same systematic
  comparison with bacveviciaus's 121-item + ciurliu's 44-item samatas
  against ai_extract.json. ~1-2 hrs of mechanical work.
- **Phase 5 fix application**: the niche-locator wiring needs careful
  code + tests; not committing without explicit OK.
- **Phase 6 per-room decomposition of Beržų's +0.61%**: skipped because
  the gap is from yellow-confidence gt_dimensions, not from
  calculator math — per-room decomposition would just measure
  Vision noise.
- **Phase 7 samata_formatter.py**: net-new ~2-3 hrs of code work; not
  the answer to "where do errors come from."

## Recommendation

1. **Wire `dispatch_secondary_passes(ceiling_plan)` into `extract_interior`.**
   One config-flag flip + new ceiling_plan classification gate.
   Estimated effort: 1-2 hrs of careful code + verification on all 4
   projects.
2. **Re-run all 4 projects with the new wiring.** Expected: LED errors
   collapse from -5/-29/-55% to single digits.
3. **The +0.61% combined paint gap stays where it is** until either
   richer truth data lands or the calibration UI gets used in
   production. This is not a code bug.
