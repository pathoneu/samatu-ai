"""Truth for the FROZEN-CONSTANT test of the raster lane on sheets the spike never saw (plan 2026-10-24 §9,
founder's restated raster clause). Run with the PROJECT venv (imports backend/ read-only):

  venv/bin/python spikes/raster_rooms/dump_unseen.py <codename> <pdf> <pages> <out.json> [--seed ground_truth/<slug>]

- rooms: the ground-truth room list (`--seed`: ai_extract.json nr / name / area only) or, without a seed, the
  room table read from the text layer (`pdfplumber_eksplikacija`, units keyed `<unit>-<nr>`) — the cold run.
- the lane runs exactly as `scripts/cold_run/run_cold.py` runs it (no model).
- per target page: the scale from `backend/geometry/scale.py` (`scale_for_page`, with its provenance); seats =
  the lane's `_vieta` on that page, else the printed room number in the text layer (nearest to the room's seat
  on another sheet when the number repeats); vector truth = the lane's own outline on that page, else the
  one-click `outline_at` at the seat. Rooms with no vector truth keep only the table (the clause's fallback).

Output (outside git: spikes/raster_rooms/out/ is ignored): {codename, pdf_path, pages: {page: {scale, rooms:
[{nr, seat_pct, table_m2, vector_pct, vector_m2, vector_from}]}}}.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "cold_run"))
MAIN = Path("/Users/ignasgaldikas/samatu-ai")


def _area_m2(pct, W, H, m_per_pt, holes=None) -> float | None:
    from shapely.geometry import Polygon
    try:
        p = Polygon([(x * W, y * H) for x, y in pct], [[(x * W, y * H) for x, y in h] for h in (holes or [])])
        if not p.is_valid:
            p = p.buffer(0)
        return round(p.area * m_per_pt ** 2, 3)
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codename")
    ap.add_argument("pdf")
    ap.add_argument("pages")
    ap.add_argument("out")
    ap.add_argument("--seed", help="ground_truth/<slug> folder (main checkout)")
    a = ap.parse_args()

    import pdfplumber
    from run_cold import run_lane  # noqa: E402
    from extractor.plan_area_annotations import scan_text_layer
    from extractor.pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
    from extractor.vector_rooms import outline_at
    from geometry.scale import ScaleContext, scale_for_page

    pdf = Path(a.pdf).read_bytes()
    pages = [int(p) for p in a.pages.split(",")]
    if a.seed:
        parsed = json.loads((MAIN / a.seed / "ai_extract.json").read_text(encoding="utf-8"))
        rooms = [{k: r.get(k) for k in ("nr", "pavadinimas", "plotas_m2", "puslapio_nr") if r.get(k) is not None}
                 for r in parsed["patalpos"]]
    else:
        ek = extract_eksplikacija_pdfplumber(pdf)
        rooms = [{"nr": str(r.get("nr")), "pavadinimas": r.get("pavadinimas"), "plotas_m2": r.get("plotas_m2"), "puslapio_nr": r.get("page"),
                  **{k: r[k] for k in ("_vienetas", "_nr_brezinyje") if r.get(k) is not None}}
                 for r in ek.get("patalpos") or []]
    scan = scan_text_layer(pdf)
    lane = run_lane(pdf, copy.deepcopy(rooms), None, scan)
    lrooms = lane["parsed"]["patalpos"]
    ctx = ScaleContext(pdf)
    out = {"codename": a.codename, "pdf_path": str(Path(a.pdf).resolve()), "pages": {}}
    with pdfplumber.open(a.pdf) as doc:
        for pg in pages:
            sc = scale_for_page(ctx, pg)
            page = doc.pages[pg - 1]
            W, H = float(page.width), float(page.height)
            words = page.extract_words()
            entry = {"scale": sc.to_dict(), "W": W, "H": H, "rooms": []}
            out["pages"][str(pg)] = entry
            if not sc.found:
                continue
            seats = {}
            for r in lrooms:
                v = r.get("_vieta") or {}
                drawn = str(r.get("_nr_brezinyje") or r["nr"])
                if v.get("page") == pg and v.get("saltinis") != "bbox":
                    seats[str(r["nr"])] = (float(v["cx"]), float(v["cy"]), "lane")
                    continue
                cands = [w for w in words if w["text"] == drawn and 5 <= w["bottom"] - w["top"] <= 16]
                if not cands:
                    continue
                ref = (float(v.get("cx") or 0.5) * W, float(v.get("cy") or 0.5) * H)
                w = min(cands, key=lambda w: ((w["x0"] + w["x1"]) / 2 - ref[0]) ** 2 + ((w["top"] + w["bottom"]) / 2 - ref[1]) ** 2)
                if len(cands) > 1 and not v.get("page"):
                    continue                                   # an ambiguous number with nothing to choose by
                seats[str(r["nr"])] = ((w["x0"] + w["x1"]) / 2 / W, (w["top"] + w["bottom"]) / 2 / H, "text")
            for r in lrooms:
                nr = str(r["nr"])
                if nr not in seats:
                    continue
                cx, cy, seat_from = seats[nr]
                d = {"nr": nr, "seat_pct": [cx, cy], "seat_from": seat_from, "table_m2": r.get("plotas_m2")}
                k = r.get("_konturas") or {}
                v = r.get("_vieta") or {}
                same_frame = (k.get("page") and v.get("page") == k.get("page") and seat_from == "text"
                              and abs(float(v.get("cx") or -9) - cx) * W < 1.5 and abs(float(v.get("cy") or -9) - cy) * H < 1.5)
                if k.get("page") == pg and r.get("polygon_pct"):
                    d.update(vector_pct=r["polygon_pct"], vector_holes_pct=r.get("polygon_holes_pct"), vector_from="lane")
                elif same_frame and r.get("polygon_pct"):
                    # the badge stands on the same point of the same frame as on the lane's sheet: the same drawing
                    d.update(vector_pct=r["polygon_pct"], vector_holes_pct=r.get("polygon_holes_pct"),
                             vector_from=f"lane (sheet {k.get('page')}, same frame)")
                else:
                    others = {o: [x, y] for o, (x, y, _) in seats.items() if o != nr}
                    oa = outline_at(pdf, pg, cx, cy, r.get("plotas_m2"), sc.m_per_pt, page_size=(W, H), other_seats_pct=others)
                    d["outline_at_status"] = oa.get("status")
                    if oa.get("status") == "ok":
                        d.update(vector_pct=oa["polygon_pct"], vector_holes_pct=oa.get("polygon_holes_pct"), vector_from="click")
                if d.get("vector_pct"):
                    d["vector_m2"] = _area_m2(d["vector_pct"], W, H, sc.m_per_pt, d.get("vector_holes_pct"))
                entry["rooms"].append(d)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for pg, e in out["pages"].items():
        print(a.codename, "page", pg, "scale", e["scale"].get("mastelis"), e["scale"].get("source"), e["scale"].get("page_from"),
              "rooms", len(e["rooms"]), "vector", sum(1 for d in e["rooms"] if d.get("vector_pct")))
        for d in e["rooms"]:
            print("  ", d["nr"], d["table_m2"], d.get("vector_m2"), d.get("vector_from") or d.get("outline_at_status"), d["seat_from"])


if __name__ == "__main__":
    main()
