#!/usr/bin/env python3
"""Reconcile the app's emitted SANITARY FITTING lines against the contractor's.

WHY (2026-07-29): on Beržų g. 24 the app emitted 5 vnt of mixer/sprayer
installation work against the contractor's 22 — a −77% aggregate. The cause was
not a reading failure: the contractor bills the LT-conventional PAIR for every
concealed (potinkinis) mixer — the in-wall body during rough-in, the visible
trim after tiling — and we emitted one bundled line per fixture.

This script re-runs the deterministic pozicijos builder on a saved extract (zero
API spend, same tail `eval_harness --rescore --recompute` uses) and maps the
emitted Santechnikos-darbai lines onto the contractor's line items, so the
before/after is a number and not a claim.

Usage:
    ./venv/bin/python scripts/reconcile_sanitary_lines.py                # berzas
    ./venv/bin/python scripts/reconcile_sanitary_lines.py objektas_b
    ./venv/bin/python scripts/reconcile_sanitary_lines.py --all
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

# Contractor line families we compare. A "fitting" here = mixer / bidet-sprayer
# INSTALLATION work — the category the −77% was measured on. Deliberately
# EXCLUDES single-job items (klozetas, WC rėmas, gyvatukas, skalbimo mašina,
# sifonas, latakas, plautuvė) so the number isn't inflated by lines that were
# never in dispute.
# The `sistem` alternate catches ciurliu nr 1-2 ("Potinkinės dušo/praustuvo
# SISTEMOS įrengimas") — the same concealed mixer work billed as one bundled
# line instead of a pair. Without it ciurliu reads as "no sanitary lines".
FAMILIES = {
    "praustuve": {
        "lt": "Praustuvės maišytuvas",
        "contractor": re.compile(r"praustuv\w*\s+(maišytuv|sistem)", re.I),
        "app": re.compile(r"praustuvės maišytuvo", re.I),
    },
    "dusas": {
        "lt": "Dušo maišytuvas",
        "contractor": re.compile(r"dušo\s+(maišytuv|sistem)", re.I),
        "app": re.compile(r"dušo maišytuvo", re.I),
    },
    "vonia": {
        "lt": "Vonios maišytuvas",
        "new": True,          # fixture we already READ but never billed
        "contractor": re.compile(r"vonios\s+maišytuv", re.I),
        "app": re.compile(r"vonios maišytuvo", re.I),
    },
    "bide": {
        "lt": "Bidė dušiukas",
        "new": True,          # category no reader counts — checklist TODO
        "contractor": re.compile(r"bide\w*\s+dušiuk", re.I),
        "app": re.compile(r"bidė dušiuko", re.I),
    },
}
_FRAME = re.compile(r"rėmo montavimas", re.I)          # WC/bidė frame, not a fitting
_INSTALL_VERB = re.compile(r"montavim|įrengim|sumont", re.I)
_PREP = re.compile(r"privedim", re.I)


def _is_fitting_line(name: str) -> bool:
    """Fitting = mixer / bidet-sprayer INSTALLATION work.

    Two exclusions, both load-bearing:
      · '… rėmo montavimas' is the in-wall carrier frame, billed separately and
        never in dispute.
      · a pure '… privedimas' line (objektas_b nr 93/94) is pipe routing with no
        fitting installed. It must NOT swallow berzas nr 40, whose full text is
        '… potinkinės dalies montavimas, kanalizacijos privedimas' — that IS the
        rough-in half. Hence: prep-only counts as prep, prep-plus-install counts
        as install.
    """
    if _FRAME.search(name):
        return False
    if _PREP.search(name) and not _INSTALL_VERB.search(name):
        return False
    return True


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


def contractor_fittings(slug: str) -> tuple[dict, list]:
    path = REPO / "ground_truth" / slug / "contractor_samata_parsed.json"
    if not path.exists():
        return {}, []
    items = json.loads(path.read_text(encoding="utf-8")).get("line_items") or []
    per_family: dict[str, float] = {k: 0.0 for k in FAMILIES}
    rows = []
    for it in items:
        name = _norm(it.get("name"))
        if not _is_fitting_line(name):
            continue
        for key, fam in FAMILIES.items():
            if fam["contractor"].search(name):
                qty = float(it.get("quantity") or 0)
                per_family[key] += qty
                rows.append((it.get("nr"), name, qty, key))
                break
    return per_family, rows


def app_fittings(slug: str, *, rebuild: bool = True,
                 unsplit: bool = False) -> tuple[dict, list, dict]:
    """Emitted fitting lines from the saved extract.

    rebuild=False → the line set as STORED in ai_extract.json (whatever emit
      code produced that cached run).
    rebuild=True  → today's deterministic builder on the same inputs.
    unsplit=True  → today's builder with `santechnika_potinkinis` forced off,
      i.e. the one-line-per-fixture shape this change replaced, on the SAME
      inputs. That is the honest before/after control: the stored column can
      differ for reasons that have nothing to do with the split (berzas's cache
      predates the RC1 basin-count fix, so it says 2 where the symbol count
      says 3).
    """
    path = REPO / "ground_truth" / slug / "ai_extract.json"
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if rebuild:
        from extractor.vision_call import _build_pozicijos_from_rooms
        if unsplit:
            ov = dict(parsed.get("_overrides") or {})
            ov["santechnika_potinkinis"] = False
            parsed["_overrides"] = ov
        parsed = _build_pozicijos_from_rooms(parsed)
    per_family: dict[str, float] = {k: 0.0 for k in FAMILIES}
    rows = []
    for p in parsed.get("pozicijos") or []:
        if p.get("skyrius") != "Santechnikos darbai":
            continue
        name = _norm(p.get("aprasymas"))
        if not _is_fitting_line(name):
            continue
        for key, fam in FAMILIES.items():
            if fam["app"].search(name):
                qty = p.get("kiekis")
                per_family[key] += float(qty or 0)
                rows.append((name, qty, key))
                break
    return per_family, rows, parsed


def report(slug: str) -> None:
    truth, truth_rows = contractor_fittings(slug)
    if not truth_rows:
        print(f"\n=== {slug}: no contractor sanitary lines — skipped ===")
        return
    stored, stored_rows, _ = app_fittings(slug, rebuild=False)
    before, before_rows, _ = app_fittings(slug, rebuild=True, unsplit=True)
    after, after_rows, parsed = app_fittings(slug, rebuild=True)

    print(f"\n{'=' * 78}\n{slug}\n{'=' * 78}")
    print("\nCONTRACTOR (his line items):")
    for nr, name, qty, key in truth_rows:
        print(f"  {str(nr):>3}  {name[:62]:<62} {qty:>5.0f}")
    print("\nAPP — stored (line set cached in ai_extract.json):")
    for name, qty, key in stored_rows or [("(nothing emitted)", 0, "")]:
        print(f"       {name[:62]:<62} {str(qty):>5}")
    print("\nAPP — before (same inputs, split OFF = the shape this replaced):")
    for name, qty, key in before_rows or [("(nothing emitted)", 0, "")]:
        print(f"       {name[:62]:<62} {str(qty):>5}")
    print("\nAPP — after (same inputs, split ON = this change):")
    for name, qty, key in after_rows or [("(nothing emitted)", 0, "")]:
        print(f"       {name[:62]:<62} {str(qty):>5}")

    print(f"\n{'family':<24}{'contractor':>11}{'stored':>8}{'before':>8}"
          f"{'after':>7}{'Δ':>6}   residual gap")
    ts = tb = ta = tt = 0.0
    for key, fam in FAMILIES.items():
        t, st, b, a = truth[key], stored[key], before[key], after[key]
        tt, ts, tb, ta = tt + t, ts + st, tb + b, ta + a
        print(f"{fam['lt']:<24}{t:>11.0f}{st:>8.0f}{b:>8.0f}{a:>7.0f}"
              f"{a - b:>+6.0f}   {a - t:+.0f}"
              f"{'   (new coverage)' if fam.get('new') else ''}")
    print(f"{'TOTAL':<24}{tt:>11.0f}{ts:>8.0f}{tb:>8.0f}{ta:>7.0f}"
          f"{ta - tb:>+6.0f}   {ta - tt:+.0f}")
    pb = (tb - tt) / tt * 100 if tt else 0
    pa = (ta - tt) / tt * 100 if tt else 0
    print(f"\n  aggregate error   before {pb:+.1f}%   →   after {pa:+.1f}%")
    # The strict PRE-CHANGE state: the split-off column minus the families this
    # change newly covers. This is the number the gap was originally measured on.
    pre = sum(before[k] for k, f in FAMILIES.items() if not f.get("new"))
    pre_t = sum(truth[k] for k, f in FAMILIES.items() if not f.get("new"))
    print(f"  strictly pre-change (praustuvė+dušas only): {pre:.0f} vs his "
          f"{pre_t:.0f}   →   after (all families): {ta:.0f} vs his {tt:.0f}")
    notes = parsed.get("_sanitary_assumptions") or []
    if notes:
        print("\n  disclosed assumptions:")
        for n in notes:
            print(f"    · {n}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv:
        slugs = sorted(p.parent.name for p in
                       (REPO / "ground_truth").glob("*/ai_extract.json"))
    else:
        slugs = args or ["berzas"]
    for slug in slugs:
        report(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
