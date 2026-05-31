"""Deterministic plan assembler — combines a dimension list + room graph into
a typed Plan with per-room perimeters, areas, walls, and openings.

No LLM calls. The Vision side produces only references (wall → dimension_id,
opening → schedule_ref); this module resolves them and produces numbers.

Outputs feed into ``geometry_solver.solve_plan`` for orthogonality / closure
constraints, then into ``plan_to_parsed`` for the existing formula engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

from .vision.dimension_extractor import Dimension, DimensionList
from .vision.room_graph_extractor import (
    RoomGraph, Wall, Vertex, Room as GraphRoom, Opening,
)


# ── Public types ──────────────────────────────────────────────────────────────
@dataclass
class AssembledWall:
    id: str
    length_mm: float
    angle_deg: float
    dimension_id: str | None
    is_exterior: bool
    inferred: bool = False  # True if length was recovered from polygon closure


@dataclass
class AssembledOpening:
    id: str
    wall_id: str
    type: str
    width_mm: float
    height_mm: float
    schedule_ref: str | None = None
    is_exterior: bool = False
    hidden: bool = False
    width_source: str = "dimension"   # dimension | schedule | default
    height_source: str = "dimension"


@dataclass
class AssembledRoom:
    id: str
    nr: str
    name: str
    paskirtis: str
    polygon_walls: list[str]
    wall_lengths_mm: dict[str, float]
    wall_angles_deg: dict[str, float]
    perimeter_mm: float
    area_m2: float
    openings: list[AssembledOpening] = field(default_factory=list)
    lubu_aukstis_m: float = 2.82
    lubu_aukstis_source: str = "default"
    lubu_tipas: str = "gkp"
    plyteles_sienos_aukstis_m: float = 0.0
    sienu_apdailos_breakdown: dict[str, float] = field(default_factory=dict)
    confidence_score: float = 0.0          # walls with direct dim / total walls
    confidence_color: str = "yellow"       # green | yellow | red
    missing_dimension_walls: list[str] = field(default_factory=list)
    start_vertex_xy_mm: tuple[float, float] = (0.0, 0.0)


@dataclass
class Plan:
    rooms: list[AssembledRoom] = field(default_factory=list)
    schedule_doors: dict[str, dict[str, float]] = field(default_factory=dict)
    schedule_windows: dict[str, dict[str, float]] = field(default_factory=dict)
    _meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "rooms": [asdict(r) for r in self.rooms],
            "schedule_doors": self.schedule_doors,
            "schedule_windows": self.schedule_windows,
            "_meta": self._meta,
        }
        return d


# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_DOOR_W_MM = 900
DEFAULT_DOOR_H_MM = 2100
DEFAULT_WINDOW_W_MM = 1200
DEFAULT_WINDOW_H_MM = 1500


# ── Helpers ───────────────────────────────────────────────────────────────────
def _index_dimensions(dl: DimensionList) -> dict[str, Dimension]:
    return {d.id: d for d in dl.dimensions}


def _index_walls(rg: RoomGraph) -> dict[str, Wall]:
    return {w.id: w for w in rg.walls}


def _index_vertices(rg: RoomGraph) -> dict[str, Vertex]:
    return {v.id: v for v in rg.vertices}


def _wall_angle_from_vertices(w: Wall, vmap: dict[str, Vertex]) -> float:
    """Fallback angle from vertex coords when Vision didn't emit one.

    Coordinates are in 0..1 image fractions — image Y grows downward, so we
    negate dy to get a math-convention angle (E=0°, N=90°)."""
    if w.angle_deg is not None:
        return float(w.angle_deg)
    s = vmap.get(w.start_vertex)
    e = vmap.get(w.end_vertex)
    if not s or not e:
        return 0.0
    dx = e.x_pct - s.x_pct
    dy = -(e.y_pct - s.y_pct)
    return math.degrees(math.atan2(dy, dx)) % 360.0


def _polygon_area_m2(vertices_mm: Iterable[tuple[float, float]]) -> float:
    """Shoelace area for a closed polygon (mm coords)."""
    pts = list(vertices_mm)
    if len(pts) < 3:
        return 0.0
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5 / 1_000_000.0  # mm² → m²


def _infer_missing_lengths(
    polygon_walls: list[str],
    wall_lengths_mm: dict[str, float | None],
    wall_angles_deg: dict[str, float],
) -> tuple[dict[str, float], list[str]]:
    """If exactly one or two opposite walls have no dimension, infer from closure.

    Strategy:
      - Treat all walls with a known length as constants.
      - Group missing walls by direction (rounded to 1° mod 180°).
      - For each direction, the sum of signed contributions must close to 0.
      - If the group has exactly one missing wall, we can solve directly.
      - If the group has two missing walls, we can only solve if at least
        one of them is constrained by a parallel partner of known length; we
        average that length onto both unknowns. Otherwise leave both missing.
    """
    known: dict[str, float] = {w: float(L) for w, L in wall_lengths_mm.items() if L is not None}
    missing = [w for w in polygon_walls if w not in known]
    if not missing:
        return known, []

    # Group walls (known + missing) by direction key
    def dirkey(angle: float) -> int:
        return int(round(angle % 180.0))

    groups: dict[int, dict[str, list[str]]] = {}
    for wid in polygon_walls:
        ang = wall_angles_deg.get(wid, 0.0)
        k = dirkey(ang)
        g = groups.setdefault(k, {"known": [], "unknown": []})
        if wid in known:
            g["known"].append(wid)
        else:
            g["unknown"].append(wid)

    inferred = dict(known)
    still_missing: list[str] = []

    for k, grp in groups.items():
        if not grp["unknown"]:
            continue

        # Sum signed contribution of known walls along the group's axis.
        # All walls in the group are parallel — they contribute ±L to a single
        # axis (the one closest to their angle direction).
        # The polygon closes when sum(signed) = 0 along each axis.
        sum_signed_known = 0.0
        for wid in grp["known"]:
            ang_rad = math.radians(wall_angles_deg[wid])
            # Pick the dominant component direction
            cx, cy = math.cos(ang_rad), math.sin(ang_rad)
            magnitude = math.hypot(cx, cy)
            comp = cx if abs(cx) >= abs(cy) else cy
            sign = comp / magnitude if magnitude else 1.0
            sum_signed_known += inferred[wid] * sign

        # Sum the signs of the unknown walls so we know the total they must absorb
        unknown_signs: list[tuple[str, float]] = []
        for wid in grp["unknown"]:
            ang_rad = math.radians(wall_angles_deg[wid])
            cx, cy = math.cos(ang_rad), math.sin(ang_rad)
            magnitude = math.hypot(cx, cy)
            comp = cx if abs(cx) >= abs(cy) else cy
            sign = comp / magnitude if magnitude else 1.0
            unknown_signs.append((wid, sign))

        required = -sum_signed_known  # they must sum to this signed total
        unknown_sign_sum = sum(s for _, s in unknown_signs)

        if abs(unknown_sign_sum) < 1e-9 or len(unknown_signs) > 2:
            # Can't disentangle: too many unknowns or opposing
            still_missing.extend(wid for wid, _ in unknown_signs)
            continue

        if len(unknown_signs) == 1:
            wid, sign = unknown_signs[0]
            inferred[wid] = abs(required / sign) if sign else 0.0
        else:
            # Two unknowns same sign: split equally. Two unknowns opposite signs:
            # under-determined → leave missing.
            signs = [s for _, s in unknown_signs]
            if signs[0] * signs[1] > 0:
                share = abs(required / unknown_sign_sum)
                for wid, _ in unknown_signs:
                    inferred[wid] = share
            else:
                still_missing.extend(wid for wid, _ in unknown_signs)

    return inferred, still_missing


# ── Schedule helpers ──────────────────────────────────────────────────────────
def parse_schedule_payload(payload: dict[str, Any]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Convert ``{durys: [...], langai: [...]}`` schedule output to lookup tables.

    The schedule extractor emits ``{id, type, width_mm, height_mm}`` rows.
    """
    doors: dict[str, dict] = {}
    windows: dict[str, dict] = {}
    for row in (payload or {}).get("durys") or []:
        rid = str(row["id"])
        doors[rid] = {
            "width_mm": float(row.get("width_mm") or DEFAULT_DOOR_W_MM),
            "height_mm": float(row.get("height_mm") or DEFAULT_DOOR_H_MM),
        }
    for row in (payload or {}).get("langai") or []:
        rid = str(row["id"])
        windows[rid] = {
            "width_mm": float(row.get("width_mm") or DEFAULT_WINDOW_W_MM),
            "height_mm": float(row.get("height_mm") or DEFAULT_WINDOW_H_MM),
        }
    return doors, windows


def _resolve_opening(
    op: Opening,
    dmap: dict[str, Dimension],
    doors: dict[str, dict],
    windows: dict[str, dict],
) -> AssembledOpening:
    """Resolve an opening to concrete mm dimensions (schedule overrides dim
    refs, dim refs override defaults)."""
    # 1. Schedule lookup
    sched = doors if op.type in ("door", "hidden_door") else windows
    if op.schedule_ref and op.schedule_ref in sched:
        s = sched[op.schedule_ref]
        return AssembledOpening(
            id=op.id, wall_id=op.wall_id, type=op.type,
            width_mm=s["width_mm"], height_mm=s["height_mm"],
            schedule_ref=op.schedule_ref,
            is_exterior=op.is_exterior, hidden=op.hidden,
            width_source="schedule", height_source="schedule",
        )

    # 2. Dimension-id references
    w_val = h_val = None
    w_src = h_src = "default"
    if op.width_dimension_id and op.width_dimension_id in dmap:
        d = dmap[op.width_dimension_id]
        if d.value_mm is not None and d.value_mm > 0:
            w_val = d.value_mm
            w_src = "dimension"
    if op.height_dimension_id and op.height_dimension_id in dmap:
        d = dmap[op.height_dimension_id]
        if d.value_mm is not None and d.value_mm > 0:
            h_val = d.value_mm
            h_src = "dimension"

    # 3. Defaults
    if w_val is None:
        w_val = (DEFAULT_WINDOW_W_MM if op.type == "window" else DEFAULT_DOOR_W_MM)
    if h_val is None:
        h_val = (DEFAULT_WINDOW_H_MM if op.type == "window" else DEFAULT_DOOR_H_MM)

    return AssembledOpening(
        id=op.id, wall_id=op.wall_id, type=op.type,
        width_mm=w_val, height_mm=h_val,
        schedule_ref=op.schedule_ref,
        is_exterior=op.is_exterior, hidden=op.hidden,
        width_source=w_src, height_source=h_src,
    )


# ── Main entry ────────────────────────────────────────────────────────────────
def assemble_plan(
    dimensions: DimensionList,
    room_graph: RoomGraph,
    schedule_payload: dict[str, Any] | None = None,
) -> Plan:
    """Convert (dimensions, room_graph[, schedule]) → typed Plan.

    Each room ends up with:
      - per-wall length resolved (direct dim ref, schedule, or polygon-closure
        inference)
      - per-wall angle (from Vision or derived from vertex coords)
      - perimeter (sum of wall lengths)
      - area (shoelace over walked vertices in mm)
      - openings resolved to concrete widths/heights
      - confidence_score = fraction of walls with a direct dim_id reference
    """
    dmap = _index_dimensions(dimensions)
    wmap = _index_walls(room_graph)
    vmap = _index_vertices(room_graph)
    doors, windows = parse_schedule_payload(schedule_payload or {})

    plan = Plan(schedule_doors=doors, schedule_windows=windows)

    openings_by_wall: dict[str, list[Opening]] = {}
    for o in room_graph.openings:
        openings_by_wall.setdefault(o.wall_id, []).append(o)

    for groom in room_graph.rooms:
        wall_lengths: dict[str, float | None] = {}
        wall_angles: dict[str, float] = {}
        for wid in groom.polygon_walls:
            w = wmap.get(wid)
            if w is None:
                continue
            length: float | None = None
            if w.dimension_id and w.dimension_id in dmap:
                d = dmap[w.dimension_id]
                if d.value_mm and d.value_mm > 0:
                    length = float(d.value_mm)
            wall_lengths[wid] = length
            wall_angles[wid] = _wall_angle_from_vertices(w, vmap)

        resolved_lengths, still_missing = _infer_missing_lengths(
            groom.polygon_walls, wall_lengths, wall_angles
        )

        # Geometric assembly
        sx, sy = (0.0, 0.0)
        x, y = sx, sy
        points = [(x, y)]
        for wid in groom.polygon_walls:
            L = resolved_lengths.get(wid, 0.0)
            ang = math.radians(wall_angles.get(wid, 0.0))
            x += L * math.cos(ang)
            y += L * math.sin(ang)
            points.append((x, y))

        perimeter_mm = sum(resolved_lengths.get(w, 0.0) for w in groom.polygon_walls)
        area_m2 = _polygon_area_m2(points[:-1])  # drop the repeated closure point

        # Resolve openings
        room_openings: list[AssembledOpening] = []
        for wid in groom.polygon_walls:
            for op in openings_by_wall.get(wid, []):
                room_openings.append(_resolve_opening(op, dmap, doors, windows))

        # Confidence — walls with a direct dimension_id reference (not inferred)
        total_walls = len(groom.polygon_walls)
        direct = sum(
            1 for wid in groom.polygon_walls
            if (wmap[wid].dimension_id and wmap[wid].dimension_id in dmap
                and (dmap[wmap[wid].dimension_id].value_mm or 0) > 0)
        )
        score = direct / total_walls if total_walls else 0.0
        color = "green" if score >= 0.9 else ("yellow" if score >= 0.6 else "red")

        plan.rooms.append(AssembledRoom(
            id=groom.id,
            nr=groom.nr,
            name=groom.name,
            paskirtis=groom.paskirtis,
            polygon_walls=list(groom.polygon_walls),
            wall_lengths_mm={k: float(v) for k, v in resolved_lengths.items()},
            wall_angles_deg=dict(wall_angles),
            perimeter_mm=float(perimeter_mm),
            area_m2=round(area_m2, 4),
            openings=room_openings,
            lubu_aukstis_m=float(groom.lubu_aukstis_m),
            lubu_aukstis_source=groom.lubu_aukstis_source,
            lubu_tipas=groom.lubu_tipas,
            plyteles_sienos_aukstis_m=float(groom.plyteles_sienos_aukstis_m),
            sienu_apdailos_breakdown=dict(groom.sienu_apdailos_breakdown),
            confidence_score=round(score, 3),
            confidence_color=color,
            missing_dimension_walls=list(still_missing),
            start_vertex_xy_mm=(sx, sy),
        ))

    plan._meta = {
        "n_rooms": len(plan.rooms),
        "n_walls": len(room_graph.walls),
        "n_dimensions": len(dimensions.dimensions),
        "n_openings": len(room_graph.openings),
    }
    return plan


# ── Bridge to existing formula engine ─────────────────────────────────────────
def _opening_to_element(op: AssembledOpening) -> dict[str, Any]:
    """Convert an AssembledOpening → existing `elementai` schema row."""
    if op.type == "led_niche":
        return {
            "tipas": "nisa_LED",
            "kiekis": 1,
            "ilgis_m": round(op.width_mm / 1000.0, 3),
        }
    tip = "duris" if op.type == "door" else (
        "pasleptos_duris" if op.type == "hidden_door" else "langas"
    )
    return {
        "tipas": tip,
        "kiekis": 1,
        "plotis_mm": int(op.width_mm),
        "aukstis_mm": int(op.height_mm),
        "_exterior": op.is_exterior,
    }


def plan_to_parsed(plan: Plan, *, archetipas: str = "default") -> dict[str, Any]:
    """Convert an AssembledPlan into the `parsed` dict shape consumed by
    ``_recompute_per_room_via_python`` (vision_call._recompute…). All rooms
    end up in ``patalpos`` with primitives only — the deterministic engine
    fills in the calculator outputs."""
    patalpos: list[dict[str, Any]] = []
    for r in plan.rooms:
        # Group openings into the existing schema: doors aggregated by size, etc.
        elementai = [_opening_to_element(o) for o in r.openings]
        patalpos.append({
            "nr": r.nr,
            "pavadinimas": r.name,
            "paskirtis": r.paskirtis,
            "plotas_m2": round(r.area_m2, 2),
            "perimetras_m": round(r.perimeter_mm / 1000.0, 2),
            "lubu_aukstis_m": float(r.lubu_aukstis_m),
            "lubu_tipas": r.lubu_tipas,
            "plyteles_sienos_aukstis_m": float(r.plyteles_sienos_aukstis_m),
            "elementai": elementai,
            "sienu_apdailos_breakdown": dict(r.sienu_apdailos_breakdown),
            "confidence": r.confidence_color,
            "_assembler": {
                "confidence_score": r.confidence_score,
                "missing_dimension_walls": list(r.missing_dimension_walls),
            },
        })
    total_area = round(sum(r.area_m2 for r in plan.rooms), 2)
    return {
        "patalpos": patalpos,
        "archetipas": archetipas,
        "bendras_plotas_m2": total_area,
        "_meta": {**plan._meta, "pipeline": "v2_dim_graph_assembler"},
    }
