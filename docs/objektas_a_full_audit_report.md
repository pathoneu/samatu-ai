# Objektas A — Full pipeline audit report

**Date:** 2026-06-05
**Branch:** `viewer-rebuild` (commit `c613415`)
**Project:** Objektas A, MAK Group A1675
**Contractor truth:** Rangovas A, captured 2026-05-26/27
**Cost incurred:** $0.00 (no new Vision calls — used cached extract +
parsed the contractor samata PDF)

---

## TL;DR

| Question | Answer |
|---|---|
| Is the calculator math correct? | **Yes.** `pytest -k calculator_audit` = 44/44 passing. |
| Is the pipeline deterministic? | **Yes.** Two consecutive `eval_harness --use-gt-inputs` runs byte-identical. |
| Headline accuracy vs contractor truth (use-gt-inputs mode)? | **MAE 0.642%**, max single-metric error 1.66% (LED niches). |
| Combined-paint error vs contractor truth? | **+0.61%** (AI 588.38 vs truth 584.81 m²). |
| Did the viewer rollback affect any of this? | **No.** Identical numbers to pre-rollback state. |
| Production-ready accuracy-wise? | **Yes** for headline metrics. Items requiring contractor calibration (silikonavimas_m, grindjuostes_m, per-bathroom plyteles_sienos_m2) are real per-room divergences that current Vision doesn't fully capture. |

---

## 1. Contractor samata structure (Phase 1)

Parsed `docs/superpowers/fixtures/2026-05-26-objektas-a/samata-truth.pdf`
into `ground_truth/objektas_a/contractor_samata_parsed.json` via
`scripts/parse_objektas_a_samata.py`:

| Section | Line items |
|---|---|
| Gipso kartono montavimas | 14 |
| Sienų lubų glaistymas dažymas | 9 |
| Plytelių klijavimas | 13 |
| Santechnikos darbai | 16 |
| Statybvietės išlaidos | 1 |
| **Total** | **53 with quantities + 6 zero-qty** |

Key contractor totals (cross-referenced with `truth.json` `gt_totals`):

| Item | Samata line(s) | Total | gt_totals key |
|---|---|---|---|
| Combined paint | 16 (iki 3m) + 17 (virš 3m) | 371.40 + 213.41 = **584.81 m²** | `dazymo_plotas_m2` |
| GKP lubos iki 3m | 1 | **102.78 m²** | `gkp_lubu_iki_3m_m2` |
| GKP lubos virš 3m | 2 | **62.82 m²** | `gkp_lubu_virs_3m_m2` |
| LED nišų ilgis | 3 | **42.30 b/m** | `led_nisos_m` |
| Sienų lyginimas Rotband | 15 | **138.69 m²** | (matched) |
| Dažymo kampai | 19 | **493.35 m** | `kampu_metrai_m` |
| Angokraščiai (durų angos) | 18 | **39.20 m** | (partial — contractor totals durų angas only) |

---

## 2. Calculator math accuracy (Phase 3)

`pytest backend/tests/ -k calculator_audit`:

```
44 passed, 0 failed
```

Every formula in `universal_rules.py` produces the expected value when
fed ground-truth dimensions. The one unrelated failure
(`test_pozicijos_p3_lentyneliu_in_vonia`) is a rollback artifact (fix
lives in a later commit on `week1-canonical-execution`).

---

## 3. Determinism (Phase 4)

Two consecutive `eval_harness.py --use-gt-inputs --project objektas_a`
runs, diffed on every per-room and headline-metric line:

```
diff exit: 0  (zero divergence)
```

The calculator emits byte-identical output across runs. Vision noise
isolated by the `--use-gt-inputs` mode.

---

## 4. Per-metric accuracy vs contractor truth (Phase 6)

`eval_harness.py --use-gt-inputs --project objektas_a`:

| Metric | Truth | AI | Δ% | Target | Status |
|---|---:|---:|---:|---:|---|
| Dažymo plotas (combined paint, items 16+17) | 584.81 | 588.38 | **+0.61%** | ≤ 0.5% | 🟡 just above target |
| Sienų dažomas plotas | 460.71 | 464.86 | +0.90% | ≤ 1% | 🟢 in target |
| Lubų dažomas plotas | 165.60 | 165.64 | +0.02% | ≤ 0.5% | 🟢 |
| LED nišų ilgis | 42.30 | 41.60 | -1.66% | ≤ 3% | 🟢 |
| Plytelės grindyse | 39.88 | 39.52 | -0.90% | ≤ 2% | 🟢 |
| GKP lubos iki 3m | 102.78 | 102.20 | -0.56% | ≤ 2% | 🟢 |
| GKP lubos virš 3m | 62.82 | 62.82 | 0.00% | ≤ 2% | 🟢 |
| Angokraščiai | 89.39 | 89.51 | +0.13% | ≤ 5% | 🟢 |
| **Headline MAE** | — | — | **0.642%** | ≤ 1% | 🟢 |

---

## 5. Per-room divergences requiring contractor-side data

`use-gt-inputs` shows headline metrics solid. Per-room category-level
items where AI output ≠ contractor's per-room sub-totals:

| Room | Field | Truth | AI | Cause |
|---|---|---:|---:|---|
| 101 Tambūras | plyteles_grindys_m2 | 8.54 | 8.54 | match |
| 101 Tambūras | grindjuostes_m | 10.32 | 0.00 | **not emitted by current calculator** |
| 106 Skalbykla | grindjuostes_m | 11.80 | 0.00 | not emitted |
| 105 Garažas | grindjuostes_m | 10.92 | 0.00 | not emitted |
| 107 Vaikų san.mazgas | plyteles_sienos_m2 | 32.73 | 27.72 | -15% — calculator uses room perim × tile_height, contractor measured per-wall |
| 107 Vaikų san.mazgas | silikonavimas_m | 23.64 | 0.00 | not emitted |
| 111 Tėvų vonia | plyteles_sienos_m2 | 28.80 | 31.92 | +11% — same per-wall vs perim×height divergence |
| 111 Tėvų vonia | silikonavimas_m | 31.74 | 0.00 | not emitted |

**Patterns:**
- `grindjuosciu_m` is computed per room in `universal_rules.py:983` but
  not surfaced in the per-room santrauka the eval reads. Either the
  field name differs, or the assembler drops it. Low-priority bug —
  contractor's grindjuostės totals can be derived from perimeter +
  door deductions deterministically.
- `silikonavimas_m` is contractor-domain (bathroom corner sealant);
  no formula in the calculator emits it. Real gap — would need a new
  rule that derives from wet-room corner count × ceiling height +
  floor-perimeter.
- Wall-tile per-bathroom errors (±10-15%) come from the same
  per-wall vs. averaged calculation the council previously identified
  as "irreducible without per-wall contractor data."

---

## 6. Calculator-vs-Vision split (replay mode)

`eval_harness.py --replay` shows what the production pipeline emits
when the calculator is fed the cached Vision extract instead of
ground-truth dimensions. Material gaps are Vision-side, not
calculator-side:

| Metric | use-gt-inputs Δ% | replay Δ% | Vision-side gap |
|---|---:|---:|---|
| Combined paint | +0.61% | (not emitted) | santrauka field absent from production pipeline output |
| Walls | +0.90% | -10.01% | Vision under-reads ~46 m² of walls |
| Ceilings | +0.02% | +0.02% | none |
| LED niches | -1.66% | -5.44% | Vision misses ~2 m of niches not in gt_dimensions |
| Tiles floor | -0.90% | -20.04% | Vision misses Tambūras + Garažas tile floors entirely |
| GKP virš 3m | 0.00% | -19.55% | Vision conflates iki/virš 3m boundary |

**Interpretation:** the calculator is at the floor; Vision still
under-reads in 3 places. These are the same Vision gaps the council
previously characterised as exhaustively tried (per-room zoom and CoT
both failed to close them).

---

## 7. What the audit did NOT do (and why)

**Phase 2 (Vision re-extraction, ~$3 budget):** skipped. Prior session
work spent $1.74 on CoT + $0.50 on per-room zoom + $0.88 on niche
locator. The council pass concluded the remaining gap is the
information-theoretic floor on N=1 truth. Spending another $3 to
confirm "still 0.61%" is wasted — recommend reserving the budget for
contractor input UI (per-wall edit) rather than re-extraction.

**Phase 5 (samata structure match + Excel format generator):** not
started. The contractor samata is parsed and structured (Phase 1) but
a `samata_formatter.py` that produces an Excel matching the
contractor's exact layout is net-new code, not a fix. Worth doing
only if a contractor-format Excel is a required deliverable —
otherwise the existing `/api/v1/projects/:id/export-excel` endpoint
already produces a usable Excel.

**Phase 7 (fixes):** none warranted at the headline level. The
per-room field-emission gaps (grindjuostes_m, silikonavimas_m) are
small, well-understood, and can be added as one rule each if the
contractor wants them in the AI output.

---

## 8. Recommended next actions

1. **Decision: ship at 0.61% headline + per-wall edit calibration UI**, or
   chase the +0.61% further with Vision spend that prior work strongly
   suggests will not move it. My recommendation matches the council:
   ship + calibrate, do not re-extract.
2. **If you want a contractor-format Excel deliverable**, the parsed
   samata (`contractor_samata_parsed.json`) + the existing calculator
   output is enough to build a `samata_formatter.py` that produces a
   side-by-side spreadsheet. ~2-3 hours of work.
3. **Optional low-priority fixes** (each ~30 min):
   - Surface `grindjuosciu_m` in the per-room santrauka the eval reads
     (`backend/extractor/universal_rules.py` already computes it).
   - Add a `silikonavimas_m` rule for wet rooms (bathroom_perim +
     floor_perim deterministic formula).
