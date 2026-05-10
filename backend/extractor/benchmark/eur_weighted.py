"""EUR-weighted absolute percentage error (Week 4 Task 4.4 — Council R4 north star).

For a typical 17,800 €/project bundled invoice (per R4), a 10% miscount on
glaistymas/dažymas is a 322 € swing — much more impactful than a 10% miscount
on silikonas. This metric weights each line by its share of typical invoice
EUR so the benchmark optimizes for what costs estimators money, not for
line-counting parity.

Formula:
  weighted_err = Σ |pred_qty - gt_qty| × unit_price × line_weight
  weighted_total = Σ gt_qty × unit_price × line_weight
  EUR_weighted_error = weighted_err / weighted_total

Both pred and gt are dicts of `{line_code: quantity}`; missing codes count
as 0. Prices and weights come from `backend/data/lt_unit_prices.json`.
"""
from __future__ import annotations

import json
from pathlib import Path

PRICES_PATH = Path(__file__).resolve().parents[2] / "data" / "lt_unit_prices.json"


def load_prices(path: Path | str | None = None) -> dict:
    """Load prices+weights JSON. Tests can pass a custom path."""
    p = Path(path) if path else PRICES_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def eur_weighted_error(
    pred: dict[str, float],
    gt: dict[str, float],
    prices_config: dict | None = None,
) -> float:
    """Return EUR-weighted absolute percentage error in 0..1+ range.

    `prices_config` defaults to the on-disk LT prices fixture; tests pass a
    dict directly.
    """
    cfg = prices_config or load_prices()
    weights: dict[str, float] = cfg["weights"]
    prices: dict[str, float] = cfg["unit_prices"]
    other_weight = weights.get("_other", 0.0)

    weighted_err = 0.0
    weighted_total = 0.0
    all_codes = set(pred) | set(gt)
    for code in all_codes:
        weight = weights.get(code, other_weight)
        price = prices.get(code, 0.0)
        if price <= 0 or weight <= 0:
            continue
        gt_qty = float(gt.get(code, 0))
        pred_qty = float(pred.get(code, 0))
        weighted_err += abs(pred_qty - gt_qty) * price * weight
        weighted_total += gt_qty * price * weight
    if weighted_total == 0:
        return 0.0
    return weighted_err / weighted_total


def per_line_eur_impact(
    pred: dict[str, float],
    gt: dict[str, float],
    prices_config: dict | None = None,
) -> list[dict]:
    """Per-line EUR delta sorted by absolute impact (largest first).

    Useful for the Week 7 "fix top-3 EUR misses" task — the report drives
    engineering priorities by actual euros, not by raw count differences.
    """
    cfg = prices_config or load_prices()
    weights: dict[str, float] = cfg["weights"]
    prices: dict[str, float] = cfg["unit_prices"]
    other_weight = weights.get("_other", 0.0)

    rows: list[dict] = []
    for code in set(pred) | set(gt):
        gt_qty = float(gt.get(code, 0))
        pred_qty = float(pred.get(code, 0))
        delta_qty = pred_qty - gt_qty
        price = prices.get(code, 0.0)
        weight = weights.get(code, other_weight)
        rows.append({
            "code": code,
            "gt_qty": gt_qty,
            "pred_qty": pred_qty,
            "delta_qty": round(delta_qty, 3),
            "unit_price_eur_be_pvm": price,
            "weight": weight,
            "abs_eur_impact": round(abs(delta_qty) * price, 2),
            "weighted_eur_impact": round(abs(delta_qty) * price * weight, 2),
        })
    rows.sort(key=lambda r: r["abs_eur_impact"], reverse=True)
    return rows
