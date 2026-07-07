# Accuracy discrepancies for founder review (2026-07-05)

Surfaced by the calc-library test-pinning pass (commit `fde0b47`). These are **flagged, not changed** — every one alters billed quantities, so they need your decision. Each cites the code location, the CLAUDE.md rule, and the likely direction of error.

| # | Item | Code | CLAUDE.md | Discrepancy | Direction | Priority |
|---|---|---|---|---|---|---|
| 1 | **Glaistymas Q4 storis** | `interiorCalc.js` Q_THICK `{Q1:1.2, Q2:1.25, Q3:1.75, Q4:2.5}` mm | §1.11: typical `{Q1:0.5–1, Q2:1–1.5, Q3:1.5–2, Q4:3–5}` mm | Q4 coded 2.5 mm vs documented 3–5 mm full-surface skim | **Under-estimates Q4 glaistas (putty kg)** | **HIGH** — Q4 is the gloss/lacquer prep; under-ordering putty is a real miss |
| 2 | **Grindjuostės atsarga** | `interiorCalc.js` computes `perimeter − door_widths` (net, no waste) | §1.4: `baseboard = perimeter − door_widths + 10% waste` | +10% waste not applied at the calc layer | Depends — waste IS applied later in the `WASTE_FACTORS` UI table; **verify it lands once, not zero or twice** | MED |
| 3 | **Dažų kiekis — dengimo daugiklis** | backend `main.py:~3051` `paint_walls_m2 × 2 / 9` (flat ×2 coats) | §1.10: "for 2 coats multiply by **1.8×** (first coat absorbs more)" | ×2.0 vs ×1.8 | **Over-estimates paint ~11%** (conservative — safer to over-order) | LOW |
| 4 | **`dazai.sienos_l`/`lubos_l` = 0** in frontend module | `interiorCalc.js` (hardcoded 0) | — | Intentional per a 2026-05-10 hotfix comment; backend `/api/recompute-quantities` is canonical | Not a bug — pinned as expected | — |

## Recommendation
- **#1 (Q4 glaistas)** is the one worth acting on — a quick bump of the Q4 thickness toward the documented 3–5 mm (or making it a per-project assumption the user can override, like the other Q-levels) would fix a real under-estimate. Needs your sign-off since it changes quantities on every Q4 project.
- **#2** — a 5-minute check that grindjuostės waste is applied exactly once end-to-end (calc → UI → export). If the UI table already adds it, no change; if not, it's missing.
- **#3** — leave as-is (conservative) or align to 1.8× if you want tighter paint numbers.

None of these are urgent or block launch; they're accuracy refinements. Do them as a batch when you're back, against the contractor-validated fixture (Beržų g. 24) so any change is measured, not guessed.
