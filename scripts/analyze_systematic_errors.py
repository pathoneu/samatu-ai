"""Analyse cross-project AI-vs-truth errors for systematic patterns.

For each metric:
  • per-project signed % error
  • count of projects where the error is meaningful (>1%)
  • count of projects where the sign is consistent
  • if ≥3 same-sign meaningful errors → flag as CANDIDATE systematic
    error worth a prompt/pipeline fix

Reads each project's ai_extract.json + truth.json. Skips projects
that don't have an AI extract yet (no penalty for absence).
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Reuse the eval harness METRICS table so we have the canonical accessor mapping.
sys.path.insert(0, str(REPO_ROOT / "backend"))
from eval_harness import METRICS  # noqa: E402


def _load_all() -> list[dict]:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    out = []
    for entry in reg.get("projects") or []:
        slug = entry["slug"]
        if entry.get("scope_mismatch") or entry.get("blocked_for_vision_extraction"):
            # Exclude from systematic error analysis — keep visible in summary.
            out.append({
                "slug": slug, "name": entry.get("name", slug),
                "excluded": True,
                "reason": (entry.get("scope_mismatch_reason") or
                           entry.get("blocked_reason") or "excluded"),
                "truth": None, "ai": None,
            })
            continue
        truth_path = REPO_ROOT / entry["truth_path"]
        if not truth_path.exists():
            continue
        ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
        ai = json.loads(ai_path.read_text()) if ai_path.exists() else None
        if ai is None and slug == "berzas":
            # Fall back to cached replay for berzas
            ai_path = REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json"
            if ai_path.exists():
                ai = json.loads(ai_path.read_text())
        out.append({
            "slug": slug, "name": entry.get("name", slug),
            "truth": json.loads(truth_path.read_text()),
            "ai": ai,
        })
    return out


def main() -> int:
    projects = _load_all()
    excluded = [p for p in projects if p.get("excluded")]
    scored = [p for p in projects if not p.get("excluded") and p["ai"] is not None]
    print(f"\n  Analysing {len(scored)}/{len(projects)} projects with AI extracts")
    if excluded:
        print(f"  Excluded {len(excluded)} project(s):")
        for e in excluded:
            print(f"    • {e['slug']}: {e['reason'].split(chr(10))[0]}")
    print()

    # Build per-metric per-project signed % errors
    per_metric: dict[str, list[dict]] = defaultdict(list)
    for p in scored:
        gt = p["truth"].get("gt_totals") or {}
        for truth_key, spec in gt.items():
            if not isinstance(spec, dict):
                continue
            truth_val = spec.get("value")
            if not isinstance(truth_val, (int, float)) or truth_val <= 0:
                continue
            meta = METRICS.get(truth_key)
            if not meta:
                continue
            ai_val = meta["accessor"](p["ai"])
            if not isinstance(ai_val, (int, float)) or ai_val == 0.0:
                # Treat absent / zero AI value as "not emitted"
                continue
            err_pct = (ai_val - truth_val) / truth_val * 100
            per_metric[truth_key].append({
                "slug": p["slug"], "truth": truth_val, "ai": ai_val,
                "err_pct": err_pct, "label": meta["label"],
            })

    print(f"  ═══ Per-metric breakdown ═══\n")
    candidates = []
    for truth_key, rows in sorted(per_metric.items(), key=lambda x: -len(x[1])):
        if len(rows) < 2:
            continue
        n_same_sign = max(
            sum(1 for r in rows if r["err_pct"] > 1),
            sum(1 for r in rows if r["err_pct"] < -1),
        )
        median_err = statistics.median(r["err_pct"] for r in rows)
        mean_err = statistics.fmean(r["err_pct"] for r in rows)
        worst = max(rows, key=lambda r: abs(r["err_pct"]))
        is_candidate = n_same_sign >= 3
        flag = " ★ CANDIDATE" if is_candidate else ""
        if is_candidate:
            candidates.append({"metric": truth_key, "label": rows[0]["label"],
                                "median_err_pct": median_err,
                                "n_same_sign": n_same_sign,
                                "rows": rows})
        label = rows[0]["label"]
        print(f"  {label}{flag}")
        print(f"    n={len(rows)}  median Δ={median_err:+.2f}%  mean Δ={mean_err:+.2f}%  "
              f"worst={worst['slug']}@{worst['err_pct']:+.2f}%")
        for r in sorted(rows, key=lambda r: r["slug"]):
            print(f"      {r['slug']:<14} truth={r['truth']:>8.2f}  AI={r['ai']:>8.2f}  Δ={r['err_pct']:+7.2f}%")
        print()

    print(f"  ═══ Summary ═══\n")
    if not candidates:
        print("  No systematic error candidates (need ≥3 same-sign >1% errors).")
        return 0
    print(f"  {len(candidates)} systematic error candidate(s):")
    for c in candidates:
        print(f"    • {c['label']:<50} median {c['median_err_pct']:+.2f}%  "
              f"({c['n_same_sign']} same-sign across {len(c['rows'])} projects)")

    # Save raw findings
    out = REPO_ROOT / "eval_runs" / "systematic_errors.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n_projects_scored": len(scored),
        "candidates": candidates,
        "all_metrics": {k: v for k, v in per_metric.items()},
    }, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n  Saved → {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
