"""Server-side duplicate-fill resolution for auto room polygons.

Root cause (Beržų demo, 2026-07-12): several room-number labels are printed as
CALLOUTS in the corridor (not inside their rooms), so their flood-fill seeds
land in the same region and produce IDENTICAL polygons for different rooms
(103/108/109 shared one corridor fill; 101/104 near-identical). Filling each
room independently means nothing catches it — this post-pass does.

Rules (mirrors the viewer's honest-markers logic, but at the SOURCE so every
project's saved data is correct):
  1. Cluster traced fills whose bbox IoU ≥ DUP_IOU (transitive).
  2. In each cluster keep ONE owner — the room whose known plotas_m2 best
     matches the fill's area (via the page scale when available; else the fill
     the engine itself scored best). Losers are demoted to manual_needed —
     an honest "no geometry" beats a confidently wrong polygon.
  3. Area gate: a UNIQUE fill whose area disagrees with the room's known
     plotas_m2 by more than AREA_GATE× (either direction) is also demoted.
Demoted rooms keep their marker_pct (the printed label location is real —
it is where the drawing says the room is), so the viewer can still show an
honest Tier-2 circled number.
"""
from __future__ import annotations

DUP_IOU = 0.85
AREA_GATE = 3.0


def _bbox(poly_pct):
    xs = [p[0] for p in poly_pct]
    ys = [p[1] for p in poly_pct]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1])
    ub = (b[2] - b[0]) * (b[3] - b[1])
    union = ua + ub - inter
    return inter / union if union > 0 else 0.0


def _shoelace(poly_pct):
    a = 0.0
    n = len(poly_pct)
    for i in range(n):
        x0, y0 = poly_pct[i - 1]
        x1, y1 = poly_pct[i]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def _demote(entry):
    """Strip the polygon but keep the (real) label marker."""
    out = {"polygon_source": "manual_needed", "confidence": "manual"}
    if entry.get("marker_pct"):
        out["marker_pct"] = entry["marker_pct"]
        if entry.get("marker_source"):
            out["marker_source"] = entry["marker_source"]
    return out


def resolve_duplicate_fills(results: dict, plotas: dict, scale: float | None):
    """Demote duplicate / implausible auto fills in-place-style.

    results: {nr: entry} where traced entries carry polygon_pct (pct space)
    plotas:  {nr: known m² (float, may be 0/None)}
    scale:   page m²-per-area_pct (calibrate_page_scale) or None
    Returns (results, n_demoted).
    """
    traced = {}
    for nr, entry in results.items():
        poly = entry.get("polygon_pct")
        if entry.get("polygon_source") == "auto_floodfill" and poly and len(poly) >= 3:
            traced[nr] = {
                "bbox": _bbox(poly),
                "area": _shoelace(poly),
                "m2": float(plotas.get(nr) or 0) or None,
                "area_err": entry.get("area_err"),
            }

    demoted: set[str] = set()

    # 1-2. duplicate clusters → single owner
    groups: list[list[str]] = []
    for nr, t in traced.items():
        hit = next((g for g in groups
                    if any(_bbox_iou(traced[m]["bbox"], t["bbox"]) >= DUP_IOU for m in g)), None)
        (hit.append(nr) if hit else groups.append([nr]))
    for g in groups:
        if len(g) < 2:
            continue

        def fit_err(nr):
            t = traced[nr]
            if scale and t["m2"]:
                return abs(t["area"] * scale - t["m2"])
            # engine's own area error as tiebreak; unknown → worst
            return t["area_err"] if t["area_err"] is not None else float("inf")

        winner = min(sorted(g), key=fit_err)
        demoted.update(nr for nr in g if nr != winner)

    # 3. area gate on unique fills (grossly wrong size vs the known m²)
    if scale:
        in_group = {nr for g in groups if len(g) > 1 for nr in g}
        for nr, t in traced.items():
            if nr in in_group or not t["m2"]:
                continue
            est = t["area"] * scale
            if est > t["m2"] * AREA_GATE or est < t["m2"] / AREA_GATE:
                demoted.add(nr)

    for nr in demoted:
        results[nr] = _demote(results[nr])
    return results, len(demoted)
