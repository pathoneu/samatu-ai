# Determinism status — Vision pipeline

## Current status (2026-06-01, multi-project session)

**No new Vision calls were made in this session for the 5 new projects.**
The expensive Vision passes for the new batch are gated behind a per-project
authorization decision; see the "Phase B — Vision spend gate" section below.

The Objektas A majority-vote determinism check was last verified on 2026-05-26
(N=5 runs of the floor plan extractor; voted output byte-identical across all
runs). The prompt + extractor pipeline has not changed since — therefore the
existing determinism artefact remains valid.

To re-run the voter for verification (cost ~$0.50):
```
python scripts/voter_determinism_check.py --project objektas_a --runs 5
```

## Phase B — Vision spend gate

The 5 new projects need a one-time Vision extract for the floor plan / general
plans before `eval_harness.py --totals-only` can score them.

| Project | Plan pages | Est. Vision spend* |
|---|---:|---:|
| `objektas_b` | 65 (TP) | $6.50 – $10 |
| `objektas_c` | 3 (A3) | $0.30 – $0.50 |
| `romainiai` | 45 (subset) | $4.50 – $7 |
| `sernu` | ⛔ missing | — |
| `objektas_d` | 10× single-page | $1.00 – $1.50 |
| **TOTAL** | | **$12 – $19** |

*assumes Opus 4.7 Vision @ 1500 in-tok + 500 out-tok per page, $15/M input + $75/M output

After Vision extracts complete, re-run the voter on each new floor plan to
confirm determinism; record results here.

## Honest framing

A determinism check is a regression guard, not an accuracy guard. The
Objektas A voter produces byte-identical output across 5 runs, which proves
*non-flakiness*, not *correctness*. The current multi-project totals-only
baseline (`eval_runs/baseline_multi.json`) measures correctness against
contractor truth.
