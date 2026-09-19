"""Which plan pages draw the same plan, and how a point on one maps onto the
base page. objektas_h (2026-09-17): page 1 (layout, with the room badges) and
page 6 (wall painting plan, with every wall's length) are the same plan at
the same scale and position — the strings of page 6 belong to the rooms of
page 1.

Signature of a sheet: its wall fills. Two sheets are one plan when the boxes
around their walls have the same aspect (±SIZE_TOL) AND the walls themselves
coincide once one is laid over the other (SAME_WALLS of the union): two
storeys of a house share the outside walls to the millimetre, and the strings
of one floor must never be read for the rooms of the other. The transform
onto the base page is the size ratio (a plan re-printed at another scale) plus
the translation between the boxes. Pages with too few wall fills stay alone.
"""
from __future__ import annotations

from typing import Sequence

from shapely import affinity
from shapely.ops import unary_union

from .pdf_vectors import wall_fills

SIZE_TOL = 0.015
SAME_WALLS = 0.9            # overlap / union of the two wall solids, laid over each other
MIN_WALLS = 3


def _signature(pdf_bytes: bytes, page: int):
    """(bounds, solid) of the page's walls, or None."""
    walls = wall_fills(pdf_bytes, page)
    if len(walls) < MIN_WALLS:
        return None
    solid = unary_union(walls)
    x0, y0, x1, y1 = solid.bounds
    return (float(x0), float(y0), float(x1), float(y1)), solid


def align_sheets(pdf_bytes: bytes, plan_pages: Sequence[int]) -> dict:
    pages = [int(p) for p in plan_pages]
    sigs = {p: _signature(pdf_bytes, p) for p in pages}
    groups: list[list[int]] = []
    transform: dict[int, dict] = {}
    for p in pages:
        if sigs[p] is None:
            groups.append([p])
            transform[p] = {"base": p, "dx": 0.0, "dy": 0.0, "k": 1.0}
            continue
        s, solid = sigs[p]
        w, h = s[2] - s[0], s[3] - s[1]
        placed = False
        for g in groups:
            b = g[0]
            if sigs.get(b) is None or w <= 0 or h <= 0:
                continue
            bs, base_solid = sigs[b]
            bw, bh = bs[2] - bs[0], bs[3] - bs[1]
            # Two ways to lay the sheet over the base: as printed (a drawing
            # set repeats the plan at the same place — and one wall piece
            # missing at the edge of a sheet moves its box, objektas_g), or box
            # onto box (a plan shifted or re-printed at another scale).
            fits = [(1.0, 0.0, 0.0)]
            kx, ky = bw / w, bh / h
            if kx > 0 and abs(kx - ky) / kx <= SIZE_TOL:
                k = (kx + ky) / 2
                fits.append((k, bs[0] - k * s[0], bs[1] - k * s[1]))     # base_x = k * x + dx: the box corners coincide
            best = None
            for k, dx, dy in fits:
                laid = affinity.affine_transform(solid, [k, 0, 0, k, dx, dy])
                union = laid.union(base_solid).area
                same = laid.intersection(base_solid).area / union if union > 0 else 0.0
                if best is None or same > best[0]:
                    best = (same, k, dx, dy)
            if best is None or best[0] < SAME_WALLS:
                continue                                         # other walls: another plan, or another storey in the same box
            transform[p] = {"base": b, "k": best[1], "dx": best[2], "dy": best[3]}
            g.append(p)
            placed = True
            break
        if not placed:
            groups.append([p])
            transform[p] = {"base": p, "dx": 0.0, "dy": 0.0, "k": 1.0}
    return {"groups": groups, "transform": transform}


def to_base(alignment: dict, page: int, x: float, y: float) -> tuple[float, float]:
    t = (alignment.get("transform") or {}).get(int(page)) or {"k": 1.0, "dx": 0.0, "dy": 0.0}
    return t["k"] * x + t["dx"], t["k"] * y + t["dy"]


def from_base(alignment: dict, page: int, x: float, y: float) -> tuple[float, float]:
    """The base page's point, on `page`."""
    t = (alignment.get("transform") or {}).get(int(page)) or {"k": 1.0, "dx": 0.0, "dy": 0.0}
    k = t["k"] or 1.0
    return (x - t["dx"]) / k, (y - t["dy"]) / k


def base_page(alignment: dict, page: int) -> int:
    return int(((alignment.get("transform") or {}).get(int(page)) or {}).get("base", page))
