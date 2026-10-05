"""Which plan pages draw the same plan, and how a point on one maps onto the
base page. objektas_h (2026-09-17): page 1 (layout, with the room badges) and
page 6 (wall painting plan, with every wall's length) are the same plan at
the same scale and position — the strings of page 6 belong to the rooms of
page 1.

Signature of a sheet: its wall fills. Two sheets are one plan when the walls
themselves coincide once one is laid over the other (SAME_WALLS of the union):
two storeys of a house share the outside walls to the millimetre, and the
strings of one floor must never be read for the rooms of the other. Ways to lay
a sheet over the base: as printed; box onto box when the boxes have the same
aspect (±SIZE_TOL — a plan re-printed at another scale); and, at the same
scale, one CORNER of the wall box onto the same corner of the base's (the plan
drawn elsewhere on its sheet while a wall piece at one edge is missing, so the
boxes differ — objektas_g, 2026-09-20). Pages with too few wall fills stay alone.

SAME_WALLS, measured on four real sets (2026-09-20): sheets of one plan overlap
≥ 0,89 once laid right — a sheet may draw a few partitions differently — and
sheets of other plans ≤ 0,55, with nothing in between.

Walls alone cannot tell TYPICAL FLOORS apart (audit 2026-09-29, geometry-lanes-3):
the 1st and the 2nd storey of a block are drawn to the millimetre alike, so
they were laid over each other as one plan — every room of one storey shared a
face with the room above it, became an „open space" with it, and got half of
the walls. The rooms' own seats say it: when the caller gives the strong seats
(a room's number badge or area label, `seats`), a sheet whose seat of one room
lands within SEAT_CLASH_PT of a seat of ANOTHER room on a sheet of the group is
another storey drawn in the same place, and is not grouped with it.
"""
from __future__ import annotations

from typing import Sequence

from shapely import affinity
from shapely.ops import unary_union

from .pdf_vectors import wall_fills

SIZE_TOL = 0.015
SAME_WALLS = 0.85           # overlap / union of the two wall solids, laid over each other
MIN_WALLS = 3
SEAT_CLASH_PT = 6.0         # two rooms' seats this close once laid over each other are one spot: two storeys

Seats = dict[int, Sequence[tuple[str, float, float]]]    # page → [(room nr, x, y)] in the page's points


def _clash(placed: Sequence[tuple[str, float, float]], others: Sequence[tuple[str, float, float]]) -> tuple[str, str] | None:
    """The first pair of DIFFERENT rooms whose seats coincide, both in the base page's frame."""
    for nr, x, y in placed:
        for onr, ox, oy in others:
            if nr != onr and abs(x - ox) <= SEAT_CLASH_PT and abs(y - oy) <= SEAT_CLASH_PT:
                return nr, onr
    return None


def _signature(pdf_bytes: bytes, page: int):
    """(bounds, solid) of the page's walls, or None."""
    walls = wall_fills(pdf_bytes, page)
    if len(walls) < MIN_WALLS:
        return None
    solid = unary_union(walls)
    x0, y0, x1, y1 = solid.bounds
    return (float(x0), float(y0), float(x1), float(y1)), solid


def _best_fit(sig, base_sig) -> tuple[float, float, float, float] | None:
    """(overlap, k, dx, dy) of the best way to lay a sheet's walls over the base's."""
    s, solid = sig
    bs, base_solid = base_sig
    w, h = s[2] - s[0], s[3] - s[1]
    if w <= 0 or h <= 0:
        return None
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
    # …or, at the same scale, one corner of the box onto the same corner of the base's
    fits += [(1.0, bs[i] - s[i], bs[j] - s[j]) for i, j in ((0, 1), (2, 1), (0, 3), (2, 3))]
    best = None
    for k, dx, dy in fits:
        laid = affinity.affine_transform(solid, [k, 0, 0, k, dx, dy])
        union = laid.union(base_solid).area
        same = laid.intersection(base_solid).area / union if union > 0 else 0.0
        if best is None or same > best[0]:
            best = (same, k, dx, dy)
    return best


def _group(order: Sequence[int], sigs: dict, seats: dict, cautious: bool) -> dict:
    """One pass over the sheets in `order`. `cautious` (a second pass, once two storeys were told apart): a
    sheet without seats whose walls are those of a group with a twin storey could be either storey — it stays
    alone rather than lend its strings to the wrong one."""
    groups: list[list[int]] = []
    transform: dict[int, dict] = {}
    storeys: list[list] = []

    def on_base(page: int) -> list[tuple[str, float, float]]:
        t = transform[page]
        return [(str(nr), t["k"] * float(x) + t["dx"], t["k"] * float(y) + t["dy"]) for nr, x, y in seats.get(page, [])]

    def alone(p: int) -> None:
        groups.append([p])
        transform[p] = {"base": p, "dx": 0.0, "dy": 0.0, "k": 1.0}

    for p in order:
        if sigs[p] is None:
            alone(p)
            continue
        placed = False
        for g in groups:
            b = g[0]
            if sigs.get(b) is None:
                continue
            best = _best_fit(sigs[p], sigs[b])
            if best is None or best[0] < SAME_WALLS:
                continue                                         # other walls: another plan, or another storey in the same box
            if seats.get(p):
                # the same walls — but is it the same storey? Another room seated on this very spot of a
                # sheet already in the group says it is the storey above or below (typical floors)
                transform[p] = {"base": b, "k": best[1], "dx": best[2], "dy": best[3]}
                hit = _clash(on_base(p), [s for q in g for s in on_base(q)])
                del transform[p]
                if hit:
                    q = next(q for q in g if any(str(s[0]) == hit[1] for s in seats.get(q, [])))
                    storeys.append([p, q, hit[0], hit[1]])
                    continue
            elif cautious and any(q in g for clash in storeys for q in clash[:2]):
                break                                            # either storey's sheet: neither is told
            transform[p] = {"base": b, "k": best[1], "dx": best[2], "dy": best[3]}
            g.append(p)
            placed = True
            break
        if not placed:
            alone(p)
    return {"groups": groups, "transform": transform, "storeys": storeys}


def align_sheets(pdf_bytes: bytes, plan_pages: Sequence[int], seats: Seats | None = None) -> dict:
    """{groups: [[page, …]], transform: {page: {base, k, dx, dy}}, storeys: [[page, other page, nr, other nr]]}.
    `seats`: the rooms' strong seats per page (module doc); `storeys` lists the sheets whose walls coincided
    but whose rooms did not. When two storeys were told apart, the sheets are grouped again with the seated
    ones first, so a sheet without seats can no longer join one storey before the other is known."""
    pages = [int(p) for p in plan_pages]
    sigs = {p: _signature(pdf_bytes, p) for p in pages}
    seats = {int(p): list(v) for p, v in (seats or {}).items() if v}
    out = _group(pages, sigs, seats, cautious=False)
    if out["storeys"]:
        out = _group([p for p in pages if seats.get(p)] + [p for p in pages if not seats.get(p)], sigs, seats, cautious=True)
    return out


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
