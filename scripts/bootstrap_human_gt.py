"""Create skeleton ground-truth JSONs (Week 1 Task 1.5).

Creates 10 templates under `data/human_gt/` with all top-5 EUR-weighted
lines preset to quantity=0 + Rangovas mid-market Kaunas prices (R4 research).
The samatininkas fills in `quantity` and `verified_by` for each line.

Usage:
  python scripts/bootstrap_human_gt.py
  python scripts/bootstrap_human_gt.py --validate    # only validate existing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

OUT_DIR = REPO_ROOT / "data" / "human_gt"

# R4 (research session 2026-05-10): bundled glaistymas+dažymas at 14 €/m² is
# the dominant LT invoice convention, confirmed across Rangovas P2-P5.
LINE_TEMPLATE = [
    # Top-5 EUR-weighted lines (60% of typical project budget)
    {"code": "glaistymas_dazymas_bundle",
     "label_lt": "Sienų + lubų glaistymas + dažymas (bundled)",
     "unit": "m²", "quantity": 0,
     "unit_price_eur_be_pvm": 14, "bundled_group": "glaistymas_dazymas",
     "verified_by": "",
     "notes": "Σ paintable wall area + ceiling area, Q2/Q3 default"},
    {"code": "plyteles_sienos_m2",
     "label_lt": "Plytelių klijavimas sienoms (darbas)",
     "unit": "m²", "quantity": 0,
     "unit_price_eur_be_pvm": 22, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "plyteles_grindys_m2",
     "label_lt": "Plytelių klijavimas grindims (darbas)",
     "unit": "m²", "quantity": 0,
     "unit_price_eur_be_pvm": 14, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "grindys_laminatas_m2",
     "label_lt": "Grindys (laminatas/parketas/vinilas, darbas)",
     "unit": "m²", "quantity": 0,
     "unit_price_eur_be_pvm": 7, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "pasleptu_duru_kompl",
     "label_lt": "Paslėptos durys (komplektas + apdirbimas)",
     "unit": "kompl", "quantity": 0,
     "unit_price_eur_be_pvm": 250, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "lubos_virs_3m_m2",
     "label_lt": "Lubų darbai virš 3m (scaffolding adder)",
     "unit": "m²", "quantity": 0,
     "unit_price_eur_be_pvm": 18, "bundled_group": None,
     "verified_by": "", "notes": ""},
    # Other lines (20% combined weight)
    {"code": "grindjuostes_m",
     "label_lt": "Grindjuostės",
     "unit": "m", "quantity": 0,
     "unit_price_eur_be_pvm": 5, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "angokrasciai_gkp_m",
     "label_lt": "Angokraščių apdaila GKP",
     "unit": "m", "quantity": 0,
     "unit_price_eur_be_pvm": 12, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "hidroizoliacija_m2",
     "label_lt": "Hidroizoliacija (m², ne vnt)",
     "unit": "m²", "quantity": 0,
     "unit_price_eur_be_pvm": 10, "bundled_group": None,
     "verified_by": "", "notes": ""},
    {"code": "silikonas_m",
     "label_lt": "Plytelių silikonavimas",
     "unit": "m", "quantity": 0,
     "unit_price_eur_be_pvm": 2.5, "bundled_group": None,
     "verified_by": "", "notes": ""},
]


def make_skeleton(pdf_id: str) -> dict:
    return {
        "pdf_id": pdf_id,
        "pdf_hash": "",
        "project_type": "interior_finishing",
        "city": "Kaunas",
        "floor_area_m2": 0,
        "vat_mode": "be_pvm",
        "lines": [dict(line) for line in LINE_TEMPLATE],
    }


def bootstrap(n: int = 10) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for i in range(1, n + 1):
        path = OUT_DIR / f"pdf_{i:02d}.human_gt.json"
        if path.exists():
            continue
        skeleton = make_skeleton(f"pdf_{i:02d}")
        path.write_text(
            json.dumps(skeleton, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        created += 1
        print(f"created {path}")
    total = len(list(OUT_DIR.glob("*.human_gt.json")))
    print(f"OK: {total} GT skeleton(s) under {OUT_DIR} (created this run: {created})")
    return 0


def validate() -> int:
    """Schema-validate every GT file. Returns exit code (0 = all good)."""
    from backend.extractor.human_gt_schema import HumanGTPdf

    files = sorted(OUT_DIR.glob("*.human_gt.json"))
    if not files:
        print(f"WARN: no GT files in {OUT_DIR}", file=sys.stderr)
        return 1
    errors = 0
    for path in files:
        try:
            gt = HumanGTPdf.model_validate_json(path.read_text(encoding="utf-8"))
            non_zero = [l for l in gt.lines if l.quantity > 0]
            verified = [l for l in gt.lines if l.verified_by]
            print(f"{path.name}: {len(non_zero)} non-zero, "
                  f"{len(verified)}/{len(gt.lines)} verified")
            if not verified and non_zero:
                print(f"  WARN: lines have quantities but no verified_by")
        except Exception as exc:
            print(f"{path.name}: SCHEMA ERROR — {exc}", file=sys.stderr)
            errors += 1
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true",
                    help="Only validate existing files, don't create skeletons")
    ap.add_argument("-n", "--count", type=int, default=10,
                    help="Number of skeleton files to create (default 10)")
    args = ap.parse_args()
    if args.validate:
        return validate()
    return bootstrap(args.count)


if __name__ == "__main__":
    raise SystemExit(main())
