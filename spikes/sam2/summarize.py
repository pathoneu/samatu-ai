"""Tables + G0 clause numbers from spikes/sam2/out/results_*.json (any python3).

  python3 spikes/sam2/summarize.py [--tag ""]
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
VARS = ("L", "A", "B", "C", "D", "FF", "FFd", "F")


def f(v, nd=2):
    return "–" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def main(tag: str = "") -> None:
    for name in ("objektas_a_raster", "objektas_a_vector", "objektas_h", "objektas_g"):
        p = OUT / f"results_{name}{tag}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        rows = [r for r in d["rows"] if "variants" in r]
        print(f"\n### {name}  ({d['meta']['weights']}, {d['meta']['device']}, crop {d['meta']['side_m']} m)\n")
        print("| nr | table m² | vector m² (err %) | " + " | ".join(f"{k} m² (err %)" for k in VARS) + " | IoU A/B/C/D vs vector | leak A/B/C/D | enc ms | dec ms A |")
        print("|" + "---|" * (6 + len(VARS)))
        for r in rows:
            v = r["variants"]
            cells = []
            for k in VARS:
                x = v.get(k) or {}
                cells.append(f"{f(x.get('m2'))} ({f(x.get('err_pct'), 1)})" if x.get("m2") is not None else f"– ({x.get('fail', '')})")
            ious = "/".join(f((v.get(k) or {}).get("iou_vector")) for k in "ABCD")
            leaks = "/".join(("Y" if (v.get(k) or {}).get("leak") else "n") if (v.get(k) or {}).get("m2") is not None else "–" for k in "ABCD")
            vec = f"{f(r.get('vector_m2'))} ({f(r.get('vector_err_pct'), 1)})" if r.get("vector_m2") else "–"
            print(f"| {r['nr']} | {r['table_m2']} | {vec} | " + " | ".join(cells) +
                  f" | {ious} | {leaks} | {r.get('encode_ms')} | {(v.get('A') or {}).get('decode_ms')} |")
        n = len(rows)
        print(f"\nn={n}")
        for k in ("vector",) + VARS:
            if k == "vector":
                errs = [r.get("vector_err_pct") for r in rows]
                lk = [False] * n
            else:
                errs = [(r["variants"].get(k) or {}).get("err_pct") for r in rows]
                lk = [bool((r["variants"].get(k) or {}).get("leak")) or (r["variants"].get(k) or {}).get("m2") is None for r in rows]
            within2 = sum(1 for e in errs if e is not None and abs(e) <= 2)
            within5 = sum(1 for e in errs if e is not None and abs(e) <= 5)
            ae = [abs(e) for e in errs if e is not None]
            vsv = [(r["variants"].get(k) or {}).get("vs_vector_pct") for r in rows] if k != "vector" else []
            vsv2 = sum(1 for e in vsv if e is not None and abs(e) <= 2)
            print(f"  {k:6s} ≤2% table {within2}/{n}  ≤5% {within5}/{n}  median|err| {f(statistics.median(ae) if ae else None, 1)}%  "
                  f"no-leak {n - sum(lk)}/{n}" + (f"  ≤2% of vector {vsv2}/{n}" if k != "vector" else ""))
        enc = [r["encode_ms"] for r in rows[1:]]
        dec = [(r["variants"].get("A") or {}).get("decode_ms") for r in rows[1:]]
        if enc:
            print(f"  steady-state encode median {statistics.median(enc)} ms, decode A median {statistics.median([x for x in dec if x is not None])} ms, first encode {rows[0]['encode_ms']} ms")


if __name__ == "__main__":
    main(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--tag" else "")
