"""Phase 6.5.2 — Determinism stress test.

Run extract_interior 3× on P2 (3 pages) + P3 (45 pages) and measure variance
per metric. Vision is non-deterministic; goal is to characterize how stable
the headline numbers are run-to-run.

If variance >10% → we should consider averaging / voting strategies in
production. If <10% → single run is reliable enough for user-facing output.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
OUT = Path(__file__).parent / "baseline_output"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pdf_helper import find_breziniai_pdf
from extractor import extract_interior

RUNS_PER_PROJECT = 3
PROJECTS = ["P2"]  # zoom validation focus — P2 is the no-eksplikacija worst case


def headline(result: dict) -> dict:
    s = result.get("santrauka", {}) or {}
    return {
        "rooms": len(result.get("patalpos", [])),
        "bendras_plotas_m2": result.get("bendras_plotas_m2", 0),
        "dazymo_total": s.get("dazymo_plotas_total_m2", 0),
        "kampai_total": s.get("kampai_m_total", 0),
        "plyteles_sienos_total": s.get("plyteles_sienos_m2_total", 0),
        "plyteles_grindys_total": s.get("plyteles_grindys_m2_total", 0),
        "pozicijos_count": len(result.get("pozicijos", [])),
        "elapsed_s": (result.get("_meta") or {}).get("elapsed_s", 0),
    }


def coefficient_of_variation(values: list[float]) -> float:
    """CV = stdev / mean × 100. Lower = more deterministic."""
    if not values or sum(values) == 0:
        return 0.0
    m = statistics.mean(values)
    if m == 0:
        return 0.0
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return abs(sd / m) * 100


def main():
    all_results: dict[str, list[dict]] = {p: [] for p in PROJECTS}

    for proj in PROJECTS:
        n = int(proj.lstrip("Pp"))
        pdf = find_breziniai_pdf(n)
        if not pdf:
            print(f"[{proj}] no PDF found, skip")
            continue

        for run_i in range(1, RUNS_PER_PROJECT + 1):
            print(f"\n=== {proj} run {run_i}/{RUNS_PER_PROJECT} ===")
            print(f"  PDF: {pdf.name}")
            t0 = time.time()
            result = extract_interior(pdf.read_bytes())
            elapsed = time.time() - t0
            h = headline(result)
            h["run"] = run_i
            all_results[proj].append(h)
            out_file = OUT / f"DETERMINISM_ZOOM_{proj}_run{run_i}.json"
            out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"  ✓ rooms={h['rooms']} dažymas={h['dazymo_total']} "
                  f"kampai={h['kampai_total']} plytelės={h['plyteles_sienos_total']} "
                  f"pozic={h['pozicijos_count']} t={elapsed:.0f}s")

    print("\n" + "=" * 80)
    print("DETERMINISM SUMMARY")
    print("=" * 80)
    print(f"{'Project':<8} {'Metric':<22} {'min':>10} {'mean':>10} {'max':>10} {'CV%':>8}")
    print("-" * 80)

    rows: list[dict] = []
    for proj, runs in all_results.items():
        if not runs:
            continue
        for metric in ("rooms", "bendras_plotas_m2", "dazymo_total",
                       "kampai_total", "plyteles_sienos_total",
                       "plyteles_grindys_total", "pozicijos_count"):
            values = [float(r[metric] or 0) for r in runs]
            row = {
                "project": proj,
                "metric": metric,
                "values": values,
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "cv_pct": coefficient_of_variation(values),
            }
            rows.append(row)
            print(f"{proj:<8} {metric:<22} {row['min']:>10.2f} {row['mean']:>10.2f} "
                  f"{row['max']:>10.2f} {row['cv_pct']:>7.1f}%")

    # Summary verdict
    print()
    high_variance = [r for r in rows if r["cv_pct"] > 10]
    if high_variance:
        print(f"⚠ {len(high_variance)} metrics with CV >10% (less deterministic):")
        for r in high_variance:
            print(f"  - {r['project']} {r['metric']}: CV {r['cv_pct']:.1f}%")
    else:
        print("✅ All metrics CV ≤10% — single run sufficiently deterministic.")

    md_lines = [
        "# Phase 6.5.2 — Determinism Stress Test Results",
        "",
        f"Captured: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Setup: {RUNS_PER_PROJECT} runs per project. Vision is non-deterministic;",
        "this characterizes run-to-run variance per metric.",
        "",
        "## Per-metric variance",
        "",
        f"| Project | Metric | Min | Mean | Max | CV% |",
        f"|---------|--------|-----|------|-----|-----|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['project']} | {r['metric']} | {r['min']:.2f} | {r['mean']:.2f} | "
            f"{r['max']:.2f} | {r['cv_pct']:.1f}% |"
        )

    md_lines += [
        "",
        "## Verdict",
        "",
        f"Threshold: CV >10% indicates a metric where averaging/voting may help.",
        "",
    ]
    if high_variance:
        md_lines.append(f"⚠ **{len(high_variance)} metrics flagged**:")
        for r in high_variance:
            md_lines.append(f"- {r['project']} {r['metric']}: CV {r['cv_pct']:.1f}% "
                            f"(values: {r['values']})")
    else:
        md_lines.append("✅ All metrics CV ≤10% — single run sufficiently deterministic.")

    (OUT / "DETERMINISM_REVIEW.md").write_text("\n".join(md_lines))
    print(f"\nReport: {OUT / 'DETERMINISM_REVIEW.md'}")


if __name__ == "__main__":
    main()
