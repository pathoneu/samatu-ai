"""G0 tables for the raster room spike. Reads spikes/raster_rooms/out/results<tag>.json (run_raster.py) and,
for the SAM comparison, spikes/raster_rooms/out/sam/results_<run>.json (copied from the sam2 spike's out/).

  python3 spikes/raster_rooms/summarize.py [--tag _x] [--rooms]   > markdown on stdout
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SAM_RUN = {"objektas_a_flat150": "objektas_a_raster", "objektas_h_render": "objektas_h", "objektas_g_render": "objektas_g"}


def fmt(v, nd=2):
    if v is None:
        return "–"
    return f"{v:+.{nd}f}" if isinstance(v, float) and nd and abs(v) < 1000 else str(v)


def clauses(rows):
    rs = [r for r in rows if "skip" not in r]
    n = len(rs)
    tbl2 = sum(1 for r in rs if r.get("err_pct") is not None and abs(r["err_pct"]) <= 2)
    noleak = sum(1 for r in rs if not r.get("leak"))
    vr = [r for r in rs if r.get("vector_m2")]
    nv = len(vr)
    vec2 = sum(1 for r in vr if r.get("vs_vector_pct") is not None and abs(r["vs_vector_pct"]) <= 2)
    vec2iou = sum(1 for r in vr if r.get("vs_vector_pct") is not None and abs(r["vs_vector_pct"]) <= 2
                  and (r.get("iou_vector") or 0) >= 0.95)
    vec5 = sum(1 for r in vr if r.get("vs_vector_pct") is not None and abs(r["vs_vector_pct"]) <= 5)
    iou95 = sum(1 for r in vr if (r.get("iou_vector") or 0) >= 0.95)
    errs_v = [abs(r["vs_vector_pct"]) for r in vr if r.get("vs_vector_pct") is not None]
    errs_t = [abs(r["err_pct"]) for r in rs if r.get("err_pct") is not None]
    ious = [r.get("iou_vector") or 0 for r in vr]
    ms = [r["ms"] for r in rs if r.get("m2") is not None]
    return dict(n=n, nv=nv, tbl2=tbl2, noleak=noleak, vec2=vec2, vec2iou=vec2iou, vec5=vec5, iou95=iou95,
                med_v=statistics.median(errs_v) if errs_v else None, med_t=statistics.median(errs_t) if errs_t else None,
                med_iou=statistics.median(ious) if ious else None, med_ms=statistics.median(ms) if ms else None,
                failed=n - len(errs_t))


def verdict(c):
    pt = c["tbl2"] >= 0.8 * c["n"]
    pl = c["noleak"] >= 0.9 * c["n"]
    pv = c["nv"] > 0 and c["vec2iou"] >= 0.8 * c["nv"]
    return pt, pl, pv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="")
    ap.add_argument("--rooms", action="store_true")
    a = ap.parse_args()
    data = json.loads((OUT / f"results{a.tag}.json").read_text())
    groups: dict[tuple, list] = {}
    for r in data["rows"]:
        groups.setdefault((r["run"], r["dpi"]), []).append(r)
    print("| run | DPI | rooms | ≤2 % table | no leak | ≤2 % vector & IoU≥0,95 | ≤2 % vector | ≤5 % vector | IoU≥0,95 | median \\|err\\| vector | median \\|err\\| table | median IoU | failed (no outline) | ms/click | G0 table | G0 leak | G0 §9 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (run, dpi), rows in groups.items():
        c = clauses(rows)
        pt, pl, pv = verdict(c)
        f = lambda b: "PASS" if b else "FAIL"  # noqa: E731
        print(f"| {run} | {dpi} | {c['n']} | {c['tbl2']}/{c['n']} | {c['noleak']}/{c['n']} | {c['vec2iou']}/{c['nv']} | "
              f"{c['vec2']}/{c['nv']} | {c['vec5']}/{c['nv']} | {c['iou95']}/{c['nv']} | "
              f"{c['med_v']:.1f} % | {c['med_t']:.1f} % | {c['med_iou']:.3f} | {c['failed']} | {c['med_ms']:.0f} | "
              f"{f(pt)} | {f(pl)} | {f(pv)} |" if c["med_v"] is not None else
              f"| {run} | {dpi} | {c['n']} | {c['tbl2']}/{c['n']} | {c['noleak']}/{c['n']} | – | – | – | – | – | – | – | {c['failed']} | – | {f(pt)} | {f(pl)} | – |")
    if not a.rooms:
        return
    for (run, dpi), rows in groups.items():
        sam = {}
        sp = OUT / "sam" / f"results_{SAM_RUN.get(run, '')}.json"
        if run in SAM_RUN and sp.exists():
            for r in json.loads(sp.read_text())["rows"]:
                sam[str(r["nr"])] = r.get("variants") or {}
        print(f"\n#### {run} — {dpi} DPI\n")
        print("| nr | table m² | vector m² | vector click m² | raster m² | vs table | vs vector | IoU | stroke cm | status | leak | ms | SAM A vs table / IoU | SAM C vs table / IoU |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            if "skip" in r:
                continue
            sa, sc = sam.get(r["nr"], {}).get("A", {}), sam.get(r["nr"], {}).get("C", {})
            s = lambda v: f"{fmt(v.get('err_pct'), 1)} % / {v.get('iou_vector')}" if v else "–"  # noqa: E731
            st = r.get("stroke_m")
            print(f"| {r['nr']} | {r['table_m2']} | {r.get('vector_m2') or '–'} | {r.get('vector_click_m2') or '–'} | {r.get('m2') or '–'} | "
                  f"{fmt(r.get('err_pct'), 1)} | {fmt(r.get('vs_vector_pct'), 1)} | {r.get('iou_vector') or '–'} | "
                  f"{round(st * 100, 1) if st else '–'} | {r['status']} | {'L' if r.get('leak') else ''} | {r['ms']} | {s(sa)} | {s(sc)} |")


if __name__ == "__main__":
    main()
