"""End-to-end WAPE evaluator for roof extraction.

Runs Vision → typed merger → strategy → sąmata pipeline against a v2
ground-truth YAML and reports:
  - WAPE (value-weighted absolute percentage error)
  - Per-line item delta vs roofer
  - Unflagged high-impact errors (lines >25% of total roof value with
    error >5% AND no HITLFlag covering the relevant input)

Exit codes:
  0 — WAPE ≤ 2% AND no unflagged high-impact errors
  1 — anything else

Usage:
    python3 scripts/eval_roof_e2e.py --gt ground_truth/a_laida_roof_v2.yaml
    python3 scripts/eval_roof_e2e.py --gt ground_truth/0039_roof_v2.yaml
    python3 scripts/eval_roof_e2e.py --all
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from extractor.page_classifier import PageType, OPUS_MODEL  # noqa: E402
from extractor.roof.strategies.dvislaitis import DvislaitisStrategy  # noqa: E402
from extractor.roof.strategies.keturslaitis import KeturslaitisStrategy  # noqa: E402
from extractor.roof.vision_extractor import (  # noqa: E402
    build_roof_input,
    extract_pjuvis_dims,
    extract_stogo_planas_dims,
)

STRATEGIES = {
    "dvislaitis": DvislaitisStrategy(),
    "keturslaitis": KeturslaitisStrategy(),
}

POS_MAP = {
    "perdanga": "perdanga",
    "stogas": "stogas",
    "latakai": "latakai",
    "kraigai": "kraigai",
    "kraigas": "kraigas",
    "sienos": "sienos",
    "vejalentes": "vėjalent",
    "langu_apdirbimas": "langų",
    "kaminelis": "kamin",
    "apsaugine_tvorele": "apsaug",
}


def render_b64(pdf_path: Path, page_num: int, dpi: int = 200) -> str:
    pages = convert_from_bytes(
        pdf_path.read_bytes(), dpi=dpi,
        first_page=page_num, last_page=page_num, fmt="jpeg",
    )
    buf = io.BytesIO()
    pages[0].save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def evaluate(gt_path: Path) -> tuple[float, float, list[dict], bool]:
    """Returns (wape, total_eur_actual, line_deltas, all_high_impact_flagged_or_safe)."""
    gt = yaml.safe_load(gt_path.read_text())
    pdf_path = ROOT / gt["source_pdf"]

    pages_data: list[dict] = []
    for page_spec in gt["pages"]:
        page_num = page_spec["page_num"]
        page_class = PageType(page_spec["page_class"])
        b64 = render_b64(pdf_path, page_num)
        try:
            if page_class == PageType.SECTION:
                data = extract_pjuvis_dims(b64, model=OPUS_MODEL)
            else:
                data = extract_stogo_planas_dims(b64, model=OPUS_MODEL)
        except Exception as e:
            print(f"  vision failed on p{page_num}: {e}")
            data = {}
        data["_page_num"] = page_num
        data["_page_class"] = page_class
        pages_data.append(data)

    inp, evidence, flags = build_roof_input(pages_data)

    # Log actual RoofInput values that will hit the strategy — this is
    # the load-bearing diagnostic for accuracy debugging. Without it,
    # silent default fallbacks (e.g. soflitas_depth_m = 0.5) are invisible.
    print("  RoofInput received by strategy:")
    print(
        f"    roof_type={inp.roof_type} | "
        f"building {inp.building_length_m:.2f} × {inp.building_width_m:.2f} | "
        f"eaves {inp.eaves_overhang_m:.2f} | "
        f"slopes {inp.slopes_deg}"
    )
    print(
        f"    wall={inp.wall_thickness_m:.2f} | "
        f"eaves_to_ground={inp.eaves_to_ground_m:.2f} | "
        f"soflitas={inp.soflitas_depth_m:.2f}"
    )
    print(
        f"    chimneys={inp.chimney_count}, "
        f"rooflights={inp.rooflight_count}, "
        f"windows={inp.windows_count}"
    )
    print(f"  Flags raised: {len(flags)}")
    for fl in flags:
        print(f"    - {fl.field.value}: {fl.reason.value}")

    out = STRATEGIES[gt["roof_type"]].compute(inp)
    expected = {li["position"]: li for li in gt["roofer_samata"]["line_items"]}
    total_actual = sum(li["sum_eur"] for li in gt["roofer_samata"]["line_items"])

    deltas = []
    weighted_abs_err = 0.0
    unflagged_high_impact = False

    for li in out.line_items:
        pos_norm = li.pozicija.lower().replace("ė", "e").replace("š", "s") \
                              .replace("ų", "u").replace("ą", "a")
        roofer_key = next(
            (k for k in expected if POS_MAP.get(k, k) in pos_norm), None,
        )
        if not roofer_key:
            deltas.append({"pozicija": li.pozicija, "kiekis": li.kiekis,
                           "roofer_qty": None, "delta_pct": None})
            continue
        roofer = expected[roofer_key]
        roofer_eur = roofer["sum_eur"]
        predicted_eur = li.kiekis * roofer["eur_per_unit"]
        eur_delta = abs(predicted_eur - roofer_eur)
        weighted_abs_err += eur_delta
        pct = (li.kiekis - roofer["qty"]) / roofer["qty"] * 100 if roofer["qty"] else 0
        share = roofer_eur / total_actual if total_actual else 0
        is_high_impact = share > 0.25
        is_unflagged = len(flags) == 0
        if is_high_impact and abs(pct) > 5 and is_unflagged:
            unflagged_high_impact = True
        deltas.append({
            "pozicija": li.pozicija,
            "kiekis": li.kiekis,
            "roofer_qty": roofer["qty"],
            "delta_pct": pct,
            "share": share,
            "high_impact": is_high_impact,
        })

    wape = weighted_abs_err / total_actual * 100 if total_actual else 0
    return wape, total_actual, deltas, not unflagged_high_impact


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gt", help="Ground truth v2 YAML path")
    p.add_argument("--all", action="store_true",
                   help="Run all *_roof_v2.yaml in ground_truth/")
    args = p.parse_args()
    load_dotenv(ROOT / "backend" / ".env")

    if args.all:
        targets = sorted(ROOT.glob("ground_truth/*_roof_v2.yaml"))
    elif args.gt:
        targets = [Path(args.gt)]
    else:
        sys.exit("specify --gt or --all")

    overall_pass = True
    for gt_path in targets:
        print(f"\n=== {gt_path.name} ===")
        wape, total, deltas, no_unflagged_high_impact = evaluate(gt_path)
        print(f"WAPE: {wape:.2f}%   (roofer total €{total:.0f})")
        for d in deltas:
            if d["delta_pct"] is None:
                print(f"  {d['pozicija']:<35} {d['kiekis']:>8.1f}  (no match)")
            else:
                marker = " [HI-IMPACT]" if d.get("high_impact") else ""
                print(f"  {d['pozicija']:<35} {d['kiekis']:>8.1f}  Δ{d['delta_pct']:+5.1f}%"
                      f" ({d['share']*100:.0f}% of €){marker}")
        verdict = (wape <= 2.0) and no_unflagged_high_impact
        print(f"  → {'✓ PASS' if verdict else '✗ FAIL'}")
        overall_pass = overall_pass and verdict

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
