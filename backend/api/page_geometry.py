"""GET /api/projects/{project_id}/pages/{page}/geometry — the drawing's wall geometry of one sheet.

Why (2026-10-16, Togal analysis §10, docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md):
the measure and calibrate tools snapped only to the user's own measurements. On a vector PDF the walls
are right there — the geometry lane already reads them as grey fills (extractor/pdf_vectors.wall_fills)
to outline rooms. This endpoint hands the MERGED wall solid to the browser as rings in display-frame
page fractions (the frame `polygon_pct` lives in), so a click can snap to a wall corner or face, and a
layer can draw the walls the program saw.

Read-only, owner-scoped, rate-limited like the other PDF handlers, saves nothing. A sheet with no
vector walls (a scan, a schedule) answers `status: "no_walls"` with empty rings — never an error.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from shapely.ops import unary_union

from api.free_reread import NO_PDF, _project_for
from extractor.pdf_vectors import page_geometry, wall_fills

log = logging.getLogger("samatu.page_geometry")

router = APIRouter(prefix="/api/projects", tags=["page-geometry"])

SIMPLIFY_PT = 0.35          # a third of a point: below drawing precision, removes CAD triangle seams
MIN_WALLS = 4               # fewer wall-shaped fills than this is a logo or a legend swatch, not a plan
MAX_VERTICES = 20000        # the browser snaps on every pointer move — bound the work
SIMPLIFY_ROUNDS = 4


def wall_solid_rings(pdf_bytes: bytes, page: int) -> tuple[float, float, list[list[list[float]]], bool]:
    """(width_pt, height_pt, rings, truncated). Rings are the exterior and holes of the merged wall
    solid, as [[x_pct, y_pct], …] with the closing point dropped. Display frame, origin top-left."""
    W, H, _ = page_geometry(pdf_bytes, page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")
    fills = wall_fills(pdf_bytes, page)
    if len(fills) < MIN_WALLS:
        return W, H, [], False
    solid = unary_union(fills)
    tol = SIMPLIFY_PT
    rings: list[list[list[float]]] = []
    for _ in range(SIMPLIFY_ROUNDS):
        shape = solid.simplify(tol, preserve_topology=True)
        parts = list(shape.geoms) if shape.geom_type == "MultiPolygon" else [shape]
        rings = []
        for part in parts:
            if part.geom_type != "Polygon" or part.is_empty:
                continue
            for ring in (part.exterior, *part.interiors):
                pts = [[round(x / W, 5), round(y / H, 5)] for x, y in list(ring.coords)[:-1]]
                if len(pts) >= 3:
                    rings.append(pts)
        if sum(len(r) for r in rings) <= MAX_VERTICES:
            return W, H, rings, False
        tol *= 2
    return W, H, rings, True


# Plain `def`: PDFium parsing + shapely, blocking CPU — FastAPI runs it in the threadpool.
@router.get("/{project_id}/pages/{page}/geometry")
def api_page_geometry(request: Request, project_id: str, page: int):
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "page_geometry")

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("page-geometry pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)

    W, H, rings, truncated = wall_solid_rings(pdf_bytes, page)
    return {
        "page": page,
        "width_pt": W,
        "height_pt": H,
        "status": "ok" if rings else "no_walls",
        "walls_pct": rings,
        "vertex_count": sum(len(r) for r in rings),
        "truncated": truncated,
    }
