"""Phase 3 validation: run the new extractor.extract_interior on P1-P5 directly.

Purpose: Confirm the new extractor/ package produces results consistent with the
Phase 1 baseline (which used the same prompt before refactoring into a package).
The extractor adds two post-processing steps not in baseline_vision.py:
  - _recompute_santrauka (deterministic totals via calc_totals)
  - apply_lt_sanity (adds _lt_warnings, no value mutation)
Both should be transparent to the headline numbers.

Output: backend/scripts/baseline_output/EXTRACTOR_PN.json + EXTRACTOR_REVIEW.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training-data"
OUT = Path(__file__).parent / "baseline_output"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_v8_baseline import find_breziniai_pdf  # PDF discovery (largest variant)
from extractor import extract_interior


def run_one(project_id: str) -> dict:
    n = int(project_id.lstrip("Pp"))
    pdf = find_breziniai_pdf(n)
    if pdf is None or not pdf.exists():
        return {"_error": f"PDF not found for {project_id}"}
    print(f"\n=== {project_id} ===")
    print(f"  PDF: {pdf.name} ({pdf.stat().st_size // 1024} KB)")
    t0 = time.time()
    result = extract_interior(pdf.read_bytes())
    print(f"  status={result.get('status')} elapsed={round(time.time()-t0,1)}s")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="+", help="P1 P2 P3 P4 P5")
    args = ap.parse_args()

    rows = []
    for proj in args.projects:
        result = run_one(proj)
        out_file = OUT / f"EXTRACTOR_{proj.upper()}.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("status") != "ok":
            print(f"  ERROR: {result.get('_error')}")
            rows.append({"project": proj, "error": result.get("_error", "unknown")})
            continue
        s = result.get("santrauka", {}) or {}
        m = result.get("_meta", {}) or {}
        row = {
            "project": proj,
            "rooms": len(result.get("patalpos", [])),
            "bendras_plotas_m2": result.get("bendras_plotas_m2"),
            "dazymo_total": s.get("dazymo_plotas_total_m2"),
            "kampai_total": s.get("kampai_m_total"),
            "plyteles_sienos_total": s.get("plyteles_sienos_m2_total"),
            "pozicijos_count": len(result.get("pozicijos", [])),
            "lt_warnings_count": len(result.get("_lt_warnings", [])),
            "elapsed_s": m.get("elapsed_s"),
        }
        rows.append(row)
        print(f"  ✓ rooms={row['rooms']} plotas={row['bendras_plotas_m2']} "
              f"dažymas={row['dazymo_total']} kampai={row['kampai_total']} "
              f"plytelės={row['plyteles_sienos_total']} pozicijos={row['pozicijos_count']} "
              f"warns={row['lt_warnings_count']} t={row['elapsed_s']}s")

    print("\n" + "=" * 80)
    print("PHASE 3 EXTRACTOR PIPELINE SUMMARY")
    print("=" * 80)
    print(f"{'P#':<4} {'Rooms':<6} {'Plotas':<8} {'Dažymas':<9} {'Kampai':<8} "
          f"{'Plytelės':<9} {'Pozic':<6} {'Warns':<6} {'t(s)':<6}")
    for row in rows:
        if "error" in row:
            print(f"{row['project']:<4} ERROR: {row['error'][:60]}")
            continue
        print(f"{row['project']:<4} {row['rooms']:<6} "
              f"{(row['bendras_plotas_m2'] or 0):<8.1f} "
              f"{(row['dazymo_total'] or 0):<9.1f} "
              f"{(row['kampai_total'] or 0):<8.1f} "
              f"{(row['plyteles_sienos_total'] or 0):<9.1f} "
              f"{row['pozicijos_count']:<6} "
              f"{row['lt_warnings_count']:<6} "
              f"{(row['elapsed_s'] or 0):<6.1f}")
    print(f"\nResults: {OUT}")


if __name__ == "__main__":
    main()
