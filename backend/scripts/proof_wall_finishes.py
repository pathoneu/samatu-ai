"""Proof of the wall-finish-from-elevations lane on a stored project (v4, 2026-10-26).

Loads a project blob and its PDF from the local SQLite / pdf_store, runs the full `apply_geometry` tail on it
(so `_sienu_apdaila` is written to each room), then calls `calc_room_quantities` BEFORE and AFTER the lane for
every room. Reports per room:
  · gross walls (m²) and the plan's own line coverage per class;
  · the elevation zones per face and the tile-layout heights;
  · painted / tiled m² BEFORE and AFTER;
  · the source the calculation took.

Reads only; writes nothing to the DB. Prints to stdout — the report captures the tail dump.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractor.geometry_lane import apply_geometry  # noqa: E402
from extractor.universal_rules import calc_room_quantities  # noqa: E402
from extractor.wall_finishes import CLASS_LT, SOURCE as PLAN_SOURCE, is_read  # noqa: E402


def load(db_path: str, pid: str) -> tuple[dict, bytes]:
    db = sqlite3.connect(db_path)
    row = db.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        raise SystemExit(f"project not found: {pid}")
    data = json.loads(row[0])
    pdf_path = os.path.join(os.path.dirname(db_path), "pdf_store", "projects", f"{pid}.pdf")
    if not os.path.exists(pdf_path):
        raise SystemExit(f"pdf not found: {pdf_path}")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    return data, pdf_bytes


def _nr(r: dict) -> str:
    return str(r.get("nr") or r.get("id") or "?")


def _wall_sum_m(rec: dict) -> dict[str, float]:
    return {k: float(v) for k, v in (rec.get("klases_m") or {}).items()}


def _fmt(x) -> str:
    try:
        return f"{float(x):.2f}".replace(".", ",")
    except Exception:  # noqa: BLE001
        return "—"


def _calc(room: dict) -> dict:
    try:
        return calc_room_quantities(room) or {}
    except Exception as exc:  # noqa: BLE001
        return {"_error": repr(exc)}


def _paint(c: dict) -> float:
    return float(c.get("walls_paintable_m2") or 0)


def _tile(c: dict) -> float:
    return float(c.get("plyteles_sienos_m2") or 0)


def _source(c: dict) -> str:
    if c.get("_sienu_apdaila_skaiciavimas"):
        return "brezinys (wall-finish plan + elevations)"
    if c.get("_tile_read_source") == "brezinys":
        return "brezinys/text"
    return c.get("_tile_read_source") or "default"


def run(data: dict, pdf_bytes: bytes, verbose: bool = True) -> dict:
    """Returns {per_room: {nr: {before, after, record}}, totals, meta}. Mutates `data`.

    The A/B isolates the WALL-FINISH lane only: the whole `apply_geometry` runs first (so polygons, perimeters,
    openings and floor coverings are what the current lane would say regardless of this feature), the fresh
    `_sienu_apdaila` is captured, dropped for the BEFORE calc, and restored for the AFTER calc."""
    t0 = time.time()
    try:
        apply_geometry(data, pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        print(f"apply_geometry failed: {exc!r}")
    elapsed = time.time() - t0
    rooms_after = data.get("patalpos") or []
    recs = {_nr(r): r.get("_sienu_apdaila") for r in rooms_after}
    for r in rooms_after:
        r.pop("_sienu_apdaila", None)
    before = {_nr(r): _calc(r) for r in rooms_after}
    for r in rooms_after:
        rec = recs.get(_nr(r))
        if rec is not None:
            r["_sienu_apdaila"] = rec
    after = {_nr(r): _calc(r) for r in rooms_after}

    geom = (data.get("_meta") or {}).get("geometrija") or {}
    out = {"per_room": {}, "elapsed_s": round(elapsed, 2),
           "meta": {k: geom.get(k) for k in ("sienu_apdaila",) if k in geom}}
    total_paint_before = total_paint_after = total_tile_before = total_tile_after = 0.0
    rows = []
    for nr in sorted(after, key=lambda x: (len(x), x)):
        b, a = before.get(nr, {}), after.get(nr, {})
        rec = recs.get(nr)
        total_paint_before += _paint(b)
        total_paint_after += _paint(a)
        total_tile_before += _tile(b)
        total_tile_after += _tile(a)
        row = {
            "nr": nr,
            "paskirtis": next((r.get("paskirtis") for r in rooms_after if _nr(r) == nr), None),
            "pavadinimas": next((r.get("pavadinimas") for r in rooms_after if _nr(r) == nr), None),
            "walls_gross_before": round(_paint(b) + _tile(b), 2),
            "paint_before": round(_paint(b), 2),
            "paint_after": round(_paint(a), 2),
            "tile_before": round(_tile(b), 2),
            "tile_after": round(_tile(a), 2),
            "source_before": _source(b),
            "source_after": _source(a),
            "record": rec,
        }
        out["per_room"][nr] = row
        rows.append(row)

    out["totals"] = {
        "paint_before": round(total_paint_before, 2),
        "paint_after": round(total_paint_after, 2),
        "tile_before": round(total_tile_before, 2),
        "tile_after": round(total_tile_after, 2),
    }

    if verbose:
        print(f"\n== lane meta (sienu_apdaila) ==")
        print(json.dumps(out["meta"], ensure_ascii=False, indent=2, default=str))
        print(f"\n== per room (walls painted / tiled, m²) ==")
        print(f"{'nr':>4}  {'paskirtis':<18} {'name':<28}  pB/aB → aA (paint)   tB → tA (tile)   src")
        for r in rows:
            print(f"{r['nr']:>4}  {str(r['paskirtis'] or '—'):<18} {str(r['pavadinimas'] or '')[:28]:<28}  "
                  f"{_fmt(r['paint_before']):>6} → {_fmt(r['paint_after']):>6}      "
                  f"{_fmt(r['tile_before']):>6} → {_fmt(r['tile_after']):>6}   "
                  f"{r['source_after']}")
            rec = r["record"]
            if rec and isinstance(rec, dict):
                klases = rec.get("klases_m") or {}
                klt = ", ".join(f"{CLASS_LT.get(k, k)} {_fmt(v)} m" for k, v in sorted(klases.items(), key=lambda kv: -kv[1]))
                print(f"      line coverage: outline {_fmt(rec.get('konturas_m'))} m, openings {_fmt(rec.get('angos_m'))}, "
                      f"unmarked {_fmt(rec.get('nepazymeta_m'))} m, {klt or 'nothing'}; "
                      f"read={is_read(rec)}")
                el = rec.get("isklotines") or {}
                for z in (el.get("zonos") or [])[:4]:
                    print(f"        zonos: {z.get('siena')} {CLASS_LT.get(z.get('klase'), z.get('klase'))} "
                          f"{_fmt(z.get('plotis_m'))}×{_fmt(z.get('aukstis_m'))} = {_fmt(z.get('plotas_m2'))} m² "
                          f"({z.get('page')} lapas)")
                for t in (el.get("plyteles") or [])[:4]:
                    print(f"        plyteles layout: {t.get('siena')} h={_fmt(t.get('aukstis_m'))} m")
                for b in (el.get("baldai") or [])[:4]:
                    print(f"        baldai: {b.get('siena')} {str(b.get('tekstas') or '')[:40]}")

        t = out["totals"]
        print(f"\n== totals ==")
        print(f"paint {t['paint_before']} → {t['paint_after']} m²   (Δ {t['paint_after'] - t['paint_before']:+.2f})")
        print(f"tile  {t['tile_before']} → {t['tile_after']} m²   (Δ {t['tile_after'] - t['tile_before']:+.2f})")
        print(f"apply_geometry took {out['elapsed_s']} s")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/samatu.db")
    ap.add_argument("--project", required=True, help="project id in `projects`")
    ap.add_argument("--contractor-check", type=float, default=None, help="his total painted m² (printed as the check)")
    ap.add_argument("--json", action="store_true", help="dump the summary as JSON on stdout tail")
    args = ap.parse_args()

    data, pdf = load(args.db, args.project)
    out = run(data, pdf)
    if args.contractor_check is not None:
        t = out["totals"]
        print(f"\ncontractor check (manual): {args.contractor_check:.2f} m²; "
              f"before Δ={args.contractor_check - t['paint_before']:+.2f}, "
              f"after Δ={args.contractor_check - t['paint_after']:+.2f}")
    if args.json:
        print("\n--- JSON ---")
        light = {"totals": out["totals"], "elapsed_s": out["elapsed_s"], "meta": out["meta"]}
        for nr, r in out["per_room"].items():
            r2 = {k: v for k, v in r.items() if k != "record"}
            if r["record"] and isinstance(r["record"], dict):
                r2["record_klases_m"] = r["record"].get("klases_m")
                r2["record_padengta_m"] = r["record"].get("padengta_m")
                r2["record_konturas_m"] = r["record"].get("konturas_m")
                r2["record_nepazymeta_m"] = r["record"].get("nepazymeta_m")
                el = r["record"].get("isklotines") or {}
                r2["record_zonos"] = [{k: z.get(k) for k in ("siena", "klase", "plotis_m", "aukstis_m", "plotas_m2", "page")} for z in (el.get("zonos") or [])]
                r2["record_plyteles"] = el.get("plyteles") or []
                r2["record_baldai"] = [{"siena": b.get("siena"), "tekstas": (b.get("tekstas") or "")[:60]} for b in (el.get("baldai") or [])]
            light.setdefault("per_room", {})[nr] = r2
        print(json.dumps(light, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
