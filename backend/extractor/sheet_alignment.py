"""Which plan pages draw the same plan, and how a point on one maps onto the
base page. objektas_h (2026-09-17): page 1 (layout, with the room badges) and
page 6 (wall painting plan, with every wall's length) are the same plan at
the same scale and position — the strings of page 6 belong to the rooms of
page 1.

Signature of a sheet: the bounding box of its wall fills. Two sheets whose
boxes have the same aspect (±SIZE_TOL) are one plan; the transform onto the
base page is the size ratio (a plan re-printed at another scale) plus the
translation between the boxes. Pages with too few wall fills stay alone.
"""
from __future__ import annotations

from typing import Sequence

from shapely.ops import unary_union

from .pdf_vectors import wall_fills

SIZE_TOL = 0.015
MIN_WALLS = 3


def _signature(pdf_bytes: bytes, page: int) -> tuple[float, float, float, float] | None:
    walls = wall_fills(pdf_bytes, page)
    if len(walls) < MIN_WALLS:
        return None
    x0, y0, x1, y1 = unary_union(walls).bounds
    return (float(x0), float(y0), float(x1), float(y1))


def align_sheets(pdf_bytes: bytes, plan_pages: Sequence[int]) -> dict:
    pages = [int(p) for p in plan_pages]
    sigs = {p: _signature(pdf_bytes, p) for p in pages}
    groups: list[list[int]] = []
    transform: dict[int, dict] = {}
    for p in pages:
        s = sigs[p]
        if s is None:
            groups.append([p])
            transform[p] = {"base": p, "dx": 0.0, "dy": 0.0, "k": 1.0}
            continue
        w, h = s[2] - s[0], s[3] - s[1]
        placed = False
        for g in groups:
            b = g[0]
            bs = sigs.get(b)
            if bs is None or w <= 0 or h <= 0:
                continue
            bw, bh = bs[2] - bs[0], bs[3] - bs[1]
            kx, ky = bw / w, bh / h
            if kx > 0 and abs(kx - ky) / kx <= SIZE_TOL:
                k = (kx + ky) / 2
                # base_x = k * x + dx, so that the box corners coincide
                transform[p] = {"base": b, "k": k, "dx": bs[0] - k * s[0], "dy": bs[1] - k * s[1]}
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


def base_page(alignment: dict, page: int) -> int:
    return int(((alignment.get("transform") or {}).get(int(page)) or {}).get("base", page))
