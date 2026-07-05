#!/usr/bin/env python3
"""Final production-config decision table — aggregates every eval_runs config.

Scans eval_runs/<config>/<run>_vision/results.json (latest run per
config×project), prints a markdown matrix: headline MAE + all-scored MAE +
cost + wall time per project per config, with per-config averages.
Rescored artifacts (results_rescored*.json) are preferred over originals so
every config is judged against the CURRENT truth mappings.

Usage: venv/bin/python scripts/final_config_table.py [-o out.md]
"""
import argparse
import glob
import json
import os
import re
from collections import defaultdict

PROJECTS = ["berzas", "objektas_b", "ciurliu", "lazunu"]


def latest_results(config_dir, project):
    runs = sorted(glob.glob(os.path.join(config_dir, f"*_{project}_vision")))
    if not runs:
        return None
    run = runs[-1]
    # prefer the most recently rescored artifact
    cands = sorted(glob.glob(os.path.join(run, "results_rescored*.json"))) or \
        [os.path.join(run, "results.json")]
    path = cands[-1]
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def all_scored_mae(d):
    errs = [abs(m["pct_error"]) for m in d.get("metrics", [])
            if m.get("pct_error") is not None]
    return sum(errs) / len(errs) if errs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    configs = sorted(d for d in glob.glob("eval_runs/*") if os.path.isdir(d)
                     and not d.endswith("_quarantine"))
    rows = defaultdict(dict)
    for cfg_dir in configs:
        cfg = os.path.basename(cfg_dir)
        for p in PROJECTS:
            d = latest_results(cfg_dir, p)
            if not d:
                continue
            mr = d.get("meta_rollup") or {}
            rows[cfg][p] = {
                "headline": d["summary"]["headline_mae_pct"],
                "all": all_scored_mae(d),
                "eur": mr.get("cost_eur"),
                "min": (mr.get("wall_time_s") or 0) / 60,
            }

    lines = ["# Final config decision table", ""]
    header = "| config | " + " | ".join(PROJECTS) + " | avg headline | avg all-scored | total € | total min |"
    lines += [header, "|" + "---|" * (len(PROJECTS) + 5)]
    for cfg, per in sorted(rows.items()):
        cells, hl, al, eur, mins = [], [], [], 0.0, 0.0
        for p in PROJECTS:
            r = per.get(p)
            if not r:
                cells.append("—")
                continue
            cells.append(f"{r['headline']:.1f}% / {r['all']:.1f}%")
            hl.append(r["headline"])
            al.append(r["all"])
            eur += r["eur"] or 0
            mins += r["min"]
        n = len(hl)
        lines.append(
            f"| {cfg} ({n}/4) | " + " | ".join(cells)
            + f" | {sum(hl)/n:.1f}% | {sum(al)/n:.1f}% | {eur:.2f} | {mins:.0f} |"
            if n else f"| {cfg} (0/4) | " + " | ".join(cells) + " | — | — | — | — |"
        )
    lines += ["", "Cells: headline MAE / all-scored MAE. Averages over available projects only — compare configs on equal project sets."]
    out = "\n".join(lines)
    print(out)
    if args.out:
        with open(args.out, "w") as f:
            f.write(out + "\n")


if __name__ == "__main__":
    main()
