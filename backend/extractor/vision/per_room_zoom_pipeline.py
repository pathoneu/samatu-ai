"""Per-room zoom Vision pipeline.

# EXPERIMENTAL — NOT IN PRODUCTION PATH (as of 2026-06-01)
# Part of the Phase 2 deterministic pipeline (paired with plan_assembler
# and room_graph_extractor). Never wired into production extract_interior.
# Bbox-locator + zoom failures on small rooms documented in
# `docs/superpowers/research/`. Per-room re-extraction would re-replace
# good dimensions with noisier ones for small rooms. Kept for future
# iteration.

The whole-page dim→graph approach fails on complex LT floor plans because
Opus 4.7 can't track 11 rooms' axis-alignment in a single shot (the previous
live run emitted mostly 0°/270° walls, never 90°/180°). The fix: crop the
floor plan to ONE room at a time + 5% margin, then run the same two Vision
passes on the crop. Models track local geometry far better than global.

The single-room crops are also cheap to iterate on prompt-wise — one room at
~$0.40 instead of $1.50 for the whole page.

Pipeline:

  1. Old single-pass extractor gives us per-room ``bbox_pct`` (sparse — only
     some rooms have it). For rooms without bbox, we fall back to the
     old pipeline's per-room primitives (no zoom for that room this run).
  2. For each room with bbox, crop via the existing ``_crop_room_image``
     helper (high DPI rasterisation, 5% padding).
  3. Run ``extract_dimensions`` + ``extract_room_graph`` on the crop.
  4. Assemble via ``assemble_plan`` + ``solve_plan``.
  5. Stitch into the existing ``parsed`` dict, replacing only the rooms
     where the zoom pipeline returned credible polygon walks.

Determinism: cache hits make subsequent runs free + byte-identical.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..plan_assembler import (
    assemble_plan, plan_to_parsed, AssembledRoom, AssembledOpening, Plan, _polygon_area_m2,
)
from ..geometry_solver import solve_plan, walk_polygon
from .dimension_extractor import extract_dimensions, DimensionList
from .room_graph_extractor import extract_room_graph, RoomGraph
from models_config import model_for


@dataclass
class ZoomResult:
    nr: str
    name: str
    bbox_pct: dict | None
    perimeter_mm: float = 0.0
    area_m2: float = 0.0
    confidence_score: float = 0.0
    confidence_color: str = "yellow"
    n_dimensions: int = 0
    n_walls: int = 0
    n_openings: int = 0
    polygon_closed: bool = False
    error: str | None = None
    cache_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nr": self.nr, "name": self.name, "bbox_pct": self.bbox_pct,
            "perimeter_mm": round(self.perimeter_mm, 1),
            "area_m2": round(self.area_m2, 3),
            "confidence_score": round(self.confidence_score, 3),
            "confidence_color": self.confidence_color,
            "n_dimensions": self.n_dimensions, "n_walls": self.n_walls,
            "n_openings": self.n_openings, "polygon_closed": self.polygon_closed,
            "error": self.error,
            "cache_hits": self.cache_hits,
            "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
        }


def _polygon_walk_closes(room_dict: dict[str, Any]) -> bool:
    pts = walk_polygon(
        room_dict["polygon_walls"],
        room_dict["wall_lengths_mm"],
        room_dict["wall_angles_deg"],
        tuple(room_dict.get("start_vertex_xy_mm") or (0.0, 0.0)),
    )
    if len(pts) < 2:
        return False
    return math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) < 50.0  # within 5cm


def run_zoom_on_room(
    *,
    pdf_bytes: bytes,
    page_number: int,
    room_primitive: dict[str, Any],
    model: str | None = None,
    crop_dpi: int = 300,
    crop_max_dim: int = 2576,
    crop_padding: float = 0.05,
) -> ZoomResult:
    """Run the two-pass Vision pipeline on a single room's crop.

    Caller is responsible for skipping rooms without bbox_pct.
    """
    from ..vision_call import _crop_room_image

    model = model or model_for("vision_pass2")  # zoom = pass-2 measurement

    nr = str(room_primitive.get("nr") or "?")
    name = str(room_primitive.get("pavadinimas") or "")
    bbox = room_primitive.get("bbox_pct")
    result = ZoomResult(nr=nr, name=name, bbox_pct=bbox)

    if not bbox:
        result.error = "no_bbox_pct"
        return result

    crop_b64 = _crop_room_image(
        pdf_bytes, page_number, bbox,
        target_dpi=crop_dpi, max_dim=crop_max_dim, padding=crop_padding,
    )
    if crop_b64 is None:
        result.error = "crop_failed"
        return result

    try:
        dl = extract_dimensions(image_b64=crop_b64, model=model)
        result.n_dimensions = len(dl.dimensions)
        result.tokens_in += int(dl._meta.get("input_tokens") or 0)
        result.tokens_out += int(dl._meta.get("output_tokens") or 0)
        if dl._meta.get("cache") == "hit":
            result.cache_hits += 1

        rg = extract_room_graph(
            image_b64=crop_b64,
            dimensions_payload=dl.to_dict(),
            model=model,
        )
        result.n_walls = len(rg.walls)
        result.n_openings = len(rg.openings)
        result.tokens_in += int(rg._meta.get("input_tokens") or 0)
        result.tokens_out += int(rg._meta.get("output_tokens") or 0)
        if rg._meta.get("cache") == "hit":
            result.cache_hits += 1

        if not rg.rooms:
            result.error = "no_rooms_in_graph"
            return result

        plan = assemble_plan(dl, rg)
        if not plan.rooms:
            result.error = "no_rooms_in_plan"
            return result

        plan_dict = solve_plan(plan.to_dict())
        # Take the first / largest room from the crop
        r = max(plan_dict["rooms"], key=lambda x: sum(x.get("wall_lengths_mm", {}).values()))
        result.perimeter_mm = sum(r["wall_lengths_mm"].values())
        pts = walk_polygon(
            r["polygon_walls"], r["wall_lengths_mm"], r["wall_angles_deg"],
            tuple(r.get("start_vertex_xy_mm") or (0.0, 0.0)),
        )
        result.area_m2 = _polygon_area_m2(pts[:-1])
        result.polygon_closed = _polygon_walk_closes(r)
        result.confidence_score = r.get("confidence_score", 0.0)
        result.confidence_color = r.get("confidence_color", "yellow")

    except Exception as exc:                                              # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_pilot(
    *,
    pdf_path: Path,
    old_extract_path: Path,
    page_number: int = 2,
    limit: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Run the zoom pipeline on every room in ``old_extract`` that has a bbox.

    Parameters
    ----------
    limit : int | None
        Cap the number of rooms processed (cost control during pilot).
    """
    pdf_bytes = pdf_path.read_bytes()
    extract = json.loads(old_extract_path.read_text())
    rooms = [r for r in extract.get("patalpos") or [] if r.get("bbox_pct")]
    if limit:
        rooms = rooms[:limit]

    results: list[ZoomResult] = []
    for room in rooms:
        res = run_zoom_on_room(
            pdf_bytes=pdf_bytes,
            page_number=page_number,
            room_primitive=room,
            model=model,
        )
        # Compare against the old pipeline's per-room primitives
        old_perim_m = float(room.get("perimetras_m") or 0)
        old_area_m2 = float(room.get("plotas_m2") or 0)
        delta_perim_pct = None
        delta_area_pct = None
        if old_perim_m > 0 and res.perimeter_mm > 0:
            delta_perim_pct = (res.perimeter_mm / 1000.0 - old_perim_m) / old_perim_m * 100.0
        if old_area_m2 > 0 and res.area_m2 > 0:
            delta_area_pct = (res.area_m2 - old_area_m2) / old_area_m2 * 100.0
        results.append(res)
        print(
            f"  {res.nr} {res.name[:24]:<26} "
            f"closed={res.polygon_closed!s:<5} "
            f"perim_mm={res.perimeter_mm:>7.0f} (old {old_perim_m*1000:>5.0f}) "
            f"area={res.area_m2:>6.2f} (old {old_area_m2:>5.2f}) "
            f"Δperim={(f'{delta_perim_pct:+6.2f}%' if delta_perim_pct is not None else '   —   ')} "
            f"Δarea={(f'{delta_area_pct:+6.2f}%' if delta_area_pct is not None else '   —   ')} "
            f"err={res.error or '-'}"
        )

    return {
        "rooms": [r.to_dict() for r in results],
        "n_attempted": len(results),
        "n_closed": sum(1 for r in results if r.polygon_closed),
        "n_errors": sum(1 for r in results if r.error),
    }
