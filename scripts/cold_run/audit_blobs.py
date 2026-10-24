#!/usr/bin/env python3
"""Audit what production showed the contractor — the stored project blob, no PDF, no model.

Phase 0 (b) of docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md.

    venv/bin/python scripts/cold_run/audit_blobs.py --blobs DIR_WITH_<id>.json --out OUT_DIR \
        --project objektas_x=<project-id> [--project …]

Per project: the room list (count, areas, perimeter sources, heights and their
sources), the scope he chose (`_apimtis`), the designer's own figures found in
the PDF (`_autoriaus_kiekiai`), what production's geometry lane recorded
(`_meta.geometrija`), the perimeter validation, the warnings he saw, and every
`pozicijos` row with plausibility flags:

  * walls painted outside 2–4 × floor area
  * ceiling rows not ≈ floor area
  * grindjuostės longer than the sum of room perimeters
  * tile m² with no wet room; wet rooms with no hidroizoliacija row (unless out of scope)
  * corner metres far above (perimeter × height share) — reported as a ratio
  * rows without a quantity (checklist rows)
  * designer figures with no row that carries them

Writes OUT_DIR/<codename>.audit.json (keep OUT_DIR outside the repository —
blobs carry the drawing's words) and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WET = re.compile(r"(?i)(vonia|vonios|wc|san\.?\s*mazg|dušas|dusas|tualet|skalbykl)")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _row_kind(r: dict) -> str | None:
    a = str(r.get("aprasymas") or "").lower()
    u = str(r.get("vnt") or "").lower().replace("²", "2")
    if "medžiag" in str(r.get("skyrius") or "").lower():
        return None
    if u == "m2" and "sien" in a and ("dažym" in a or "glaist" in a) and "lyginim" not in a:
        return "walls_paint"
    if u == "m2" and "lub" in a and ("dažym" in a or "glaist" in a):
        return "ceiling_paint"
    if "grindjuos" in a and u == "m":
        return "skirting"
    if "plytel" in a and u == "m2":
        return "tiles"
    if "hidroizol" in a:
        return "waterproofing"
    if "kamp" in a and u == "m":
        return "corners"
    if "angokra" in a and u == "m":
        return "reveals"
    if ("grind" in a or "laminat" in a or "parket" in a or "danga" in a) and u == "m2":
        return "floor"
    return "other"


def audit(blob: dict) -> dict:
    rooms = [r for r in blob.get("patalpos") or [] if isinstance(r, dict)]
    floor = sum(_f(r.get("plotas_m2")) or 0 for r in rooms)
    perim = sum(_f(r.get("perimetras_m")) or 0 for r in rooms)
    wet = [r for r in rooms if WET.search(str(r.get("pavadinimas") or "")) or str(r.get("paskirtis") or "").lower() in ("vonia", "wc", "san_mazgas")]
    scope = blob.get("_apimtis") or (blob.get("_overrides") or {}).get("apimtis") or {}
    out_of_scope = set(scope.get("darbai_ne") or [])
    rows = []
    flags = []
    by_kind: dict[str, list] = {}
    for r in blob.get("pozicijos") or []:
        k = _row_kind(r)
        q = _f(r.get("kiekis"))
        rec = {"skyrius": r.get("skyrius"), "aprasymas": r.get("aprasymas"), "vnt": r.get("vnt"), "kiekis": q,
               "saltinis": r.get("saltinis"), "confidence": r.get("confidence"), "kind": k}
        rows.append(rec)
        if k:
            by_kind.setdefault(k, []).append(rec)
        if q is None:
            flags.append({"row": r.get("aprasymas"), "flag": "no quantity (checklist row)"})
    walls = sum(x["kiekis"] or 0 for x in by_kind.get("walls_paint", []))
    if walls and floor:
        ratio = walls / floor
        if not 2.0 <= ratio <= 4.0:
            flags.append({"row": "walls_paint", "flag": f"walls {walls:.1f} m² = {ratio:.2f} × floor {floor:.1f} m² (outside 2–4)"})
    ceiling = sum(x["kiekis"] or 0 for x in by_kind.get("ceiling_paint", []))   # „iki 3 m" + „virš 3 m" rows add up
    if floor and ceiling and abs(ceiling - floor) / floor > 0.15:
        flags.append({"row": "ceiling_paint", "flag": f"ceiling rows {ceiling:.1f} m² vs floor {floor:.1f} m²"})
    for x in by_kind.get("skirting", []):
        if perim and x["kiekis"] and x["kiekis"] > perim * 1.1:
            flags.append({"row": x["aprasymas"], "flag": f"skirting {x['kiekis']} m > sum of perimeters {perim:.1f} m"})
    if by_kind.get("tiles") and not wet:
        flags.append({"row": "tiles", "flag": "tile m² but no wet room in the room list"})
    if wet and not by_kind.get("waterproofing") and "plyteles" not in out_of_scope:
        flags.append({"row": "waterproofing", "flag": f"{len(wet)} wet room(s) but no hidroizoliacija row"})
    corners = sum(x["kiekis"] or 0 for x in by_kind.get("corners", []))
    if corners and perim:
        flags.append({"row": "corners", "flag": f"corner metres {corners:.1f} = {corners / perim:.2f} × sum of perimeters {perim:.1f} m"})
    figures = blob.get("_autoriaus_kiekiai") or []
    fig_check = []
    for f in figures:
        fam = str(f.get("family") or "")
        hits = [x for x in rows if fam and fam[:4] in str(x["aprasymas"] or "").lower()]
        fig_check.append({"family": fam, "value": f.get("value"), "unit": f.get("unit"), "page": f.get("page"),
                          "rows_with_family_word": [(x["aprasymas"], x["kiekis"]) for x in hits]})
    pv = blob.get("_perimeter_validation") or {}
    geo = (blob.get("_meta") or {}).get("geometrija") or {}
    reasons: dict[str, int] = {}
    for v in (geo.get("konturu_priezastys") or {}).values():
        key = re.sub(r"\d+[,.]\d+", "N", str(v))
        reasons[key] = reasons.get(key, 0) + 1
    warnings = []
    for w in (blob.get("warnings") or []) + (blob.get("_lt_warnings") or []):
        if isinstance(w, dict):
            warnings.append({"level": w.get("level"), "code": w.get("code"), "message": str(w.get("message") or "")[:400]})
    return {
        "rooms": [{"nr": r.get("nr"), "name": r.get("pavadinimas"), "m2": _f(r.get("plotas_m2")), "perim_m": _f(r.get("perimetras_m")),
                   "perim_source": r.get("perimetras_saltinis") or r.get("_walls_perimetras_saltinis"),
                   "perim_floor": r.get("_perimetras_floor_applied"), "height_m": _f(r.get("lubu_aukstis_m")),
                   "height_source": r.get("lubu_aukstis_saltinis"), "polygon_source": r.get("polygon_source"),
                   "walls_paintable_m2": _f(r.get("walls_paintable_m2")), "wet": r in wet} for r in rooms],
        "n_rooms": len(rooms), "floor_m2": round(floor, 2), "sum_perimeters_m": round(perim, 2),
        "eksplikacija_rows": len((blob.get("_eksplikacija") or {}).get("patalpos") or []),
        "eksplikacija_merged": (blob.get("_meta") or {}).get("eksplikacija_merged_rooms"),
        "scope": scope, "overrides": {k: v for k, v in (blob.get("_overrides") or {}).items() if k != "apimtis"},
        "designer_figures": fig_check,
        "perimeter_validation": {k: pv.get(k) for k in ("n_total", "n_pass", "n_needs_reextraction", "n_no_data")} |
                                {"flagged": [(x.get("room_nr"), x.get("perim_m"), x.get("reason")) for x in pv.get("flagged_rooms") or []]},
        "prod_geometry_lane": {"versija": geo.get("versija"), "vietos": geo.get("vietos"), "konturai": len(geo.get("konturai") or []),
                               "perimetrai_sudeti": len(geo.get("perimetrai_sudeti") or []), "reasons": reasons,
                               "masteliai": geo.get("masteliai")},
        "warnings": warnings, "rows": rows, "flags": flags,
        "model": (blob.get("_meta") or {}).get("model"), "voting_cost_usd": (blob.get("_meta") or {}).get("voting_cost_usd"),
        "elapsed_s": blob.get("_elapsed_s"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blobs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--project", action="append", required=True, help="codename=project-id")
    args = ap.parse_args()
    if ROOT in args.out.resolve().parents or args.out.resolve() == ROOT:
        print("refusing: --out must be outside the repository (blobs contain the drawing's words)")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    for spec in args.project:
        codename, _, pid = spec.partition("=")
        p = args.blobs / f"{pid}.json"
        if not p.exists():
            print(f"{codename}: no blob")
            continue
        raw = json.loads(p.read_text())
        blob = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        a = audit(blob)
        (args.out / f"{codename}.audit.json").write_text(json.dumps(a, ensure_ascii=False, indent=1, default=str))
        print(f"{codename}: rooms {a['n_rooms']} ({a['floor_m2']} m²) | rows {len(a['rows'])} | flags {len(a['flags'])} | "
              f"warnings {len(a['warnings'])} | prod lane v{a['prod_geometry_lane']['versija']} outlines {a['prod_geometry_lane']['konturai']}")
        for f in a["flags"]:
            print(f"   - {f['flag']}  [{f['row']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
