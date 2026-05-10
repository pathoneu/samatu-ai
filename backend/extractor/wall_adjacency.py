"""Sprint 2: deterministic polygon adjacency graph.

Consumes per-room `polygon_pct[]` (optional Vision output, see prompt.py).
For each pair of rooms whose polygons share collinear edge segments we
compute the overlap length.

**Week 1 Task 1.4 (canonical plan, 2026-05-10):** the half-subtraction
mutation of `perimetras_m` is **disabled by default** because interior
finishing (paint, baseboard, plaster corners) needs BOTH faces of a shared
wall — each room's polygon describes that room's own inner contour, so
naive A.perim + B.perim is the correct linear footage for finishes. Only
GK partition CONSTRUCTION (not finishing) needs the deduplicated count.

Set `ENABLE_LEGACY_HALF_SUBTRACT=1` to restore the pre-2026-05-10 behavior
during migration (e.g. to A/B compare a single project against the old
output). Default is OFF in beta and production.

When the wall-faces-vs-cores graph (Week 6 Task 6.1) lands, the audit
information here moves into the new model. For now we still compute the
shared-edge metric and surface it as `shared_with_neighbors_m` per room
for debugging, but we never reduce `perimetras_m`.

Feature-flag gated: ENABLE_POLYGON_PREPASS=1 turns on the prepass at all.
When ENABLE_POLYGON_PREPASS is off or any room lacks polygon_pct, no work
happens.

Coordinates: polygon_pct is in 0..1 page-fraction space. We convert to
metric using page-level page_width_m / page_height_m supplied by caller.

References:
- Spec: docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §4.3 wall_adjacency
- Canonical plan: docs/superpowers/plans/2026-05-10-canonical-plan.md Task 1.4
- Sprint 2 risk register: spec §10 (validate against golden test PDFs)
"""
from __future__ import annotations

import os

# Floating-point epsilon for collinearity test (in 0..1 page-fraction space).
# At A3 (297×420 mm), 0.005 ≈ 1.5–2 mm — well below LT wall thickness (75–250 mm),
# so we never falsely merge real walls but still tolerate Vision rounding noise.
_COLLINEAR_EPS = 0.005

# Week 1 Task 1.4: default OFF. Set ENABLE_LEGACY_HALF_SUBTRACT=1 only as a
# rollback safety hatch. The plan's Week 6 wall-graph rewrite removes the flag
# entirely once the faces-vs-cores model is live.
_ENABLE_LEGACY_HALF_SUBTRACT = os.environ.get("ENABLE_LEGACY_HALF_SUBTRACT", "0") == "1"


Point = tuple[float, float]
Segment = tuple[Point, Point]


def polygon_to_segments(poly: list[Point]) -> list[Segment]:
    """Return closed polygon as list of segments, last one closing back to start.

    Coerces point coordinates to float defensively: Vision occasionally emits
    polygon_pct entries as JSON strings (`"0.25"`) instead of numbers, and the
    downstream arithmetic in `_segment_axis` would crash with
    `unsupported operand type(s) for -: 'str' and 'str'`. Malformed entries
    (missing axis, non-numeric, wrong shape) cause us to drop the polygon and
    return an empty segment list — `apply_shared_edges` then sees zero shared
    edges for that room and leaves its perimetras unchanged.
    """
    if not poly or len(poly) < 2:
        return []
    pts: list[Point] = []
    for p in poly:
        try:
            pts.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError, IndexError, KeyError):
            return []
    segs: list[Segment] = []
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        segs.append((a, b))
    return segs


def _segment_axis(seg: Segment) -> tuple[str, float] | None:
    """Classify segment as horizontal / vertical / diagonal. Returns (axis, anchor).

    For diagonals we compute the slope-intercept anchor 'b' in y = mx + b form;
    pairs with same (m, b) are collinear. We don't currently chase diagonals
    (LT plans are nearly all rectilinear) → return None for non-axis-aligned.
    """
    (x1, y1), (x2, y2) = seg
    if abs(x1 - x2) < _COLLINEAR_EPS:
        return ("v", (x1 + x2) / 2)
    if abs(y1 - y2) < _COLLINEAR_EPS:
        return ("h", (y1 + y2) / 2)
    return None


def segments_overlap_length(a: Segment, b: Segment) -> float:
    """Length of the collinear overlap between two axis-aligned segments.

    Returns 0 if not collinear or if axes differ.
    """
    cls_a = _segment_axis(a)
    cls_b = _segment_axis(b)
    if cls_a is None or cls_b is None:
        return 0.0
    if cls_a[0] != cls_b[0]:
        return 0.0
    if abs(cls_a[1] - cls_b[1]) > _COLLINEAR_EPS:
        return 0.0
    # Project both segments onto the moving axis (x for h, y for v) and intersect.
    if cls_a[0] == "h":
        a_lo, a_hi = sorted([a[0][0], a[1][0]])
        b_lo, b_hi = sorted([b[0][0], b[1][0]])
    else:
        a_lo, a_hi = sorted([a[0][1], a[1][1]])
        b_lo, b_hi = sorted([b[0][1], b[1][1]])
    overlap = max(0.0, min(a_hi, b_hi) - max(a_lo, b_lo))
    return overlap


def shared_edges_between(poly_a: list[Point], poly_b: list[Point]) -> float:
    """Total length of edges shared between two polygons (pct units).

    Sums collinear overlaps between every segment pair from A × B.
    """
    if not poly_a or not poly_b:
        return 0.0
    segs_a = polygon_to_segments(poly_a)
    segs_b = polygon_to_segments(poly_b)
    total = 0.0
    for sa in segs_a:
        for sb in segs_b:
            total += segments_overlap_length(sa, sb)
    return total


def _shared_edge_metric_length(poly_a: list[Point], poly_b: list[Point],
                               page_width_m: float, page_height_m: float) -> float:
    """Sum collinear overlaps between A and B, each scaled to metric per its axis."""
    if not poly_a or not poly_b:
        return 0.0
    segs_a = polygon_to_segments(poly_a)
    segs_b = polygon_to_segments(poly_b)
    total_m = 0.0
    for sa in segs_a:
        for sb in segs_b:
            cls = _segment_axis(sa)
            if cls is None:
                continue
            overlap_pct = segments_overlap_length(sa, sb)
            if overlap_pct <= 0:
                continue
            # axis 'h' moves along x → scale by page_width_m
            # axis 'v' moves along y → scale by page_height_m
            scale = page_width_m if cls[0] == "h" else page_height_m
            total_m += overlap_pct * scale
    return total_m


def apply_shared_edges(rooms: list[dict], page_width_m: float,
                       page_height_m: float) -> list[dict]:
    """Compute shared-edge metric length per room from polygon_pct.

    Default behaviour (Week 1 Task 1.4, 2026-05-10): DOES NOT reduce
    `perimetras_m`. Each room's polygon already describes its own face of any
    shared wall, so the room-local perimeter is the correct length for paint,
    baseboard, and plaster-corners. We surface the shared length as
    `shared_with_neighbors_m` (audit-only) so the UI can explain what was
    detected.

    Legacy behaviour (when `ENABLE_LEGACY_HALF_SUBTRACT=1`): subtract half of
    the shared length from each room's perimetras_m — this was the pre-2026-05-10
    default but mis-counts finish quantities. Kept behind the env flag so a
    single project can be A/B-compared during migration.

    Returns a NEW list of room dicts. `perimetras_m` is never set to NaN.
    Bails out (returns rooms unchanged) if ANY room lacks polygon_pct.
    """
    if any(r.get("polygon_pct") is None for r in rooms):
        return [{**r} for r in rooms]

    # Pair-wise shared metric length
    n = len(rooms)
    shared_per_room = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            metres = _shared_edge_metric_length(
                rooms[i]["polygon_pct"], rooms[j]["polygon_pct"],
                page_width_m, page_height_m,
            )
            if metres > 0:
                shared_per_room[i] += metres / 2.0
                shared_per_room[j] += metres / 2.0

    out: list[dict] = []
    for i, r in enumerate(rooms):
        room = {**r}
        orig = float(r.get("perimetras_m") or 0.0)
        if shared_per_room[i] > 0:
            # Always expose the audit metric (full length on this room's side =
            # 2 × half-share, since shared_per_room already split 50/50).
            room["shared_with_neighbors_m"] = round(shared_per_room[i] * 2.0, 3)
            room.setdefault(
                "shared_edges_provenance",
                "polygon_adjacency_audit",
            )
            if _ENABLE_LEGACY_HALF_SUBTRACT:
                room["perimetras_m"] = max(0.0, orig - shared_per_room[i])
                room["perimetras_orig_m"] = orig
                room["perimetras_saltinis"] = "polygon_adjacency_legacy"
        out.append(room)
    return out
