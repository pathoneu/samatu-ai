"""Deterministic geometry constraints for assembled room plans.

Three independent operations, applied in order by ``solve``:

  1. snap_to_orthogonal — wall angles within ``tolerance_deg`` of 0/90/180/270°
     get snapped exactly. Floor plans are >99% axis-aligned in residential
     LT projects; this removes Vision angle jitter.
  2. enforce_parallel_walls — within a single room, pairs of walls whose
     directions match (modulo 180°) and whose lengths differ by less than
     ``parallel_tolerance_pct`` get averaged. This eliminates the ±2-3%
     left/right wall asymmetry that comes from independent dimension reads.
  3. close_polygon — after the above, walk the room's wall cycle from the
     start vertex; if the implied final vertex doesn't land back on the start,
     distribute the closure gap proportionally across the wall lengths (each
     wall's length is scaled by (1 + correction/total_length × axis_share)).

Each step is pure: it returns a new list/dict without mutating the input.

The expected input is a ``Plan`` dict with shape:

    {
      "rooms": [
        {
          "id": "r1", "nr": "101", "polygon_walls": ["w1","w2","w3","w4"],
          "wall_lengths_mm": {"w1": 3150, "w2": 4250, "w3": 3150, "w4": 4250},
          "wall_angles_deg": {"w1": 0,    "w2": 90,   "w3": 180,  "w4": 270},
          "start_vertex_xy_mm": [0.0, 0.0],
        }
      ]
    }

This matches what ``plan_assembler.assemble_plan`` produces (modulo extra
fields it keeps).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

DEFAULT_ANGLE_TOLERANCE_DEG = 2.0
DEFAULT_PARALLEL_TOLERANCE_PCT = 1.0
DEFAULT_CLOSURE_MAX_MM = 200.0


# ── 1. Orthogonal snap ────────────────────────────────────────────────────────
def snap_to_orthogonal(
    angle_deg: float,
    tolerance_deg: float = DEFAULT_ANGLE_TOLERANCE_DEG,
) -> float:
    """Snap an angle to {0, 90, 180, 270} if within tolerance, else passthrough.

    The input angle is normalised to [0, 360). The wrap-around at 360 is handled
    by also checking against 360 (i.e. 359.5° snaps to 0).
    """
    a = angle_deg % 360.0
    targets = (0.0, 90.0, 180.0, 270.0, 360.0)
    for t in targets:
        if abs(a - t) <= tolerance_deg:
            return t % 360.0
    return a


def snap_room_walls_to_orthogonal(
    wall_angles_deg: dict[str, float],
    tolerance_deg: float = DEFAULT_ANGLE_TOLERANCE_DEG,
) -> dict[str, float]:
    """Apply ``snap_to_orthogonal`` to every wall in a per-room angle dict."""
    return {wid: snap_to_orthogonal(a, tolerance_deg) for wid, a in wall_angles_deg.items()}


# ── 2. Parallel wall length averaging ─────────────────────────────────────────
def _direction_key(angle_deg: float) -> float:
    """Two walls are 'parallel' when their angles match mod 180°. Reduce to [0,180)."""
    return angle_deg % 180.0


def enforce_parallel_walls(
    wall_lengths_mm: dict[str, float],
    wall_angles_deg: dict[str, float],
    tolerance_pct: float = DEFAULT_PARALLEL_TOLERANCE_PCT,
) -> dict[str, float]:
    """Within a room, average lengths of pairs of walls with parallel angles
    whose lengths differ by less than ``tolerance_pct``.

    Strategy: group walls by direction (rounded mod-180 angle to 1°). For
    every pair (cliques are handled by transitive averaging in a single pass:
    we average the whole group when its max/min ratio is within tolerance).
    Returns a new dict.
    """
    if not wall_lengths_mm:
        return dict(wall_lengths_mm)

    groups: dict[int, list[str]] = {}
    for wid, ang in wall_angles_deg.items():
        if wid not in wall_lengths_mm:
            continue
        key = int(round(_direction_key(ang)))
        groups.setdefault(key, []).append(wid)

    out = dict(wall_lengths_mm)
    for wids in groups.values():
        if len(wids) < 2:
            continue
        lengths = [out[w] for w in wids]
        lo, hi = min(lengths), max(lengths)
        if lo <= 0:
            continue
        spread_pct = (hi - lo) / lo * 100.0
        if spread_pct <= tolerance_pct:
            mean = sum(lengths) / len(lengths)
            for w in wids:
                out[w] = mean
    return out


# ── 3. Polygon closure ────────────────────────────────────────────────────────
@dataclass
class ClosureReport:
    gap_mm: float                       # Euclidean distance between start and computed end
    gap_xy_mm: tuple[float, float]      # signed (dx, dy)
    corrected: bool                     # True if a scale correction was applied
    correction_factor: float | None     # multiplier applied to all wall lengths
    max_adjust_pct: float | None        # equivalent max-per-wall pct change


def walk_polygon(
    polygon_walls: list[str],
    wall_lengths_mm: dict[str, float],
    wall_angles_deg: dict[str, float],
    start_xy_mm: tuple[float, float] = (0.0, 0.0),
) -> list[tuple[float, float]]:
    """Walk the polygon and return the list of vertex coordinates (mm).

    Returns N+1 points: vertex(0..N-1) plus the implied closure point.
    If the polygon truly closes, points[-1] == points[0].
    """
    x, y = start_xy_mm
    points: list[tuple[float, float]] = [(x, y)]
    for wid in polygon_walls:
        L = wall_lengths_mm.get(wid, 0.0)
        ang = math.radians(wall_angles_deg.get(wid, 0.0))
        x += L * math.cos(ang)
        y += L * math.sin(ang)
        points.append((x, y))
    return points


def close_polygon(
    polygon_walls: list[str],
    wall_lengths_mm: dict[str, float],
    wall_angles_deg: dict[str, float],
    start_xy_mm: tuple[float, float] = (0.0, 0.0),
    max_closure_mm: float = DEFAULT_CLOSURE_MAX_MM,
    max_adjust_pct: float = 2.0,
) -> tuple[dict[str, float], ClosureReport]:
    """Distribute a closure gap across wall lengths.

    For each axis (x and y) we partition the walls into positive-going and
    negative-going groups, then push both groups toward a common target =
    (pos_sum + neg_sum) / 2. Scaling each group's walls by target/group_sum
    drives ``pos_sum_new == neg_sum_new`` so the signed sum closes to zero.

    If the residual gap exceeds ``max_closure_mm`` OR the required per-wall
    correction would exceed ``max_adjust_pct``, the function returns the
    original lengths and ``corrected=False`` — the caller should treat this
    as a Vision quality issue rather than silently absorb a big gap.
    """
    pts = walk_polygon(polygon_walls, wall_lengths_mm, wall_angles_deg, start_xy_mm)
    sx, sy = pts[0]
    ex, ey = pts[-1]
    dx, dy = sx - ex, sy - ey
    gap = math.hypot(dx, dy)

    report = ClosureReport(
        gap_mm=gap,
        gap_xy_mm=(dx, dy),
        corrected=False,
        correction_factor=None,
        max_adjust_pct=None,
    )

    if gap < 1.0:                          # already closed to the millimetre
        report.corrected = True
        report.max_adjust_pct = 0.0
        return dict(wall_lengths_mm), report
    if gap > max_closure_mm:               # too far to silently absorb
        return dict(wall_lengths_mm), report

    # Partition walls into x-axis (pos/neg) and y-axis (pos/neg) groups,
    # storing magnitudes (unsigned lengths).
    pos_x: list[str] = []
    neg_x: list[str] = []
    pos_y: list[str] = []
    neg_y: list[str] = []
    for wid in polygon_walls:
        if wid not in wall_lengths_mm:
            continue
        ang_rad = math.radians(wall_angles_deg.get(wid, 0.0))
        cx, cy = math.cos(ang_rad), math.sin(ang_rad)
        if abs(cx) >= abs(cy):
            (pos_x if cx >= 0 else neg_x).append(wid)
        else:
            (pos_y if cy >= 0 else neg_y).append(wid)

    out = dict(wall_lengths_mm)
    max_pct_applied = 0.0

    def _balance(pos_ids: list[str], neg_ids: list[str]) -> float:
        nonlocal max_pct_applied
        if not pos_ids or not neg_ids:
            return 0.0
        pos_sum = sum(out[w] for w in pos_ids)
        neg_sum = sum(out[w] for w in neg_ids)
        if pos_sum <= 0 or neg_sum <= 0:
            return 0.0
        target = 0.5 * (pos_sum + neg_sum)
        if target <= 0:
            return 0.0
        f_pos = target / pos_sum
        f_neg = target / neg_sum
        pct = max(abs(f_pos - 1.0), abs(f_neg - 1.0)) * 100.0
        if max_pct_applied + pct > max_adjust_pct + max_pct_applied:
            # max_pct_applied is the running max across axes
            pass
        max_pct_applied = max(max_pct_applied, pct)
        return target, f_pos, f_neg

    # Compute correction factors but don't apply yet — first check the budget.
    plans = []
    for pos_ids, neg_ids in ((pos_x, neg_x), (pos_y, neg_y)):
        if not pos_ids or not neg_ids:
            continue
        pos_sum = sum(out[w] for w in pos_ids)
        neg_sum = sum(out[w] for w in neg_ids)
        if pos_sum <= 0 or neg_sum <= 0:
            continue
        if abs(pos_sum - neg_sum) < 1e-3:
            continue
        target = 0.5 * (pos_sum + neg_sum)
        f_pos = target / pos_sum
        f_neg = target / neg_sum
        pct = max(abs(f_pos - 1.0), abs(f_neg - 1.0)) * 100.0
        max_pct_applied = max(max_pct_applied, pct)
        plans.append((pos_ids, neg_ids, f_pos, f_neg))

    if max_pct_applied > max_adjust_pct:
        report.max_adjust_pct = max_pct_applied
        return dict(wall_lengths_mm), report

    # Apply
    for pos_ids, neg_ids, f_pos, f_neg in plans:
        for w in pos_ids:
            out[w] = out[w] * f_pos
        for w in neg_ids:
            out[w] = out[w] * f_neg

    # Verify closure
    pts2 = walk_polygon(polygon_walls, out, wall_angles_deg, start_xy_mm)
    final_gap = math.hypot(pts2[-1][0] - pts2[0][0], pts2[-1][1] - pts2[0][1])
    report.max_adjust_pct = max_pct_applied
    report.corrected = final_gap < 1.0
    if not report.corrected:
        return dict(wall_lengths_mm), report
    return out, report


# ── Top-level apply ───────────────────────────────────────────────────────────
def solve_room(
    room: dict[str, Any],
    *,
    angle_tolerance_deg: float = DEFAULT_ANGLE_TOLERANCE_DEG,
    parallel_tolerance_pct: float = DEFAULT_PARALLEL_TOLERANCE_PCT,
    closure_max_mm: float = DEFAULT_CLOSURE_MAX_MM,
) -> dict[str, Any]:
    """Apply snap → parallel-equality → polygon closure to one room.

    Returns a new room dict (does not mutate). Adds a ``_geometry_solver``
    sub-dict to the room describing what changed."""
    poly = list(room.get("polygon_walls") or [])
    angles_in = dict(room.get("wall_angles_deg") or {})
    lengths_in = dict(room.get("wall_lengths_mm") or {})
    start_xy = tuple(room.get("start_vertex_xy_mm") or (0.0, 0.0))

    angles_snapped = snap_room_walls_to_orthogonal(angles_in, angle_tolerance_deg)
    lengths_avg = enforce_parallel_walls(lengths_in, angles_snapped, parallel_tolerance_pct)
    lengths_closed, closure = close_polygon(
        poly, lengths_avg, angles_snapped, start_xy,
        max_closure_mm=closure_max_mm,
    )

    new_room = dict(room)
    new_room["wall_angles_deg"] = angles_snapped
    new_room["wall_lengths_mm"] = lengths_closed
    new_room["_geometry_solver"] = {
        "angle_snaps": sum(
            1 for k in angles_in if angles_in[k] != angles_snapped[k]
        ),
        "parallel_avg_applied": sum(
            1 for k in lengths_in if abs(lengths_in[k] - lengths_avg.get(k, 0)) > 0.5
        ),
        "closure_gap_mm_before": closure.gap_mm,
        "closure_corrected": closure.corrected,
        "closure_max_adjust_pct": closure.max_adjust_pct,
    }
    return new_room


def solve_plan(plan: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Apply ``solve_room`` to every room in the plan."""
    new_rooms = [solve_room(r, **kwargs) for r in (plan.get("rooms") or [])]
    return {**plan, "rooms": new_rooms}


# ── Adjacency detection ──────────────────────────────────────────────────────
def _segment_endpoints(
    poly_walls: list[str],
    wall_lengths_mm: dict[str, float],
    wall_angles_deg: dict[str, float],
    start_xy_mm: tuple[float, float],
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Walk the polygon and return {wall_id: (start_xy, end_xy)} in mm."""
    pts = walk_polygon(poly_walls, wall_lengths_mm, wall_angles_deg, start_xy_mm)
    out: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for i, wid in enumerate(poly_walls):
        out[wid] = (pts[i], pts[i + 1])
    return out


def _segments_overlap_collinear(
    a: tuple[tuple[float, float], tuple[float, float]],
    b: tuple[tuple[float, float], tuple[float, float]],
    tol_mm: float = 200.0,
) -> bool:
    """True iff segments a and b lie on the same axis-aligned line within
    ``tol_mm`` AND share a non-zero overlap along that line.

    Objektas A's walls are all axis-aligned (snapped by the solver). We require
    one of:
        - both horizontal (Δy < tol) and overlapping in x
        - both vertical   (Δx < tol) and overlapping in y
    """
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b
    a_horiz = abs(ay1 - ay2) <= tol_mm
    b_horiz = abs(by1 - by2) <= tol_mm
    a_vert = abs(ax1 - ax2) <= tol_mm
    b_vert = abs(bx1 - bx2) <= tol_mm

    if a_horiz and b_horiz:
        # Same horizontal line?
        if abs(((ay1 + ay2) * 0.5) - ((by1 + by2) * 0.5)) > tol_mm:
            return False
        a_lo, a_hi = sorted((ax1, ax2))
        b_lo, b_hi = sorted((bx1, bx2))
        overlap = min(a_hi, b_hi) - max(a_lo, b_lo)
        return overlap > tol_mm

    if a_vert and b_vert:
        if abs(((ax1 + ax2) * 0.5) - ((bx1 + bx2) * 0.5)) > tol_mm:
            return False
        a_lo, a_hi = sorted((ay1, ay2))
        b_lo, b_hi = sorted((by1, by2))
        overlap = min(a_hi, b_hi) - max(a_lo, b_lo)
        return overlap > tol_mm

    return False


def detect_shared_walls(
    rooms: list[dict[str, Any]],
    tol_mm: float = 200.0,
) -> dict[str, int]:
    """For each room id, count how many of its walls are shared with another room.

    Inputs are the same shape as ``solve_room``'s input:
      ``{id, polygon_walls, wall_lengths_mm, wall_angles_deg, start_vertex_xy_mm}``

    Returns ``{room_id: n_partition_walls}``.

    Each room's polygon is walked from its ``start_vertex_xy_mm``; the
    resulting absolute segment endpoints are compared between rooms. Two
    rooms share a wall when one of their wall segments is collinear AND
    overlapping with one of the other's, within ``tol_mm``. The shared
    count for each room is the number of *its own* walls touching some
    other room (so a wall shared between A and B counts as 1 for A and 1
    for B).

    When room polygons aren't yet aligned in a common coordinate frame
    (each polygon walks from (0,0)), this function returns 0 across the
    board — caller should pre-translate each room to a shared origin
    before calling. We don't infer that translation here; callers should
    supply ``start_vertex_xy_mm`` per room from the room-graph extractor's
    absolute coordinates.
    """
    # Build absolute segments per room
    room_segments: dict[str, dict[str, tuple[tuple[float, float], tuple[float, float]]]] = {}
    for r in rooms:
        rid = str(r.get("id") or r.get("nr") or "")
        if not rid:
            continue
        room_segments[rid] = _segment_endpoints(
            list(r.get("polygon_walls") or []),
            dict(r.get("wall_lengths_mm") or {}),
            dict(r.get("wall_angles_deg") or {}),
            tuple(r.get("start_vertex_xy_mm") or (0.0, 0.0)),
        )

    counts: dict[str, int] = {rid: 0 for rid in room_segments}
    ids = list(room_segments.keys())
    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1:]:
            for _wa, seg_a in room_segments[a_id].items():
                for _wb, seg_b in room_segments[b_id].items():
                    if _segments_overlap_collinear(seg_a, seg_b, tol_mm):
                        counts[a_id] += 1
                        counts[b_id] += 1
                        break  # one shared wall per room-pair per other-wall
    return counts


def attach_partition_counts(
    rooms: list[dict[str, Any]],
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    """Mutate each room dict to carry ``n_partition_walls`` so
    ``calc_room_quantities`` picks it up on the next recompute."""
    for r in rooms:
        rid = str(r.get("id") or r.get("nr") or "")
        if rid in counts:
            r["n_partition_walls"] = counts[rid]
    return rooms
