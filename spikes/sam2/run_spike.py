"""SAM 2 viability spike (plan 2026-10-24, Phase 0 (c), gate G0). Spike venv:

  spikes/sam2/.venv/bin/python spikes/sam2/run_spike.py [--weights spikes/sam2/weights/sam2.1_b.pt] [--side-m 20]

Needs spikes/sam2/out/lane_<slug>.json from dump_lane.py (project venv) first. For every room with a table
area and a seat (its printed number / area label, found by the app's room_locator on the VECTOR drawing):
crop a square of `side_m` metres around the seat from a 300 DPI PDFium render, encode it once, and prompt
  A  one positive point at the seat (multimask, highest predicted IoU kept; all three areas recorded)
  B  the point + up to 4 negative points on the nearest thick-wall pixels (wall_mask, 8 rays)
  C  a loose box: the reference outline's bbox x1.1 (no point)
  F  A on the FULL page (no crop) — how much the crop matters
Then largest component under the click -> polygon (ε 2 cm) -> m², perimeter; IoU vs the vector outline;
leak flags. Overlays to spikes/sam2/out/<run>/<nr>.png, rows to spikes/sam2/out/results_<run>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Point, Polygon, box as sbox, shape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sam_source import (clear_floor_point, flood_fill_room, load_model, walls_only_image, largest_component, mask_to_polygon, negative_points_on_walls,  # noqa: E402
                        polygon_metrics, render_page, wall_mask)

OUT = HERE / "out"
FIX = Path("/Users/ignasgaldikas/samatu-ai/docs/superpowers/fixtures")
RUNS = {
    # run name: (lane dump slug, pdf to segment)
    "objektas_a_raster": ("objektas_a", FIX / "2026-08-22-objektas-a-ablations/objektas_a_flat150.pdf"),
    "objektas_a_vector": ("objektas_a", None),
    "objektas_h": ("objektas_h", None),
    "objektas_g": ("objektas_g", None),
}
EPS_M = 0.02
LEAK_RATIO = 1.3


def ref_outline(room: dict, page: int, wpt: float, hpt: float):
    """The current vector outline on the seat's page: the one-click outline_at answer when it is a room's
    face, else the lane's stored outline when it lies on the same page. -> (Polygon in pts, label, m²)."""
    oa = room.get("outline_at") or {}
    k = room.get("_konturas") or {}
    cands = []
    if k.get("page") == page and room.get("polygon_pct"):
        cands.append(("lane", room["polygon_pct"], k.get("plotas_m2"), room.get("polygon_holes_pct")))
    if oa.get("status") == "ok" and oa.get("polygon_pct"):
        cands.append(("click", oa["polygon_pct"], oa.get("plotas_m2"), oa.get("polygon_holes_pct")))
    for label, pct, m2, holes in cands:
        try:
            shell = [(float(x) * wpt, float(y) * hpt) for x, y in pct]
            hs = [[(float(x) * wpt, float(y) * hpt) for x, y in h] for h in (holes or [])]
            p = Polygon(shell, hs)
            if not p.is_valid:
                p = p.buffer(0)
            return p, label, m2
        except Exception:  # noqa: BLE001
            continue
    return None, None, None


def pct_err(a, b):
    if a is None or not b:
        return None
    return round((a - b) / b * 100, 2)


def iou(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return None
    u = a.union(b).area
    return round(a.intersection(b).area / u, 3) if u else None


def run(name: str, model, side_m: float, only: set[str] | None) -> list[dict]:
    slug, pdf_override = RUNS[name]
    lane = json.loads((OUT / f"lane_{slug}.json").read_text(encoding="utf-8"))
    pdf = pdf_override or Path(lane["pdf_path"])
    odir = OUT / name
    odir.mkdir(parents=True, exist_ok=True)
    pages: dict[int, tuple] = {}
    rooms = lane["rooms"]
    seats_by_page: dict[int, dict[str, tuple[float, float]]] = {}
    for r in rooms:
        v = r.get("_vieta") or {}
        if v.get("page"):
            seats_by_page.setdefault(int(v["page"]), {})[str(r["nr"])] = (float(v["cx"]), float(v["cy"]))
    rows = []
    for r in rooms:
        nr = str(r["nr"])
        if only and nr not in only:
            continue
        v = r.get("_vieta") or {}
        table = r.get("table_m2")
        row = {"run": name, "nr": nr, "table_m2": table}
        if not v.get("page") or not table:
            row["skip"] = "no seat or no table area"
            rows.append(row)
            continue
        page = int(v["page"])
        sc = ((lane.get("masteliai") or {}).get(str(page)) or {}).get("m_per_pt")
        if not sc:
            row["skip"] = f"no scale on page {page}"
            rows.append(row)
            continue
        m_per_pt = float(sc)
        if page not in pages:
            t = time.perf_counter()
            pages[page] = render_page(pdf, page, 300)
            row["render_ms"] = round((time.perf_counter() - t) * 1000)
        img, frame = pages[page]
        row.update(page=page, m_per_pt=m_per_pt, seat_source=v.get("saltinis"))
        sx, sy = frame.pct_to_px(float(v["cx"]), float(v["cy"]))
        ref, ref_label, ref_m2 = ref_outline(r, page, frame.width_pt, frame.height_pt)
        if ref is not None:
            row["vector_m2"] = round(ref.area * m_per_pt ** 2, 3)
            row["vector_from"] = ref_label
            row["vector_m2_app"] = ref_m2
            row["vector_err_pct"] = pct_err(row["vector_m2"], table)
        lane_k = r.get("_konturas") or {}
        row["lane_m2"] = lane_k.get("plotas_m2")
        row["lane_err_pct"] = pct_err(lane_k.get("plotas_m2"), table)
        oa = r.get("outline_at") or {}
        row["click_status"] = oa.get("status")
        row["click_m2"] = oa.get("plotas_m2") if oa.get("status") == "ok" else None
        row["click_err_pct"] = pct_err(row["click_m2"], table)
        row["click_ms"] = oa.get("ms")

        # crop around the seat
        half = side_m / m_per_pt * frame.px_per_pt / 2
        x0, y0 = int(max(0, sx - half)), int(max(0, sy - half))
        x1, y1 = int(min(frame.width_px, sx + half)), int(min(frame.height_px, sy + half))
        crop = np.ascontiguousarray(img[y0:y1, x0:x1])
        lx, ly = sx - x0, sy - y0              # the label itself
        enc_ms = model.set_image(crop)
        row["encode_ms"] = round(enc_ms)
        row["crop_px"] = [x1 - x0, y1 - y0]
        others = [Point(px * frame.width_pt, py * frame.height_pt)
                  for o, (px, py) in seats_by_page.get(page, {}).items() if o != nr]
        px_m = frame.px_per_pt / m_per_pt       # pixels per metre on the sheet
        min_wall_px = max(5, int(0.08 * px_m))
        walls = wall_mask(crop, min_wall_px)
        (cx, cy), snap = clear_floor_point(crop, walls, (lx, ly), clear_px=0.25 * px_m, radius_px=1.5 * px_m)
        row["snap"] = snap
        row["snap_m"] = round(float(np.hypot(cx - lx, cy - ly)) / px_m, 2)
        row["click_px"] = [round(cx + x0), round(cy + y0)]
        negs = negative_points_on_walls(walls, (cx, cy), n=4, max_px=int(8 * px_m))
        variants: dict[str, dict] = {}

        def evaluate(key, masks_scores, off=(x0, y0), shape_hw=crop.shape[:2], seed=(cx, cy), t_dec=0.0):
            t = time.perf_counter()
            if not masks_scores:
                variants[key] = {"m2": None, "fail": "no mask"}
                return None
            best_i = int(np.argmax([s for _, s in masks_scores]))
            mask, score = masks_scores[best_i]
            comp = largest_component(mask, seed)
            gj = mask_to_polygon(comp, frame, EPS_M, m_per_pt, offset_px=off)
            poly_ms = (time.perf_counter() - t) * 1000
            if gj is None:
                variants[key] = {"m2": None, "fail": "no polygon"}
                return None
            met = polygon_metrics(gj, m_per_pt)
            p = shape(gj)
            hh, ww = shape_hw
            ys, xs = np.nonzero(comp)
            touches = bool(len(xs) and (xs.min() <= 1 or ys.min() <= 1 or xs.max() >= ww - 2 or ys.max() >= hh - 2))
            eats = [o for o in others if p.contains(o)]
            d = {"m2": met["area_m2"], "perim_m": met["perimeter_m"], "err_pct": pct_err(met["area_m2"], table),
                 "score": round(float(score), 3), "iou_vector": iou(p, ref),
                 "vs_vector_pct": pct_err(met["area_m2"], row.get("vector_m2")),
                 "leak_area": met["area_m2"] > LEAK_RATIO * table, "leak_neighbour_seat": len(eats),
                 "touches_crop_edge": touches, "decode_ms": round(t_dec), "poly_ms": round(poly_ms),
                 "n_vertices": len(gj["coordinates"][0]) - 1}
            if len(masks_scores) > 1:
                d["all_m2"] = []
                for m_, s_ in masks_scores:
                    g_ = mask_to_polygon(largest_component(m_, seed), frame, EPS_M, m_per_pt, offset_px=off)
                    d["all_m2"].append([polygon_metrics(g_, m_per_pt)["area_m2"] if g_ else None, round(float(s_), 3)])
            d["leak"] = bool(d["leak_area"] or d["leak_neighbour_seat"] or touches)
            variants[key] = d
            return comp

        t = time.perf_counter(); ms = model.segment([(lx, ly)], multimask=True); tL = (time.perf_counter() - t) * 1000
        evaluate("L", ms, seed=(lx, ly), t_dec=tL)
        t = time.perf_counter(); ms = model.segment([(cx, cy)], multimask=True); tA = (time.perf_counter() - t) * 1000
        mA = evaluate("A", ms, t_dec=tA)
        t = time.perf_counter(); ms = model.segment([(cx, cy)], neg_points=negs); tB = (time.perf_counter() - t) * 1000
        mB = evaluate("B", ms, t_dec=tB)
        variants.setdefault("B", {})["n_neg"] = len(negs)
        mC = None
        if ref is not None:
            bx0, by0, bx1, by1 = ref.bounds
            mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
            hw, hh_ = (bx1 - bx0) * 1.1 / 2, (by1 - by0) * 1.1 / 2
            (px0, py0), (px1, py1) = frame.pt_to_px(mx - hw, my - hh_), frame.pt_to_px(mx + hw, my + hh_)
            bb = [px0 - x0, py0 - y0, px1 - x0, py1 - y0]
            t = time.perf_counter(); ms = model.segment(box=bb); tC = (time.perf_counter() - t) * 1000
            # seed: the click when it is inside the box, else the largest component
            mC = evaluate("C", ms, t_dec=tC)
        else:
            variants["C"] = {"m2": None, "fail": "no vector outline for the box"}
        # FF: no model — flood fill of the free space in the walls-only mask
        t = time.perf_counter(); ff = flood_fill_room(walls, (cx, cy)); tF = (time.perf_counter() - t) * 1000
        evaluate("FF", [(ff, 1.0)] if ff.any() else [], t_dec=tF)
        # FFd: the same with door gaps bridged — walls closed by a 1.2 m square (no model either)
        t = time.perf_counter()
        kd = int(1.2 * px_m)
        walls_d = cv2.morphologyEx(walls.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((kd, kd), np.uint8)).astype(bool)
        ffd = flood_fill_room(walls_d, (cx, cy)); tFd = (time.perf_counter() - t) * 1000
        evaluate("FFd", [(ffd, 1.0)] if ffd.any() else [], t_dec=tFd)
        # D: SAM on the walls-only image (furniture/text/hatch removed), snapped point, multimask best
        model.set_image(walls_only_image(walls))
        t = time.perf_counter(); ms = model.segment([(cx, cy)], multimask=True); tD = (time.perf_counter() - t) * 1000
        mD = evaluate("D", ms, t_dec=tD)
        row["variants"] = variants
        rows.append(row)
        draw_overlay(odir / f"{nr}.png", crop, (x0, y0), frame, (cx, cy), negs, ref, {"A": mA, "B": mB, "C": mC, "D": mD}, nr, row)
    # F: single point on the full page (one encode per page, then per-room decode)
    for page, (img, frame) in pages.items():
        enc = model.set_image(img)
        for row in rows:
            if row.get("page") != page or "variants" not in row:
                continue
            sx, sy = row["click_px"]          # the same snapped click as A
            t = time.perf_counter(); ms = model.segment([(sx, sy)], multimask=True); tF = (time.perf_counter() - t) * 1000
            if not ms:
                row["variants"]["F"] = {"m2": None, "fail": "no mask"}
                continue
            mask, score = ms[int(np.argmax([s for _, s in ms]))]
            gj = mask_to_polygon(largest_component(mask, (sx, sy)), frame, EPS_M, row["m_per_pt"])
            m2 = polygon_metrics(gj, row["m_per_pt"])["area_m2"] if gj else None
            row["variants"]["F"] = {"m2": m2, "err_pct": pct_err(m2, row["table_m2"]), "score": round(float(score), 3),
                                    "encode_ms_page": round(enc), "decode_ms": round(tF),
                                    "leak": bool(m2 and m2 > LEAK_RATIO * row["table_m2"])}
    return rows


COLORS = {"A": (0, 0, 255), "B": (0, 160, 0), "C": (255, 120, 0), "D": (0, 200, 255)}


def draw_overlay(path, crop, off, frame, seed, negs, ref, masks, nr, row):
    vis = crop.copy()
    over = vis.copy()
    for k, m in masks.items():
        if m is not None:
            over[m] = (0.5 * np.array(over[m], float) + 0.5 * np.array(COLORS[k], float)).astype(np.uint8)
    vis = cv2.addWeighted(over, 0.6, vis, 0.4, 0)
    for k, m in masks.items():
        if m is not None:
            cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, cs, -1, COLORS[k], 3)
    if ref is not None:
        rings = [ref.exterior] if ref.geom_type == "Polygon" else [g.exterior for g in ref.geoms]
        for ring in rings:
            pts = np.array([frame.pt_to_px(x, y) for x, y in ring.coords]) - np.array(off)
            cv2.polylines(vis, [pts.astype(np.int32)], True, (200, 0, 200), 3)
    cv2.circle(vis, (int(seed[0]), int(seed[1])), 12, (0, 0, 255), -1)
    for x, y in negs:
        cv2.drawMarker(vis, (int(x), int(y)), (0, 0, 0), cv2.MARKER_TILTED_CROSS, 28, 4)
    v = row.get("variants", {})
    txt = f"{nr} table {row['table_m2']}  vec {row.get('vector_m2')}  A {v.get('A', {}).get('m2')}  B {v.get('B', {}).get('m2')}  C {v.get('C', {}).get('m2')}  D {v.get('D', {}).get('m2')}"
    cv2.putText(vis, txt, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 4)
    s = 1400 / max(vis.shape[:2])
    if s < 1:
        vis = cv2.resize(vis, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), vis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(HERE / "weights" / "sam2.1_b.pt"))
    ap.add_argument("--device", default=None)
    ap.add_argument("--side-m", type=float, default=20.0)
    ap.add_argument("--runs", default=",".join(RUNS))
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t = time.perf_counter()
    model = load_model(a.weights, a.device)
    load_ms = (time.perf_counter() - t) * 1000
    only = set(a.only.split(",")) if a.only else None
    for name in a.runs.split(","):
        rows = run(name, model, a.side_m, only)
        meta = {"weights": Path(a.weights).name, "device": model.device, "side_m": a.side_m,
                "eps_m": EPS_M, "model_load_ms": round(load_ms)}
        (OUT / f"results_{name}{a.tag}.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1, default=str),
                                                         encoding="utf-8")
        print(name, "rows", len(rows), "device", model.device)


if __name__ == "__main__":
    main()
