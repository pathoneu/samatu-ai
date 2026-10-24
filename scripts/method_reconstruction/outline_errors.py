"""Per-room error of the VECTOR geometry lane, in-process, zero API.

For every project with a cached extract and its fixture PDF:
  1. load ground_truth/<folder>/ai_extract.json,
  2. take back every earlier lane's state (eval_harness._undo_lane_state —
     raster outlines, bbox polygons, lane perimeters), so the vector lane
     decides alone, from scratch,
  3. run extractor.geometry_lane.apply_geometry(parsed, pdf_bytes),
  4. per room compare
       • outline area (`_konturas.plotas_m2`) vs the designer's area
         (`plotas_m2` when `plotas_saltinis` ∈ {eksplikacija, plano_uzrasas} —
         the room table or the area label written on the plan),
       • outline perimeter (`_konturas.perimetras_m`) vs the perimeter ADDED
         from the plan's dimension strings (`perimetras_saltinis ==
         "matmenu_eilutes"`, dimension_sum.SOURCE) — where both exist.
     Rooms in an open space (`_atvira_erdve`) are reported per space: the
     shared outline vs the sum of its members' table areas.

    venv/bin/python scripts/method_reconstruction/outline_errors.py

Writes <out>/outline_errors.json and prints the per-project table.
"""
from __future__ import annotations

import contextlib
import io
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

TABLE_SOURCES = ("eksplikacija", "plano_uzrasas")


def _pct(a: float, b: float) -> float:
    return (a - b) / b * 100.0


def _q(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def measure(folder: str, eh) -> dict:
    from extractor.dimension_sum import SOURCE as SUMMED
    from extractor.geometry_lane import VECTOR_SOURCE, apply_geometry

    extract = common.GT / folder / "ai_extract.json"
    pdf = common.pdf_path(folder)
    if not extract.exists():
        return {"status": "no extract"}
    if pdf is None:
        return {"status": "no PDF"}
    parsed = json.loads(extract.read_text(encoding="utf-8"))
    # the designer's figure as the extract stored it, BEFORE the lanes are taken back (objektas_g's
    # areas are the labels on the plan, written by the text-scan lane that _undo_lane_state removes)
    designer = {str(r.get("nr")): float(r.get("plotas_m2") or 0) for r in parsed.get("patalpos") or []
                if isinstance(r, dict) and r.get("plotas_saltinis") in TABLE_SOURCES and r.get("plotas_m2")}
    log = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(log):
        undone = eh._undo_lane_state(parsed)
        g = apply_geometry(parsed, pdf.read_bytes())
    rooms = [r for r in parsed.get("patalpos") or [] if isinstance(r, dict)]
    per_room, spaces = [], {}
    for r in rooms:
        nr = str(r.get("nr"))
        table = designer.get(nr)
        k = r.get("_konturas") if isinstance(r.get("_konturas"), dict) else {}
        outlined = str(r.get("polygon_source") or "") == VECTOR_SOURCE and k.get("plotas_m2")
        row = {"nr": nr, "table_m2": table, "area_source": r.get("plotas_saltinis"),
               "outline_m2": k.get("plotas_m2") if outlined else None,
               "outline_perimeter_m": k.get("perimetras_m") if outlined else None,
               "perimeter_m": r.get("perimetras_m"), "perimeter_source": r.get("perimetras_saltinis"),
               "reason": r.get("_konturo_priezastis")}
        if outlined and table:
            row["area_err_pct"] = round(_pct(float(k["plotas_m2"]), table), 2)
        if outlined and r.get("perimetras_saltinis") == SUMMED and r.get("perimetras_m"):
            row["perimeter_err_pct"] = round(_pct(float(k["perimetras_m"]), float(r["perimetras_m"])), 2)
        sp = r.get("_atvira_erdve") if isinstance(r.get("_atvira_erdve"), dict) else None
        if sp:
            key = ",".join(sorted(str(x) for x in sp.get("nariai") or []))
            row["open_space"] = key
            spaces.setdefault(key, {"members": sp.get("nariai"), "outline_m2": sp.get("plotas_m2"),
                                    "perimeter_m": sp.get("perimetras_m"), "table_sum_m2": 0.0, "all_tabled": True})
            if table:
                spaces[key]["table_sum_m2"] += table
            else:
                spaces[key]["all_tabled"] = False
        per_room.append(row)
    for s in spaces.values():
        if s["all_tabled"] and s["outline_m2"] and s["table_sum_m2"]:
            s["area_err_pct"] = round(_pct(float(s["outline_m2"]), s["table_sum_m2"]), 2)
    errs = [abs(r["area_err_pct"]) for r in per_room if "area_err_pct" in r]
    perrs = [abs(r["perimeter_err_pct"]) for r in per_room if "perimeter_err_pct" in r]
    tabled = [r for r in per_room if r["table_m2"]]
    return {
        "status": g.get("status"), "lane_version": g.get("versija"), "seconds": round(time.time() - t0, 1),
        "undone": undone, "n_rooms": len(rooms), "n_tabled": len(tabled),
        "n_outlined": sum(1 for r in per_room if r["outline_m2"]),
        "n_tabled_outlined": len(errs),
        "n_tabled_not_outlined": sum(1 for r in tabled if not r["outline_m2"]),
        "n_in_open_space": sum(1 for r in per_room if r.get("open_space")),
        "area_abs_err_median_pct": round(statistics.median(errs), 2) if errs else None,
        "area_abs_err_p90_pct": round(_q(errs, 0.9), 2) if errs else None,
        "area_within_1pct": sum(1 for e in errs if e <= 1.0), "area_within_2pct": sum(1 for e in errs if e <= 2.0),
        "n_perimeter_pairs": len(perrs),
        "perimeter_abs_err_median_pct": round(statistics.median(perrs), 2) if perrs else None,
        "perimeter_abs_err_p90_pct": round(_q(perrs, 0.9), 2) if perrs else None,
        "n_summed_perimeters": sum(1 for r in per_room if r["perimeter_source"] == SUMMED),
        "reasons": g.get("konturu_priezastys"), "located": g.get("vietos"), "sheets": g.get("lapai"),
        "rooms": per_room, "open_spaces": list(spaces.values()),
        "log_tail": common.scrub(log.getvalue())[-3000:],
    }


def main() -> int:
    eh = common.harness()
    res = {}
    for code, folder in common.projects():
        res[code] = measure(folder, eh)
        m = res[code]
        if "n_rooms" not in m:
            print(f"  {code:<13} {m['status']}")
            continue
        print(f"  {code:<13} rooms {m['n_rooms']:>2}  table {m['n_tabled']:>2}  outlined {m['n_outlined']:>2}  "
              f"(tabled+outlined {m['n_tabled_outlined']}, tabled w/o outline {m['n_tabled_not_outlined']}, "
              f"open-space {m['n_in_open_space']})  area |err| med {m['area_abs_err_median_pct']} p90 "
              f"{m['area_abs_err_p90_pct']}  perim pairs {m['n_perimeter_pairs']} med "
              f"{m['perimeter_abs_err_median_pct']} p90 {m['perimeter_abs_err_p90_pct']}  ({m['seconds']} s)", flush=True)
    p = common.out_dir() / "outline_errors.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
