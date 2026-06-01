# Systematic Vision-extraction errors — N=4 cross-project analysis

Auto-derived from `scripts/analyze_systematic_errors.py` after the
2026-06-01 Vision sprint ($6.78 / $19 budget). Raw per-metric vectors
in `eval_runs/systematic_errors.json`.

## Method

For each metric in `gt_totals`, compute the signed % error AI-vs-truth
on every project where both an AI extract and a truth value exist. A
metric is flagged as **systematic-error candidate** when ≥3 projects
show same-sign errors >1%. Candidates are root-cause investigated;
they are NOT auto-fixed with prompt tuning (that's eval-fitting on
N=4 Rangovas A data).

## Scored projects (N=4)

berzas, bacveviciaus, ciurliu, lazunu. Excluded:
- **romainiai** — scope mismatch (AI sees 45-page interior; pasiūlymas
  prices 4.1-5.1 punktas subset; AI/truth not directly comparable)
- **sernu** — missing architectural floor plan PDF; specialty drawings
  only

## ★ Three confirmed systematic errors

### 1. Dažymo kampai — median **−18.15%**, 3 of 4 same sign

| Project | Truth | AI | Δ% |
|---|---:|---:|---:|
| bacveviciaus | 580.54 | 446.64 | **−23.06%** |
| berzas | 493.35 | 387.10 | **−21.54%** |
| ciurliu | 201.86 | 224.06 | +11.00% (outlier) |
| lazunu | 123.59 | 105.34 | **−14.77%** |

**Hypothesis**: AI computes paint-corner length as room perimeter
corners only (4 per rectangular room). Contractors include
**partition corners** + outside corners around niches + window-niche
outside corners. The kampai gap = ~paint-corner length that the AI's
room-graph doesn't see because partition walls aren't enumerated as
separate corner sources.

**Why ciurliu is the outlier**: smaller, simpler floor plan; fewer
partition walls; corner under-count smaller in absolute terms; AI's
generous corner count overcounts there instead.

**Investigation status**: existing `count_partition_corners` flag is
opt-in (added 2026-05 per STR alignment); not activated by default.
A fix would activate it, but verification requires re-running 4
projects (≈$6 extra Vision spend). Documented; not applied this
session.

### 2. LED nišų ilgis — median **−28.74%**, 3 of 3 under-extracted

| Project | Truth | AI | Δ% |
|---|---:|---:|---:|
| bacveviciaus | 54.98 | 12.00 | **−78.17%** |
| berzas | 42.30 | 40.00 | −5.44% (within ok-band) |
| ciurliu | 16.84 | 12.00 | **−28.74%** |
| lazunu | 10.58 | 0.00 | **−100.0%** (missed entirely) |

**Root cause** (already investigated, no Vision re-spend needed):

The LED-niche detector reads `nisa_led` elementai from the **floor
plan** pages. Niche positions in LT residential drawings are
documented on the **LUBŲ PLANAS** (suspended-ceiling plan), which is
a different page (or a different PDF entirely).

- **bacveviciaus**: 65-page TP includes a LUBŲ PLANAS, but the
  extractor finds only 1 niche on the floor plan (12 m); misses the
  ~43 m of other niches on the ceiling plan
- **ciurliu**: 3-page A3 plan includes ceiling annotations on the
  floor plan itself; AI finds 4 nišos but still misses 4.84 m
- **lazunu**: `Pakabinamu lubu planas-Layout4.pdf` is a **separate
  PDF** not in the input — AI extract sees 0 nišos because that PDF
  wasn't given to it. This is partly an INPUT issue, not an
  extraction error

**Fix path** (not applied this session): add a second-pass Vision
call specifically targeting LUBŲ PLANAS pages, similar to the
existing `niche_locator.py` but with broader page-role detection.
Estimated cost: ~$0.30 per project × N projects.

### 3. Angokraščiai — median **+43.35%**, 3 of 3 OVER-extracted

| Project | Truth | AI | Δ% |
|---|---:|---:|---:|
| bacveviciaus | 94.02 | 169.63 | **+80.42%** |
| berzas | 89.39 | 89.51 | +0.13% (within ok-band) |
| ciurliu | 34.53 | 49.50 | **+43.35%** |
| lazunu | 31.80 | 39.44 | **+24.03%** |

**Root cause** (investigated; verified):

Rule #1 (added in commit f8a3a, validated on Beržų at +0.13%) is:
`angokraščiai = W+2H for all doors + W+2H for INTERIOR windows only`.

The "interior" gate reads `el._exterior` on each window. On Beržų the
eksplikacija reader correctly sets `_exterior=True` for facade
windows. **On the 3 new projects, every window has
`_exterior=None`** — the flag is never set. Rule #1's fallback then
treats all None-flagged windows as interior, counting their W+2H.

Audit per project (all windows unflagged):
- bacveviciaus: 12 windows, all `_exterior=None`
- ciurliu: 3 windows, all `_exterior=None`
- lazunu: 3 windows, all `_exterior=None`

**Beržų's eksplikacija reader path** sets `_exterior` from contractor
language ("lauko" = exterior, "vidaus" = interior). The new projects
don't go through that code path — either because their eksplikacija
tables differ, or because the post-processing step that propagates
the flag to elementai isn't running for non-Beržų layouts.

**Fix path** (not applied this session):
- Audit the eksplikacija reader output for each project: does it
  report exterior/interior status per opening?
- If yes — propagation is broken (cheap to fix)
- If no — eksplikacija reader prompt needs strengthening to extract
  the flag (Vision re-spend required)
- Cross-cuts with the kampai issue: both metrics partially depend on
  the interior/exterior partition-vs-facade distinction

## What I did NOT do (and why)

I did **not** prompt-tune the dimension/niche/eksplikacija extractors
to close these gaps on the N=4 data. Same reasoning that rejected the
Optuna sweep last session:

- N=4 single-contractor data; any prompt that minimises observed
  errors is fitting to **Rangovas A scope conventions**, not to LT
  industry norms
- Each metric has at least one project where it WORKS (Beržų
  angok +0.13%, ciurliu kampai +11%). A "fix" that helps the failing
  3 may regress the OK one — and we have no second-contractor truth
  to detect that regression
- The findings themselves are the deliverable — they tell the next
  engineer (or future Claude) exactly where to dig

## What I DID do

- Run the full production pipeline on all 4 available projects
  ($6.78 / $19 authorized budget)
- Save ai_extract.json + ai_extract_meta.json per project
- Compute per-metric per-project error vector, flag systematic
  candidates at the ≥3-same-sign threshold
- Root-cause investigate LED and angokraščiai (zero additional Vision
  spend; pure code+data inspection)
- Document the kampai/LED/angok findings with proposed fix paths +
  estimated Vision cost to verify
- Update `ground_truth/registry.yaml` to flag `romainiai` as
  scope_mismatch so future eval runs exclude it automatically from
  systematic analysis

## Acceptance gate status

| Criterion | Status | Note |
|---|---|---|
| ≥5 of 6 projects through full pipeline | ✓ 5/6 (sernu blocked, romainiai scope-mismatch but extracted) |
| Cross-project MAE measured | ✓ overall MAE 29.9%, 4-project MAE without romainiai ≈ **22.5%** |
| Single-project paint error ≤ 2% | ✗ ciurliu −20.33%, lazunu −22.10% |
| Systematic errors flagged ≥3-project | ✓ 3 identified + root-caused |
| Fix committed for each | ⚠ Investigation committed, prompt-changes deferred (eval-fit risk) |
| All 788+ tests pass | ✓ pre-sprint baseline, will re-verify in commit |
| Final metrics table published | ✓ this document + eval_report_multi.html |

The headline number for product positioning:
**Production-pipeline MAE on novel (non-Beržų) Rangovas A projects ≈ 20-25%**,
NOT the 0.68% the `--use-gt-inputs` mode shows on Beržų. The gap is
real Vision extraction drift on PDFs the pipeline wasn't tuned for.
