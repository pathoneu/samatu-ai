"""FROZEN-CONSTANT test of the raster lane on sheets the spike never saw (plan 2026-10-24 §9, the founder's
restated raster clause, „ok, 5%"). Spike venv (or the project venv):

  python spikes/raster_rooms/run_unseen.py [--dpi 150,300] [--only objektas_i:4,...]

Reads spikes/raster_rooms/out/unseen_<codename>.json (written by dump_unseen.py in the project venv).
The constants are the ones committed in raster_rooms.py — imported, never overridden here.

Per room (clause): area within 5 % of the vector outline (the table where no vector truth exists),
IoU >= 0,9 against the vector outline (when there is one), no leak (status open / outside / no face,
or > 1,3 x the table). A sheet passes when >= 80 % of its rooms pass.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import Polygon, shape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from raster_rooms import RasterPage, room_at_click, render_page  # noqa: E402

OUT = HERE / "out"
AREA_TOL = 0.05
IOU_MIN = 0.9
LEAK_RATIO = 1.3
SHARE = 0.8
# codename -> sheets in the unseen set (objektas_i sheets 5 and 7: the dumper found no vector truth and its text
# seats are not trustworthy there — reported, not scored)
SETS = {"objektas_d": [2], "objektas_b": [1], "objektas_i": [4], "objektas_a": [4]}


def _poly(pct, holes, W, H):
    p = Polygon([(x * W, y * H) for x, y in pct], [[(x * W, y * H) for x, y in h] for h in (holes or [])])
    return p if p.is_valid else p.buffer(0)


def score_sheet(code: str, page_no: int, dpi: int) -> tuple[list[dict], dict]:
    d = json.loads((OUT / f"unseen_{code}.json").read_text(encoding="utf-8"))
    pe = d["pages"][str(page_no)]
    m_per_pt = pe["scale"]["m_per_pt"]
    img, frame = render_page(d["pdf_path"], page_no, dpi)
    W, H = pe["W"], pe["H"]
    if abs(frame.width_pt - W) > 1 or abs(frame.height_pt - H) > 1:
        raise SystemExit(f"{code} p{page_no}: render frame {frame.width_pt}x{frame.height_pt} != text frame {W}x{H}")
    page = RasterPage(img, frame, m_per_pt)
    seats = {r["nr"]: (r["seat_pct"][0] * frame.width_px, r["seat_pct"][1] * frame.height_px) for r in pe["rooms"]}
    rows = []
    for r in pe["rooms"]:
        nr = r["nr"]
        sx, sy = seats[nr]
        others = {o: p for o, p in seats.items() if o != nr}
        res = room_at_click(page, sx, sy, r.get("table_m2"), others)
        ref = _poly(r["vector_pct"], r.get("vector_holes_pct"), W, H) if r.get("vector_pct") else None
        truth = r.get("vector_m2") if ref is not None else r.get("table_m2")
        row = {"sheet": f"{code} p{page_no}", "dpi": dpi, "nr": nr, "table_m2": r.get("table_m2"), "vector_m2": r.get("vector_m2"),
               "truth": "vector" if ref is not None else "table", "status": res["status"], "ms": res["ms"]}
        if "polygon" in res:
            p = shape(res["polygon"])
            area = res["area_m2"]
            row["raster_m2"] = area
            row["err_pct"] = round((area - truth) / truth * 100, 2) if truth else None
            row["iou"] = round(p.intersection(ref).area / p.union(ref).area, 3) if ref is not None else None
            row["leak"] = bool(res["status"] != "ok" or (r.get("table_m2") and area > LEAK_RATIO * r["table_m2"]))
        else:
            row.update(raster_m2=None, err_pct=None, iou=None, leak=True)
        row["area_ok"] = row["err_pct"] is not None and abs(row["err_pct"]) <= AREA_TOL * 100
        row["iou_ok"] = row["iou"] is None if ref is None else (row["iou"] is not None and row["iou"] >= IOU_MIN)
        row["pass"] = bool(row["area_ok"] and row["iou_ok"] and not row["leak"])
        rows.append(row)
    n = len(rows)
    k = sum(r["pass"] for r in rows)
    meta = {"sheet": f"{code} p{page_no}", "dpi": dpi, "rooms": n, "pass": k,
            "area_ok": sum(r["area_ok"] for r in rows), "iou_ok": sum(r["iou_ok"] for r in rows if r["truth"] == "vector"),
            "vector_rooms": sum(r["truth"] == "vector" for r in rows), "no_leak": sum(not r["leak"] for r in rows),
            "verdict": "PASS" if n and k / n >= SHARE else "FAIL", "scale": pe["scale"].get("mastelis"),
            "scale_source": pe["scale"].get("source"), "prep_ms": round(page.prep_ms)}
    return rows, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", default="150,300")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    todo = [(c, int(p)) for c, ps in SETS.items() for p in ps]
    if a.only:
        todo = [(x.split(":")[0], int(x.split(":")[1])) for x in a.only.split(",")]
    allrows, metas = [], []
    for code, pg in todo:
        for dpi in map(int, a.dpi.split(",")):
            rows, meta = score_sheet(code, pg, dpi)
            allrows += rows
            metas.append(meta)
            print(f"{meta['sheet']} {dpi} DPI: {meta['verdict']} {meta['pass']}/{meta['rooms']} "
                  f"(area ok {meta['area_ok']}, IoU ok {meta['iou_ok']}/{meta['vector_rooms']}, no leak {meta['no_leak']})")
            for r in rows:
                print(f"   {r['nr']:>4} truth {r['truth']:6} tbl {r['table_m2']} vec {r['vector_m2']} -> {r['raster_m2']} "
                      f"err {r['err_pct']} IoU {r['iou']} {r['status']}{' LEAK' if r['leak'] else ''} {'ok' if r['pass'] else '--'}")
    (OUT / "unseen_results.json").write_text(json.dumps({"rows": allrows, "meta": metas}, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
