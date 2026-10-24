"""What the plan DRAWS in a wall opening — a window's glazing lines or a door's swing arc — read from the
PDF's vector objects (€0, pdfplumber), so the doors-and-windows pass knows what stands in each opening even
where the reader listed nothing (2026-09-25).

What the corpus sheets taught (objektas_h, objektas_a, looked at by eye and by object dump):
  · a WINDOW in plan is the opening with two or three thin parallel lines running along it INSIDE the wall
    band (the frame) and a short post at each end; the wall faces are drawn across the opening as well (the
    sill), but those lie ON the band's edges, never inside it;
  · a DOOR is a leaf and a quarter arc — the swing. Sheets differ in how the arc is stored: one CAD export
    writes the dashed arc as dozens of separate hairline pieces (objektas_h), another as one bezier curve
    (objektas_a). Both are read: the pieces are chained by touching ends and a circle is fitted to the
    chain; a curve is flattened and fitted the same way. Radius = the leaf, 0,45–1,6 m; a quarter to a
    half of a circle — a full circle is a table or a lamp;
  · a door may be drawn where the wall solid is NOT cut (objektas_h's terrace door: leaf and arc outside a
    continuous wall) — the walls reader sees no gap there, the arc still says „door". Such a door is
    returned as an opening of its own (`be_tarpo`), hinge on the room's outline, width = the swing radius.

Nothing here decides quantities: it labels openings `nupiesta = "langas" | "durys"` and the pass in
universal_rules stands the counted units by that label (or adds what the drawing shows and nobody listed).
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

LEAF_M = (0.45, 1.6)           # a door leaf = the swing's radius
ARC_SPAN_DEG = (60.0, 200.0)   # one leaf swings a quarter, a two-way leaf a half; a full circle is furniture
SINGLE_LEAF_SPAN_DEG = 125.0   # only a single leaf's arc says where a door stands when the wall is not cut
DASH_MAX_PT = 4.0              # a dash of a dashed arc
DASH_GAP_PT = 3.0              # …and how far the next one may start
DASH_MIN_PT = 0.5              # a piece shorter than this has no direction and links no chain
DASH_TURN_CAP_DEG = 45.0       # …and the direction never turns more than this between two dashes of one arc
MIN_DASHES = 6
TRIM_ROUNDS = 3                # a chain that fits no circle: dashes off the circle are set aside this many times…
TRIM_KEEP = 0.75               # …while the arc keeps this share of the chain's dashes
FIT_TOL_PT = 0.6               # the circle fit's worst residual (or 3 % of the radius)
MIN_ANGLE_BINS = 5             # points spread over at least this many 10° bins — not one dash cluster
GLAZING_MIN_LINES = 2
GLAZING_MIN_COVER = 0.55       # a glazing line runs at least this much of the opening
GLAZING_INSET_PT = 0.5         # …strictly inside the band: the sill lines lie on its edges
PARALLEL_DEG = 8.0
HINGE_TOL_M = 0.3              # the arc's centre against the wall end (it sits on the face, the end on the axis)
LEAF_VS_OPENING = (0.6, 1.2)   # one leaf against the opening's width
HALF_LEAF_VS_OPENING = (0.33, 0.62)  # one of two leaves
WALL_PROBE_MAX_M = 1.2         # how thick a wall may be before an arc beside it is not a door through it
GRID_PT = 24.0


@dataclass
class Arc:
    cx: float
    cy: float
    r: float
    a0: float          # degrees, the covering arc starts here…
    span: float        # …and runs this far counter-clockwise (page frame, y down)
    n: int
    source: str        # "dash" | "curve"

    def point(self, deg: float) -> tuple[float, float]:
        a = math.radians(deg)
        return self.cx + self.r * math.cos(a), self.cy + self.r * math.sin(a)

    def ends(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return self.point(self.a0), self.point(self.a0 + self.span)

    def mid(self) -> tuple[float, float]:
        return self.point(self.a0 + self.span / 2)


@dataclass
class PageMarks:
    W: float
    H: float
    arcs: list[Arc]
    lines: list[tuple[tuple[float, float], tuple[float, float]]]
    _grid: dict = field(default_factory=dict, repr=False)

    def index(self) -> None:
        self._grid = {}
        for k, (a, b) in enumerate(self.lines):
            for cell in _cells(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])):
                self._grid.setdefault(cell, []).append(k)

    def lines_near(self, x0: float, y0: float, x1: float, y1: float):
        seen: set[int] = set()
        for cell in _cells(x0, y0, x1, y1):
            for k in self._grid.get(cell, ()):
                if k not in seen:
                    seen.add(k)
                    yield self.lines[k]


def _cells(x0: float, y0: float, x1: float, y1: float):
    for cx in range(int(x0 // GRID_PT), int(x1 // GRID_PT) + 1):
        for cy in range(int(y0 // GRID_PT), int(y1 // GRID_PT) + 1):
            yield (cx, cy)


# ---------------------------------------------------------------- reading the page

def page_marks(pdf_bytes: bytes, page_no: int, m_per_pt: float) -> PageMarks | None:
    """The swing arcs and the line segments of one sheet (page frame: points, y down — the frame the
    walls reader and every `line_pct` use). None when the sheet has no vector content or cannot be read."""
    if not m_per_pt or m_per_pt <= 0:
        return None
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_no < 1 or page_no > len(pdf.pages):
                return None
            page = pdf.pages[page_no - 1]
            W, H = float(page.width), float(page.height)
            lines = list(page.lines)
            curves = list(page.curves)
            rects = list(page.rects)
    except Exception:  # noqa: BLE001 — a sheet that cannot be read has no marks
        return None
    if not lines and not curves:
        return None
    r_lo, r_hi = LEAF_M[0] / m_per_pt, LEAF_M[1] / m_per_pt
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    pieces: list[tuple[tuple[float, float], tuple[float, float], object]] = []   # (end, end, colour key)
    for ln in lines:
        pts = ln.get("pts") or []
        if len(pts) < 2:
            continue
        a, b = (float(pts[0][0]), float(pts[0][1])), (float(pts[-1][0]), float(pts[-1][1]))
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0:
            continue
        segs.append((a, b))
        if L <= DASH_MAX_PT:
            pieces.append((a, b, _colour(ln)))
    for rc in rects:
        w, h = float(rc.get("width") or 0), float(rc.get("height") or 0)
        if min(w, h) <= 2.0 and max(w, h) >= 6.0:              # a thin filled bar: a leaf, a post — one segment
            x0, top = float(rc["x0"]), float(rc["top"])
            if w >= h:
                segs.append(((x0, top + h / 2), (x0 + w, top + h / 2)))
            else:
                segs.append(((x0 + w / 2, top), (x0 + w / 2, top + h)))
    arcs: list[Arc] = []
    for cv in curves:
        if cv.get("fill"):
            continue
        pts = _flatten(cv)
        if len(pts) < 2:
            continue
        ext = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
        if ext <= DASH_MAX_PT:
            pieces.append((pts[0], pts[-1], _colour(cv)))
            continue
        if len(pts) >= 5 and 0.5 * r_lo <= ext <= 2.2 * r_hi:
            arc = _fit_arc(pts, r_lo, r_hi, "curve")
            if arc is not None:
                arcs.append(arc)
    arcs.extend(_arcs_from_dashes(pieces, r_lo, r_hi))
    arcs = _dedupe_arcs(arcs)
    marks = PageMarks(W=W, H=H, arcs=arcs, lines=segs)
    marks.index()
    return marks


def _colour(obj) -> object:
    c = obj.get("stroking_color")
    if isinstance(c, (list, tuple)):
        return tuple(round(float(v), 2) for v in c)
    return c


def _flatten(curve) -> list[tuple[float, float]]:
    """The points along a curve object — a cubic bezier sampled, a polyline as is (page frame, y down)."""
    path = curve.get("path")
    out: list[tuple[float, float]] = []
    if path:
        cur = None
        for op, *pts in path:
            pts = [(float(p[0]), float(p[1])) for p in pts]
            if op == "m" and pts:
                cur = pts[0]
                out.append(cur)
            elif op == "l" and pts:
                cur = pts[-1]
                out.append(cur)
            elif op in ("c", "v", "y") and pts and cur is not None:
                if op == "c" and len(pts) >= 3:
                    p1, p2, p3 = pts[0], pts[1], pts[2]
                elif op == "v" and len(pts) >= 2:
                    p1, p2, p3 = cur, pts[0], pts[1]
                elif op == "y" and len(pts) >= 2:
                    p1, p2, p3 = pts[0], pts[1], pts[1]
                else:
                    continue
                for k in range(1, 9):
                    t = k / 8.0
                    mt = 1 - t
                    out.append((mt ** 3 * cur[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                                mt ** 3 * cur[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
                cur = p3
        if out:
            return out
    return [(float(p[0]), float(p[1])) for p in (curve.get("pts") or [])]


def _turn_max_deg(r_lo: float) -> float:
    """How far the direction may turn from one dash to the next along a swing arc. Consecutive dashes of an arc
    of radius r stand at most (dash + gap) apart along it, so their directions differ by at most
    (DASH_MAX_PT + DASH_GAP_PT) / r radians — largest at the smallest leaf radius. Half as much again covers
    the direction noise of a piece a point or two long. A sharper turn is not the same arc: a dashed threshold
    or a badge box whose corner touches the arc's end (objektas_i, 2026-10-24: every swing arc chained into
    the dashed threshold rectangle beside it, and no circle fitted the chain — 0 doors on the sheet)."""
    if r_lo <= 0:
        return DASH_TURN_CAP_DEG
    return min(DASH_TURN_CAP_DEG, 1.5 * math.degrees((DASH_MAX_PT + DASH_GAP_PT) / r_lo))


def _direction_deg(a, b) -> float | None:
    """The undirected direction of a piece (0–180°), None when it is too short to have one."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if math.hypot(dx, dy) < DASH_MIN_PT:
        return None
    return math.degrees(math.atan2(dy, dx)) % 180.0


def _arcs_from_dashes(pieces, r_lo: float, r_hi: float) -> list[Arc]:
    """Dashed arcs stored as separate hairline pieces: chain pieces whose ends touch (same colour) and whose
    directions turn no more than an arc's dashes can (`_turn_max_deg`), fit a circle to every chain long
    enough. A piece too short to have a direction (a speck of a dash pattern) joins no chain."""
    if len(pieces) < MIN_DASHES:
        return []
    dirs = [_direction_deg(a, b) for a, b, _ in pieces]
    turn_max = _turn_max_deg(r_lo)

    def compatible(i: int, j: int) -> bool:
        if dirs[i] is None or dirs[j] is None:
            return False
        d = abs(dirs[i] - dirs[j]) % 180.0
        return min(d, 180.0 - d) <= turn_max
    grid: dict[tuple[int, int], list[int]] = {}
    cell = DASH_GAP_PT + 1.0
    for k, (a, b, _) in enumerate(pieces):
        for p in (a, b):
            grid.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(k)
    parent = list(range(len(pieces)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for k, (a, b, col) in enumerate(pieces):
        for p in (a, b):
            cx, cy = int(p[0] // cell), int(p[1] // cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((cx + dx, cy + dy), ()):
                        if j == k or pieces[j][2] != col or not compatible(k, j):
                            continue
                        if any(math.hypot(p[0] - q[0], p[1] - q[1]) <= DASH_GAP_PT for q in pieces[j][:2]):
                            ri, rj = find(k), find(j)
                            if ri != rj:
                                parent[ri] = rj
    chains: dict[int, list[int]] = {}
    for k in range(len(pieces)):
        chains.setdefault(find(k), []).append(k)
    out = []
    for idxs in chains.values():
        if len(idxs) < MIN_DASHES:
            continue
        arc = _fit_dash_chain([pieces[i][:2] for i in idxs], r_lo, r_hi)
        if arc is not None:
            out.append(arc)
    return out


def _circle(pts):
    """(cx, cy, r) of the algebraic least-squares circle through the points, or None."""
    n = len(pts)
    sx = sy = sxx = syy = sxy = sxz = syz = sz = 0.0
    for x, y in pts:
        z = x * x + y * y
        sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; sxz += x * z; syz += y * z; sz += z
    sol = _solve3([[2 * sxx, 2 * sxy, sx], [2 * sxy, 2 * syy, sy], [2 * sx, 2 * sy, float(n)]], [sxz, syz, sz])
    if sol is None:
        return None
    cx, cy, c = sol
    r2 = c + cx * cx + cy * cy
    return (cx, cy, math.sqrt(r2)) if r2 > 0 else None


def _fit_dash_chain(segs, r_lo: float, r_hi: float) -> Arc | None:
    """A circle through a chain of dashes. The whole chain first; when that fails, the dashes that lie off the
    best circle are set aside and the rest fitted again (at most TRIM_ROUNDS times), so long as the arc keeps
    MIN_DASHES dashes and TRIM_KEEP of the chain. A swing arc whose end touches one or two pieces of a dashed
    threshold or a box corner of the same colour (objektas_i: the bathroom door's arc ran into the threshold
    corner) is still an arc; a chain that is mostly something else is not."""
    pts = [p for s in segs for p in s]
    arc = _fit_arc(pts, r_lo, r_hi, "dash")
    if arc is not None:
        return arc
    keep = list(segs)
    for _ in range(TRIM_ROUNDS):
        c = _circle([p for s in keep for p in s])
        if c is None:
            return None
        cx, cy, r = c
        tol = max(FIT_TOL_PT, 0.03 * r)
        worst = lambda s: max(abs(math.hypot(x - cx, y - cy) - r) for x, y in s)   # noqa: E731
        trimmed = [s for s in keep if worst(s) <= tol]
        if len(trimmed) == len(keep):
            trimmed = sorted(keep, key=worst)[:-1]              # nothing within: drop the farthest and refit
        keep = trimmed
        if len(keep) < MIN_DASHES or len(keep) < TRIM_KEEP * len(segs):
            return None
        arc = _fit_arc([p for s in keep for p in s], r_lo, r_hi, "dash")
        if arc is not None:
            return arc
    return None


def _fit_arc(pts: Sequence[tuple[float, float]], r_lo: float, r_hi: float, source: str) -> Arc | None:
    """A circle through the points (algebraic least squares) if they lie on one of leaf radius over a
    quarter to a half turn."""
    n = len(pts)
    if n < 5:
        return None
    sx = sy = sxx = syy = sxy = sxz = syz = sz = 0.0
    for x, y in pts:
        z = x * x + y * y
        sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; sxz += x * z; syz += y * z; sz += z
    # normal equations of  2a·x + 2b·y + c = x² + y²
    A = [[2 * sxx, 2 * sxy, sx], [2 * sxy, 2 * syy, sy], [2 * sx, 2 * sy, float(n)]]
    B = [sxz, syz, sz]
    sol = _solve3(A, B)
    if sol is None:
        return None
    cx, cy, c = sol
    r2 = c + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    if not (r_lo <= r <= r_hi):
        return None
    if max(abs(math.hypot(x - cx, y - cy) - r) for x, y in pts) > max(FIT_TOL_PT, 0.03 * r):
        return None
    angs = sorted(math.degrees(math.atan2(y - cy, x - cx)) % 360.0 for x, y in pts)
    if len({int(a // 10) for a in angs}) < MIN_ANGLE_BINS:
        return None
    gaps = [(angs[(i + 1) % len(angs)] - angs[i]) % 360.0 for i in range(len(angs))]
    i_gap = max(range(len(gaps)), key=lambda i: gaps[i])
    span = 360.0 - gaps[i_gap]
    if not (ARC_SPAN_DEG[0] <= span <= ARC_SPAN_DEG[1]):
        return None
    a0 = angs[(i_gap + 1) % len(angs)]
    return Arc(cx=cx, cy=cy, r=r, a0=a0, span=span, n=n, source=source)


def _solve3(A, B):
    m = [row[:] + [b] for row, b in zip(A, B)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(3):
            if r != col:
                f = m[r][col] / m[col][col]
                for k in range(col, 4):
                    m[r][k] -= f * m[col][k]
    return [m[i][3] / m[i][i] for i in range(3)]


def _dedupe_arcs(arcs: list[Arc]) -> list[Arc]:
    out: list[Arc] = []
    for a in sorted(arcs, key=lambda a: -a.n):
        if any(math.hypot(a.cx - b.cx, a.cy - b.cy) < 1.5 and abs(a.r - b.r) < 1.5 for b in out):
            continue
        out.append(a)
    return out


# ---------------------------------------------------------------- what an opening carries

def opening_kind(line: Sequence[Sequence[float]], plotis_m: float, storis_m: float, marks: PageMarks | None,
                 m_per_pt: float, used: set[int] | None = None) -> tuple[str | None, int | None]:
    """(„durys" | „langas" | None, the arc's index) for one wall opening: `line` = the gap crossed along the
    wall's axis from one wall end to the other (page frame, points). A swing arc hinged at either end whose
    radius is the opening (one leaf) or about half of it (two leaves) says door; failing that, two or more
    thin lines running along the opening inside the wall band say window."""
    if marks is None or not m_per_pt:
        return None, None
    (px, py), (qx, qy) = (float(line[0][0]), float(line[0][1])), (float(line[1][0]), float(line[1][1]))
    L = math.hypot(qx - px, qy - py)
    if L <= 0:
        return None, None
    w_pt = plotis_m / m_per_pt if plotis_m else L
    tol = max(HINGE_TOL_M, 0.75 * float(storis_m or 0)) / m_per_pt
    for k, arc in enumerate(marks.arcs):
        if used is not None and k in used:
            continue
        if min(math.hypot(arc.cx - px, arc.cy - py), math.hypot(arc.cx - qx, arc.cy - qy)) > tol:
            continue
        if (LEAF_VS_OPENING[0] * w_pt <= arc.r <= LEAF_VS_OPENING[1] * w_pt
                or HALF_LEAF_VS_OPENING[0] * w_pt <= arc.r <= HALF_LEAF_VS_OPENING[1] * w_pt):
            if used is not None:
                used.add(k)
            return "durys", k
    if _glazing_lines(marks, (px, py), (qx, qy), L, float(storis_m or 0) / m_per_pt) >= GLAZING_MIN_LINES:
        return "langas", None
    return None, None


def _glazing_lines(marks: PageMarks, p, q, L: float, storis_pt: float) -> int:
    ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
    nx, ny = -uy, ux
    half = storis_pt / 2.0 if storis_pt > 0 else 2.0
    inset = half - GLAZING_INSET_PT
    if inset <= 0:
        inset = half * 0.5
    cos_par = math.cos(math.radians(PARALLEL_DEG))
    pad = half + 2.0
    x0, y0 = min(p[0], q[0]) - pad, min(p[1], q[1]) - pad
    x1, y1 = max(p[0], q[0]) + pad, max(p[1], q[1]) + pad
    found: list[tuple[float, float, float]] = []                # (offset across, from, to) along the axis
    for a, b in marks.lines_near(x0, y0, x1, y1):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < GLAZING_MIN_COVER * L:
            continue
        if abs(dx * ux + dy * uy) / ln < cos_par:
            continue                                           # not along the opening
        mx, my = (a[0] + b[0]) / 2 - p[0], (a[1] + b[1]) / 2 - p[1]
        off = mx * nx + my * ny
        if abs(off) > inset:
            continue                                           # on the band's edge (a sill line) or outside it
        along = mx * ux + my * uy
        if along < -0.15 * L or along > 1.15 * L:
            continue
        lo, hi = along - ln / 2, along + ln / 2
        if any(abs(off - o) < 0.15 and lo < h and hi > l for o, l, h in found):
            continue                                           # the same line drawn twice
        found.append((off, lo, hi))
    return len(found)


def doors_without_gap(marks: PageMarks | None, used: set[int], solved: dict, where: Callable, solid, m_per_pt: float,
                      existing: dict[str, list[dict]]) -> list[dict]:
    """Doors the arcs show where the walls reader recorded no gap — one record per single-leaf arc:
    {nr, plotis_m, storis_m, line, i, nupiesta, be_tarpo}. Two drawings meet here: a door beside a wall
    that is NOT cut (objektas_h's terrace door: leaf and swing outside a continuous wall) and a door in a
    gap the reader rejected (objektas_a: a leaf drawn closed in the gap). The swing's two legs tell them
    apart — one leg lies along the wall (between two wall ends, or beside a continuous wall), the other
    points into the space the door opens to. `solved` maps room nr → outline polygon (shapely), `where(pt)`
    names the space a point lies in (the walls reader's resolver), `solid` is the wall solid; `existing`
    = the openings already read per room (their `line`), so a door whose gap WAS read is not listed twice."""
    if marks is None or not solved or not m_per_pt or solid is None:
        return []
    try:
        from shapely.geometry import Point
    except Exception:  # noqa: BLE001
        return []
    inside = lambda x, y: solid.contains(Point(x, y))          # noqa: E731
    limit = WALL_PROBE_MAX_M / m_per_pt
    out: list[dict] = []
    for k, arc in enumerate(marks.arcs):
        if k in used or arc.span > SINGLE_LEAF_SPAN_DEG:
            continue
        hinge = (arc.cx, arc.cy)
        legs = []
        for e in arc.ends():
            ux, uy = (e[0] - hinge[0]) / arc.r, (e[1] - hinge[1]) / arc.r
            nx, ny = -uy, ux
            beside = 0
            for f in (0.2, 0.4, 0.6, 0.8):
                px, py = hinge[0] + ux * f * arc.r, hinge[1] + uy * f * arc.r
                if inside(px, py) or inside(px + nx * 2.5, py + ny * 2.5) or inside(px - nx * 2.5, py - ny * 2.5):
                    beside += 1
            near_ext = inside(hinge[0] - ux * 2.0, hinge[1] - uy * 2.0)
            far_ext = inside(e[0] + ux * 2.0, e[1] + uy * 2.0)
            legs.append({"u": (ux, uy), "beside": beside / 4.0, "gap": near_ext and far_ext})
        along = next((lg for lg in legs if lg["gap"] and lg["beside"] <= 0.25), None)      # a leaf in a gap
        style = "gap"
        if along is None:
            along = next((lg for lg in legs if lg["beside"] >= 0.75), None)                # a leaf beside a wall
            style = "beside"
        if along is None:
            continue
        perp = legs[1] if legs[0] is along else legs[0]
        ux, uy = along["u"]
        nx, ny = perp["u"]                                     # the swing side
        mid = (hinge[0] + ux * arc.r / 2, hinge[1] + uy * arc.r / 2)
        swing = where((mid[0] + nx * 3.0, mid[1] + ny * 3.0))
        swing = swing[0] if isinstance(swing, tuple) else swing
        swing_poly = solved.get(str(swing))
        if style == "gap":
            # the space beyond the gap: the first OTHER outline the probe enters, else the first point past
            # the swing room's own outline and past any wall (a traced outline runs into the doorway up to
            # the neighbour's face, and may even overlap the neighbour — objektas_a's laundry over the corridor)
            t, other = 1.0, None
            while t <= limit:
                pt = Point(mid[0] - nx * t, mid[1] - ny * t)
                hit = next((nr for nr, poly in solved.items() if nr != str(swing) and poly.contains(pt)), None)
                if hit is not None:
                    other = hit
                    break
                if inside(pt.x, pt.y) or (swing_poly is not None and swing_poly.contains(pt)):
                    t += 0.5
                    continue
                other = where((mid[0] - nx * (t + 1.0), mid[1] - ny * (t + 1.0)))
                other = other[0] if isinstance(other, tuple) else other
                break
            if other is None:
                continue
            shift = 0.0
            # the wall's thickness: across the wall at either end of the gap — the thinner reading, because
            # one end may be a T-junction with a long wall (objektas_a: the laundry's south wall)
            thick = None
            for base in ((hinge[0] - ux * 2.0, hinge[1] - uy * 2.0), (hinge[0] + ux * (arc.r + 2.0), hinge[1] + uy * (arc.r + 2.0))):
                if not inside(*base):
                    continue
                t_a = t_b = 0.0
                while t_a < limit and inside(base[0] + nx * t_a, base[1] + ny * t_a):
                    t_a += 0.5
                while t_b < limit and inside(base[0] - nx * t_b, base[1] - ny * t_b):
                    t_b += 0.5
                thick = t_a + t_b if thick is None else min(thick, t_a + t_b)
            if thick is None or thick * m_per_pt > 0.6:
                known = sorted(o["storis_m"] for nr in (str(swing),) for o in existing.get(nr, ()) if o.get("storis_m"))
                thick = (known[len(known) // 2] / m_per_pt) if known else 0.15 / m_per_pt
            thick = max(thick, 1.0)
        else:
            t = 1.0
            while t <= 3.0 and not inside(mid[0] - nx * t, mid[1] - ny * t):
                t += 0.5
            if t > 3.0:
                continue                                       # no wall right behind the leaf
            t_in = t
            while t <= limit and inside(mid[0] - nx * t, mid[1] - ny * t):
                t += 0.5
            if t > limit:
                continue                                       # too thick to be a wall a door goes through
            other = where((mid[0] - nx * (t + 2.0), mid[1] - ny * (t + 2.0)))
            other = other[0] if isinstance(other, tuple) else other
            thick = max(t - t_in, 1.0)
            shift = t_in + thick / 2
        if swing == other or (str(swing) not in solved and str(other) not in solved):
            continue
        P = (hinge[0] - nx * shift, hinge[1] - ny * shift)
        Q = (P[0] + ux * arc.r, P[1] + uy * arc.r)
        mid_line = ((P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2)
        reach = max(HINGE_TOL_M / m_per_pt, arc.r * 0.75)
        rooms = [str(swing), str(other)]
        if any(math.hypot((o["line"][0][0] + o["line"][1][0]) / 2 - mid_line[0],
                          (o["line"][0][1] + o["line"][1][1]) / 2 - mid_line[1]) <= reach
               for nr in rooms for o in existing.get(nr, ()) if o.get("line")):
            continue                                           # that gap was read — the arc belongs to it
        if any(math.hypot((o["line"][0][0] + o["line"][1][0]) / 2 - mid_line[0],
                          (o["line"][0][1] + o["line"][1][1]) / 2 - mid_line[1]) <= reach for o in out):
            continue                                           # the second leaf of a pair
        used.add(k)
        room = str(other) if str(other) in solved else str(swing)
        there = str(swing) if room == str(other) else str(other)
        out.append({"nr": room, "plotis_m": round(arc.r * m_per_pt, 2), "storis_m": round(thick * m_per_pt, 2),
                    "line": (P, Q), "i": there, "nupiesta": "durys", "be_tarpo": True})
    return out


def _wall_direction(poly, pt) -> tuple[float | None, float | None]:
    """The unit direction of the outline edge nearest `pt`."""
    coords = list(poly.exterior.coords)
    best, bd = None, None
    for a, b in zip(coords, coords[1:]):
        d = _seg_dist(pt, a, b)
        if bd is None or d < bd:
            best, bd = (a, b), d
    if best is None:
        return None, None
    (ax, ay), (bx, by) = best
    L = math.hypot(bx - ax, by - ay)
    if L <= 0:
        return None, None
    return (bx - ax) / L, (by - ay) / L


def _seg_dist(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 <= 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
    return math.hypot(p[0] - (ax + t * vx), p[1] - (ay + t * vy))
