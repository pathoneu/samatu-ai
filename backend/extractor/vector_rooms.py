"""Room outlines from the PDF's vector walls.

Research 2026-09-17 (objektas_h): the raster flood-fill solved 4/11 rooms and
all four as fragments — furniture and hatching cut the fills. The walls
themselves are clean grey fills in the vector layer, so the outline is read
from them. What two real sheets taught (objektas_g, objektas_h, 2026-09-19):

1. SOLID = every fill of the walls' colour, MERGED. CAD exports a wall as
   triangles (objektas_h: 176 pieces); a triangle's own axis points anywhere,
   so nothing may be decided per piece. Compact fills of the wall colour
   (columns, the wall between two windows) are walls too.
2. OPENINGS are found between FACING boundary edges of the solid: two edges
   that look at each other across free space, overlap by no more than a wall
   is thick (STRIP_MAX_M) and have free space on BOTH sides of the strip
   between them (an opening leads somewhere; a short wall piece facing the
   wall across a narrow room does not). That one rule covers a door between
   two wall ends, a door beside a corner (an end facing a face), a door
   between the corners of two wall boxes (two faces, objektas_h room 11) and
   a slanted bay window. Up to the door limit any such gap is bridged; beyond it,
   up to LONG_MAX_M, only between two wall ENDS (windows, glazed walls —
   wall thickness decides nothing: objektas_h has 0,2 m outside walls).
3. FACES = free space inside the bridged solid; the one touching the frame is
   the outside.
4. A face is room `nr` when its ONE reliably located room (badge, area label)
   is `nr`. A room located only by Vision's box never blocks the face it
   lands in. Area against the table: within AREA_TOL it agrees; within
   AREA_WARN the outline is kept and `plotas_nesutampa` says so (objektas_h's
   designer moved partitions and kept the architect's areas: 4,04 m² drawn,
   4,90 m² listed); beyond that it is refused. A face that is too SMALL takes
   in neighbouring faces that have no room of their own, across a bridge,
   while that brings the area closer (objektas_g room 01: the kitchen behind
   a 1,15 m opening with no door).
5. Two or more reliably located rooms in one face is an OPEN PLAN: a group
   with the shared outline, never an invented cut line.

Everything not matched gets a reason. Coordinates: display frame (points,
origin top-left); `polygon_pct` = fractions of the page size.
"""
from __future__ import annotations

import math
from typing import Sequence

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .pdf_vectors import _is_wall_shape, dominant_wall_colour, filled_shapes, page_geometry

AREA_TOL = 0.08             # the outline agrees with the table
AREA_WARN = 0.25            # …or is kept with the disagreement shown; beyond this it is not this room
MERGE_GAIN = 0.005          # a neighbouring face is taken in only when the area gets this much closer to the table
DOOR_SWEEP_M = (1.25, 1.6)  # any facing gap this narrow is bridged; the wider limit only for rooms the first left open
LONG_MAX_M = 6.5            # …wider ones only between two wall ends
STRIP_MAX_M = 0.75          # facing edges overlap by no more than a wall is thick
MIN_OVERLAP_M = 0.05
ANTIPARALLEL_DEG = 6.0
MIN_EDGE_PT = 0.8
HAIRLINE_PT = 0.5           # ≈ 0,18 mm on paper — closes float-rounding gaps, never a door
SIMPLIFY_PT = 1.5
MAX_FILL_SHARE = 0.2        # a fill covering more of the page than this is a background, not a wall
MIN_WALLS = 3
STRONG = ("zenkliukas", "plotas_uzrasas")
UNCLOSED = "sienos neuždaro patalpos (vieta ne uždaroje erdvėje)"
SOURCE = "vektoriniai_konturai"


def _wall_solid(pdf_bytes: bytes, page: int, page_area: float):
    """(solid, number of wall-shaped pieces). Pieces that only touch are fused
    and collinear vertices dropped, so an edge of the solid is a wall face."""
    shapes = filled_shapes(pdf_bytes, page)
    colour = dominant_wall_colour(shapes)
    if colour is None:
        return None, 0
    fills = [p for c, p in shapes if c == colour and p.area < MAX_FILL_SHARE * page_area]
    n_walls = sum(1 for p in fills if _is_wall_shape(p))
    if not fills:
        return None, 0
    solid = unary_union(fills).buffer(HAIRLINE_PT / 2, join_style=2).buffer(-HAIRLINE_PT / 2, join_style=2).simplify(0.3)
    return solid, n_walls


def _polygons(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    parts = geom.geoms if hasattr(geom, "geoms") else [geom]
    return [p for p in parts if p.geom_type == "Polygon" and not p.is_empty]


def _edges(solid) -> list[dict]:
    """Boundary edges with the unit normal pointing into FREE space."""
    out = []
    for poly in _polygons(solid):
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            for a, b in zip(pts, pts[1:]):
                length = math.dist(a, b)
                if length < MIN_EDGE_PT:
                    continue
                ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
                nx, ny = uy, -ux
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if solid.contains(Point(mx + nx * 0.4, my + ny * 0.4)):
                    nx, ny = -nx, -ny
                out.append({"a": a, "b": b, "L": length, "u": (ux, uy), "n": (nx, ny), "mid": (mx, my)})
    return out


def _side_is_free(solid, p, q, outward) -> bool:
    """Is there free space just outside the strip's side p→q?"""
    free = 0
    for t in (0.25, 0.5, 0.75):
        x = p[0] + (q[0] - p[0]) * t + outward[0] * 0.7
        y = p[1] + (q[1] - p[1]) * t + outward[1] * 0.7
        free += not solid.contains(Point(x, y))
    return free >= 2


def _bridges(solid, edges: Sequence[dict], m_per_pt: float, door_max_m: float) -> list[Polygon]:
    if not edges:
        return []
    tree = STRtree([LineString([e["a"], e["b"]]) for e in edges])
    reach = LONG_MAX_M / m_per_pt
    cos_anti = -math.cos(math.radians(ANTIPARALLEL_DEG))
    out: list[Polygon] = []
    for i, e in enumerate(edges):
        nx, ny = e["n"]
        ux, uy = e["u"]
        for j in tree.query(LineString([e["a"], e["b"]]).buffer(reach)):
            j = int(j)
            if j <= i:
                continue
            f = edges[j]
            if nx * f["n"][0] + ny * f["n"][1] > cos_anti:
                continue                                       # not looking at each other
            d = (f["mid"][0] - e["mid"][0]) * nx + (f["mid"][1] - e["mid"][1]) * ny
            if d <= 0.5:
                continue                                       # f is behind e, or on it
            gap_m = d * m_per_pt
            if gap_m > LONG_MAX_M:
                continue
            pe = sorted((e["a"][0] * ux + e["a"][1] * uy, e["b"][0] * ux + e["b"][1] * uy))
            pf = sorted((f["a"][0] * ux + f["a"][1] * uy, f["b"][0] * ux + f["b"][1] * uy))
            lo, hi = max(pe[0], pf[0]), min(pe[1], pf[1])
            overlap_m = (hi - lo) * m_per_pt
            if not (MIN_OVERLAP_M <= overlap_m <= STRIP_MAX_M):
                continue
            if gap_m > door_max_m:                             # a window: two wall ENDS, mostly overlapping
                if max(e["L"], f["L"]) * m_per_pt > STRIP_MAX_M or (hi - lo) < 0.6 * min(e["L"], f["L"]):
                    continue
            off = e["a"][0] * nx + e["a"][1] * ny              # e's line, measured along its normal
            p1 = (ux * lo + nx * off, uy * lo + ny * off)
            p2 = (ux * hi + nx * off, uy * hi + ny * off)
            p3 = (p2[0] + nx * d, p2[1] + ny * d)
            p4 = (p1[0] + nx * d, p1[1] + ny * d)
            strip = Polygon([p1, p2, p3, p4])
            if not strip.is_valid or strip.area <= 0:
                continue
            core = strip.buffer(-0.35)
            if core.is_empty or core.intersects(solid):
                continue                                       # something stands in the gap
            if not (_side_is_free(solid, p2, p3, (ux, uy)) and _side_is_free(solid, p4, p1, (-ux, -uy))):
                continue                                       # closed on a side: a recess, not an opening
            out.append(strip)
    return out


def _faces(solid, bridges: Sequence[Polygon]) -> list[Polygon]:
    """Free-space faces inside the walls. The solid is grown by HAIRLINE_PT
    before the difference and each face grown back by the same amount, so
    pieces that only "touch" in floating point do not leave a hairline channel
    that joins two rooms into one face."""
    full = unary_union([solid, *bridges]).buffer(HAIRLINE_PT, join_style=2)
    x0, y0, x1, y1 = full.bounds
    frame = box(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
    rim = frame.exterior
    faces = []
    for part in _polygons(frame.difference(full)):
        if part.intersects(rim):
            continue                                           # the outside
        restored = part.buffer(HAIRLINE_PT, join_style=2)
        if restored.geom_type == "Polygon" and not restored.is_empty:
            faces.append(restored)
    return faces


def _fuse(parts: Sequence[Polygon]) -> Polygon | None:
    """Faces and the bridge between them as ONE polygon (seams of a hairline closed)."""
    merged = unary_union(list(parts)).buffer(HAIRLINE_PT * 1.5, join_style=2).buffer(-HAIRLINE_PT * 1.5, join_style=2)
    polys = _polygons(merged)
    if not polys:
        return None
    return max(polys, key=lambda p: p.area)


def _to_pct(poly: Polygon, W: float, H: float) -> list[list[float]]:
    ring = poly.simplify(SIMPLIFY_PT, preserve_topology=True).exterior
    return [[round(x / W, 5), round(y / H, 5)] for x, y in list(ring.coords)[:-1]]


def _match(solid, bridges: Sequence[Polygon], pts: dict[str, Point], strong: set[str], table_areas: dict[str, float],
           m_per_pt: float, W: float, H: float, page: int, door_m: float, solved: dict[str, Polygon]) -> tuple[dict, dict, dict, list]:
    """One pass: the faces behind these bridges, given to the rooms standing in
    them. Rooms `solved` by an earlier pass keep their outlines: they still own
    the faces they stand in, and every face inside their outline."""
    m2 = m_per_pt ** 2
    faces = _faces(solid, bridges)
    near_bridge = [[k for k, f in enumerate(faces) if f.distance(b) <= 1.0] for b in bridges]
    taken_faces = {k for k, f in enumerate(faces) if any(poly.contains(f.representative_point()) for poly in solved.values())}

    def face_of(nr: str) -> list[int]:
        """The face the room stands in — or, standing in a doorway, the faces on both sides."""
        p = pts[nr]
        for k, f in enumerate(faces):
            if f.contains(p):
                return [k]
        for b, ks in zip(bridges, near_bridge):
            if ks and b.buffer(1.0).contains(p):
                return list(ks)
        return []

    seat = {nr: face_of(nr) for nr in pts}
    owners: dict[int, list[str]] = {}
    for nr in sorted(strong):
        for k in seat[nr]:
            owners.setdefault(k, []).append(nr)
    weak_in: dict[int, list[str]] = {}
    for nr in sorted(set(pts) - strong):
        for k in seat[nr]:
            weak_in.setdefault(k, []).append(nr)

    rooms: dict[str, dict] = {}
    polygons: dict[str, Polygon] = {}
    reasons: dict[str, str] = {}
    groups: list[dict] = []

    def grow(nr: str, start: list[int]) -> tuple[Polygon, int] | None:
        """The room's polygon: its face(s), plus neighbouring faces that have
        no room of their own, one at a time, while each brings the area closer
        to the table (the best fit, not the first that passes)."""
        want = float(table_areas.get(nr) or 0)
        used = list(start)
        parts = [faces[k] for k in used] + [b for b, ks in zip(bridges, near_bridge) if len(ks) > 1 and set(ks) <= set(used)]
        poly = _fuse(parts)
        if poly is None:
            return None
        while want > 0 and poly.area * m2 < want:
            best = None
            for b, ks in zip(bridges, near_bridge):
                inside = [k for k in ks if k in used]
                outside = [k for k in ks if k not in used]
                if not inside or len(outside) != 1:
                    continue
                k = outside[0]
                if owners.get(k) or weak_in.get(k) or k in taken_faces:
                    continue                                   # that face is somebody's room
                cand = _fuse([poly, b, faces[k]])
                if cand is None:
                    continue
                err = abs(cand.area * m2 - want) / want
                if err < abs(poly.area * m2 - want) / want - MERGE_GAIN and (best is None or err < best[0]):
                    best = (err, cand, k)
            if best is None:
                break
            poly = best[1]
            used.append(best[2])
        return poly, len(used)

    def accept(nr: str, start: list[int], tol: float) -> None:
        want = float(table_areas.get(nr) or 0)
        if want <= 0:
            reasons[nr] = "lentelėje nėra ploto"
            return
        grown = grow(nr, start)
        if grown is None:
            reasons[nr] = UNCLOSED
            return
        poly, n_parts = grown
        area = poly.area * m2
        err = abs(area - want) / want
        if err > tol:
            reasons[nr] = f"nesutampa su lentele: kontūras {area:.2f} m², lentelė {want:.2f} m²"
            return
        outline = poly.simplify(SIMPLIFY_PT, preserve_topology=True)
        rooms[nr] = {"polygon_pct": _to_pct(poly, W, H), "plotas_m2": round(area, 2),
                     "perimetras_m": round(outline.exterior.length * m_per_pt, 2), "paklaida": round(err, 4),
                     "plotas_nesutampa": err > AREA_TOL, "sujungta": n_parts, "durys_m": door_m, "page": page}
        polygons[nr] = poly

    done: set[str] = set(solved)
    for nr in sorted(strong):
        if nr in done or not seat[nr]:
            continue
        ks = seat[nr]
        sharing = sorted({o for k in ks for o in owners.get(k, [])})
        if any(o in solved for o in sharing):
            reasons[nr] = f"atvira erdvė su {', '.join(o for o in sharing if o != nr)}: sienos šių patalpų neskiria"
            done.add(nr)
            continue
        if len(sharing) == 1:
            accept(nr, ks, AREA_WARN)
            done.add(nr)
            continue
        poly = _fuse([faces[k] for k in sorted({k for o in sharing for k in seat[o]})])
        done.update(sharing)
        for o in sharing:
            others = ", ".join(x for x in sharing if x != o)
            reasons[o] = f"atvira erdvė su {others}: sienos šių patalpų neskiria"
        if poly is not None:
            outline = poly.simplify(SIMPLIFY_PT, preserve_topology=True)
            groups.append({"nariai": sharing, "polygon_pct": _to_pct(poly, W, H), "plotas_m2": round(poly.area * m2, 2),
                           "perimetras_m": round(outline.exterior.length * m_per_pt, 2),
                           "lenteles_suma_m2": round(sum(float(table_areas.get(o) or 0) for o in sharing), 2), "page": page})
    for nr in sorted(set(pts) - strong - set(solved)):
        ks = seat[nr]
        if not ks:
            continue
        taken = sorted({o for k in ks for o in owners.get(k, [])} | {o for o, poly in solved.items() if poly.contains(pts[nr])})
        if taken:
            reasons[nr] = f"vieta netiksli (Vision langelis pataikė į patalpą {', '.join(taken)})"
        elif len({w for k in ks for w in weak_in.get(k, [])}) > 1:
            reasons[nr] = "vieta netiksli (keli Vision langeliai vienoje erdvėje)"
        else:
            accept(nr, ks, AREA_TOL)                           # an unreliable seat must at least agree on the area
    for nr in pts:
        if nr not in rooms and nr not in reasons and nr not in solved:
            reasons[nr] = UNCLOSED
    return rooms, polygons, reasons, groups


def trace_vector_rooms(pdf_bytes: bytes, page: int, locations: dict[str, dict], table_areas: dict[str, float],
                       m_per_pt: float, page_size: tuple[float, float] | None = None) -> dict:
    """{rooms: {nr: {polygon_pct, plotas_m2, perimetras_m, paklaida, plotas_nesutampa, sujungta, durys_m, page}},
        reasons: {nr: str},
        groups: [{nariai, polygon_pct, plotas_m2, perimetras_m, lenteles_suma_m2, page}]}

    Door limits are swept narrow to wide (one limit does not fit every
    drawing): a room solved at a narrower limit keeps that outline; the wider
    limit is for the rooms still open. More bridges only ever split faces, so
    outlines from different passes never overlap."""
    here = {str(nr): loc for nr, loc in locations.items() if int(loc.get("page", page)) == page}
    if page_size is None:
        W, H, _ = page_geometry(pdf_bytes, page)
    else:
        W, H = page_size
    solid, n_walls = _wall_solid(pdf_bytes, page, W * H)
    if solid is None or n_walls < MIN_WALLS:
        return {"rooms": {}, "reasons": {nr: "nėra vektorinių sienų" for nr in here}, "groups": []}
    pts = {nr: Point(float(loc["cx"]) * W, float(loc["cy"]) * H) for nr, loc in here.items()}
    strong = {nr for nr, loc in here.items() if loc.get("saltinis") in STRONG}
    edges = _edges(solid)
    rooms: dict[str, dict] = {}
    solved: dict[str, Polygon] = {}
    reasons: dict[str, str] = {}
    groups: list[dict] = []
    for door_m in DOOR_SWEEP_M:
        if len(rooms) == len(pts):
            break
        found, polygons, reasons, groups = _match(solid, _bridges(solid, edges, m_per_pt, door_m), pts, strong,
                                                  table_areas, m_per_pt, W, H, page, door_m, solved)
        rooms.update(found)
        solved.update(polygons)
    return {"rooms": rooms, "reasons": {nr: why for nr, why in reasons.items() if nr not in rooms}, "groups": groups}
