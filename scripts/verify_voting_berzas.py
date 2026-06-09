"""Live A/B verification of N-pass extraction voting on the Beržų fixture.

Runs extract_interior twice on the SAME PDF:
  A) single-pass (ENABLE_EXTRACTION_VOTING=0) — reproduces the production bug
     (no adjacency pass → n_partition_walls=0 → kampai missing pusiniai).
  B) N-pass voting  (ENABLE_EXTRACTION_VOTING=1, VOTING_N=3) — the fix.

Writes both results to /tmp (NEVER overwrites the cached benchmark extract) and
prints kampai / combined-paint / n_partition_walls vs contractor truth (493.35
kampai, 584.81 combined paint).

Usage: venv/bin/python scripts/verify_voting_berzas.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

PDF = REPO / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf"
TRUTH_KAMPAI = 493.35
TRUTH_PAINT = 584.81


def _kampai(result: dict) -> float:
    for p in result.get("pozicijos") or []:
        if (p.get("aprasymas") or "") == "Dažymo kampų montavimas":
            return float(p.get("kiekis") or 0)
    return 0.0


def _combined_paint(result: dict) -> float:
    tot = 0.0
    for p in result.get("pozicijos") or []:
        a = p.get("aprasymas") or ""
        if a.startswith("Sienų, lubų glaistymas/dažymas") or \
           a.startswith("Sienų glaistymas/dažymas") or \
           a.startswith("Lubų glaistymas/dažymas"):
            tot += float(p.get("kiekis") or 0)
    return round(tot, 2)


def _npw_total(result: dict) -> int:
    return sum(int(r.get("n_partition_walls") or 0) for r in (result.get("patalpos") or []))


def _walls_paint_total(result: dict) -> float:
    import sys as _s
    _s.path.insert(0, str(REPO / "backend"))
    from extractor.universal_rules import calc_room_quantities
    tot = 0.0
    for r in result.get("patalpos") or []:
        q = calc_room_quantities(r)
        tot += float(q.get("walls_paintable_m2") or 0)
    return round(tot, 1)


def _doors_total(result: dict) -> int:
    return sum(int(e.get("kiekis") or 1)
               for r in (result.get("patalpos") or [])
               for e in (r.get("elementai") or [])
               if (e.get("tipas") or "").startswith(("duris", "pasleptos")))


def _ceiling_heights(result: dict):
    return sorted({round(float(r.get("lubu_aukstis_m") or 0), 2)
                   for r in (result.get("patalpos") or [])})


def run(label: str, voting: bool, n: int = 3) -> dict:
    os.environ["ENABLE_EXTRACTION_VOTING"] = "1" if voting else "0"
    if voting:
        os.environ["VOTING_N"] = str(n)
    from importlib import reload
    import extractor.feature_flags as ff
    reload(ff)  # pick up env change
    from extractor.vision_call import extract_interior

    print(f"\n══════ {label} (voting={voting}{', N='+str(n) if voting else ''}) ══════", flush=True)
    t0 = time.time()
    result = extract_interior(PDF.read_bytes(), rules_override=None)
    dt = time.time() - t0
    if result.get("status") == "error":
        print(f"  ✗ ERROR: {result.get('_error')}", flush=True)
        return {"label": label, "error": result.get("_error"), "seconds": dt}

    out = {
        "label": label, "voting": voting, "seconds": round(dt, 1),
        "n_rooms": len(result.get("patalpos") or []),
        "kampai": round(_kampai(result), 2),
        "combined_paint": _combined_paint(result),
        "walls_paint_total": _walls_paint_total(result),
        "doors_total": _doors_total(result),
        "ceiling_heights": _ceiling_heights(result),
        "apdailos_rooms_updated": (result.get("_meta") or {}).get("apdailos_rooms_updated"),
        "doors_reader_total": (result.get("_meta") or {}).get("doors_total_count"),
        "n_partition_walls_total": _npw_total(result),
        "voting_meta": result.get("_voting"),
    }
    (Path("/tmp") / f"berzas_{label}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {dt:.0f}s · {out['n_rooms']} rooms", flush=True)
    print(f"    kampai            = {out['kampai']:.2f}  (truth {TRUTH_KAMPAI}, "
          f"Δ {(out['kampai']-TRUTH_KAMPAI)/TRUTH_KAMPAI*100:+.1f}%)", flush=True)
    print(f"    combined paint    = {out['combined_paint']:.2f}  (truth {TRUTH_PAINT}, "
          f"Δ {(out['combined_paint']-TRUTH_PAINT)/TRUTH_PAINT*100:+.1f}%)", flush=True)
    print(f"    walls_paint total = {out['walls_paint_total']}  (GT 460.7)", flush=True)
    print(f"    doors total       = {out['doors_total']}  (reader said {out['doors_reader_total']}; truth 14)", flush=True)
    print(f"    apdailos updated  = {out['apdailos_rooms_updated']} rooms", flush=True)
    print(f"    ceiling heights   = {out['ceiling_heights']}  (cached: 2.8/3.0/3.4)", flush=True)
    print(f"    n_partition_walls = {out['n_partition_walls_total']}", flush=True)
    if out["voting_meta"]:
        lcf = out["voting_meta"].get("low_confidence_fields") or []
        print(f"    voting: {out['voting_meta'].get('n_runs')} runs, "
              f"rooms/run {out['voting_meta'].get('n_rooms_per_run')}, "
              f"{len(lcf)} low-confidence fields", flush=True)
    return out


def main() -> int:
    results = [
        run("A_single_pass", voting=False),
        run("B_voted_n3", voting=True, n=3),
    ]
    print("\n════════ SUMMARY ════════", flush=True)
    for r in results:
        if r.get("error"):
            print(f"  {r['label']}: ERROR {r['error']}", flush=True)
        else:
            print(f"  {r['label']:16} kampai={r['kampai']:7.2f}  "
                  f"paint={r['combined_paint']:7.2f}  npw={r['n_partition_walls_total']:3d}  "
                  f"({r['seconds']:.0f}s)", flush=True)
    (Path("/tmp") / "berzas_voting_ab_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSaved → /tmp/berzas_voting_ab_summary.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
