# backend/scripts/bench_room_polygons.py
"""Benchmark accurate-polygon detection across all ground-truth projects.

For each project with a PDF + rooms (nr, plotas_m2, bbox_pct), runs the SAME
seeding the endpoint uses (label seed + bbox centroid, multi-seed + guard) and
reports auto/manual counts, mean area_err on auto rooms, and wrong-room-fill
count (a fill whose room-number label seed is NOT inside the polygon).

Usage: cd backend && python scripts/bench_room_polygons.py
"""
import json, sys, glob, os
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractor.cv_polygon import auto_room_polygon, point_in_polygon_px
from extractor.room_seeds import locate_room_seeds, calibrate_page_scale, bbox_centroid_seed
import page_raster_cache as cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_project(gt_dir):
    """Return (pdf_bytes, page_nr, [rooms]) or None. rooms: {nr, plotas_m2, bbox_pct}.

    The source PDF lives under docs/superpowers/fixtures/… and its repo-relative
    path is recorded in the project's truth.json `pdf_path` (ground_truth dirs
    hold no PDFs of their own)."""
    ai = os.path.join(gt_dir, "ai_extract.json")
    truth = os.path.join(gt_dir, "truth.json")
    if not os.path.exists(ai) or not os.path.exists(truth):
        return None
    data = json.load(open(ai))
    rooms = data.get("v8_rooms") or data.get("patalpos") or []
    rooms = [r for r in rooms if r.get("nr") is not None]
    if not rooms:
        return None
    page_nr = rooms[0].get("puslapio_nr") or rooms[0].get("page_nr") or 1
    pdf_rel = (json.load(open(truth)) or {}).get("pdf_path")
    if not pdf_rel:
        return None
    pdf_abs = os.path.join(ROOT, pdf_rel)
    if not os.path.exists(pdf_abs):
        return None
    return open(pdf_abs, "rb").read(), int(page_nr), rooms

def bench(name, pdf_bytes, page_nr, rooms):
    try:
        raster = cache.render_grayscale_from_bytes(pdf_bytes, page_nr=page_nr)
    except Exception as e:
        print(f"{name:14s} SKIP (page {page_nr} render failed: {e})")
        return None
    h, w = raster.shape[:2]
    nrs = [str(r["nr"]) for r in rooms]
    plot = {str(r["nr"]): float(r.get("plotas_m2") or 0) for r in rooms}
    bbox = {str(r["nr"]): r.get("bbox_pct") for r in rooms}
    label_seeds = locate_room_seeds(pdf_bytes, page_nr - 1, nrs)
    # Per-room seeds (primary + extra), same as the endpoint; drives BOTH passes.
    seeds_by_nr = {}
    for nr in nrs:
        label = label_seeds.get(nr); bc = bbox_centroid_seed(bbox.get(nr))
        primary = label or bc
        if primary is not None:
            seeds_by_nr[nr] = (primary, [bc] if (label and bc) else [])
    samples = []
    for nr, (primary, extra) in seeds_by_nr.items():
        r0 = auto_room_polygon(raster, primary[0], primary[1], seeds_pct=extra)
        if r0 is not None and plot.get(nr):
            samples.append((cv2.contourArea(r0.polygon_px.reshape(-1, 1, 2).astype(np.int32)) / (h * w), plot[nr]))
    scale = calibrate_page_scale(samples)
    auto = manual = wrong = 0
    errs = []
    for nr in nrs:
        bc = bbox_centroid_seed(bbox.get(nr))
        seed = seeds_by_nr.get(nr)
        if seed is None:
            manual += 1; continue
        (primary, extra) = seed
        r = auto_room_polygon(raster, primary[0], primary[1], seeds_pct=extra,
                              room_plotas_m2=plot.get(nr) or None, page_scale_m2_per_pct=scale)
        if r is None:
            manual += 1; continue
        auto += 1
        if r.area_err is not None:
            errs.append(r.area_err)
        # wrong-room check: a room's bbox CENTROID (a reliable interior anchor)
        # must fall inside its detected polygon. The printed number label is a
        # callout that often sits OUTSIDE the room outline, so it is not a valid
        # test; the bbox centroid is. Only checked for rooms that carry a bbox.
        if bc and not point_in_polygon_px(r.polygon_px, bc[0] * w, bc[1] * h):
            wrong += 1
    mean_err = round(sum(errs) / len(errs), 3) if errs else None
    print(f"{name:14s} total={len(nrs):2d} auto={auto:2d} manual={manual:2d} "
          f"mean_area_err={mean_err} wrong_room_fills={wrong}")
    return {"total": len(nrs), "auto": auto, "manual": manual, "wrong": wrong, "mean_err": mean_err}

if __name__ == "__main__":
    gt_root = os.path.join(ROOT, "ground_truth")
    dirs = sorted(glob.glob(os.path.join(gt_root, "*")))
    any_run = False
    for d in dirs:
        if not os.path.isdir(d):
            continue
        loaded = load_project(d)
        if not loaded:
            print(f"{os.path.basename(d):14s} SKIP (no pdf/rooms)")
            continue
        any_run = True
        bench(os.path.basename(d), *loaded)
    if not any_run:
        print("No ground-truth projects with pdf+rooms found.")
