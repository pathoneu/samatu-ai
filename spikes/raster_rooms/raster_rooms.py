"""Deterministic raster rooms — the seed of backend/geometry/raster_source.py (plan 2026-10-24 §3.1, §9).

No model. A raster plan sheet (scan, flattened PDF, render of a vector sheet) -> the room a person clicked:

  wall_mask_raster(img, px_per_m)             -> bool mask of walls: dark, low-saturation, at least a
                                                  partition thick (opening tied to the sheet scale), long
                                                  bars or rings; text, dimension lines, hatching strokes,
                                                  furniture outlines and coloured markup removed
  wall_solid(walls)                           -> the mask as shapely polygons in PIXELS (the vector lane's
                                                  "solid"), so its opening rules apply unchanged
  bridge_door_gaps(walls, px_per_m, door_max_m) -> [Bridge]: the vector lane's facing-edge rule
                                                  (backend/extractor/vector_rooms.py `_bridge_records`)
                                                  ported to pixels: two boundary edges of the solid that look
                                                  at each other across free space, overlap by no more than a
                                                  wall is thick, free space on both sides of the strip; up to
                                                  `door_max_m` any such gap, beyond it up to LONG_MAX_M only
                                                  between two wall ENDS (windows, glazed walls)
  RasterPage(img, px_per_m)                   -> per-sheet cache: walls + bridges for the door sweep
  room_at_click(page, x_px, y_px, ...)        -> the vector lane's `outline_at` decisions on the raster:
                                                  the free face under the click after bridging; door sweep
                                                  1,25 -> 1,6 m when the first leaves it open; a face that is
                                                  too small takes in a neighbouring seat-less face across a
                                                  doorless bridge only when that brings the area closer to
                                                  the table; another seat inside = "open"; touching the
                                                  sheet frame = "outside"
  snap_to_axes(polygon)                       -> wall-aligned edges (near-axis edges made exactly axis)

Pixel <-> PDF point frame and the polygon/metrics helpers are imported from spikes/sam2/sam_source.py
(`render_page`, `largest_component`, `mask_to_polygon`, `polygon_metrics`). Areas and perimeters are
shapely on the polygon; the only scale input is m per PDF point.
"""
from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sam2"))
from sam_source import PageFrame, largest_component, mask_to_polygon, polygon_metrics, render_page  # noqa: E402,F401  (render_page re-exported)

# --- the vector lane's constants (backend/extractor/vector_rooms.py), in metres --------------------------
DOOR_SWEEP_M = (1.25, 1.6)
LONG_MAX_M = 6.5
STRIP_MAX_M = 0.75
MIN_OVERLAP_M = 0.05
ANTIPARALLEL_DEG = 6.0
AREA_TOL = 0.08
MERGE_GAIN = 0.005
OPEN_FACTOR = 1.6

# --- raster-only constants ----------------------------------------------------------------------------
MIN_WALL_M = 0.07            # thinnest wall kept (GK partitions 0,075-0,10 m; objektas_a 0,08 m)
OPEN_SHARE = 0.6             # opening kernel = this share of MIN_WALL_M (a stroke thinner than that goes)
INK_DARK = 170               # a stroke's core
FILL_M = 0.06                # light fill must be at least this wide to count
DARK_MAX = 240               # light-grey wall fills (objektas_h 232, objektas_g 170) are walls
CHROMA_MAX = 0.2             # (max-min)/max above this = coloured markup (blue dimensions, red leaders, cyan radiators, pen)
HATCH_M = 0.065              # enclosed white cells up to this size² (hatch, cross-hatch, honeycomb) are filled
BAR_M = 0.25                 # a wall bar is at least this long in one of four directions
MIN_PIECE_LEN_M = 0.4        # an isolated piece shorter than this…
MIN_PIECE_AREA_M2 = 0.06     # …and smaller than this is a symbol or a text clump, not a wall
EDGE_EPS_M = 0.012           # contour simplification of the solid
MIN_EDGE_M = 0.02
KNOB_M = 0.08               # vector opening of the solid: knobs (frame stubs, ticks) narrower than this go — and so would a wall thinner than this (0,06 in sensitivity)
SNAP_DEG = 12.0              # solid edges within this of an axis are put on it
END_SIDE_M = 0.15             # a wall end: the bar runs on behind its cap at least this far, cap-wide


@dataclass
class Bridge:
    poly: Polygon                       # pixels
    gap_m: float
    thick_m: float
    sides: tuple[tuple[float, float], tuple[float, float]]
    kind: str                           # "door" (<= door limit) or "long" (between two wall ends)


def _sat_gray(img_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    mx = img_bgr.max(axis=2).astype(np.int16)
    mn = img_bgr.min(axis=2).astype(np.int16)
    return gray, (mx - mn)


def wall_mask_raster(img_bgr: np.ndarray, px_per_m: float, min_wall_m: float = MIN_WALL_M,
                     open_share: float = OPEN_SHARE, dark_max: int = DARK_MAX, sat_max_ratio: float = None,
                     bar_m: float = None, hatch_m: float = None) -> np.ndarray:
    """Walls of a raster plan sheet. The thickness band comes from the sheet scale: a stroke thinner than
    `open_share * min_wall_m` (text, dimension and leader lines, hatching strokes, furniture outlines,
    door leaves and swing arcs) is removed by a morphological opening; what survives must be a long bar
    or part of a ring (isolated short compact pieces = symbols, filled glyph clumps, are dropped)."""
    bar_m = BAR_M if bar_m is None else bar_m
    hatch_m = HATCH_M if hatch_m is None else hatch_m
    sat_max_ratio = CHROMA_MAX if sat_max_ratio is None else sat_max_ratio
    gray, chroma = _sat_gray(img_bgr)
    # coloured markup is never wall; chroma RELATIVE to brightness (JPEG-smeared red text is (67,65,135))
    # …but a DARK coloured fill (brick-red masonry hatch) is wall-capable: thin dark markup dies in the opening
    mxc = img_bgr.max(axis=2)
    grey_ok = (chroma < sat_max_ratio * np.maximum(mxc, 1)) | (mxc < 170)
    # two levels: DARK ink (< INK_DARK) is any stroke; LIGHT ink (< dark_max: light-grey wall fills) counts
    # only where it is a wide area — a line's anti-aliased halo is never FILL_M wide
    kf = max(3, int(round(FILL_M * px_per_m)))
    light = ((gray < dark_max) & grey_ok).astype(np.uint8)
    light = cv2.morphologyEx(light, cv2.MORPH_OPEN, np.ones((kf, kf), np.uint8))
    ink = (((gray < INK_DARK) & grey_ok) | light.astype(bool)).astype(np.uint8)
    # join 1-px breaks in hatch strokes, then fill the ENCLOSED small white cells: hatch, cross-hatch and
    # honeycomb cells between a wall's outlines are holes of the ink; text is not made solid by this
    # (letters are separate strokes, a filled glyph counter stays far below a bar)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    nh, hl, hs, _ = cv2.connectedComponentsWithStats(1 - ink, connectivity=4)
    small = np.zeros(nh, bool)
    small[1:] = hs[1:, cv2.CC_STAT_AREA] <= hatch_m ** 2 * px_per_m ** 2
    border = np.unique(np.concatenate([hl[0], hl[-1], hl[:, 0], hl[:, -1]]))
    small[border] = False
    closed = (ink | small[hl]).astype(np.uint8)
    k = max(2, int(round(open_share * min_wall_m * px_per_m)))
    # a wall is a BAR: at least k thick across and BAR_M long along one of four directions. Union of
    # openings with a k x L rectangle (0°, 90°) and a k-wide diagonal line (45°, 135°): dimension ticks,
    # arrow heads, digits and short glyph strokes fit none of them; wall corners and ends survive whole
    L = max(k + 2, int(round(bar_m * px_per_m)))
    opened = np.zeros_like(closed)
    for ker in (np.ones((k, L), np.uint8), np.ones((L, k), np.uint8)):
        opened |= cv2.morphologyEx(closed, cv2.MORPH_OPEN, ker)
    d = max(k + 2, int(round(L / math.sqrt(2))))
    diag = np.zeros((d, d), np.uint8)
    for i in range(d):
        diag[i, max(0, i - k // 2):min(d, i - k // 2 + k)] = 1      # a k-wide band along the diagonal
    for ker in (diag, np.fliplr(diag).copy()):
        opened |= cv2.morphologyEx(closed, cv2.MORPH_OPEN, ker)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    keep = np.zeros(n, bool)
    min_len = MIN_PIECE_LEN_M * px_per_m
    min_area = MIN_PIECE_AREA_M2 * px_per_m ** 2
    for i in range(1, n):
        w, h, a = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
        keep[i] = max(w, h) >= min_len or a >= min_area
    return keep[lab]


def wall_solid(walls: np.ndarray, px_per_m: float, eps_m: float = EDGE_EPS_M, snap_deg: float = SNAP_DEG):
    """The wall mask as one shapely (Multi)Polygon in pixel coordinates (holes kept)."""
    m = walls.astype(np.uint8)
    contours, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or hier is None:
        return None
    hier = hier[0]
    eps = max(0.8, eps_m * px_per_m)
    polys = []
    for i, c in enumerate(contours):
        if hier[i][3] >= 0:
            continue
        shell = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(shell) < 3:
            continue
        holes = []
        ch = hier[i][2]
        while ch >= 0:
            hc = cv2.approxPolyDP(contours[ch], eps, True).reshape(-1, 2)
            if len(hc) >= 3:
                holes.append(hc)
            ch = hier[ch][0]
        # pixel centres -> pixel-edge coordinates: a contour runs through the centres of the boundary
        # pixels; +0.5 keeps the solid where the pixels are (the face sits on the pixel boundary)
        # walls are drawn on the axes: a raster edge a few degrees off (stair-stepping, a chamfered
        # end cap) is snapped onto its axis, so facing edges are exactly antiparallel as in the vector solid
        if snap_deg:
            shell = _rdp_axis_snap(shell, snap_deg)
            holes = [_rdp_axis_snap(h, snap_deg) for h in holes]
        p = Polygon(shell + 0.5, [h + 0.5 for h in holes])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    solid = unary_union(polys)
    # knobs stuck on a wall (a window-frame stub, a dimension tick that fitted inside a bar) are shorter
    # than the thinnest wall is thick: a vector opening by KNOB_M removes them, walls stay
    r = KNOB_M / 2 * px_per_m
    if r >= 0.75:
        solid = solid.buffer(-r, join_style=2).buffer(r, join_style=2)
    # one-pixel steps along a face (anti-aliasing) split a wall end into two edges: simplify them away
    return solid.simplify(max(1.0, 0.012 * px_per_m))


def _polygons(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    parts = geom.geoms if hasattr(geom, "geoms") else [geom]
    return [p for p in parts if p.geom_type == "Polygon" and not p.is_empty]


def _edges(solid, min_edge_px: float, end_side_px: float = 0.0) -> list[dict]:
    """vector_rooms._edges: boundary edges with the unit normal pointing into FREE space. Raster addition:
    `end` — the edge is a wall's END CAP (its two neighbouring edges run back antiparallel, both
    roughly perpendicular to it), the only kind of edge a raster door bridge may start from."""
    out = []
    for poly in _polygons(solid):
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)[:-1]
            n = len(pts)
            segs = []
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                length = math.dist(a, b)
                segs.append((a, b, length, ((b[0] - a[0]) / length, (b[1] - a[1]) / length) if length else (0.0, 0.0)))
            for i, (a, b, length, (ux, uy)) in enumerate(segs):
                if length < min_edge_px:
                    continue
                nx, ny = uy, -ux
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if solid.contains(Point(mx + nx * 0.6, my + ny * 0.6)):
                    nx, ny = -nx, -ny
                out.append({"a": a, "b": b, "L": length, "u": (ux, uy), "n": (nx, ny), "mid": (mx, my),
                            "end": _is_end(solid, a, b, (ux, uy), (nx, ny), end_side_px) if end_side_px else False})
    return out


def _is_end(solid, a, b, u, n, depth_px: float) -> bool:
    """A wall END CAP: behind the edge (against its free-side normal) the solid runs on for `depth_px`
    no wider than the edge on at least one side — just beyond that end of the edge, behind it, is free space.
    A bump on a wall face (a notch left by a crossing dimension line, a glyph stuck to the wall) has
    wall beside it, so it is not an end. Raster replacement for the vector solid's clean wall ends."""
    L = math.dist(a, b)
    if L <= 0:
        return False
    hits = 0
    for t in (0.25, 0.5, 0.75):
        px = a[0] + (b[0] - a[0]) * t - n[0] * depth_px * 0.6
        py = a[1] + (b[1] - a[1]) * t - n[1] * depth_px * 0.6
        hits += solid.contains(Point(px, py))
    if hits < 3:
        return False
    side = max(1.5, 0.15 * L)
    free_sides = 0
    for (ex, ey), s_ in ((a, -1), (b, 1)):
        # beyond the end point along the edge (u points a->b), 40 % and 80 % of the depth behind the cap;
        # ONE free side is enough: a window jamb at a room corner has the partition attached on the other
        free_sides += all(not solid.contains(Point(ex + u[0] * s_ * side - n[0] * depth_px * d,
                                                   ey + u[1] * s_ * side - n[1] * depth_px * d)) for d in (0.4, 0.8))
    return free_sides >= 1


def _side_is_free(solid, p, q, outward, probe_px: float) -> bool:
    free = 0
    for t in (0.25, 0.5, 0.75):
        x = p[0] + (q[0] - p[0]) * t + outward[0] * probe_px
        y = p[1] + (q[1] - p[1]) * t + outward[1] * probe_px
        free += not solid.contains(Point(x, y))
    return free >= 2


def bridge_door_gaps(walls: np.ndarray, px_per_m: float, door_max_m: float = DOOR_SWEEP_M[0],
                     solid=None, edges: list[dict] | None = None, door_needs_end: bool = False) -> list[Bridge]:
    """vector_rooms._bridge_records on the raster solid (same rule, metres converted with the sheet scale).
    Covers a door between two wall ends, an end facing a face (door beside a corner), two faces (door
    between the corners of two wall boxes), and — beyond the door limit — windows and glazed walls
    between two wall ends up to LONG_MAX_M."""
    if solid is None:
        solid = wall_solid(walls, px_per_m)
    if solid is None:
        return []
    if edges is None:
        edges = _edges(solid, MIN_EDGE_M * px_per_m, END_SIDE_M * px_per_m)
    if not edges:
        return []
    m_per_px = 1.0 / px_per_m
    tree = STRtree([LineString([e["a"], e["b"]]) for e in edges])
    reach = LONG_MAX_M * px_per_m
    cos_anti = -math.cos(math.radians(ANTIPARALLEL_DEG))
    core_px = max(0.8, 0.006 * px_per_m)          # vector lane: 0,35 pt
    probe_px = max(1.5, 0.015 * px_per_m)         # vector lane: 0,7 pt
    out: list[Bridge] = []
    for i, e in enumerate(edges):
        nx, ny = e["n"]
        ux, uy = e["u"]
        for j in tree.query(LineString([e["a"], e["b"]]).buffer(reach)):
            j = int(j)
            if j <= i:
                continue
            f = edges[j]
            if nx * f["n"][0] + ny * f["n"][1] > cos_anti:
                continue
            d = (f["mid"][0] - e["mid"][0]) * nx + (f["mid"][1] - e["mid"][1]) * ny
            if d <= 1.0:
                continue
            gap_m = d * m_per_px
            if gap_m > LONG_MAX_M:
                continue
            pe = sorted((e["a"][0] * ux + e["a"][1] * uy, e["b"][0] * ux + e["b"][1] * uy))
            pf = sorted((f["a"][0] * ux + f["a"][1] * uy, f["b"][0] * ux + f["b"][1] * uy))
            lo, hi = max(pe[0], pf[0]), min(pe[1], pf[1])
            overlap_m = (hi - lo) * m_per_px
            if not (MIN_OVERLAP_M <= overlap_m <= STRIP_MAX_M):
                continue
            kind = "door"
            if gap_m <= door_max_m and door_needs_end and not (e["end"] or f["end"]):
                continue                                       # (option) a door starts at a wall END
            if gap_m > door_max_m:
                if max(e["L"], f["L"]) * m_per_px > STRIP_MAX_M or (hi - lo) < 0.6 * min(e["L"], f["L"]):
                    continue
                if not (e["end"] and f["end"]):
                    continue                                   # raster: a short edge is often a bump, not an end
                kind = "long"
            off = e["a"][0] * nx + e["a"][1] * ny
            p1 = (ux * lo + nx * off, uy * lo + ny * off)
            p2 = (ux * hi + nx * off, uy * hi + ny * off)
            p3 = (p2[0] + nx * d, p2[1] + ny * d)
            p4 = (p1[0] + nx * d, p1[1] + ny * d)
            strip = Polygon([p1, p2, p3, p4])
            if not strip.is_valid or strip.area <= 0:
                continue
            core = strip.buffer(-core_px)
            if core.is_empty or core.intersects(solid):
                continue
            if not (_side_is_free(solid, p2, p3, (ux, uy), probe_px) and _side_is_free(solid, p4, p1, (-ux, -uy), probe_px)):
                continue
            mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)      # noqa: E731
            s1, s2 = mid(p2, p3), mid(p4, p1)
            sp = 2 * probe_px
            out.append(Bridge(strip, round(gap_m, 3), round(overlap_m, 3),
                              ((s1[0] + ux * sp, s1[1] + uy * sp), (s2[0] - ux * sp, s2[1] - uy * sp)), kind))
    return out


def burn_bridges(walls: np.ndarray, bridges: Sequence[Bridge]) -> np.ndarray:
    """Walls with every bridge strip drawn in (slightly grown so no hairline channel survives)."""
    out = walls.astype(np.uint8).copy()
    for b in bridges:
        g = b.poly.buffer(0.75, join_style=2)
        for p in _polygons(g):
            cv2.fillPoly(out, [np.round(np.asarray(p.exterior.coords) - 0.5).astype(np.int32)], 1)
    return out.astype(bool)


def _rdp_axis_snap(coords: np.ndarray, tol_deg: float) -> np.ndarray:
    """Near-axis edges made exactly axis-aligned: each vertex takes x from an adjacent near-vertical edge
    and y from an adjacent near-horizontal edge (mean of that edge's two ends)."""
    n = len(coords)
    if n < 3:
        return coords
    out = coords.astype(float).copy()
    tol = math.tan(math.radians(tol_deg))
    kinds, means = [], []
    for i in range(n):
        a, b = coords[i], coords[(i + 1) % n]
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
        if dx > 0 and dy / dx <= tol:
            kinds.append("h"); means.append((a[1] + b[1]) / 2)
        elif dy > 0 and dx / dy <= tol:
            kinds.append("v"); means.append((a[0] + b[0]) / 2)
        else:
            kinds.append(None); means.append(None)
    for i in range(n):
        for e in (i - 1, i):                     # edge ending at i, edge starting at i
            k, m = kinds[e % n], means[e % n]
            if k == "h":
                out[i][1] = m
            elif k == "v":
                out[i][0] = m
    return out


def snap_to_axes(geojson: dict, tol_deg: float = 3.0) -> dict:
    p = shape(geojson)
    shell = _rdp_axis_snap(np.asarray(p.exterior.coords)[:-1], tol_deg)
    holes = [_rdp_axis_snap(np.asarray(h.coords)[:-1], tol_deg) for h in p.interiors]
    q = Polygon(shell, holes)
    if not q.is_valid:
        q = q.buffer(0)
        if q.geom_type == "MultiPolygon":
            q = max(q.geoms, key=lambda g: g.area)
    if q.is_empty or q.area < 0.9 * p.area or q.area > 1.1 * p.area:
        return geojson                           # snapping must never reshape the room
    return mapping(q)


@dataclass
class RasterPage:
    """Per-sheet preprocessing (done once, like SAM's encoder): walls, solid, edges, bridges per door limit."""
    img: np.ndarray
    frame: PageFrame
    m_per_pt: float
    min_wall_m: float = MIN_WALL_M
    open_share: float = OPEN_SHARE
    door_needs_end: bool = False
    walls: np.ndarray = field(init=False)
    prep_ms: float = field(init=False)
    _bridged: dict = field(init=False, default_factory=dict)

    def __post_init__(self):
        t = time.perf_counter()
        self.px_per_m = self.frame.px_per_pt / self.m_per_pt
        self.walls = wall_mask_raster(self.img, self.px_per_m, self.min_wall_m, self.open_share)
        self.solid = wall_solid(self.walls, self.px_per_m)
        self.edges = _edges(self.solid, MIN_EDGE_M * self.px_per_m, END_SIDE_M * self.px_per_m) if self.solid is not None else []
        for door_m in DOOR_SWEEP_M:
            self.bridged(door_m)
        self.prep_ms = (time.perf_counter() - t) * 1000

    def bridged(self, door_m: float):
        """(bridges, labels of the free faces after bridging, stats) for one door limit."""
        if door_m not in self._bridged:
            br = bridge_door_gaps(self.walls, self.px_per_m, door_m, self.solid, self.edges, self.door_needs_end) if self.solid is not None else []
            closed = burn_bridges(self.walls, br)
            free = (~closed).astype(np.uint8)
            n, lab, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
            self._bridged[door_m] = (br, lab, stats)
        return self._bridged[door_m]


def face_stroke_px(page: "RasterPage", room: np.ndarray, max_m: float = 0.03) -> float:
    """Median width of the dark outline stroke just outside a room mask: from each boundary pixel walk
    outward (4 directions) over pixels darker than INK_DARK; runs longer than `max_m` are solid dark walls
    (no separate outline) and are ignored. 0 when no outline stroke is found."""
    gray = cv2.cvtColor(page.img, cv2.COLOR_BGR2GRAY)
    dark = gray < INK_DARK
    H, W = room.shape
    lim = max(2, int(round(max_m * page.px_per_m)))
    er = cv2.erode(room.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    ys, xs = np.nonzero(room & ~er)
    if len(xs) > 4000:
        sel = np.linspace(0, len(xs) - 1, 4000).astype(int)
        ys, xs = ys[sel], xs[sel]
    runs = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx_, ny_ = xs + dx, ys + dy
        ok = (nx_ >= 0) & (nx_ < W) & (ny_ >= 0) & (ny_ < H)
        ok[ok] &= ~room[ny_[ok], nx_[ok]]
        bx, by = xs[ok], ys[ok]
        run = np.zeros(len(bx), int)
        alive = np.ones(len(bx), bool)
        for step in range(1, lim + 2):
            px_, py_ = bx + dx * step, by + dy * step
            inb = (px_ >= 0) & (px_ < W) & (py_ >= 0) & (py_ < H)
            d = np.zeros(len(bx), bool)
            d[inb] = dark[py_[inb], px_[inb]]
            alive &= d
            run += alive
        runs.append(run[(run > 0) & (run <= lim)])
    r = np.concatenate(runs) if runs else np.array([])
    if len(r) < 20:
        return 0.0
    return float(np.median(r))


def _touches_frame(stats_row, shape_hw) -> bool:
    x, y, w, h = stats_row[:4]
    H, W = shape_hw
    return x <= 0 or y <= 0 or x + w >= W or y + h >= H


def _free_seed(lab: np.ndarray, x: float, y: float, r_px: int) -> int:
    """Face label under the click; a click on ink left inside the wall mask moves to the nearest free pixel."""
    xi, yi = int(round(x)), int(round(y))
    H, W = lab.shape
    xi, yi = min(max(xi, 0), W - 1), min(max(yi, 0), H - 1)
    if lab[yi, xi] > 0:
        return int(lab[yi, xi])
    y0, y1, x0, x1 = max(0, yi - r_px), min(H, yi + r_px + 1), max(0, xi - r_px), min(W, xi + r_px + 1)
    win = lab[y0:y1, x0:x1]
    ys, xs = np.nonzero(win)
    if not len(xs):
        return 0
    i = int(np.argmin((xs + x0 - xi) ** 2 + (ys + y0 - yi) ** 2))
    return int(win[ys[i], xs[i]])


def room_at_click(page: RasterPage, x_px: float, y_px: float, table_m2: float | None = None,
                  other_seats_px: dict[str, tuple[float, float]] | None = None, eps_m: float = 0.02,
                  axis_snap: bool = True, fill_holes: bool = True, grow: bool = True,
                  stroke_comp: bool = True) -> dict:
    """The vector lane's `outline_at` on a raster sheet. -> {status, polygon (GeoJSON, PDF points),
    area_m2, perimeter_m, door_m, merged, ms}. status: ok | open (another seat inside, or > 1,6x table) |
    outside (the face reaches the sheet frame at every door limit) | no_face."""
    t = time.perf_counter()
    m_per_pt = page.m_per_pt
    px_m = page.px_per_m
    want = float(table_m2 or 0)
    seats = other_seats_px or {}
    shape_hw = page.walls.shape
    result = {"status": "outside"}
    for door_m in DOOR_SWEEP_M:
        br, lab, stats = page.bridged(door_m)
        start = _free_seed(lab, x_px, y_px, int(0.3 * px_m))
        if start == 0:
            result = {"status": "no_face"}
            continue
        if _touches_frame(stats[start], shape_hw):
            result = {"status": "outside", "mask": lab == start}
            continue
        faces = {start}
        area_px = int(stats[start, cv2.CC_STAT_AREA])
        merged = 1
        seat_face = {nr: int(lab[int(round(sy)), int(round(sx))]) for nr, (sx, sy) in seats.items()
                     if 0 <= int(round(sy)) < shape_hw[0] and 0 <= int(round(sx)) < shape_hw[1]}
        if grow and want > 0:
            # vector_rooms._match "grow": take in a seat-less neighbour across a doorless bridge while that
            # brings the area closer to the table (objektas_g 01: kitchen behind a 1,15 m opening)
            to_m2 = (1 / px_m) ** 2
            taken = set(seat_face.values())
            improved = True
            while improved:
                improved = False
                err = abs(area_px * to_m2 - want) / want
                if err <= AREA_TOL:
                    break
                best = None
                for b in br:
                    la = [int(lab[min(max(int(round(sy)), 0), shape_hw[0] - 1), min(max(int(round(sx)), 0), shape_hw[1] - 1)])
                          for sx, sy in b.sides]
                    if len(set(la)) != 2 or 0 in la:
                        continue
                    inside = [l for l in la if l in faces]
                    if len(inside) != 1:
                        continue
                    nb = la[0] if la[1] in faces else la[1]
                    if nb in taken or _touches_frame(stats[nb], shape_hw):
                        continue
                    new_area = area_px + int(stats[nb, cv2.CC_STAT_AREA]) + b.poly.area
                    new_err = abs(new_area * to_m2 - want) / want
                    if new_err < err - MERGE_GAIN and (best is None or new_err < best[0]):
                        best = (new_err, nb, b, new_area)
                if best is not None:
                    _, nb, b, new_area = best
                    faces.add(nb)
                    area_px = new_area
                    merged += 1
                    improved = True
            if merged > 1 and abs(area_px * to_m2 - want) / want > AREA_TOL:
                faces, merged = {start}, 1          # growing did not explain the table: the plain face
        mask = np.isin(lab, list(faces)).astype(np.uint8)
        if merged > 1:                              # the bridge between merged faces belongs to the room
            for b in br:
                la = {int(lab[min(max(int(round(sy)), 0), shape_hw[0] - 1), min(max(int(round(sx)), 0), shape_hw[1] - 1)])
                      for sx, sy in b.sides}
                if len(la) == 2 and la <= faces:
                    ring = np.asarray(b.poly.buffer(1, join_style=2).exterior.coords) - 0.5
                    cv2.fillPoly(mask, [np.round(ring).astype(np.int32)], 1)
        mask = mask.astype(bool)
        if fill_holes:
            mm = mask.astype(np.uint8)
            cnts, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            mm[:] = 0
            cv2.drawContours(mm, cnts, -1, 1, thickness=cv2.FILLED)
            mask = mm.astype(bool)
        comp = largest_component(mask, (x_px, y_px))
        # contours run through boundary pixel CENTRES: shift by half a pixel into the render frame and grow
        # by half a pixel so the outline sits on the pixel boundary (else every room is ~1 % small at 150 DPI)
        gj = mask_to_polygon(comp, page.frame, eps_m, m_per_pt, offset_px=(0.5, 0.5))
        if gj is None:
            result = {"status": "no_face"}
            continue
        half_pt = 0.5 * 72.0 / page.frame.dpi
        grown = shape(gj).buffer(half_pt, join_style=2)
        if grown.geom_type == "Polygon":
            gj = mapping(grown)
        raw_area = polygon_metrics(gj, m_per_pt)["area_m2"]
        stroke_px = 0.0
        if stroke_comp:
            # the wall's outline stroke sits ON the wall face (CAD draws the hatch boundary on the line's
            # centre); the mask stops at the stroke's inner edge, so the face is half a stroke further out
            stroke_px = face_stroke_px(page, comp)
            if stroke_px > 0:
                g2 = shape(gj).buffer(stroke_px / 2 * 72.0 / page.frame.dpi, join_style=2)
                if g2.geom_type == "Polygon":
                    gj = mapping(g2)
        if axis_snap:
            gj = snap_to_axes(gj)
        met = polygon_metrics(gj, m_per_pt)
        sharing = sorted(nr for nr, f in seat_face.items() if f in faces)
        status = "ok"
        if sharing or (want > 0 and met["area_m2"] > OPEN_FACTOR * want):
            status = "open"
        result = {"status": status, "polygon": gj, "area_m2": met["area_m2"], "perimeter_m": met["perimeter_m"],
                  "area_m2_raw": raw_area, "stroke_m": round(stroke_px / px_m, 4),
                  "door_m": door_m, "merged": merged, "sharing": sharing, "mask": comp}
        break
    result["ms"] = round((time.perf_counter() - t) * 1000, 1)
    return result
