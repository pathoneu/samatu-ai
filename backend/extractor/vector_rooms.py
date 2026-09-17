"""Room outlines from the PDF's vector walls.

Research 2026-09-17 (objektas_h): the raster flood-fill solved 4/11 rooms and
all four as fragments — furniture and hatching cut the fills. The walls
themselves are 176 clean grey polygons in the vector layer, so the outline is
read from them:

1. walls = the page's wall fills (`pdf_vectors.wall_fills`).
2. bridges: a door gap is bridged ALONG the wall — a wall end that has another
   wall end ahead of it on the same line, within DOOR_MAX_M, gets a bridge of
   the wall's own thickness (WINDOW_MAX_M for thick, exterior walls). Buffering
   every wall would also fatten them and shrink every room; this does not.
3. faces = the free space inside the walls' bounding box minus (walls ∪
   bridges); the face touching the box edge is the outside.
4. a face is room `nr` when the room's location lies inside it and its area
   matches the table area within AREA_TOL. Two locations in one face is an
   open plan: the face is cut by a straight line between the two points,
   placed where the parts match the table ratio (AREA_TOL), else refused.

Everything not matched gets a reason. Coordinates: pdfplumber frame (points,
origin top-left); `polygon_pct` = fractions of the page size.
"""
from __future__ import annotations

import math
import warnings
from typing import Sequence

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union

from .pdf_vectors import page_geometry, wall_fills

AREA_TOL = 0.05
DOOR_MAX_M = 1.25
WINDOW_MAX_M = 3.2          # gaps this long are bridged only in thick (exterior) walls
THICK_WALL_M = 0.25
COLLINEAR_TOL_DEG = 8.0
SIMPLIFY_PT = 1.5
HAIRLINE_PT = 0.5           # ≈ 0,18 mm on paper — closes float-rounding gaps, never a door
MIN_WALLS = 3
SOURCE = "vektoriniai_konturai"


def _axis(poly: Polygon) -> tuple[tuple[float, float], tuple[float, float], float]:
    """(end_a, end_b, thickness): the centreline ends of a wall piece and its
    thickness, from its minimum rotated rectangle."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        rect = poly.minimum_rotated_rectangle
    xs = list(rect.exterior.coords)[:4]
    edges = [(xs[i], xs[(i + 1) % 4]) for i in range(4)]
    lens = [math.dist(a, b) for a, b in edges]
    long_i = max(range(4), key=lambda i: lens[i])
    thick = min(lens)
    s1, s2 = edges[(long_i + 1) % 4], edges[(long_i + 3) % 4]        # the two short sides
    p = ((s1[0][0] + s1[1][0]) / 2, (s1[0][1] + s1[1][1]) / 2)
    q = ((s2[0][0] + s2[1][0]) / 2, (s2[0][1] + s2[1][1]) / 2)
    return p, q, thick


def _bridges(walls: Sequence[Polygon], m_per_pt: float) -> list[Polygon]:
    ends: list[tuple[tuple[float, float], tuple[float, float], float, int]] = []
    for i, w in enumerate(walls):
        p, q, t = _axis(w)
        ends.append((p, q, t, i))
        ends.append((q, p, t, i))                                # (end, other end, thickness, wall index)
    out: list[Polygon] = []
    cos_tol = math.cos(math.radians(COLLINEAR_TOL_DEG))
    for e, o, t, wi in ends:
        ux, uy = e[0] - o[0], e[1] - o[1]
        n = math.hypot(ux, uy)
        if n == 0:
            continue
        ux, uy = ux / n, uy / n                                  # points out of the wall end
        best = None
        for e2, o2, t2, wj in ends:
            if wj == wi:
                continue
            vx, vy = e2[0] - e[0], e2[1] - e[1]
            d = math.hypot(vx, vy)
            if d == 0:
                continue
            if (vx * ux + vy * uy) / d < cos_tol:
                continue                                         # not ahead of this end
            lateral = abs(-vx * uy + vy * ux)
            if lateral > max(t, t2):
                continue                                         # not on the same line
            gap_m = d * m_per_pt
            limit = DOOR_MAX_M if min(t, t2) * m_per_pt < THICK_WALL_M else WINDOW_MAX_M
            if gap_m <= limit and (best is None or d < best[0]):
                best = (d, e2, min(t, t2))
        if best is not None:
            out.append(LineString([e, best[1]]).buffer(best[2] / 2, cap_style=2))
    return out


def _faces(walls: Sequence[Polygon], bridges: Sequence[Polygon]) -> list[Polygon]:
    """Free-space faces inside the walls. The solid is grown by HAIRLINE_PT
    before the difference and each face grown back by the same amount: two
    wall pieces that only "touch" in floating point (a partition meeting the
    outer wall, objektas_h and the synthetic sheet alike) would otherwise
    leave a hairline channel that joins two rooms into one face."""
    solid = unary_union(list(walls) + list(bridges)).buffer(HAIRLINE_PT, join_style=2)
    x0, y0, x1, y1 = solid.bounds
    frame = box(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
    free = frame.difference(solid)
    parts = list(free.geoms) if hasattr(free, "geoms") else [free]
    rim = frame.exterior
    faces = []
    for p in parts:
        if p.geom_type != "Polygon" or p.intersects(rim):
            continue
        restored = p.buffer(HAIRLINE_PT, join_style=2)
        if restored.geom_type == "Polygon" and not restored.is_empty:
            faces.append(restored)
    return faces


def _split_two(face: Polygon, pa: Point, pb: Point, want_a: float, want_b: float, m2: float):
    """Cut `face` perpendicular to pa→pb at the offset that gives the wanted
    areas (binary search); None when no cut satisfies AREA_TOL for both."""
    ax, ay, bx, by = pa.x, pa.y, pb.x, pb.y
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0 or want_a <= 0 or want_b <= 0:
        return None
    nx, ny = -dy / length, dx / length
    span = max(face.bounds[2] - face.bounds[0], face.bounds[3] - face.bounds[1]) * 2
    lo, hi = 0.0, 1.0
    for _ in range(40):
        t = (lo + hi) / 2
        cx, cy = ax + dx * t, ay + dy * t
        cut = LineString([(cx - nx * span, cy - ny * span), (cx + nx * span, cy + ny * span)])
        parts = split(face, cut)
        part_a = next((g for g in parts.geoms if g.contains(pa)), None)
        part_b = next((g for g in parts.geoms if g.contains(pb)), None)
        if part_a is None or part_b is None or part_a is part_b:
            return None
        area_a, area_b = part_a.area * m2, part_b.area * m2
        if abs(area_a - want_a) / want_a <= AREA_TOL and abs(area_b - want_b) / want_b <= AREA_TOL:
            return part_a, part_b
        if area_a < want_a:
            lo = t
        else:
            hi = t
    return None


def _to_pct(poly: Polygon, W: float, H: float) -> list[list[float]]:
    ring = poly.simplify(SIMPLIFY_PT, preserve_topology=True).exterior
    return [[round(x / W, 5), round(y / H, 5)] for x, y in list(ring.coords)[:-1]]


def trace_vector_rooms(pdf_bytes: bytes, page: int, locations: dict[str, dict], table_areas: dict[str, float],
                       m_per_pt: float, page_size: tuple[float, float] | None = None) -> dict:
    """{rooms: {nr: {polygon_pct, plotas_m2, perimetras_m, paklaida, padalyta, page}}, reasons: {nr: str}}"""
    here = {nr: loc for nr, loc in locations.items() if int(loc.get("page", page)) == page}
    walls = wall_fills(pdf_bytes, page)
    if len(walls) < MIN_WALLS:
        return {"rooms": {}, "reasons": {nr: "nėra vektorinių sienų" for nr in here}}
    if page_size is None:
        W, H, _ = page_geometry(pdf_bytes, page)
    else:
        W, H = page_size
    m2 = m_per_pt ** 2
    faces = _faces(walls, _bridges(walls, m_per_pt))
    pts = {nr: Point(float(loc["cx"]) * W, float(loc["cy"]) * H) for nr, loc in here.items()}
    rooms: dict[str, dict] = {}
    reasons: dict[str, str] = {}

    def accept(nr: str, poly: Polygon, padalyta: bool) -> None:
        want = float(table_areas.get(nr) or 0)
        area = poly.area * m2
        if want <= 0:
            reasons[nr] = "lentelėje nėra ploto"
            return
        err = abs(area - want) / want
        if err > AREA_TOL:
            reasons[nr] = f"nesutampa su lentele: kontūras {area:.2f} m², lentelė {want:.2f} m²"
            return
        simplified = poly.simplify(SIMPLIFY_PT, preserve_topology=True)
        rooms[nr] = {"polygon_pct": _to_pct(poly, W, H), "plotas_m2": round(area, 2),
                     "perimetras_m": round(simplified.exterior.length * m_per_pt, 2),
                     "paklaida": round(err, 4), "padalyta": padalyta, "page": page}

    for face in faces:
        inside = [nr for nr, p in pts.items() if face.contains(p)]
        if len(inside) == 1:
            accept(inside[0], face, False)
        elif len(inside) == 2:
            a, b = inside
            parts = _split_two(face, pts[a], pts[b], float(table_areas.get(a) or 0), float(table_areas.get(b) or 0), m2)
            if parts is None:
                reasons[a] = reasons[b] = "atviras planas: nepavyko padalyti pagal lentelės plotus"
            else:
                accept(a, parts[0], True)
                accept(b, parts[1], True)
        elif len(inside) > 2:
            for nr in inside:
                reasons[nr] = f"atviras planas ({len(inside)} patalpos viename kontūre)"
    for nr in here:
        if nr not in rooms and nr not in reasons:
            reasons[nr] = "sienos neuždaro patalpos (vieta ne uždaroje erdvėje)"
    return {"rooms": rooms, "reasons": reasons}
