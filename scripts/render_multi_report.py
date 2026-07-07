"""Render the multi-project baseline JSON into a single HTML page.

Reads the latest eval_runs/*_multi_totals_only/baseline_multi.json
and emits eval_report_multi.html in the repo root for the user to view.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _latest_baseline() -> Path:
    runs = sorted((REPO_ROOT / "eval_runs").glob("*_multi_totals_only/baseline_multi.json"))
    if not runs:
        raise SystemExit("No multi-project baseline found — run eval_harness.py --totals-only first")
    return runs[-1]


def main() -> int:
    path = _latest_baseline()
    data = json.loads(path.read_text(encoding="utf-8"))

    rows_proj = []
    for p in data["projects"]:
        if p["status"] != "ok":
            rows_proj.append(
                f"<tr><td>{html.escape(p['slug'])}</td>"
                f"<td colspan='4' class='muted'>{html.escape(p['status'])} — "
                f"{html.escape(p.get('reason') or '')}</td></tr>"
            )
            continue
        worst_class = "fail" if (p.get("worst_pct") or 0) > 2.0 else "ok"
        rows_proj.append(
            f"<tr>"
            f"<td>{html.escape(p['slug'])} <span class='muted'>({html.escape(p.get('ai_mode') or '?')})</span></td>"
            f"<td>{p['metrics_scored']}</td>"
            f"<td>{p['mae_pct']:.3f}%</td>"
            f"<td class='{worst_class}'>{p['worst_pct']:.3f}%</td>"
            f"<td class='muted'>{html.escape(', '.join(p.get('metrics_not_emitted') or []))}</td>"
            f"</tr>"
        )

    rows_metric = []
    for p in data["projects"]:
        if p["status"] != "ok":
            continue
        for m in p["metrics"]:
            cls = m["status"]
            rows_metric.append(
                f"<tr class='{cls}'>"
                f"<td>{html.escape(p['slug'])}</td>"
                f"<td>{html.escape(m['label'])}</td>"
                f"<td>{m['truth']:.2f}</td>"
                f"<td>{m['actual']:.2f}</td>"
                f"<td>{m['pct_error']:+.3f}%</td>"
                f"</tr>"
            )

    mae = data.get("overall_mae_pct")
    body = f"""<!DOCTYPE html>
<html lang="lt">
<head><meta charset="utf-8"><title>Multi-project totals-only baseline</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         max-width: 900px; margin: 2em auto; padding: 0 1em;
         color: #222; background: #f6f5f2; }}
  h1, h2 {{ color: #1a3a5c; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ padding: 6px 10px; border-bottom: 1px solid #ddd; text-align: left; }}
  th {{ background: #e6e2d6; }}
  td.muted {{ color: #888; font-size: 0.9em; }}
  tr.ok td:nth-child(5), td.ok {{ color: #2a6f3c; }}
  tr.fail td:nth-child(5), td.fail {{ color: #b22; font-weight: 600; }}
  tr.warn td:nth-child(5) {{ color: #b87800; }}
  .banner {{ background: #fff8e1; padding: 1em; border-left: 4px solid #b87800; margin: 1em 0; }}
  .ok-banner {{ background: #ecf7ed; padding: 1em; border-left: 4px solid #2a6f3c; margin: 1em 0; }}
  code {{ background: #eee; padding: 2px 5px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Multi-project totals-only baseline</h1>
<p><strong>Timestamp:</strong> {html.escape(data.get('ts', '?'))}<br>
   <strong>Registry:</strong> <code>{html.escape(data.get('registry', '?'))}</code></p>

<div class='banner'>
  <strong>Single-contractor caveat:</strong> all 6 projects are from Rangovas A (Rangovas A).
  This is a single-contractor cross-project benchmark, NOT cross-contractor.
</div>

<h2>Overall: MAE = {mae:.3f}%  ({data.get('n_metric_observations')} metric observations)</h2>

<h2>Per-project summary</h2>
<table>
  <thead><tr>
    <th>Project (AI mode)</th><th>Metrics scored</th><th>MAE</th><th>Worst</th><th>Not emitted by production</th>
  </tr></thead>
  <tbody>{''.join(rows_proj)}</tbody>
</table>

<h2>Per-metric detail</h2>
<table>
  <thead><tr><th>Project</th><th>Metric</th><th>Truth</th><th>AI</th><th>Δ%</th></tr></thead>
  <tbody>{''.join(rows_metric)}</tbody>
</table>

<h2>Honest disclosure</h2>
<ul>
  <li>The <code>--use-gt-inputs</code> mode (math correctness only) shows Beržų MAE 0.68%.</li>
  <li>The <code>--totals-only</code> mode (production pipeline incl Vision drift)
      shows Beržų MAE {mae:.2f}%. <strong>This is the user-facing accuracy.</strong></li>
  <li>5 of 6 projects show <em>no_ai_side</em>: no cached extract and no
      <code>gt_dimensions</code> populated. To bring them into this baseline,
      either run Vision extraction (~$2–10/project for the larger TPs) or
      enter <code>gt_dimensions</code> manually.</li>
</ul>
</body></html>
"""
    out = REPO_ROOT / "eval_report_multi.html"
    out.write_text(body, encoding="utf-8")
    print(f"  HTML report → {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
