#!/usr/bin/env python3
"""Leave-one-out: how much does the family template actually buy?

The council's €0 falsification of week 2's own hypothesis, before any UI work:
*hold one sąmata out, build the template from the rest, and measure how many of
the held-out rows the template even offers.* `sernu` — the real holdout — has no
cached extract, so nothing can be RENDERED for it; instead every one of the five
corpus sąmatas takes its turn as the held-out one, with the template built from
the other four.

Three numbers per project, all against HIS priced rows:

  coverage   his rows whose FAMILY the template offers at all (the skeleton)
  filled     …of those, the ones the render put a quantity into. Only a
             verified or ledgered number may fill one of his cells, so this is
             gated by `samata_template.is_fillable`, not by whether we have a
             number.
  ±10 %      his rows the rendered sheet reproduces within 10 %, scored by
             `row_scorecard` — the same instrument, so the result is directly
             comparable to the plain app list in the baseline column.

`±10 % (su pasiūlymais)` re-scores the same sheet with the greyed
`_siulomas_kiekis` substituted in. It is NOT a shippable number — it is what
the sheet would read if the verification gate were open, i.e. the ceiling the
ledger and the room check sheet have to climb to.

HONEST CAVEAT, stated here and in the write-up: the TEMPLATE is held out, the
CONCEPT TABLE is not. `scripts/reconcile_samata_lines.CONCEPTS` was hand-written
against this corpus, so the mapping has seen the held-out project. That inflates
`±10 %` (not `coverage`, which is decided by the template alone) and is the
reason `sernu` stays reserved.

Zero API spend — everything is scored off the cached
`ground_truth/<slug>/ai_extract.json` through the same deterministic recompute
the headline MAE uses.

Usage:
    ./venv/bin/python scripts/samata_template_holdout.py
    ./venv/bin/python scripts/samata_template_holdout.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from extractor.row_scorecard import priced_rows, score_rows          # noqa: E402
from extractor.samata_template import (                              # noqa: E402
    FILL_DONE, FILL_SUGGESTED, build_template, contractor_family_keys,
    offered_families, render_samata,
)

# The five with both a parsed sąmata and a cached extract. `sernu` is the
# HOLDOUT and is deliberately absent: reading it would let this work be fitted
# to the project the four-week target is claimed against.
SLUGS = ["objektas_a", "objektas_b", "objektas_c", "objektas_d", "romainiai"]
# Outside the mean for the reason ground_truth/registry.yaml already gives
# (scope_mismatch) — the same exclusion the headline MAE and the row scorecard
# apply, kept identical so one project cannot be in one number and out of another.
EXCLUDED_FROM_MEAN = {"romainiai"}


def load_samata(slug: str) -> dict | None:
    path = REPO / "ground_truth" / slug / "contractor_samata_parsed.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("slug", slug)
    return data


def app_rows(slug: str) -> tuple[list[dict], list[dict]]:
    """Today's engine over the cached Vision reads.

    Imported from `eval_harness`, not reimplemented: `_rerun_deterministic_tail`
    is the exact path `--totals-only --recompute` and the published row
    scorecard use (positioned height markers, salvage, plausibility gate,
    per-room recompute, pozicijos rebuild). A bare `_build_pozicijos_from_rooms`
    here scored objektas_c at 13.9 % against the published 22.2 % — a baseline
    column that does not reproduce the number it is compared against is worse
    than no column.

    Returns (app rows, patalpos). `pozicijos` is what the scorecard reads;
    `darbu_sarasas` is the same rows in the UI's spelling (verified identical
    concept-for-concept on all four corpus projects) and is what the endpoint
    renders from in production.
    """
    path = REPO / "ground_truth" / slug / "ai_extract.json"
    if not path.exists():
        return [], []
    sys.path.insert(0, str(REPO))
    from eval_harness import _rerun_deterministic_tail, run_pipeline_replay
    parsed = _rerun_deterministic_tail(run_pipeline_replay(path), slug)
    rows = parsed.get("pozicijos") or parsed.get("darbu_sarasas") or []
    return rows, parsed.get("patalpos") or []


def _with_suggestions(rows: list[dict]) -> list[dict]:
    """The same sheet with the greyed suggestion promoted into `kiekis`."""
    out = []
    for r in rows:
        if r.get("kiekis") is None and r.get("_siulomas_kiekis") is not None:
            out.append({**r, "kiekis": r["_siulomas_kiekis"]})
        else:
            out.append(r)
    return out


def measure(slug: str, samatas: dict[str, dict]) -> dict:
    """One leave-one-out round."""
    others = [s for name, s in sorted(samatas.items()) if name != slug]
    template = build_template(others, name=f"Šablonas be {slug}")
    held = samatas[slug]
    his = priced_rows(held.get("line_items") or [])

    offered = offered_families(template)
    keys = contractor_family_keys(held.get("line_items") or [])
    covered = [k in offered for k in keys]

    rows, rooms = app_rows(slug)
    rendered = render_samata(template, rows, rooms)

    # Which of HIS families the render actually put a number into.
    filled_families = {r["_sablono_eile"] for r in rendered
                       if r.get("_pildymas") == FILL_DONE}
    suggested_families = {r["_sablono_eile"] for r in rendered
                          if r.get("_pildymas") == FILL_SUGGESTED}
    filled = [k in filled_families for k in keys]
    suggested = [k in suggested_families for k in keys]

    card_template = score_rows(his, rendered)
    card_suggest = score_rows(his, _with_suggestions(rendered))
    card_baseline = score_rows(his, rows)

    n = len(his) or 1
    # Percentages are kept UNROUNDED — the mean is taken over these, and
    # averaging four already-rounded shares is how a corpus mean drifts from the
    # published one (26,4 vs 26,5).
    return {
        "slug": slug,
        "n_his_rows": len(his),
        "n_template_families": sum(len(s["families"]) for s in template["sections"]),
        "n_template_sections": len(template["sections"]),
        "n_itemised_families": sum(1 for s in template["sections"]
                                   for f in s["families"] if f["itemised"]),
        "coverage_n": sum(covered),
        "coverage_pct": sum(covered) / n * 100,
        "filled_n": sum(filled),
        "filled_pct": sum(filled) / n * 100,
        "suggested_n": sum(suggested),
        "suggested_pct": sum(suggested) / n * 100,
        "template_within_10": card_template.within_10_share or 0.0,
        "suggest_within_10": card_suggest.within_10_share or 0.0,
        "baseline_within_10": card_baseline.within_10_share or 0.0,
        "baseline_unmapped": card_baseline.buckets["unmapped"],
        "baseline_missing": card_baseline.buckets["missing"],
        "n_app_rows": len(rows),
        "n_rendered": len(rendered),
        "n_kita": sum(1 for r in rendered if not r["_sablonas"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args()

    samatas = {}
    for slug in SLUGS:
        s = load_samata(slug)
        if s is None:
            print(f"  ! {slug}: no parsed sąmata — skipped", file=sys.stderr)
            continue
        samatas[slug] = s
    if len(samatas) < 2:
        print("need at least two sąmatas to hold one out", file=sys.stderr)
        return 1

    results = [measure(slug, samatas) for slug in samatas]
    scored = [r for r in results if r["slug"] not in EXCLUDED_FROM_MEAN]

    if args.json:
        print(json.dumps({"projects": [{k: (round(v, 2) if isinstance(v, float)
                                            else v)
                                        for k, v in r.items()}
                                       for r in results],
                          "mean": _mean(scored)},
                         ensure_ascii=False, indent=2))
        return 0

    print("\n  Šablono hold-out — leave-one-out per project (€0, cached extracts)")
    print(f"  {'project':<12} {'his':>4} {'offers':>8} {'filled':>8} "
          f"{'±10%':>7} {'±10% su siūl.':>14} {'be šablono':>11}")
    print("  " + "─" * 74)
    for r in results:
        tail = "  (out of the mean — scope mismatch)" \
            if r["slug"] in EXCLUDED_FROM_MEAN else ""
        print(f"  {r['slug']:<12} {r['n_his_rows']:>4} "
              f"{r['coverage_pct']:>7.1f}% {r['filled_pct']:>7.1f}% "
              f"{r['template_within_10']:>6.1f}% {r['suggest_within_10']:>13.1f}% "
              f"{r['baseline_within_10']:>10.1f}%{tail}")
    print("  " + "─" * 74)
    m = _mean(scored)
    print(f"  {'mean':<12} {'':>4} {m['coverage_pct']:>7.1f}% "
          f"{m['filled_pct']:>7.1f}% {m['template_within_10']:>6.1f}% "
          f"{m['suggest_within_10']:>13.1f}% {m['baseline_within_10']:>10.1f}%")
    print(f"  (n={len(scored)} projects; sernu held out entirely — no extract exists)")
    print("\n  · `offers` is decided by the template alone. `±10 %` runs through the")
    print("    FROZEN concept table, which was hand-written against this corpus —")
    print("    the template is held out, the mapping is not.")
    return 0


def _mean(rows: list[dict]) -> dict:
    if not rows:
        return {k: 0.0 for k in ("coverage_pct", "filled_pct", "suggested_pct",
                                 "template_within_10", "suggest_within_10",
                                 "baseline_within_10")}
    keys = ("coverage_pct", "filled_pct", "suggested_pct", "template_within_10",
            "suggest_within_10", "baseline_within_10")
    return {k: round(sum(r[k] for r in rows) / len(rows), 1) for k in keys}


if __name__ == "__main__":
    raise SystemExit(main())
