"""Analyse saved per-project calibrations to surface systematic biases.

Per the council R3 verdict: closing the residual eval gap further on N=1
truth is eval-fitting. The honest path forward is to collect N≥3 truth
files and look for systematic patterns in the contractor corrections.

This module READS the per-project calibration files written by
``backend/api/calibrate.py`` and reports:

  • Per-metric factor median + IQR across all projects
  • Outlier projects (factors > 1.5σ from median)
  • Direction-consistency check (do all contractors push the same way?)
  • A "would-not-propose-global-change" guardrail: a candidate global
    correction is reported only if direction-consistent across ≥3
    projects AND IQR < 0.05.

It does NOT write back to global formulas. Output is advisory; promotion
to global tuning is a human review decision (separate process).
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

CALIB_ROOT = Path(__file__).resolve().parents[1] / "data" / "calibrations"

PROMOTION_RULES = {
    # A candidate global correction is reported only when ALL of these hold.
    "min_projects": 3,
    "max_iqr": 0.05,                 # interquartile range must be tight
    "direction_consistency": 1.0,    # 100% of projects pushing same way
}


@dataclass
class MetricStats:
    metric: str
    label: str
    unit: str
    n_projects: int
    factors: list[float]
    median: float
    mean: float
    stdev: float
    iqr: float
    direction_consistency: float  # fraction of projects in the dominant sign
    outliers: list[dict[str, Any]] = field(default_factory=list)
    promotion_candidate: bool = False
    promotion_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_calibrations(root: Path | None = None) -> list[dict[str, Any]]:
    root = root or CALIB_ROOT
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(root.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _iqr(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    q = statistics.quantiles(values, n=4, method="inclusive")
    return q[2] - q[0]


def _direction_consistency(factors: list[float]) -> float:
    """Fraction of factors pointing in the dominant direction (>1 vs <1)."""
    if not factors:
        return 0.0
    up = sum(1 for f in factors if f > 1.0)
    down = sum(1 for f in factors if f < 1.0)
    dominant = max(up, down)
    nonzero = up + down
    return (dominant / nonzero) if nonzero else 0.0


def analyze(root: Path | None = None) -> dict[str, Any]:
    calibs = _load_calibrations(root)
    by_metric: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for cal in calibs:
        pid = cal.get("project_id") or "?"
        for metric, info in (cal.get("factors") or {}).items():
            if not info.get("applied"):
                continue
            f = info.get("factor")
            if f is None:
                continue
            by_metric.setdefault(metric, []).append((pid, info))

    metric_stats: list[MetricStats] = []
    for metric, entries in by_metric.items():
        factors = [float(info["factor"]) for _pid, info in entries]
        label = entries[0][1].get("label", metric)
        unit = entries[0][1].get("unit", "")
        median = statistics.median(factors)
        mean = statistics.fmean(factors)
        stdev = statistics.pstdev(factors) if len(factors) > 1 else 0.0
        iqr = _iqr(factors)
        dirc = _direction_consistency(factors)

        outliers = []
        if stdev > 0:
            for (pid, info) in entries:
                z = (float(info["factor"]) - median) / stdev
                if abs(z) > 1.5:
                    outliers.append({"project_id": pid, "factor": info["factor"],
                                     "z_score": round(z, 3)})

        # Promotion candidate gating
        is_candidate = (
            len(factors) >= PROMOTION_RULES["min_projects"]
            and iqr <= PROMOTION_RULES["max_iqr"]
            and dirc >= PROMOTION_RULES["direction_consistency"]
            and abs(median - 1.0) > 0.005  # meaningful (>0.5%) median shift
        )
        reason = ""
        if not is_candidate:
            if len(factors) < PROMOTION_RULES["min_projects"]:
                reason = f"only {len(factors)} project(s); need ≥{PROMOTION_RULES['min_projects']}"
            elif iqr > PROMOTION_RULES["max_iqr"]:
                reason = f"IQR {iqr:.3f} > {PROMOTION_RULES['max_iqr']}: corrections vary across contractors"
            elif dirc < PROMOTION_RULES["direction_consistency"]:
                reason = f"direction inconsistency: only {dirc * 100:.0f}% in dominant sign"
            elif abs(median - 1.0) <= 0.005:
                reason = f"median factor {median:.4f} within ±0.5% of 1.0; no shift"
        else:
            reason = (f"{len(factors)} projects, IQR {iqr:.3f}, "
                      f"{dirc * 100:.0f}% same direction, median {median:.4f} "
                      f"(~{(median - 1) * 100:+.2f}%): consider promoting")

        metric_stats.append(MetricStats(
            metric=metric, label=label, unit=unit, n_projects=len(factors),
            factors=factors, median=median, mean=mean, stdev=stdev,
            iqr=iqr, direction_consistency=dirc, outliers=outliers,
            promotion_candidate=is_candidate, promotion_reason=reason,
        ))

    perim_factors = [
        (cal.get("project_id"), float(cal["perimeter_correction_factor"]))
        for cal in calibs
        if cal.get("perimeter_correction_factor") is not None
    ]

    return {
        "n_projects": len(calibs),
        "project_ids": [c.get("project_id") for c in calibs],
        "metrics": [m.to_dict() for m in metric_stats],
        "perimeter_correction_factor": {
            "n_projects": len(perim_factors),
            "values": perim_factors,
            "median": statistics.median([v for _, v in perim_factors]) if perim_factors else None,
        },
        "promotion_rules": PROMOTION_RULES,
        "candidates": [m.to_dict() for m in metric_stats if m.promotion_candidate],
    }


def _fmt_table_row(*cells: str, widths: tuple[int, ...]) -> str:
    return "  ".join(c.ljust(w) for c, w in zip(cells, widths))


def render_report(report: dict[str, Any]) -> str:
    lines = []
    lines.append("")
    lines.append(f"═══ Calibration Learner — {report['n_projects']} project(s) analysed ═══")
    lines.append("")
    if not report["metrics"]:
        lines.append("  No applied calibrations found yet.")
        lines.append("  Save at least one calibration via the Kalibruoti modal to populate this report.")
        return "\n".join(lines)

    widths = (28, 4, 9, 9, 9, 9, 28)
    lines.append(_fmt_table_row("metric", "n", "median", "iqr", "stdev", "dir", "promotion", widths=widths))
    lines.append("  " + "─" * 100)
    for m in report["metrics"]:
        lines.append(_fmt_table_row(
            m["label"][:28],
            str(m["n_projects"]),
            f"{m['median']:.4f}",
            f"{m['iqr']:.3f}",
            f"{m['stdev']:.3f}",
            f"{m['direction_consistency'] * 100:.0f}%",
            "CANDIDATE" if m["promotion_candidate"] else "no",
            widths=widths,
        ))
        if m["outliers"]:
            for o in m["outliers"]:
                lines.append(f"    outlier: {o['project_id']:<20} factor={o['factor']}  z={o['z_score']:+.2f}")
        if m["promotion_reason"]:
            lines.append(f"    → {m['promotion_reason']}")

    pcf = report["perimeter_correction_factor"]
    lines.append("")
    lines.append(f"  Perimeter correction factor: {pcf['n_projects']} project(s) configured.")
    if pcf["values"]:
        for pid, v in pcf["values"]:
            lines.append(f"    {pid}: {v:.5f}")
        if pcf["median"] is not None:
            lines.append(f"    median: {pcf['median']:.5f}")

    if report["candidates"]:
        lines.append("")
        lines.append("  ⚠ GLOBAL-PROMOTION CANDIDATES (human review required):")
        for c in report["candidates"]:
            lines.append(f"    • {c['label']} ({c['metric']}) — {c['promotion_reason']}")
        lines.append("    Promotion is a manual decision. Verify the metric's formula in")
        lines.append("    CLAUDE.md Section 1, run eval_harness.py with the candidate factor,")
        lines.append("    and confirm headline MAE does NOT regress on any existing truth.")
    else:
        lines.append("")
        lines.append("  No promotion candidates. Either insufficient projects or the corrections")
        lines.append("  are not consistent enough to indicate a systematic formula bias.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m backend.extractor.calibration_learner")
    ap.add_argument("--root", type=Path, default=None,
                    help="Override calibration root (default: backend/data/calibrations)")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON instead of a human-readable table")
    args = ap.parse_args(argv)
    report = analyze(root=args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
