"""Sąmatų AI interior takeoff evaluation harness.

Usage:
    python eval_harness.py --use-gt-inputs            # bypass Vision, feed GT primitives
    python eval_harness.py --use-gt-inputs --project berzas
    python eval_harness.py --replay <extract.json>    # diff a saved extractor output
    python eval_harness.py --vision                   # call the real Vision pipeline ($$)

Stop condition (Phase 1): `python eval_harness.py --use-gt-inputs` succeeds, prints
per-category absolute / percentage error vs contractor truth, and writes an HTML report.

Registry: each entry maps `project_id` → `ground_truth/<project_id>/truth.json`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent
GROUND_TRUTH_ROOT = REPO_ROOT / "ground_truth"
EVAL_RUNS_ROOT = REPO_ROOT / "eval_runs"

# ── Registry ───────────────────────────────────────────────────────────────────
REGISTRY: dict[str, dict[str, str]] = {
    "berzas": {
        "name": "Beržų g. 24",
        "truth_path": "ground_truth/berzas/truth.json",
        "pdf_path": "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf",
        # Cached known-good Vision extract used by --replay if Vision is not called.
        "replay_path": "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json",
    },
}

# Backend import path setup
sys.path.insert(0, str(REPO_ROOT / "backend"))


# ── Metric mapping: contractor truth field → extractor output field/extractor ──
# Each entry: truth_key → (label, accessor(parsed_extractor_output) → float)
def _santrauka_get(parsed: dict, key: str) -> float:
    return float((parsed.get("santrauka") or {}).get(key) or 0.0)


def _sum_room_field(parsed: dict, field: str) -> float:
    return float(sum((r.get(field) or 0) for r in (parsed.get("patalpos") or [])))


def _gkp_lubu_only_for_type(parsed: dict, field: str) -> float:
    """Sum a per-room GKP-ceiling field only across rooms whose ceiling type
    is actually GKP / tempiamos — the calculator already gates this, but make
    it explicit here for the truth diff."""
    total = 0.0
    for r in (parsed.get("patalpos") or []):
        if (r.get("lubu_tipas") or "").lower() in ("gkp", "tempiamos"):
            total += float(r.get(field) or 0)
    return round(total, 2)


METRICS: dict[str, dict[str, Any]] = {
    "dazymo_walls_plus_ceilings_combined_m2": {
        "label": "Dažymo plotas (sienos + lubos)",
        "accessor": lambda p: _santrauka_get(p, "dazymo_plotas_total_m2"),
        "unit": "m²",
        "tier": "headline",
    },
    "walls_paint_total_m2": {
        "label": "Sienų dažomas plotas",
        "accessor": lambda p: round(_sum_room_field(p, "walls_paintable_m2"), 2),
        "unit": "m²",
        "tier": "headline",
    },
    "ceiling_paint_total_m2": {
        "label": "Lubų dažomas plotas",
        "accessor": lambda p: round(_sum_room_field(p, "ceiling_paintable_m2"), 2),
        "unit": "m²",
        "tier": "headline",
    },
    "led_nisos_m": {
        "label": "LED nišų ilgis",
        "accessor": lambda p: _santrauka_get(p, "nisu_metrai_total"),
        "unit": "m",
        "tier": "headline",
    },
    "floor_total_m2": {
        "label": "Bendras plotas",
        "accessor": lambda p: round(_sum_room_field(p, "plotas_m2"), 2),
        "unit": "m²",
        "tier": "headline",
    },
    "plyteles_grindys_total_m2": {
        "label": "Plytelės grindyse",
        "accessor": lambda p: _santrauka_get(p, "plyteles_grindys_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "plyteles_sienos_total_m2": {
        "label": "Plytelės sienose",
        "accessor": lambda p: _santrauka_get(p, "plyteles_sienos_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "gkp_lubu_iki_3m_m2": {
        "label": "GKP lubos iki 3m",
        "accessor": lambda p: _santrauka_get(p, "gkp_lubu_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "gkp_lubu_virs_3m_m2": {
        "label": "GKP lubos virš 3m",
        "accessor": lambda p: _santrauka_get(p, "gkp_lubu_virs_3m_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "kampu_metrai_m": {
        "label": "Dažymo kampai",
        "accessor": lambda p: _santrauka_get(p, "kampai_m_total"),
        "unit": "m",
        "tier": "category",
    },
    # The following truth fields don't have a current extractor output — they
    # surface as "MISSING" in the report and signal the next gap to close.
    "rotband_lyginimas_m2": {
        "label": "Sienų lyginimas Rotband",
        "accessor": lambda p: None,  # not currently emitted as a single total
        "unit": "m²",
        "tier": "category",
    },
    "angokrasciu_m": {
        "label": "Angokraščiai",
        "accessor": lambda p: _santrauka_get(p, "angokrasciu_gkp_m_total"),
        "unit": "m",
        "tier": "category",
    },
    "rozetes_jungtukai_count": {
        "label": "Rozetės + jungtukai",
        "accessor": lambda p: None,
        "unit": "vnt",
        "tier": "counts",
    },
    "sviestuvai_priglaistomi_count": {
        "label": "Priglaistomi šviestuvai",
        "accessor": lambda p: None,
        "unit": "vnt",
        "tier": "counts",
    },
    "difuzoriai_count": {
        "label": "Difūzoriai",
        "accessor": lambda p: None,
        "unit": "vnt",
        "tier": "counts",
    },
    "siuksles_m3": {
        "label": "Šiukšlių išvežimas",
        "accessor": lambda p: None,
        "unit": "m³",
        "tier": "counts",
    },
}


# ── Pipeline drivers ───────────────────────────────────────────────────────────
def run_pipeline_use_gt_inputs(truth: dict) -> dict:
    """Bypass Vision: feed GT primitives straight into the deterministic engine.

    Strips the `_dim_confidence` annotation from each room (calculator-side fields
    only) before invoking the engine; the rest of the GT room dict is exactly
    the primitive schema the calculator already consumes in production.
    """
    vc = importlib.import_module("extractor.vision_call")
    _recompute_per_room = vc._recompute_per_room_via_python
    _recompute_santrauka = vc._recompute_santrauka

    rooms_in: list[dict] = []
    for r in truth["gt_dimensions"]:
        room = {k: v for k, v in r.items() if not k.startswith("_dim")}
        rooms_in.append(room)

    parsed = {
        "patalpos": rooms_in,
        "archetipas": "dideli_namu_premium",
        "bendras_plotas_m2": truth.get("floor_total_sanity_check_m2") or 0,
        "_meta": {
            "mode": "use_gt_inputs",
            "harness": "eval_harness.py",
        },
    }
    parsed = _recompute_per_room(parsed, None)
    parsed = _recompute_santrauka(parsed)
    return parsed


def run_pipeline_replay(extract_path: Path) -> dict:
    """Load a previously-recorded full extractor output and diff its totals.

    Useful for offline iteration without burning Vision credits. The recorded
    output is treated as if produced by the current pipeline.
    """
    with extract_path.open() as f:
        return json.load(f)


def run_pipeline_vision(pdf_path: Path) -> dict:
    """Full Vision pipeline (Phase 2 stop condition)."""
    vc = importlib.import_module("extractor.vision_call")
    pdf_bytes = pdf_path.read_bytes()
    return vc.extract_interior(pdf_bytes, rules_override=None)


# ── Eval core ──────────────────────────────────────────────────────────────────
@dataclass
class MetricResult:
    truth_key: str
    label: str
    unit: str
    tier: str
    truth_value: float | None
    truth_confidence: str
    actual_value: float | None
    abs_error: float | None
    pct_error: float | None
    status: str          # "ok" | "warn" | "fail" | "missing" | "no_truth"

    @property
    def color(self) -> str:
        return {
            "ok": "🟢", "warn": "🟡", "fail": "🔴",
            "missing": "⬜", "no_truth": "⬛",
        }[self.status]


THRESHOLD_OK = 0.5     # %
THRESHOLD_WARN = 3.0   # %


def _classify(pct: float | None) -> str:
    if pct is None:
        return "missing"
    abs_pct = abs(pct)
    if abs_pct <= THRESHOLD_OK:
        return "ok"
    if abs_pct <= THRESHOLD_WARN:
        return "warn"
    return "fail"


def evaluate(parsed: dict, truth: dict) -> list[MetricResult]:
    results: list[MetricResult] = []
    gt_totals = truth.get("gt_totals", {})
    for key, meta in METRICS.items():
        spec = gt_totals.get(key)
        truth_val: float | None
        truth_conf = "n/a"
        if spec is None:
            truth_val = None
            truth_conf = "absent"
        elif isinstance(spec, dict):
            v = spec.get("value")
            # Skip multi-value (e.g. led_nisos_breakdown) — handled separately
            if isinstance(v, list):
                continue
            truth_val = float(v) if v is not None else None
            truth_conf = spec.get("confidence", "n/a")
        else:
            truth_val = float(spec) if spec is not None else None

        actual_val = meta["accessor"](parsed)
        if actual_val is None and truth_val is None:
            status = "no_truth"
            abs_err = pct_err = None
        elif actual_val is None:
            status = "missing"
            abs_err = pct_err = None
        elif truth_val is None:
            status = "no_truth"
            abs_err = pct_err = None
        else:
            abs_err = round(actual_val - truth_val, 3)
            pct_err = round((abs_err / truth_val) * 100.0, 3) if truth_val else None
            status = _classify(pct_err)

        results.append(MetricResult(
            truth_key=key,
            label=meta["label"],
            unit=meta["unit"],
            tier=meta["tier"],
            truth_value=truth_val,
            truth_confidence=truth_conf,
            actual_value=actual_val if isinstance(actual_val, (int, float)) else None,
            abs_error=abs_err,
            pct_error=pct_err,
            status=status,
        ))
    return results


def evaluate_per_room(parsed: dict, truth: dict) -> list[dict]:
    """Diff per-room contractor-given values where present."""
    gt_per_room = truth.get("gt_per_room") or {}
    rooms_by_nr = {str(r.get("nr")): r for r in (parsed.get("patalpos") or [])}

    rows: list[dict] = []
    for nr, fields in gt_per_room.items():
        actual_room = rooms_by_nr.get(str(nr))
        if not actual_room:
            rows.append({"nr": nr, "missing": True})
            continue
        for field_key, spec in fields.items():
            truth_val = float(spec["value"])
            actual_val = float(actual_room.get(field_key) or 0)
            abs_err = round(actual_val - truth_val, 3)
            pct_err = round((abs_err / truth_val) * 100.0, 3) if truth_val else None
            rows.append({
                "nr": nr,
                "pavadinimas": actual_room.get("pavadinimas"),
                "field": field_key,
                "truth": truth_val,
                "actual": actual_val,
                "abs_error": abs_err,
                "pct_error": pct_err,
                "status": _classify(pct_err),
                "source": spec.get("source", ""),
            })
    return rows


# ── Reporting ──────────────────────────────────────────────────────────────────
def _fmt_num(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:>10.2f}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "    —"
    return f"{v:+7.2f}%"


def print_report(project_id: str, mode: str, results: list[MetricResult],
                 per_room: list[dict]) -> None:
    print()
    print("═" * 96)
    print(f"  Project: {project_id}   |   mode: {mode}")
    print("═" * 96)
    print(f"  {'metric':<40} {'truth':>10} {'actual':>10}   {'Δ':>10}   {'pct':>8}   conf  status")
    print("  " + "─" * 92)
    for r in results:
        if r.status == "no_truth":
            continue
        line = (
            f"  {r.label[:38]:<40} {_fmt_num(r.truth_value):>10} "
            f"{_fmt_num(r.actual_value):>10}   {_fmt_num(r.abs_error):>10}   "
            f"{_fmt_pct(r.pct_error):>8}   {r.truth_confidence[:5]:<5} {r.color}"
        )
        print(line)

    if per_room:
        print()
        print("  Per-room (contractor-validated rows):")
        print("  " + "─" * 92)
        for row in per_room:
            if row.get("missing"):
                print(f"    nr={row['nr']}: ⬛ room not in extract")
                continue
            color = {"ok": "🟢", "warn": "🟡", "fail": "🔴", "missing": "⬜"}[row["status"]]
            print(
                f"  nr={row['nr']:<4} {row.get('pavadinimas','')[:20]:<22} "
                f"{row['field']:<22} truth={row['truth']:>8.2f} "
                f"actual={row['actual']:>8.2f} Δ={row['abs_error']:>+7.2f} "
                f"({row['pct_error']:>+6.2f}%) {color}"
            )

    summary = _summarize(results)
    print()
    print("  ── Summary ────────────────────────────────────────────────────────────────")
    print(f"    Headline MAE %:        {summary['headline_mae_pct']:6.3f}%")
    print(f"    Headline max |error| %:{summary['headline_max_pct']:6.3f}%")
    print(f"    Headline rooms ok:     {summary['headline_ok']} / {summary['headline_total']}")
    print(f"    Category MAE %:        {summary['category_mae_pct']:6.3f}%")
    print("═" * 96)


def _summarize(results: list[MetricResult]) -> dict:
    def _pct_values(tier: str) -> list[float]:
        return [abs(r.pct_error) for r in results
                if r.tier == tier and r.pct_error is not None]

    head_pcts = _pct_values("headline")
    cat_pcts = _pct_values("category")
    head_ok = sum(1 for r in results if r.tier == "headline" and r.status == "ok")
    head_total = sum(1 for r in results if r.tier == "headline" and r.pct_error is not None)

    return {
        "headline_mae_pct": (sum(head_pcts) / len(head_pcts)) if head_pcts else 0.0,
        "headline_max_pct": max(head_pcts) if head_pcts else 0.0,
        "headline_ok": head_ok,
        "headline_total": head_total,
        "category_mae_pct": (sum(cat_pcts) / len(cat_pcts)) if cat_pcts else 0.0,
    }


def write_html_report(out_path: Path, project_id: str, mode: str,
                      results: list[MetricResult], per_room: list[dict],
                      summary: dict) -> None:
    rows_html = []
    for r in results:
        if r.status == "no_truth":
            continue
        rows_html.append(
            f"<tr class='row-{r.status}'>"
            f"<td>{r.label}</td>"
            f"<td class='num'>{_fmt_num(r.truth_value)} {r.unit}</td>"
            f"<td class='num'>{_fmt_num(r.actual_value)} {r.unit}</td>"
            f"<td class='num'>{_fmt_num(r.abs_error)}</td>"
            f"<td class='num'>{_fmt_pct(r.pct_error)}</td>"
            f"<td>{r.truth_confidence}</td>"
            f"<td>{r.color}</td>"
            f"</tr>"
        )

    per_room_html = ""
    if per_room:
        per_room_rows = []
        for row in per_room:
            if row.get("missing"):
                per_room_rows.append(f"<tr><td>{row['nr']}</td><td colspan=6>missing</td></tr>")
                continue
            per_room_rows.append(
                f"<tr class='row-{row['status']}'>"
                f"<td>{row['nr']}</td><td>{row.get('pavadinimas','')}</td>"
                f"<td>{row['field']}</td>"
                f"<td class='num'>{row['truth']:.2f}</td>"
                f"<td class='num'>{row['actual']:.2f}</td>"
                f"<td class='num'>{row['abs_error']:+.2f}</td>"
                f"<td class='num'>{row['pct_error']:+.2f}%</td>"
                f"</tr>"
            )
        per_room_html = (
            "<h3>Per-room (contractor-validated)</h3>"
            "<table><thead><tr><th>nr</th><th>room</th><th>field</th>"
            "<th>truth</th><th>actual</th><th>Δ</th><th>pct</th></tr></thead><tbody>"
            + "".join(per_room_rows) + "</tbody></table>"
        )

    html = f"""<!doctype html>
<html lang="lt"><head><meta charset="utf-8">
<title>Eval — {project_id} — {mode}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1080px; margin: 24px auto; padding: 0 16px; color: #1a1a1a; }}
  h1 {{ margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .summary {{ background: #f6f5f2; border-left: 4px solid #2a6fb5; padding: 12px 16px; margin: 16px 0 32px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-bottom: 24px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left; }}
  th {{ background: #fafafa; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.row-ok    {{ background: rgba(72, 187, 120, 0.05); }}
  tr.row-warn  {{ background: rgba(237, 137, 54, 0.07); }}
  tr.row-fail  {{ background: rgba(229, 62, 62, 0.10); }}
  tr.row-missing {{ color: #999; }}
</style>
</head><body>
<h1>Eval report — {project_id}</h1>
<div class="meta">mode={mode} &middot; generated {_dt.datetime.now().isoformat(timespec='seconds')}</div>
<div class="summary">
  Headline MAE: <b>{summary['headline_mae_pct']:.3f}%</b> &middot;
  Max headline |Δ|: <b>{summary['headline_max_pct']:.3f}%</b> &middot;
  Headline ok: <b>{summary['headline_ok']}/{summary['headline_total']}</b> &middot;
  Category MAE: <b>{summary['category_mae_pct']:.3f}%</b>
</div>
<h3>Headline + category metrics</h3>
<table>
  <thead><tr><th>metric</th><th>truth</th><th>actual</th><th>Δ</th><th>pct</th><th>conf</th><th>status</th></tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
{per_room_html}
</body></html>
"""
    out_path.write_text(html, encoding="utf-8")


# ── CLI ────────────────────────────────────────────────────────────────────────
def _load_truth(project_id: str) -> dict:
    entry = REGISTRY.get(project_id)
    if not entry:
        raise SystemExit(f"Unknown project '{project_id}'. Known: {list(REGISTRY)}")
    path = REPO_ROOT / entry["truth_path"]
    with path.open() as f:
        return json.load(f)


def run_one(project_id: str, mode: str) -> int:
    truth = _load_truth(project_id)
    entry = REGISTRY[project_id]

    if mode == "use_gt_inputs":
        parsed = run_pipeline_use_gt_inputs(truth)
    elif mode == "replay":
        parsed = run_pipeline_replay(REPO_ROOT / entry["replay_path"])
    elif mode == "vision":
        parsed = run_pipeline_vision(REPO_ROOT / entry["pdf_path"])
    else:
        raise SystemExit(f"Unknown mode {mode!r}")

    results = evaluate(parsed, truth)
    per_room = evaluate_per_room(parsed, truth)
    summary = _summarize(results)
    print_report(project_id, mode, results, per_room)

    ts = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = EVAL_RUNS_ROOT / f"{ts}_{project_id}_{mode}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2))
    (run_dir / "results.json").write_text(json.dumps({
        "project": project_id,
        "mode": mode,
        "summary": summary,
        "metrics": [r.__dict__ for r in results],
        "per_room": per_room,
    }, ensure_ascii=False, indent=2))
    write_html_report(run_dir / "report.html", project_id, mode, results, per_room, summary)
    print(f"\n  Report → {run_dir / 'report.html'}")

    # Exit code: 1 if any headline metric is "fail", 0 otherwise.
    failing = [r for r in results if r.tier == "headline" and r.status == "fail"]
    return 1 if failing else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sąmatų AI evaluation harness")
    ap.add_argument("--project", default="berzas", help="project id in REGISTRY")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--use-gt-inputs", action="store_true",
                     help="bypass Vision; feed GT primitives into the deterministic engine")
    grp.add_argument("--replay", action="store_true",
                     help="reuse cached extractor output (registry.replay_path)")
    grp.add_argument("--vision", action="store_true",
                     help="run the full Vision pipeline (costs API $$)")
    args = ap.parse_args()

    if args.use_gt_inputs:
        mode = "use_gt_inputs"
    elif args.replay:
        mode = "replay"
    elif args.vision:
        mode = "vision"
    else:
        mode = "use_gt_inputs"  # default: cheapest, safest
    return run_one(args.project, mode)


if __name__ == "__main__":
    sys.exit(main())
