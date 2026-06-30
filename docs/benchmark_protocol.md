# Sąmatų AI human-GT benchmark protocol

## Goal

Replace AI-seeded ground truth (49.3 % Claude-grading-Claude) with human-verified
GT for 10 LT interior PDFs by Week 6 of the canonical plan
(`docs/superpowers/plans/2026-05-10-canonical-plan.md`).

## Sample selection

- 6 LT butai/namai with floor plan + eksplikacija (most common case)
- 2 with sienų išklotinės (tile zone validation)
- 2 with lubų / elektros / santechnikos planai (symbol-count validation)
- All `vat_mode: be_pvm` so VAT mode does not introduce noise (R4)
- Mix Vilnius / Kaunas (R4 +15-25 % regional price calibration)

## Workflow per PDF (~45–60 min, 35–60 €)

1. Owner provides PDF + skeleton JSON from `data/human_gt/`.
2. Samatininkas opens the PDF in their normal tool.
3. Manually measures + fills `quantity` for each line.
4. Adds `verified_by: <name>` per line + `notes:` if relevant.
5. Returns JSON.
6. CI runs `python scripts/bootstrap_human_gt.py --validate`.

## Coverage targets (canonical plan timeline)

- **Week 1** (this commit): 10 skeleton files in `data/human_gt/`.
- **Week 6**: 10 fully filled (`verified_by` set on each line).
- **Week 8**: re-run pipeline against all 10 + 5 new unseen PDFs.

## Metric (computed via `scripts/run_eur_benchmark.py`, scaffold lands Week 4)

```
EUR_weighted_error =
  Σ (|qty_pred − qty_gt| × unit_price_eur_be_pvm × line_weight)
/ Σ (qty_gt × unit_price_eur_be_pvm × line_weight)
```

Weights (R4 research):

| Line | Weight |
|---|---|
| `glaistymas_dazymas_bundle` | 0.30 |
| `plyteles_*` (sienos+grindys, work+material) | 0.20 |
| `grindys_*` (laminatas+material) | 0.15 |
| `pasleptu_duru_kompl` | 0.10 |
| `lubos_virs_3m_m2` | 0.05 |
| Everything else | 0.20 |

## Targets

- **Week 6 mid-bake**: ≤25 % EUR-weighted error (sanity).
- **Week 8 final**: ≤15 % EUR-weighted error on top-5 lines (paywall gate).

## Anti-patterns (do not use)

- ❌ Claude grading Claude (any AI-only GT).
- ❌ Single-source labour-only GT (must include material + bundled lines).
- ❌ Mixing PVM modes in one report — keep `be_pvm` throughout.
- ❌ Counting cell-level mismatch instead of EUR magnitude — a 1 m baseboard miss costs €5; a 1 m² paint miss costs €14.

## Reference R4 invoice data

Confirmed via Rangovas P2-P5 audit (`docs/superpowers/research/2026-04-28-rangovas-p2-p5-audit.md`):

- Bundled glaistymas + dažymas: **13–15 €/m²**
- Wall tiles labor: 15–30 €/m²; large-format (>80 cm): 50–70 €/m²
- Hidden door komplektas (frame + apdirbimas): 200–300 €/kompl (~4× standard door)
- Q4 sanding adds +50–100 % over Q3 (DIN 18363 raking-light requirement)
- Vilnius runs +15–25 % over Kaunas mid-market

Bootstrap defaults (`scripts/bootstrap_human_gt.py`) use Rangovas mid-market Kaunas prices.
