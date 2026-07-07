"""Compare two eval_harness model runs → markdown report (W1.2, 2026-07-03).

Pure post-processing: reads results.json files written by
``eval_harness.py --vision --model <id>`` (eval_runs/<model>/<ts>_<slug>_vision/
results.json) and emits a markdown comparison table. NO API calls, no
backend imports — safe to run anywhere.

Usage:
    # one project, two runs
    python scripts/compare_model_runs.py opus_results.json fable_results.json

    # the 4-project benchmark: N runs per side, matched by project slug
    python scripts/compare_model_runs.py \
        --a eval_runs/claude-opus-4-8/*/results.json \
        --b eval_runs/claude-fable-5/*/results.json \
        -o docs/superpowers/research/2026-07-03-fable5-benchmark.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_TOKEN_KEYS = ("input_tokens", "output_tokens",
               "cache_read_tokens", "cache_write_tokens")


def _load(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    if "metrics" not in data or "project" not in data:
        raise SystemExit(
            f"{path}: not an eval_harness results.json "
            "(expected 'project' + 'metrics' keys)"
        )
    return data


def _fmt(v, nd: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _fmt_pct(v) -> str:
    return "—" if v is None else f"{v:+.2f}%"


def _mae(metrics: list[dict]) -> float | None:
    errs = [abs(m["pct_error"]) for m in metrics if m.get("pct_error") is not None]
    return round(sum(errs) / len(errs), 2) if errs else None


def _label(runs: list[dict], explicit: str | None) -> str:
    if explicit:
        return explicit
    models = {r.get("model") or (r.get("meta_rollup") or {}).get("model")
              for r in runs}
    models.discard(None)
    if len(models) == 1:
        return next(iter(models))
    return "A/B run"


def _rollup(run: dict) -> dict:
    return run.get("meta_rollup") or {}


def _reader_elapsed(run: dict) -> dict[str, float]:
    """Per-reader breakdown when _meta carries it: any raw_meta key shaped
    ``<reader>_elapsed_s`` (doors_elapsed_s, apdailos_elapsed_s, ...)."""
    raw = _rollup(run).get("raw_meta") or {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        m = re.fullmatch(r"([a-z0-9_]+)_elapsed_s", k)
        if m and isinstance(v, (int, float)) and m.group(1) != "":
            out[m.group(1)] = float(v)
    return out


def build_report(runs_a: list[dict], runs_b: list[dict],
                 label_a: str | None = None, label_b: str | None = None) -> str:
    la = _label(runs_a, label_a)
    lb = _label(runs_b, label_b)
    by_a = {r["project"]: r for r in runs_a}
    by_b = {r["project"]: r for r in runs_b}
    projects = sorted(set(by_a) | set(by_b))

    lines: list[str] = []
    lines.append(f"# Model comparison — {la} vs {lb}")
    lines.append("")
    lines.append(f"- A = **{la}** ({len(runs_a)} run(s))")
    lines.append(f"- B = **{lb}** ({len(runs_b)} run(s))")
    lines.append("")

    # ── Per-project metric tables ────────────────────────────────────────
    project_maes: list[tuple[str, float | None, float | None]] = []
    for slug in projects:
        ra, rb = by_a.get(slug), by_b.get(slug)
        lines.append(f"## {slug}")
        lines.append("")
        if ra is None or rb is None:
            missing = la if ra is None else lb
            lines.append(f"⚠ no {missing} run for this project — skipped.")
            lines.append("")
            project_maes.append((slug,
                                 _mae(ra["metrics"]) if ra else None,
                                 _mae(rb["metrics"]) if rb else None))
            continue
        ma = {m["truth_key"]: m for m in ra["metrics"]}
        mb = {m["truth_key"]: m for m in rb["metrics"]}
        lines.append(f"| Metric | Unit | Truth | {la} | {lb} "
                     f"| %err {la} | %err {lb} |")
        lines.append("|---|---|---:|---:|---:|---:|---:|")
        for key in ma:
            a = ma[key]
            b = mb.get(key, {})
            truth = a.get("truth_value")
            if truth is None and a.get("status") in ("no_truth",):
                continue
            lines.append(
                f"| {a.get('label', key)} | {a.get('unit', '')} "
                f"| {_fmt(truth)} | {_fmt(a.get('actual_value'))} "
                f"| {_fmt(b.get('actual_value'))} "
                f"| {_fmt_pct(a.get('pct_error'))} "
                f"| {_fmt_pct(b.get('pct_error'))} |"
            )
        mae_a, mae_b = _mae(ra["metrics"]), _mae(rb["metrics"])
        project_maes.append((slug, mae_a, mae_b))
        lines.append(f"| **MAE** | % | | | | **{_fmt(mae_a)}** | **{_fmt(mae_b)}** |")
        lines.append("")

    # ── MAE summary ──────────────────────────────────────────────────────
    lines.append("## Per-project MAE (mean |%err| over scored metrics)")
    lines.append("")
    lines.append(f"| Project | {la} | {lb} |")
    lines.append("|---|---:|---:|")
    for slug, mae_a, mae_b in project_maes:
        lines.append(f"| {slug} | {_fmt(mae_a)} | {_fmt(mae_b)} |")
    a_maes = [m for _, m, _ in project_maes if m is not None]
    b_maes = [m for _, _, m in project_maes if m is not None]
    lines.append(
        f"| **mean** | **{_fmt(sum(a_maes) / len(a_maes) if a_maes else None)}** "
        f"| **{_fmt(sum(b_maes) / len(b_maes) if b_maes else None)}** |"
    )
    lines.append("")

    # ── Totals: tokens, cost, wall time ──────────────────────────────────
    lines.append("## Totals (tokens / cost / time)")
    lines.append("")
    lines.append(f"| | {la} | {lb} |")
    lines.append("|---|---:|---:|")
    for key in _TOKEN_KEYS:
        ta = sum(int(_rollup(r).get(key) or 0) for r in runs_a)
        tb = sum(int(_rollup(r).get(key) or 0) for r in runs_b)
        lines.append(f"| {key} | {ta:,} | {tb:,} |")
    for cost_key, unit in (("cost_usd", "$"), ("cost_eur", "€")):
        ca = [(_rollup(r).get(cost_key)) for r in runs_a]
        cb = [(_rollup(r).get(cost_key)) for r in runs_b]
        sa = sum(c for c in ca if c is not None) if any(c is not None for c in ca) else None
        sb = sum(c for c in cb if c is not None) if any(c is not None for c in cb) else None
        lines.append(f"| {cost_key} | {unit}{_fmt(sa, 4)} | {unit}{_fmt(sb, 4)} |")
    wa = sum(float(_rollup(r).get("wall_time_s") or 0) for r in runs_a)
    wb = sum(float(_rollup(r).get("wall_time_s") or 0) for r in runs_b)
    lines.append(f"| wall time (min) | {wa / 60:.1f} | {wb / 60:.1f} |")
    lines.append("")

    # ── Per-reader breakdown (when _meta carries it) ─────────────────────
    reader_rows: dict[str, dict[str, dict[str, float]]] = {}
    for side, runs in ((la, runs_a), (lb, runs_b)):
        for r in runs:
            for reader, elapsed in _reader_elapsed(r).items():
                reader_rows.setdefault(reader, {}).setdefault(side, {})
                reader_rows[reader][side][r["project"]] = elapsed
    if reader_rows:
        lines.append("## Per-reader elapsed (s, summed across projects)")
        lines.append("")
        lines.append(f"| Reader | {la} | {lb} |")
        lines.append("|---|---:|---:|")
        for reader in sorted(reader_rows):
            sa = sum(reader_rows[reader].get(la, {}).values()) or None
            sb = sum(reader_rows[reader].get(lb, {}).values()) or None
            lines.append(f"| {reader} | {_fmt(sa, 1)} | {_fmt(sb, 1)} |")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Diff two eval_harness model runs → markdown (no API calls)")
    ap.add_argument("positional", nargs="*",
                    help="shorthand: exactly two results.json files (A B)")
    ap.add_argument("--a", nargs="+", default=None, metavar="RESULTS_JSON",
                    help="side-A results.json file(s), one per project")
    ap.add_argument("--b", nargs="+", default=None, metavar="RESULTS_JSON",
                    help="side-B results.json file(s), one per project")
    ap.add_argument("--label-a", default=None)
    ap.add_argument("--label-b", default=None)
    ap.add_argument("-o", "--out", default=None,
                    help="write markdown here (also printed to stdout)")
    args = ap.parse_args(argv)

    if args.a and args.b:
        files_a, files_b = args.a, args.b
    elif len(args.positional) == 2 and not (args.a or args.b):
        files_a, files_b = [args.positional[0]], [args.positional[1]]
    else:
        ap.error("pass exactly two results.json files, or --a ... --b ...")

    report = build_report([_load(p) for p in files_a],
                          [_load(p) for p in files_b],
                          args.label_a, args.label_b)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"\n→ written to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
