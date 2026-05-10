"""Wall faces vs wall cores graph (Week 6 Task 6.1, R6 Algorithm A).

Replaces the naive collinear-segment detection in `wall_adjacency.py` with a
buffered-boundary intersection that handles:
  - Vision floating-point noise (~0.5% in pct space)
  - Wall thickness (two rooms' inner contours offset by 5-25 cm)
  - Non-rectilinear rooms (40°/45° walls)
  - Open-plan partial overlaps (flagged, not merged)
  - Self-intersecting Vision artifacts (rescued by `make_valid`)

Why not the legacy approach: each room's polygon describes its OWN inner
contour. Two rooms abutting through a 100mm wall have boundaries that are
NOT collinear — they're parallel, offset by wall thickness. Naive collinear
returns 0 shared length. Buffer-and-intersect handles this without requiring
a calibrated wall_thickness parameter.

The graph is AUDIT-ONLY for finishes — paint/baseboard/plaster corners stay
per-room. Later (Week 6+) the `cores` (deduplicated physical walls) feed
GK-partition material counts, which should NOT double-count.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
import networkx as nx

GRID_SIZE_PCT = 1e-4
DEFAULT_WALL_TOLERANCE_PCT = 0.012
MIN_SHARED_LEN_M = 0.20
SIMPLIFY_TOL_PCT = 0.001
HULL_RATIO_MIN = 0.40
OPEN_PLAN_AREA_FACTOR = 4  # tol_pct² × this → open-plan threshold


@dataclass(frozen=True)
class WallFace:
    """One side of a wall belonging to a single room."""
    room_id: str
    neighbor_id: str | None
    length_m: float
    confidence: str = "medium"


@dataclass
class WallGraph:
    graph: nx.MultiGraph
    faces: list[WallFace]
    warnings: list[str] = field(default_factory=list)


def _pct_to_m(line: LineString, w_m: float, h_m: float) -> float:
    coords = np.asarray(line.coords)
    if len(coords) < 2:
        return 0.0
    deltas = np.diff(coords, axis=0)
    return float(np.sqrt((deltas[:, 0] * w_m) ** 2 + (deltas[:, 1] * h_m) ** 2).sum())


def _segments_total_length_m(geom, w_m: float, h_m: float) -> float:
    """Sum lengths across LineString or MultiLineString-like geometry."""
    if geom is None or geom.is_empty:
        return 0.0
    if isinstance(geom, LineString):
        return _pct_to_m(geom, w_m, h_m)
    if hasattr(geom, "geoms"):
        return sum(
            _pct_to_m(g, w_m, h_m)
            for g in geom.geoms if isinstance(g, LineString)
        )
    return 0.0


def _clean(pts) -> Polygon | None:
    if not pts or len(pts) < 3:
        return None
    try:
        coords = [(float(p[0]), float(p[1])) for p in pts]
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    poly = Polygon(coords)
    poly = shapely.make_valid(poly)
    if poly.is_empty:
        return None
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    if poly.geom_type != "Polygon":
        return None
    poly = shapely.set_precision(poly, GRID_SIZE_PCT, mode="valid_output")
    poly = poly.simplify(SIMPLIFY_TOL_PCT, preserve_topology=True)
    if poly.is_empty or not poly.is_valid:
        return None
    return poly


def build_wall_graph(
    rooms: Iterable[dict],
    page_width_m: float,
    page_height_m: float,
    wall_tolerance_pct: float = DEFAULT_WALL_TOLERANCE_PCT,
) -> WallGraph:
    """Compute the wall-faces / shared-walls graph for a set of rooms.

    Each input room dict needs at least `id` and `polygon_pct`. Page metric
    extents (`page_width_m`, `page_height_m`) are used to convert pct lengths
    into metres. `wall_tolerance_pct` is the buffer width used to find
    shared walls — defaults to ~5 mm on A3 which covers Vision noise + most
    LT wall thicknesses; bump it if elevations give a calibrated thickness.
    """
    g = nx.MultiGraph()
    faces: list[WallFace] = []
    warnings: list[str] = []

    cleaned: list[tuple[str, Polygon | None]] = []
    rooms_list = list(rooms)
    for r in rooms_list:
        rid = r.get("id") or str(id(r))
        poly = _clean(r.get("polygon_pct") or [])
        if poly is None:
            warnings.append(f"room {rid}: polygon dropped (invalid)")
            cleaned.append((rid, None))
            continue
        if poly.area / max(poly.convex_hull.area, 1e-9) < HULL_RATIO_MIN:
            warnings.append(f"room {rid}: hull ratio low — possible Vision artefact")
        cleaned.append((rid, poly))
        g.add_node(rid)

    valid = [(rid, p) for rid, p in cleaned if p is not None]
    if not valid:
        return WallGraph(graph=g, faces=faces, warnings=warnings)

    bounds = [p.boundary for _, p in valid]
    fat_bounds = [b.buffer(wall_tolerance_pct, cap_style="flat") for b in bounds]
    polys_only = [p for _, p in valid]

    open_plan_threshold = (wall_tolerance_pct ** 2) * OPEN_PLAN_AREA_FACTOR

    for i in range(len(valid)):
        rid_i, poly_i = valid[i]
        for j in range(i + 1, len(valid)):
            rid_j, poly_j = valid[j]
            try:
                overlap_area = poly_i.intersection(poly_j).area
            except Exception:
                overlap_area = 0.0
            if overlap_area > open_plan_threshold:
                warnings.append(
                    f"{rid_i} ↔ {rid_j}: polygons overlap (open-plan?) — no wall edge added"
                )
                continue

            piece_i = bounds[i].intersection(fat_bounds[j])
            piece_j = bounds[j].intersection(fat_bounds[i])

            length_i = _segments_total_length_m(piece_i, page_width_m, page_height_m)
            length_j = _segments_total_length_m(piece_j, page_width_m, page_height_m)
            length_m = max(length_i, length_j)
            if length_m < MIN_SHARED_LEN_M:
                continue

            # L-shaped pairs: when the two rooms share TWO non-collinear
            # segments the intersection comes back as a MultiLineString.
            # Emit one edge per LineString component (NetworkX MultiGraph
            # tolerates parallel edges — that's why we picked it).
            segments: list[LineString] = []
            for piece in (piece_i,):
                if piece.is_empty:
                    continue
                if isinstance(piece, LineString):
                    if piece.length > 0:
                        segments.append(piece)
                elif hasattr(piece, "geoms"):
                    for sub in piece.geoms:
                        if isinstance(sub, LineString) and sub.length > 0:
                            segments.append(sub)

            if len(segments) <= 1:
                g.add_edge(
                    rid_i, rid_j,
                    length_m=round(length_m, 3),
                    confidence="medium",
                )
                faces.append(WallFace(rid_i, rid_j, round(length_m, 3)))
                faces.append(WallFace(rid_j, rid_i, round(length_m, 3)))
            else:
                # Multi-segment shared wall — keep edges per segment so
                # downstream callers see the L-shape.
                for seg in segments:
                    seg_len_m = _pct_to_m(seg, page_width_m, page_height_m)
                    if seg_len_m < MIN_SHARED_LEN_M:
                        continue
                    g.add_edge(
                        rid_i, rid_j,
                        length_m=round(seg_len_m, 3),
                        confidence="medium",
                    )
                    faces.append(WallFace(rid_i, rid_j, round(seg_len_m, 3)))
                    faces.append(WallFace(rid_j, rid_i, round(seg_len_m, 3)))

    return WallGraph(graph=g, faces=faces, warnings=warnings)
