"""Deterministic raster room spike — gate G0 (plan 2026-10-24 §4 Phase 0, §9). Spike venv:

  spikes/raster_rooms/.venv/bin/python spikes/raster_rooms/run_raster.py [--runs a,b] [--dpi 150,300]
        [--min-wall-m 0.07] [--tag _x] [--no-overlays]

Needs spikes/raster_rooms/out/lane_<slug>.json (spikes/sam2/dump_lane.py for objektas_a/h/g and
spikes/raster_rooms/dump_j2.py for objektas_j2, both in the PROJECT venv). Seats (room badge / area label),
table m², the sheet scale and the reference vector outline all come from the VECTOR drawing; the raster
pipeline itself reads nothing but pixels. For the contractor scan objektas_j3 the j2 truth is carried over
by a homography fitted between the j2 render and the scan (SIFT + RANSAC on the drawings themselves).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from shapely.affinity import affine_transform
from shapely.geometry import shape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sam2"))
from raster_rooms import RasterPage, room_at_click, render_page  # noqa: E402
from run_spike import iou, pct_err, ref_outline  # noqa: E402  (spikes/sam2 — same reference outline as SAM)

OUT = HERE / "out"
SCRATCH = OUT / "_pdfs"
FIX = Path("/Users/ignasgaldikas/samatu-ai/docs/superpowers/fixtures")
PROD = Path("/private/tmp/claude-501/-Users-ignasgaldikas-samatu-ai/17639f50-ffef-49b5-8063-bb81f19b2420/scratchpad/prod-pull/pdfs")
J3 = PROD / "640df8be-884a-4300-a39a-f215c2805a50.pdf"
FURNITURE = re.compile(r"baldai|furniture", re.I)
LEAK_RATIO = 1.3
DOOR_NEEDS_END = False
OV_HALF_M = 5.0
OPEN_SHARE = 0.6

# run: (lane slug, pdf (None = the lane's own vector pdf), page, furniture off?, registered to the vector sheet?)
RUNS = {
    "objektas_a_flat150": ("objektas_a", FIX / "2026-08-22-objektas-a-ablations/objektas_a_flat150.pdf", 2, False, False),
    "objektas_a_render": ("objektas_a", None, 2, False, False),
    "objektas_a_render_nofurn": ("objektas_a", None, 2, True, False),
    "objektas_h_render": ("objektas_h", None, 1, False, False),
    "objektas_g_render": ("objektas_g", None, 4, False, False),
    "objektas_g_render_nofurn": ("objektas_g", None, 4, True, False),
    "objektas_j3_scan": ("objektas_j2", J3, 1, False, True),
}


def furniture_off(pdf: Path) -> Path:
    """Copy of `pdf` with every optional-content layer named like furniture switched OFF (PDFium honours
    the default /OFF list when rendering). Written under out/_pdfs (gitignored)."""
    import pymupdf
    SCRATCH.mkdir(parents=True, exist_ok=True)
    dst = SCRATCH / f"{hashlib.sha1(str(pdf).encode()).hexdigest()[:10]}_nofurn.pdf"
    doc = pymupdf.open(str(pdf))
    ocgs = doc.get_ocgs()
    off = [x for x, v in ocgs.items() if FURNITURE.search(v["name"] or "")]
    on = [x for x in ocgs if x not in off]
    doc.set_layer(-1, on=on, off=off)
    doc.save(str(dst))
    return dst


def register(j2_img: np.ndarray, j3_img: np.ndarray) -> np.ndarray:
    """Homography mapping j3 pixels -> j2 pixels (both renders at the given dpi)."""
    g2 = cv2.cvtColor(j2_img, cv2.COLOR_BGR2GRAY)
    g3 = cv2.cvtColor(j3_img, cv2.COLOR_BGR2GRAY)
    sift = cv2.SIFT_create(nfeatures=20000)
    k2, d2 = sift.detectAndCompute(g2, None)
    k3, d3 = sift.detectAndCompute(g3, None)
    m = cv2.BFMatcher().knnMatch(d3, d2, k=2)
    good = [a for a, b in m if a.distance < 0.75 * b.distance]
    src = np.float32([k3[a.queryIdx].pt for a in good])
    dst = np.float32([k2[a.trainIdx].pt for a in good])
    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    return H, int(inl.sum()), len(good)


def run(name: str, dpi: int, min_wall_m: float, overlays: bool, tag: str) -> list[dict]:
    slug, pdf_override, page_no, nofurn, registered = RUNS[name]
    lane = json.loads((OUT / f"lane_{slug}.json").read_text(encoding="utf-8"))
    vec_pdf = Path(lane["pdf_path"])
    pdf = pdf_override or vec_pdf
    if nofurn:
        pdf = furniture_off(pdf)
    m_per_pt_vec = float(lane["masteliai"][str(page_no)]["m_per_pt"])
    t = time.perf_counter()
    img, frame = render_page(pdf, page_no if not registered else 1, dpi)
    render_ms = (time.perf_counter() - t) * 1000
    vimg, vframe = (img, frame) if not registered else render_page(vec_pdf, page_no, dpi)

    # pixel-in-run -> PDF point on the VECTOR sheet (where seats and outlines live)
    if registered:
        Hpx, n_inl, n_good = register(vimg, img)
        k_v, k_r = 72.0 / vframe.dpi, frame.dpi / 72.0
        S_v = np.diag([k_v, k_v, 1.0])
        S_r = np.diag([k_r, k_r, 1.0])
        H_pt = S_v @ Hpx @ S_r                                          # run pt -> run px -> vector px -> vector pt
        lin = H_pt[:2, :2]
        scale = float(np.sqrt(abs(np.linalg.det(lin))))                # vector pt per run pt
        m_per_pt = m_per_pt_vec * scale
        Hinv = np.linalg.inv(H_pt)
        reg = {"inliers": n_inl, "matches": n_good, "vector_pt_per_run_pt": round(scale, 5),
               "rotation_deg": round(float(np.degrees(np.arctan2(lin[1, 0], lin[0, 0]))), 3)}
    else:
        H_pt = np.eye(3)
        Hinv = np.eye(3)
        m_per_pt = m_per_pt_vec
        reg = None

    def run_pt_to_vec(p):
        q = H_pt @ np.array([p[0], p[1], 1.0])
        return q[0] / q[2], q[1] / q[2]

    def vec_pt_to_run_px(p):
        q = Hinv @ np.array([p[0], p[1], 1.0])
        return q[0] / q[2] * frame.px_per_pt, q[1] / q[2] * frame.px_per_pt

    page = RasterPage(img, frame, m_per_pt, min_wall_m=min_wall_m, open_share=OPEN_SHARE, door_needs_end=DOOR_NEEDS_END)
    odir = OUT / f"{name}{tag}_{dpi}"
    if overlays:
        odir.mkdir(parents=True, exist_ok=True)
        wv = np.full(img.shape, 255, np.uint8)
        wv[page.walls] = (0, 0, 0)
        for b in page.bridged(1.6)[0]:
            cv2.fillPoly(wv, [np.round(np.asarray(b.poly.exterior.coords) - 0.5).astype(np.int32)],
                         (0, 160, 0) if b.kind == "door" else (200, 120, 0))
        cv2.imwrite(str(odir / "_walls_bridges.png"), wv)

    vw, vh = vframe.width_pt, vframe.height_pt
    seats_vec = {}
    for r in lane["rooms"]:
        v = r.get("_vieta") or {}
        if v.get("page") == page_no:
            seats_vec[str(r["nr"])] = (float(v["cx"]) * vw, float(v["cy"]) * vh)
    seats_px = {nr: vec_pt_to_run_px(p) for nr, p in seats_vec.items()}
    rows = []
    for r in lane["rooms"]:
        nr = str(r["nr"])
        table = r.get("table_m2")
        row = {"run": name, "dpi": dpi, "nr": nr, "table_m2": table, "min_wall_m": min_wall_m}
        if nr not in seats_px or not table:
            row["skip"] = "no seat on this sheet or no table area"
            rows.append(row)
            continue
        ref, ref_label, _ = ref_outline(r, page_no, vw, vh)
        if ref is not None:
            row["vector_m2"] = round(ref.area * m_per_pt_vec ** 2, 3)
            row["vector_err_pct"] = pct_err(row["vector_m2"], table)
            row["vector_from"] = ref_label
        oa = r.get("outline_at") or {}
        row["vector_click_m2"] = oa.get("plotas_m2") if oa.get("status") == "ok" else None   # vector one-click baseline
        sx, sy = seats_px[nr]
        others = {o: p for o, p in seats_px.items() if o != nr}
        res = room_at_click(page, sx, sy, table, others)
        row.update(status=res["status"], ms=res["ms"], prep_ms=round(page.prep_ms), render_ms=round(render_ms))
        if "polygon" in res:
            poly_run = shape(res["polygon"])
            a, b_, c, d = H_pt[0, 0], H_pt[0, 1], H_pt[1, 0], H_pt[1, 1]
            poly_vec = poly_run if not registered else affine_transform(poly_run, [a, b_, c, d, H_pt[0, 2], H_pt[1, 2]])
            area_vec = poly_vec.area * m_per_pt_vec ** 2                  # in the vector sheet's frame
            row.update(m2=round(area_vec, 3), m2_own_scale=res["area_m2"], m2_raw_own_scale=res["area_m2_raw"], stroke_m=res["stroke_m"], perim_m=res["perimeter_m"],
                       err_pct=pct_err(area_vec, table), vs_vector_pct=pct_err(area_vec, row.get("vector_m2")),
                       iou_vector=iou(poly_vec, ref), door_m=res["door_m"], merged=res["merged"],
                       n_vertices=len(res["polygon"]["coordinates"][0]) - 1)
            row["leak"] = bool(res["status"] == "open" or area_vec > LEAK_RATIO * table)
        else:
            row["leak"] = res["status"] == "outside"
            row["m2"] = None
        rows.append(row)
        if overlays:
            x0 = int(max(0, sx - OV_HALF_M / m_per_pt * frame.px_per_pt)); x1 = int(min(frame.width_px, sx + OV_HALF_M / m_per_pt * frame.px_per_pt))
            y0 = int(max(0, sy - OV_HALF_M / m_per_pt * frame.px_per_pt)); y1 = int(min(frame.height_px, sy + OV_HALF_M / m_per_pt * frame.px_per_pt))
            ov = img.copy()
            if "mask" in res:
                tint = ov.copy(); tint[res["mask"]] = (80, 80, 255)
                ov = cv2.addWeighted(ov, 0.6, tint, 0.4, 0)
            wl = page.walls
            ov[wl] = (ov[wl] * 0.5 + np.array([0, 90, 0]) * 0.5).astype(np.uint8)
            for b in page.bridged(res.get("door_m") or 1.25)[0]:
                cv2.polylines(ov, [np.round(np.asarray(b.poly.exterior.coords) - 0.5).astype(np.int32)], True, (0, 200, 0), 2)
            if ref is not None:
                pts = [vec_pt_to_run_px(p) for p in ref.exterior.coords]
                cv2.polylines(ov, [np.round(pts).astype(np.int32)], True, (255, 0, 255), 2)
            cv2.circle(ov, (int(sx), int(sy)), 6, (0, 0, 255), -1)
            cv2.imwrite(str(odir / f"{nr}.png"), ov[y0:y1, x0:x1])
    meta = {"run": name, "dpi": dpi, "render_ms": round(render_ms), "prep_ms": round(page.prep_ms),
            "m_per_pt": m_per_pt, "registration": reg, "n_bridges_125": len(page.bridged(1.25)[0]),
            "n_bridges_16": len(page.bridged(1.6)[0])}
    return rows, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=",".join(RUNS))
    ap.add_argument("--dpi", default="150,300")
    ap.add_argument("--min-wall-m", type=float, default=0.07)
    ap.add_argument("--open-share", type=float, default=0.6)
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-overlays", action="store_true")
    ap.add_argument("--door-needs-end", action="store_true", help="a door bridge must start at a wall end cap")
    a = ap.parse_args()
    global DOOR_NEEDS_END, OPEN_SHARE
    OPEN_SHARE = a.open_share
    DOOR_NEEDS_END = a.door_needs_end
    allrows, metas = [], []
    for name in a.runs.split(","):
        for dpi in map(int, a.dpi.split(",")):
            rows, meta = run(name, dpi, a.min_wall_m, not a.no_overlays, a.tag)
            allrows += rows; metas.append(meta)
            ok = [r for r in rows if "skip" not in r]
            print(name, dpi, "prep", meta["prep_ms"], "ms", meta.get("registration") or "")
            for r in ok:
                print(f"  {r['nr']:>4} table {r['table_m2']:>6} vec {r.get('vector_m2')} -> {r.get('m2')} "
                      f"({r.get('err_pct')} % tbl, {r.get('vs_vector_pct')} % vec, IoU {r.get('iou_vector')}) "
                      f"{r['status']} door {r.get('door_m')} merged {r.get('merged')} {r['ms']} ms")
    (OUT / f"results{a.tag}.json").write_text(json.dumps({"rows": allrows, "meta": metas}, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
