"""Run EUR-weighted benchmark over the human GT corpus.

Usage:
  python scripts/run_eur_benchmark.py
  python scripts/run_eur_benchmark.py --gt data/human_gt --pred data/predictions \
                                       --out reports/benchmark/latest.md

Reads each `*.human_gt.json` from `--gt`, looks for matching
`<pdf_id>.pred.json` in `--pred`, and writes a Markdown report with
per-PDF + mean EUR-weighted error plus top-EUR misses.

This is the scaffolding (Week 4 Task 4.4). Until human GT is filled in
(Week 6) and predictions are generated against it, the report will simply
list zeros — that's expected and not a bug.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.extractor.benchmark.eur_weighted import (  # noqa: E402
    eur_weighted_error,
    per_line_eur_impact,
)


def _load_lines(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {l["code"]: float(l.get("quantity", 0)) for l in raw.get("lines", [])}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--gt", default="data/human_gt", help="GT directory")
    p.add_argument("--pred", default="data/predictions", help="Predictions directory")
    p.add_argument("--out", default="reports/benchmark/latest.md")
    args = p.parse_args()

    gt_dir = REPO_ROOT / args.gt
    pred_dir = REPO_ROOT / args.pred
    out_path = REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gt_files = sorted(gt_dir.glob("*.human_gt.json"))
    if not gt_files:
        print(f"WARN: no GT files in {gt_dir}", file=sys.stderr)

    rows: list[dict] = []
    aggregate_misses: dict[str, float] = {}

    for gt_file in gt_files:
        pdf_id = gt_file.stem.replace(".human_gt", "")
        pred_file = pred_dir / f"{pdf_id}.pred.json"
        if not pred_file.exists():
            rows.append({"pdf_id": pdf_id, "status": "no_pred", "error": None})
            continue
        gt = _load_lines(gt_file)
        pred = _load_lines(pred_file)
        err = eur_weighted_error(pred, gt)
        err_in_scope = eur_weighted_error(pred, gt, in_scope_only=True)
        rows.append({
            "pdf_id": pdf_id,
            "status": "ok",
            "error": err,
            "error_in_scope": err_in_scope,
        })
        for impact in per_line_eur_impact(pred, gt)[:5]:
            aggregate_misses[impact["code"]] = (
                aggregate_misses.get(impact["code"], 0.0) + impact["abs_eur_impact"]
            )

    with out_path.open("w", encoding="utf-8") as f:
        f.write("# EUR-weighted benchmark report\n\n")
        f.write("| PDF | Status | All-codes error | In-scope error |\n"
                "|---|---|---|---|\n")
        ok_rows = [r for r in rows if r["status"] == "ok"]
        for r in rows:
            if r["status"] != "ok":
                f.write(f"| {r['pdf_id']} | {r['status']} | — | — |\n")
                continue
            f.write(
                f"| {r['pdf_id']} | ok "
                f"| {r['error']*100:.1f}% "
                f"| {r['error_in_scope']*100:.1f}% |\n"
            )
        if ok_rows:
            mean_all = sum(r["error"] for r in ok_rows) / len(ok_rows)
            mean_scope = sum(r["error_in_scope"] for r in ok_rows) / len(ok_rows)
            f.write(
                f"\n**Mean across {len(ok_rows)} PDFs:** "
                f"all-codes {mean_all*100:.1f}% · "
                f"**in-scope {mean_scope*100:.1f}%** "
                f"(target ≤ 8% per R4)\n"
            )
            f.write(
                "\n_In-scope counts only codes where GT > 0. Use this when "
                "samatininkas bid only a partial scope; otherwise the metric "
                "explodes on every category they didn't price._\n"
            )

        if aggregate_misses:
            f.write("\n## Top EUR misses across corpus (sum of abs deltas)\n\n")
            f.write("| Line code | Aggregate EUR impact |\n|---|---|\n")
            for code, eur in sorted(aggregate_misses.items(), key=lambda kv: -kv[1])[:10]:
                f.write(f"| {code} | {eur:.2f} € |\n")

        if not gt_files:
            f.write("\n_No GT files found. Bootstrap with `python scripts/bootstrap_human_gt.py`._\n")
        elif not ok_rows:
            f.write(
                "\n_No predictions matched GT. Run pipeline against the GT PDFs and "
                "place outputs at `data/predictions/<pdf_id>.pred.json` first._\n"
            )

    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
