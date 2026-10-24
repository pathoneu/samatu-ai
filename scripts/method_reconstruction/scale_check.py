"""Is an outline-vs-table area gap the SHEET SCALE or the TABLE's boundary?

For one project (default objektas_a), zero API:
  1. the dimension strings the geometry reading receives on each sheet: how
     many are backed by a dimension line, the scale each implies
     (value_m / line length in points), their spread, and the scale the sheet
     WRITES (`mastelis_kitas` / `mastelis_atmestas`, plus any „M 1:xx" text);
  2. the vector lane's outline of every room, edge by edge, against the
     dimension strings whose line runs along that edge (same axis, both ends
     within END_TOL_M of the edge's ends, line within NEAR_M of the edge):
     edge length vs the string's value — if they agree, the scale is right
     and the walls are where the strings say;
  3. the bounding box of each outline against its table area, and the sum of
     the table areas against the extract's stated total.

    venv/bin/python scripts/method_reconstruction/scale_check.py [codename]
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PT_M = 25.4 / 72 / 1000
END_TOL_M = 0.30
NEAR_M = 1.5


def main() -> int:
    code = sys.argv[1] if len(sys.argv) > 1 else "objektas_a"
    folder = dict(common.projects())[code]
    eh = common.harness()
    from extractor.geometry_lane import VECTOR_SOURCE, apply_geometry, geometry_dimension_strings

    pdf = common.pdf_path(folder).read_bytes()
    dims = geometry_dimension_strings(pdf)
    parsed = json.loads((common.GT / folder / "ai_extract.json").read_text(encoding="utf-8"))
    table = {str(r["nr"]): float(r["plotas_m2"]) for r in parsed["patalpos"]
             if r.get("plotas_saltinis") in ("eksplikacija", "plano_uzrasas") and r.get("plotas_m2")}
    with contextlib.redirect_stdout(io.StringIO()):
        eh._undo_lane_state(parsed)
        g = apply_geometry(parsed, pdf)
    pages = sorted({int(r["_konturas"]["page"]) for r in parsed["patalpos"] if isinstance(r.get("_konturas"), dict)})
    report: dict = {"code": code, "lane_scales": g.get("masteliai"), "pages": {}}
    print(f"{code}: outlines on sheet(s) {pages}; lane scales {g.get('masteliai')}")

    meta = (parsed.get("_meta") or {}).get("geometrija") or {}
    align = meta.get("sutapdinimas") or {}
    group = sorted({q for grp in (meta.get("grupes") or []) for q in grp if set(grp) & set(pages)})
    report["group"] = group
    print(f"  sheets laid over the outline sheet: {group}; alignment {json.dumps({q: align.get(str(q)) for q in group})}")
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for p in sorted(set(pages) | set(group)):
            text = doc.pages[p - 1].extract_text() or ""
            stated = sorted(set(re.findall(r"M\s*1\s*:\s*(\d{2,4})|1\s*:\s*(\d{2,3})\b", text)))
            report["pages"][p] = {"stated_scale_text": [a or b for a, b in stated]}

    sizes = {int(x["page"]): (float(x["page_width"]), float(x["page_height"])) for x in dims if x.get("page_width")}

    def to_page(x: dict, p: int) -> dict | None:
        """A line-backed string of sheet q in sheet p's points, through the lane's alignment (no rotation)."""
        q = int(x["page"])
        if q == p:
            return x
        aq, ap = align.get(str(q)), align.get(str(p))
        if not aq or not ap or aq["base"] != ap["base"] or q not in sizes or p not in sizes:
            return None
        Wb, Hb = sizes.get(int(aq["base"]), sizes[p])
        horiz = x.get("orientation") == "h"
        kq, kp = float(aq["k"]), float(ap["k"])
        dq = float(aq["dx_pct"] if horiz else aq["dy_pct"]) * (Wb if horiz else Hb)
        dp = float(ap["dx_pct"] if horiz else ap["dy_pct"]) * (Wb if horiz else Hb)
        dq2 = float(aq["dy_pct"] if horiz else aq["dx_pct"]) * (Hb if horiz else Wb)
        dp2 = float(ap["dy_pct"] if horiz else ap["dx_pct"]) * (Hb if horiz else Wb)
        f = lambda v, a, b: (kq * v + a - b) / kp  # noqa: E731
        return {**x, "page": p, "span": [f(x["span"][0], dq, dp), f(x["span"][1], dq, dp)],
                "line_pos": f(float(x.get("line_pos") or 0), dq2, dp2)}

    for p in pages:
        d = [x for x in dims if int(x["page"]) == p]
        own = [x for x in d if x.get("span_source") == "line" and x.get("span")]
        lined = [y for y in (to_page(x, p) for x in dims if int(x["page"]) in group and x.get("span_source") == "line"
                             and x.get("span")) if y]
        implied = [float(x["value_m"]) / abs(x["span"][1] - x["span"][0]) for x in own if abs(x["span"][1] - x["span"][0]) > 1]
        sc = float((g.get("masteliai") or {}).get(str(p), {}).get("m_per_pt") or 0) or None
        info = report["pages"][p]
        for q in group:
            dq = [x for x in dims if int(x["page"]) == q]
            imp = [float(x["value_m"]) / abs(x["span"][1] - x["span"][0]) for x in dq
                   if x.get("span_source") == "line" and x.get("span") and abs(x["span"][1] - x["span"][0]) > 1]
            report["pages"].setdefault(q, {}).update({
                "line_backed": len(imp),
                "written_other": next((x.get("mastelis_kitas") for x in dq if x.get("mastelis_kitas")), None)})
            print(f"  sheet {q}: {report['pages'][q]}")
        info.update({"strings": len(d), "own_line_backed": len(own), "strings_from_group": len(lined), "scale_m_per_pt": sc,
                     "scale_1_to": round(sc / PT_M, 2) if sc else None,
                     "written_other": next((x.get("mastelis_kitas") for x in d if x.get("mastelis_kitas")), None),
                     "refused": next((x.get("mastelis_atmestas") for x in d if x.get("mastelis_atmestas")), None)})
        print(f"\n sheet {p}: {info}")
        if not sc:
            continue
        W, H = float(d[0]["page_width"]), float(d[0]["page_height"])
        rows, all_pairs = [], []
        for r in parsed["patalpos"]:
            k = r.get("_konturas") if isinstance(r.get("_konturas"), dict) else None
            if not k or int(k["page"]) != p or str(r.get("polygon_source")) != VECTOR_SOURCE:
                continue
            ring = [(float(x) * W, float(y) * H) for x, y in r["polygon_pct"]]
            xs, ys = [q[0] for q in ring], [q[1] for q in ring]
            bw, bh = (max(xs) - min(xs)) * sc, (max(ys) - min(ys)) * sc
            pairs = []
            for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
                horiz = abs(y1 - y0) < 1.0
                vert = abs(x1 - x0) < 1.0
                if not (horiz or vert):
                    continue
                a0, a1 = sorted((x0, x1) if horiz else (y0, y1))
                pos = y0 if horiz else x0
                L = (a1 - a0) * sc
                if L < 0.8:
                    continue
                best = None
                for s in lined:
                    if (s.get("orientation") == "h") != horiz:
                        continue
                    s0, s1 = sorted(s["span"])
                    if abs(s0 - a0) * sc > END_TOL_M or abs(s1 - a1) * sc > END_TOL_M:
                        continue
                    if abs(float(s.get("line_pos") or 0) - pos) * sc > NEAR_M:
                        continue
                    dv = abs(float(s["value_m"]) - L)
                    if best is None or dv < best[1]:
                        best = (float(s["value_m"]), dv)
                if best:
                    pairs.append((round(L, 3), best[0], round((L - best[0]) / best[0] * 100, 2)))
            all_pairs += pairs
            nr = str(r["nr"])
            t = table.get(nr)
            rows.append({"nr": nr, "table_m2": t, "outline_m2": k.get("plotas_m2"),
                         "outline_err_pct": round((k["plotas_m2"] - t) / t * 100, 2) if t else None,
                         "bbox_m": [round(bw, 3), round(bh, 3)], "bbox_m2": round(bw * bh, 2),
                         "edges_matched": pairs})
            print(f"  room {nr}: table {t} outline {k.get('plotas_m2')} bbox {bw:.2f}×{bh:.2f}={bw * bh:.2f}  "
                  f"edges vs strings: {pairs}")
        # Discriminating test: the designer writes room widths/lengths as strings. If the SCALE were short by the
        # area gap, the outline's box sides × sqrt(table/outline) would be the written values; if the scale is right,
        # the box sides themselves are. Count, over the group's strings, how many box sides each hypothesis finds
        # within ±1 %.
        vals = [float(x["value_m"]) for x in dims if int(x["page"]) in group]
        hit = lambda v: any(abs(w - v) / v <= 0.01 for w in vals)  # noqa: E731
        as_is = scaled = n_sides = 0
        for row in rows:
            if not row["table_m2"] or not row["outline_m2"]:
                continue
            f = (row["table_m2"] / row["outline_m2"]) ** 0.5
            for side in row["bbox_m"]:
                n_sides += 1
                as_is += hit(side)
                scaled += hit(side * f)
        # …and the signed gap of each box side to its NEAREST written string, sides with no string within 5 %
        # dropped (a side no string states): a scale short by the area gap shows as a median near −√gap
        gaps_as_is, gaps_scaled = [], []
        for row in rows:
            if not row["table_m2"] or not row["outline_m2"]:
                continue
            f = (row["table_m2"] / row["outline_m2"]) ** 0.5
            for side in row["bbox_m"]:
                for v, acc in ((side, gaps_as_is), (side * f, gaps_scaled)):
                    w = min(vals, key=lambda x: abs(x - v))
                    if abs(v - w) / w <= 0.05:
                        acc.append((v - w) / w * 100)
        info["box_side_gap_as_traced"] = {"n": len(gaps_as_is), "median_pct": round(statistics.median(gaps_as_is), 2) if gaps_as_is else None}
        info["box_side_gap_if_scaled"] = {"n": len(gaps_scaled), "median_pct": round(statistics.median(gaps_scaled), 2) if gaps_scaled else None}
        print(f"  box side vs nearest string (within 5 %): as traced {info['box_side_gap_as_traced']}; "
              f"scaled to the table {info['box_side_gap_if_scaled']}")
        info["box_sides"] = n_sides
        info["box_sides_written_as_is"] = as_is
        info["box_sides_written_if_scaled_to_table"] = scaled
        print(f"  box sides found among the written strings (±1 %): as traced {as_is}/{n_sides}; "
              f"if scaled up to the table area {scaled}/{n_sides}")
        errs = [e for _, _, e in all_pairs]
        info["rooms"] = rows
        info["edge_string_pairs"] = len(all_pairs)
        if errs:
            info["edge_vs_string_median_pct"] = round(statistics.median(errs), 2)
            info["edge_vs_string_abs_median_pct"] = round(statistics.median([abs(e) for e in errs]), 2)
            print(f"  → {len(errs)} outline edges matched to strings: signed median {info['edge_vs_string_median_pct']} %, "
                  f"|median| {info['edge_vs_string_abs_median_pct']} %")
    report["table_sum_m2"] = round(sum(table.values()), 2)
    report["stated_total"] = (parsed.get("santrauka") or {}).get("bendras_plotas_m2") or parsed.get("bendras_plotas_m2")
    print(f"\n table areas sum {report['table_sum_m2']} m²; extract's stated total {report['stated_total']}")
    p = common.out_dir() / f"scale_check_{code}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
