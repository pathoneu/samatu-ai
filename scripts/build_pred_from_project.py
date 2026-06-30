"""Translate a saved project's pozicijos[] into the canonical predictions
shape (data/predictions/<pdf_id>.pred.json) used by the EUR benchmark.

The same code-classification rules as build_gt_from_pasiulymai.py — single
source of truth so GT and pred land on identical canonical codes.

Usage:
  python scripts/build_pred_from_project.py <project_id> <pdf_id>

Example:
  python scripts/build_pred_from_project.py 79c46c0e-… projektas_p1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import db  # noqa: E402

from build_gt_from_pasiulymai import (  # noqa: E402
    DEFAULT_PRICES, LABELS_LT, UNITS, _classify,
)

PRED_DIR = REPO / "data" / "predictions"


def project_to_predictions(project: dict) -> dict[str, float]:
    """Build canonical-code prediction sums.

    Counted PER ROOM from v8_rooms (the deterministic per-surface fields)
    rather than per-pozicija — V8 splits bundle into 8+ rows of the SAME
    surface (lyginimas / Q1 / Q2 / šlifavimas / gruntavimas / dažymas×2),
    so summing pozicijos would 8× the bundle area. v8_rooms has the canonical
    per-surface m² that maps cleanly onto Rangovas's bundled invoice.

    For microworks not captured per-room (silikonas), we still classify
    matching pozicijos, but defensive: only those that didn't already feed
    a per-room field.
    """
    sums: dict[str, float] = {code: 0.0 for code in DEFAULT_PRICES}

    rooms = project.get("v8_rooms") or project.get("patalpos") or []
    for r in rooms:
        # 1. Glaistymas+dažymas bundle = paintable surface (walls + ceiling).
        #    Rangovas charges €14/m² for the whole stack on one m².
        sums["glaistymas_dazymas_bundle"] += float(r.get("dazymo_plotas_m2") or 0)
        # 2. Wall tiles per room.
        sums["plyteles_sienos_m2"] += float(r.get("plyteles_sienos_m2") or 0)
        # 3. Floor tiles per room.
        sums["plyteles_grindys_m2"] += float(r.get("plyteles_grindys_m2") or 0)
        # 4. Soft floor (PVC/laminate/parquet) per room.
        sums["grindys_laminatas_m2"] += float(r.get("pvc_grindys_m2") or 0)
        # 5. Ceiling work above 3m.
        sums["lubos_virs_3m_m2"] += float(r.get("gkp_lubu_virs_3m_m2") or 0)
        # 6. Baseboards.
        sums["grindjuostes_m"] += float(r.get("grindjuostes_m") or 0)
        # 7. Real hidroizoliacija m² (post-Week 2 fix).
        sums["hidroizoliacija_m2"] += float(r.get("hidroizoliacija_m2") or 0)

    # 8. Microworks not stored per-room — classify via pozicija text.
    pozicijos = project.get("pozicijos") or []
    for p in pozicijos:
        code = _classify(p.get("aprasymas", ""), p.get("vnt", ""))
        # Only accept the few codes that aren't already tallied via v8_rooms,
        # so we don't double-count the bundle.
        if code in {"silikonas_m", "pasleptu_duru_kompl",
                    "angokrasciai_gkp_m"}:
            sums[code] += float(p.get("kiekis") or 0)

    return sums


def write_predictions(pdf_id: str, sums: dict[str, float]) -> Path:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out = PRED_DIR / f"{pdf_id}.pred.json"
    payload = {
        "pdf_id": pdf_id,
        "lines": [{
            "code": code,
            "label_lt": LABELS_LT[code],
            "unit": UNITS[code],
            "quantity": round(qty, 2),
            "unit_price_eur_be_pvm": DEFAULT_PRICES[code],
        } for code, qty in sums.items()],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    project_id, pdf_id = sys.argv[1], sys.argv[2]
    project = db.get_project(project_id)
    if not project:
        print(f"ERR: project {project_id} not found", file=sys.stderr)
        return 1
    sums = project_to_predictions(project)
    out = write_predictions(pdf_id, sums)
    matched = sum(1 for v in sums.values() if v > 0)
    print(f"  {project_id[:8]} → {pdf_id}: {matched}/10 codes filled → {out.name}")
    for code, qty in sums.items():
        if qty > 0:
            print(f"    {code:<28} {qty:>8.2f} {UNITS[code]:<5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
