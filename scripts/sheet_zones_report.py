"""Print the sheet zones (backend/extractor/sheet_zones.py) of every corpus project, sheet by sheet.

Non-asserting: a report for eyes, not a test — the corpus PDFs are confidential and untracked
(docs/superpowers/fixtures/, see ground_truth/registry.yaml), so nothing here may become a fixture.
Projects are printed by CODENAME only (the registry's `name`, e.g. „Objektas E" → objektas_e); labels are
cut to 40 characters and can be hidden with --no-labels.

    venv/bin/python scripts/sheet_zones_report.py                    # every project with a PDF on disk
    venv/bin/python scripts/sheet_zones_report.py objektas_h --pages 2,3
    venv/bin/python scripts/sheet_zones_report.py --summary          # one line per project
"""
from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import yaml  # noqa: E402

from extractor import sheet_zones as sz  # noqa: E402
from extractor.pdf_page_cache import page_count  # noqa: E402

CORE = ("objektas_a", "objektas_b", "objektas_c", "romainiai", "objektas_d", "objektas_g", "objektas_h")


def _codename(entry: dict) -> str:
    slug = str(entry.get("slug") or "")
    if slug.startswith("objektas_"):
        return slug
    name = str(entry.get("name") or slug)
    return name.strip().lower().replace(" ", "_")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projects", nargs="*", help="codenames or registry slugs (default: the core corpus)")
    ap.add_argument("--pages", default="", help="comma-separated 1-based pages (default: all)")
    ap.add_argument("--summary", action="store_true", help="one line per project")
    ap.add_argument("--no-labels", action="store_true")
    args = ap.parse_args()

    reg = yaml.safe_load((REPO / "ground_truth" / "registry.yaml").read_text())
    entries = {e["slug"]: e for e in reg.get("projects") or []}
    by_code = {_codename(e): e for e in entries.values()}
    wanted = args.projects or list(CORE)
    for want in wanted:
        entry = entries.get(want) or by_code.get(want)
        if not entry:
            print(f"{want}: not in the registry")
            continue
        code = _codename(entry)
        pdf_path = REPO / str(entry.get("project_pdf") or "")
        if not pdf_path.is_file():
            print(f"{code}: PDF not on disk (copy the untracked fixtures into this checkout)")
            continue
        pdf = pdf_path.read_bytes()
        n = page_count(pdf)
        pages = [int(p) for p in args.pages.split(",") if p.strip()] or list(range(1, n + 1))
        kinds: collections.Counter = collections.Counter()
        statuses: collections.Counter = collections.Counter()
        empty: list[str] = []
        t0 = time.time()
        slowest = (0.0, None)
        for p in pages:
            t1 = time.time()
            res = sz.read_zones(pdf, p)
            dt = time.time() - t1
            slowest = max(slowest, (dt, p), key=lambda v: v[0])
            statuses[res["status"]] += 1
            for z in res["zones"]:
                kinds[z["kind"]] += 1
            if not res["zones"]:
                empty.append(f"{p}({res['detail'] or res['status']})")
            if args.summary:
                continue
            print(f"{code} p{p} {res['width_pt']:.0f}×{res['height_pt']:.0f} rot {res['rotation']} "
                  f"{res['status']} {dt:.2f}s" + (f" — {res['detail']}" if res["detail"] else ""))
            for z in res["zones"]:
                label = "" if args.no_labels or not z["label"] else f" „{z['label'][:40]}“"
                box = ", ".join(f"{v:.3f}" for v in z["bbox_pct"])
                print(f"    {z['kind']:<10} [{box}] {z['confidence']:<7} {z['evidence']['source']:<18}"
                      f"{label} — {z['evidence']['detail']}")
        total = time.time() - t0
        counts = " ".join(f"{k} {kinds.get(k, 0)}" for k in sz.KINDS)
        print(f"== {code}: {len(pages)} sheets, {total:.1f}s (slowest p{slowest[1]} {slowest[0]:.1f}s) | {counts} | "
              f"status {dict(statuses)} | no zones: {', '.join(empty) if empty else '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
