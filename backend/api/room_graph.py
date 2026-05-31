"""GET /api/projects/{project_id}/room-graph

Returns the project's per-room geometry primitives — polygon coordinates (in
mm), perimeter, area, ceiling height, paskirtis, computed paint area — in a
flat shape the frontend Annotator can render directly as overlay polygons.

The data comes from the project's saved extract (Vision output +
`_recompute_per_room_via_python` outputs). Polygon coords come from
``bbox_pct`` / ``polygon_pct`` on the saved patalpa when present; otherwise
we don't synthesise a polygon (caller renders the room as a list entry only).

Scale factor: returned as ``page_scale_mm_per_pct`` for the floor-plan page.
Computed from the saved dimension list when present; null when not yet
available (the Annotator falls back to user calibration).

Fixture mode (``?fixture=berzas``) reads the contractor-validated
to-the-dot extract directly so the Annotator can be demoed without a real
upload + DB write.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

import db as _db
import auth as _auth

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "berzas": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json",
}

router = APIRouter(prefix="/api/projects", tags=["room-graph"])


def _load_fixture(name: str) -> dict[str, Any]:
    p = FIXTURES.get(name)
    if not p or not p.exists():
        raise HTTPException(status_code=404, detail=f"unknown fixture: {name}")
    return json.loads(p.read_text(encoding="utf-8"))


def _room_polygon_from_patalpa(room: dict[str, Any]) -> list[dict[str, float]] | None:
    """Build a polygon vertex list in fractional page coords.

    Priority order:
      1. ``polygon_pct`` — explicit [[x_pct, y_pct], …]
      2. ``bbox_pct``    — rectangle corners
      3. None            — no geometry available
    """
    poly = room.get("polygon_pct")
    if isinstance(poly, list) and len(poly) >= 3:
        return [{"x_pct": float(p[0]), "y_pct": float(p[1])} for p in poly]
    bb = room.get("bbox_pct")
    if isinstance(bb, dict) and "x" in bb and "y" in bb and "w" in bb and "h" in bb:
        x, y, w, h = float(bb["x"]), float(bb["y"]), float(bb["w"]), float(bb["h"])
        return [
            {"x_pct": x,     "y_pct": y},
            {"x_pct": x + w, "y_pct": y},
            {"x_pct": x + w, "y_pct": y + h},
            {"x_pct": x,     "y_pct": y + h},
        ]
    return None


def _extract_scale_factor(parsed: dict[str, Any]) -> float | None:
    """Reach into the saved extract for a global scale (mm per page-fraction).

    Best source: dimension extractor output (Phase 2 pipeline). When that's
    absent, we estimate from the largest room's perim × H and bbox span,
    but that's noisier — we return null and let the frontend rely on user
    calibration."""
    meta = parsed.get("_meta") or {}
    scale = meta.get("page_scale_mm_per_pct") or meta.get("scale_mm_per_pct")
    if isinstance(scale, (int, float)) and scale > 0:
        return float(scale)
    return None


def _build_room_graph(parsed: dict[str, Any]) -> dict[str, Any]:
    page_nr = parsed.get("scale_source_page") or 2
    rooms_out: list[dict[str, Any]] = []
    for room in parsed.get("patalpos") or []:
        poly = _room_polygon_from_patalpa(room)
        rooms_out.append({
            "id": str(room.get("nr") or ""),
            "nr": str(room.get("nr") or ""),
            "name": room.get("pavadinimas") or "",
            "paskirtis": room.get("paskirtis") or "",
            "puslapio_nr": int(room.get("puslapio_nr") or page_nr),
            "polygon_pct": poly,
            "perimeter_mm": int(round(float(room.get("perimetras_m") or 0) * 1000)),
            "area_m2": float(room.get("plotas_m2") or 0),
            "ceiling_height_m": float(room.get("lubu_aukstis_m") or 2.82),
            "ceiling_type": room.get("lubu_tipas") or "gkp",
            "walls_paintable_m2": float(room.get("walls_paintable_m2") or 0),
            "ceiling_paintable_m2": float(room.get("ceiling_paintable_m2") or 0),
            "dazymo_plotas_m2": float(room.get("dazymo_plotas_m2") or 0),
            "confidence": room.get("confidence") or "medium",
            "elementai_count": len(room.get("elementai") or []),
        })

    return {
        "project_id": parsed.get("_meta", {}).get("project_id") or "",
        "floor_plan_page_nr": page_nr,
        "page_scale_mm_per_pct": _extract_scale_factor(parsed),
        "rooms": rooms_out,
        "rooms_with_polygons": sum(1 for r in rooms_out if r["polygon_pct"]),
        "total_floor_area_m2": float(parsed.get("bendras_plotas_m2") or 0),
    }


@router.get("/{project_id}/room-graph")
async def get_room_graph(
    request: Request,
    project_id: str,
    fixture: str | None = Query(default=None,
                                description="If set, ignore DB and load a named fixture (demo only)."),
) -> dict[str, Any]:
    """Return per-room polygons + paint quantities for the Annotator overlay."""
    if fixture:
        # Demo / dev mode — no auth, no DB. Useful for the Beržų fixture.
        parsed = _load_fixture(fixture)
        rg = _build_room_graph(parsed)
        rg["project_id"] = f"fixture:{fixture}"
        rg["_source"] = "fixture"
        return rg

    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = _db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    rg = _build_room_graph(project)
    rg["_source"] = "db"
    return rg
