"""Translate training-data/parsed_pasiulymai.json (real samatininkų quotes
for projects P1-P5) into the canonical human_gt format the EUR benchmark
expects.

For every benchmark line code (glaistymas_dazymas_bundle, plyteles_sienos_m2,
…) we sum quantities from rows whose `aprasymas` matches a conservative
keyword pattern. Unmatched rows are dropped (they fall under the benchmark's
implicit `_other` weight).

Output: data/human_gt/projektas_NN.human_gt.json (one per P1..P5).
Existing pdf_01..10 placeholder files are preserved.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "training-data" / "parsed_pasiulymai.json"
GT_DIR = REPO / "data" / "human_gt"

# Canonical line code → list of (pattern, unit_filter|None) tuples.
# `pattern` matches against `aprasymas.lower()`; `unit_filter` (if set) must
# also match `vnt.lower()` to avoid e.g. counting m² rows as m of frame.
# Order matters when the same row could match two — we test in declared order
# and only assign the first hit.
PATTERNS: list[tuple[str, list[tuple[str, str | None]]]] = [
    # 1) Wall+ceiling glaistymas/dažymas bundle (R4 30% weight).
    # Includes prep (Rotband leveling), primer (gruntavimas), Q1/Q2 putty,
    # sanding, paint coats — all priced per m² of paintable surface.
    ("glaistymas_dazymas_bundle", [
        (r"sien.*lyginim.*rotband", "m2"),
        (r"sien.*pirmin.*glaistym", "m2"),
        (r"sien.*antrin.*glaistym", "m2"),
        (r"sien.*šlifavim", "m2"),
        (r"sien.*gruntavim", "m2"),
        (r"sien.*dažym", "m2"),
        (r"lub.*pirmin.*glaistym", "m2"),
        (r"lub.*antrin.*glaistym", "m2"),
        (r"lub.*šlifavim", "m2"),
        (r"lub.*gruntavim", "m2"),
        (r"lub.*dažym", "m2"),
        (r"lubų glaistym.*dažym", "m2"),
        (r"sienų lubų glaistym", "m2"),
    ]),
    # 2) Wall tile work (R4 10% weight).
    ("plyteles_sienos_m2", [
        (r"vonios sien.*plyteli", "m2"),
        (r"virtuv.*atatvar.*plyteli", "m2"),
        (r"plyteli.*klijavim.*ant sien", "m2"),
        (r"didžiaformat.*plyteli.*klijavim", "m2"),
    ]),
    # 3) Floor tile work (R4 10% weight).
    ("plyteles_grindys_m2", [
        (r"vonios grindų plyteli", "m2"),
        (r"virtuv.*grindų plyteli", "m2"),
        (r"plyteli.*klijavim.*grind", "m2"),
        (r"kit.*grindų plyteli.*klijavim", "m2"),
    ]),
    # 4) Soft floor (laminate / parquet / vinyl) (R4 15% weight).
    ("grindys_laminatas_m2", [
        (r"laminat.*klojim", "m2"),
        (r"parket.*klojim", "m2"),
        (r"vinil.*klojim", "m2"),
        (r"grindų dang.*klojim", "m2"),
    ]),
    # 5) Hidden doors (R4 10% weight) — only the kompl, not staktos.
    ("pasleptu_duru_kompl", [
        (r"paslėpt.*durų.*komplekt", "kompl"),
        (r"paslėpt.*durų.*montavim", None),
    ]),
    # 6) Ceiling work above 3m (R4 5% weight).
    ("lubos_virs_3m_m2", [
        (r"lub.*virš 3m", "m2"),
        (r"virš.*3m.*lub", "m2"),
        (r"aukšt.*virš 3m", None),  # GKP montavimas above 3m
    ]),
    # 7) Baseboards (m).
    ("grindjuostes_m", [
        (r"grindjuost", "m"),
    ]),
    # 8) GKP angokraščiai (m).
    ("angokrasciai_gkp_m", [
        (r"angokrašči.*gkp", "m"),
        (r"angokrašči.*gips", "m"),
        (r"angokrašči.*apdirbim", None),
    ]),
    # 9) Real hidroizoliacija m² (samatininkai often write vnt; we still
    # capture the row but the unit might mismatch — the GT JSON schema
    # accepts a single value so we accept the row at face value).
    ("hidroizoliacija_m2", [
        (r"hidroizoliacij", None),
    ]),
    # 10) Silicone joints (m).
    ("silikonas_m", [
        (r"kampų silikonavim", "m"),
        (r"plyteli.*silikonavim", "m"),
        (r"silikonavim.*sanitar", "m"),
        (r"silikonavim", "m"),
    ]),
]

# Default LT unit prices (mirrors backend/extractor/lt_unit_prices.json
# weights/unit_prices keys). Sourced from canonical plan §4.4 Step 1.
DEFAULT_PRICES = {
    "glaistymas_dazymas_bundle": 14.0,
    "plyteles_sienos_m2": 22.0,
    "plyteles_grindys_m2": 14.0,
    "grindys_laminatas_m2": 7.0,
    "pasleptu_duru_kompl": 250.0,
    "lubos_virs_3m_m2": 18.0,
    "grindjuostes_m": 5.0,
    "angokrasciai_gkp_m": 12.0,
    "hidroizoliacija_m2": 10.0,
    "silikonas_m": 2.5,
}

LABELS_LT = {
    "glaistymas_dazymas_bundle": "Sienų + lubų glaistymas + dažymas (bundled)",
    "plyteles_sienos_m2": "Plytelių klijavimas sienoms",
    "plyteles_grindys_m2": "Plytelių klijavimas grindims",
    "grindys_laminatas_m2": "Grindų danga (laminatas/parketas/vinilas)",
    "pasleptu_duru_kompl": "Paslėptos durys (komplektas)",
    "lubos_virs_3m_m2": "Lubų darbai virš 3m",
    "grindjuostes_m": "Grindjuostės",
    "angokrasciai_gkp_m": "Angokraščių apdaila GKP",
    "hidroizoliacija_m2": "Hidroizoliacija",
    "silikonas_m": "Silikonavimas",
}

UNITS = {
    "glaistymas_dazymas_bundle": "m²",
    "plyteles_sienos_m2": "m²",
    "plyteles_grindys_m2": "m²",
    "grindys_laminatas_m2": "m²",
    "pasleptu_duru_kompl": "kompl",
    "lubos_virs_3m_m2": "m²",
    "grindjuostes_m": "m",
    "angokrasciai_gkp_m": "m",
    "hidroizoliacija_m2": "m²",
    "silikonas_m": "m",
}


def _classify(aprasymas: str, vnt: str) -> str | None:
    a = (aprasymas or "").lower()
    v = (vnt or "").lower().strip()
    for code, patterns in PATTERNS:
        for pattern, unit_filter in patterns:
            if not re.search(pattern, a):
                continue
            if unit_filter is not None and unit_filter not in v:
                continue
            return code
    return None


_MAX_CODES = {"glaistymas_dazymas_bundle", "lubos_virs_3m_m2"}


def _build_one(project_key: str, project_data: dict) -> dict:
    """Aggregate samatininkų rows into canonical codes.

    Two reduction strategies:
      • SUM (default) — for codes where every row maps to a distinct surface
        (silikonas joints, plytelės, durys per kompl).
      • MAX (codes in _MAX_CODES) — for "bundle" codes where samatininkas
        prices the same surface in N steps (Rotband + Q1 glaistymas + Q2 +
        gruntavimas + dažymas×2). Each row reports the SAME m². Summing
        would inflate the GT 4–7×; MAX recovers the true paintable area.

    Hidroizoliacija pricing in samatininkų quotes is `kompl/vnt` (per room),
    not m². We skip those rows and rely on the V8-side per-room m² when
    comparing — see scripts/build_pred_from_project.py for the matching
    convention.
    """
    matches: dict[str, list[float]] = {code: [] for code in DEFAULT_PRICES}
    unmatched: list[str] = []
    for skyrius in project_data["skyriai"]:
        for row in skyrius["eilutes"]:
            vnt = (row.get("vnt") or "").lower()
            code = _classify(row.get("aprasymas", ""), row.get("vnt", ""))
            qty = float(row.get("kiekis") or 0)
            if code == "hidroizoliacija_m2" and "vnt" in vnt:
                # Quote priced hidroiz per-room (vnt). Skip — comparing
                # vnt-count to V8's m² value is an apples/oranges error.
                continue
            if code:
                matches[code].append(qty)
            else:
                unmatched.append(f"{row.get('vnt','?'):<8} {row.get('aprasymas','')}")
    sums: dict[str, float] = {}
    for code, vals in matches.items():
        if not vals:
            sums[code] = 0.0
        elif code in _MAX_CODES:
            sums[code] = max(vals)
        else:
            sums[code] = sum(vals)
    lines = [{
        "code": code,
        "label_lt": LABELS_LT[code],
        "unit": UNITS[code],
        "quantity": round(sums[code], 2),
        "unit_price_eur_be_pvm": DEFAULT_PRICES[code],
        "bundled_group": "glaistymas_dazymas" if code == "glaistymas_dazymas_bundle" else None,
        "verified_by": f"samatininkas (parsed_pasiulymai/{project_key})",
        "notes": "",
    } for code in DEFAULT_PRICES]
    return {
        "pdf_id": f"projektas_{project_key.lower()}",
        "pdf_hash": "",
        "project_type": "interior_finishing",
        "city": "",
        "floor_area_m2": 0,
        "vat_mode": "be_pvm",
        "lines": lines,
        "_unmatched_count": len(unmatched),
        "_unmatched_sample": unmatched[:10],
    }


def main() -> int:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    GT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for key, data in raw.items():
        gt = _build_one(key, data)
        out = GT_DIR / f"{gt['pdf_id']}.human_gt.json"
        out.write_text(json.dumps(gt, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        matched = sum(1 for l in gt["lines"] if l["quantity"] > 0)
        print(f"  {key}: {matched}/10 codes filled, {gt['_unmatched_count']} rows unmatched → {out.name}")
        written += 1
    print(f"\nWrote {written} GT files to {GT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
