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

Fixture mode (``?fixture=objektas_a``) reads the contractor-validated
to-the-dot extract directly so the Annotator can be demoed without a real
upload + DB write.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

import db as _db
import auth as _auth

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "objektas_a": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/app-output-to-the-dot.json",
}

router = APIRouter(prefix="/api/projects", tags=["room-graph"])


def _load_fixture(name: str) -> dict[str, Any]:
    p = FIXTURES.get(name)
    if not p or not p.exists():
        raise HTTPException(status_code=404, detail=f"unknown fixture: {name}")
    return json.loads(p.read_text(encoding="utf-8"))


# ASCII space / NBSP / narrow NBSP — the three thousands separators a LT number
# can carry (spelled as escapes: literally they are indistinguishable in an editor).
_LT_SEP_RE = re.compile("[\u0020\u00a0\u202f]")


def _num(v: Any, default: float = 0.0) -> float:
    """Tolerant float coercion — LT comma-decimals ("12,5") and stray strings
    reach here straight out of saved project blobs, and a bare float() raised
    ValueError → HTTP 500 for the whole room-graph. (2026-07-28 audit.)"""
    if isinstance(v, bool) or v is None:
        return float(default)
    if isinstance(v, (int, float)):
        return float(v) if v == v else float(default)   # NaN → default
    try:
        return float(_LT_SEP_RE.sub("", str(v)).replace(",", ".").strip())
    except (TypeError, ValueError):
        return float(default)


def _int(v: Any, default: int) -> int:
    """Tolerant int coercion (page numbers arrive as "3", 3.0, or junk)."""
    n = _num(v, float(default))
    try:
        return int(n)
    except (ValueError, OverflowError):
        return int(default)


def _room_polygon_from_patalpa(room: dict[str, Any]) -> list[dict[str, float]] | None:
    """Build a polygon vertex list in fractional page coords.

    Priority order:
      1. ``polygon_pct`` — accepts BOTH shapes (see below)
      2. ``bbox_pct``    — rectangle corners
      3. None            — no geometry available

    THE SHAPE MISMATCH (2026-07-28 audit): this reader only understood
    ``[[x, y], …]``, but it EMITS ``[{"x_pct": …, "y_pct": …}, …]`` — and the
    frontend persists what it renders. So the app's own output could not be read
    back: a project whose polygons had round-tripped through the Annotator hit
    ``p[0]`` on a dict → KeyError → 500, or silently lost its geometry. Both
    shapes are accepted now; the emitted shape is unchanged.
    """
    poly = room.get("polygon_pct")
    if isinstance(poly, list) and len(poly) >= 3:
        out: list[dict[str, float]] = []
        for p in poly:
            if isinstance(p, dict):
                if "x_pct" not in p or "y_pct" not in p:
                    return None
                out.append({"x_pct": _num(p["x_pct"]), "y_pct": _num(p["y_pct"])})
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                out.append({"x_pct": _num(p[0]), "y_pct": _num(p[1])})
            else:
                return None      # mixed / unknown vertex shape — no geometry
        return out
    bb = room.get("bbox_pct")
    if isinstance(bb, dict) and "x" in bb and "y" in bb and "w" in bb and "h" in bb:
        x, y, w, h = _num(bb["x"]), _num(bb["y"]), _num(bb["w"]), _num(bb["h"])
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
            # Every coercion below is _num/_int (2026-07-28 audit): these come
            # from a saved blob, so a legacy comma-decimal ("12,5") or a room
            # whose puslapio_nr is "3 a." used to raise ValueError and 500 the
            # WHOLE room-graph — the Annotator lost every room over one field.
            "puslapio_nr": _int(room.get("puslapio_nr"), page_nr),
            "polygon_pct": poly,
            "perimeter_mm": int(round(_num(room.get("perimetras_m")) * 1000)),
            "area_m2": _num(room.get("plotas_m2")),
            "ceiling_height_m": _num(room.get("lubu_aukstis_m") or 2.82, 2.82),
            "ceiling_type": room.get("lubu_tipas") or "gkp",
            "walls_paintable_m2": _num(room.get("walls_paintable_m2")),
            "ceiling_paintable_m2": _num(room.get("ceiling_paintable_m2")),
            "dazymo_plotas_m2": _num(room.get("dazymo_plotas_m2")),
            "confidence": room.get("confidence") or "medium",
            "elementai_count": len(room.get("elementai") or []),
        })

    return {
        "project_id": parsed.get("_meta", {}).get("project_id") or "",
        "floor_plan_page_nr": page_nr,
        "page_scale_mm_per_pct": _extract_scale_factor(parsed),
        "rooms": rooms_out,
        "rooms_with_polygons": sum(1 for r in rooms_out if r["polygon_pct"]),
        "total_floor_area_m2": _num(parsed.get("bendras_plotas_m2")),
    }


@router.get("/{project_id}/room-graph")
async def get_room_graph(
    request: Request,
    project_id: str,
    fixture: str | None = Query(default=None,
                                description="If set, ignore DB and load a named fixture (demo only)."),
) -> dict[str, Any]:
    """Return per-room polygons + paint quantities for the Annotator overlay."""
    if fixture and os.environ.get("ENV") != "production":
        # Demo / dev mode — no auth, no DB. Useful for the Objektas A fixture.
        # SECURITY (2026-07-15): gated to non-production. Even though this branch
        # reads only a fixed committed file (no per-tenant leak), serving a real
        # contractor project's geometry to ANONYMOUS callers on prod is not
        # acceptable — so in production we ignore ?fixture= and fall through to
        # the normal authenticated path below.
        # SECURITY (pass-3 sweep, 2026-07-04): safe ONLY because this branch reads
        # nothing but the fixed FIXTURES file and echoes ``fixture:{name}`` as the
        # id — it never touches a ``{URL_project_id}``-keyed per-user store. If you
        # add such a read, call ``_auth.require_owned_project(request, project_id)``
        # FIRST, or ``?fixture=`` becomes an unauth cross-tenant read (P1/P2 class).
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
