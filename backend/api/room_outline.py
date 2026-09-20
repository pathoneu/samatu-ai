"""/api/projects/{project_id}/rooms/{room_nr}/outline-at — a room gets its outline from ONE
click inside it, and its walls are read again right away. No Vision call, no cost.

A room the geometry lane could not outline (its number is not printed where it could be found,
its drawn area disagrees with the table) showed WHY on the check sheet and a blank perimeter —
and nothing there could fix it. The person points at the room; the outline is the face of the
wall solid under the click (extractor/vector_rooms.outline_at), marked `corrected`, which the
lane already honours: it is never re-traced, the strings along its walls are summed, the
openings in its walls are read.

The server SAVES NOTHING (same rule as api/free_reread.py): it answers with the room's geometry
keys — a key that is `null` is to be removed — and with the neighbours' wall openings, which now
lead to a NAMED room. The sheet patches the room and recomputes on the one path every other edit
takes (/recompute-interior → consequence strip → undo).
"""
from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.free_reread import NO_PDF, _project_for
from extractor.geometry_lane import KEEP_POLYGONS, apply_geometry
from extractor.pdf_vectors import page_geometry
from extractor.plan_dimensions import read_dimension_strings
from extractor.vector_rooms import STRONG, outline_at

log = logging.getLogger("samatu.room_outline")

router = APIRouter(prefix="/api/projects", tags=["room-outline"])

POINTED_AT = "parodyta"           # `_konturas.saltinis` of an outline a person pointed at

# What a room's geometry is made of — everything else of the room (its name, its area, the
# quantities built from it) is never sent back, so a click can never overwrite it.
GEOMETRY_ROOM_KEYS = (
    "polygon_pct", "polygon_source", "polygon_corrected_at", "_konturas", "_konturo_priezastis", "_atvira_erdve",
    "perimetras_m", "perimetras_saltinis", "_sienos", "_perimetras_suma", "_perimetras_priezastis",
    "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis", "_perimetras_pries_geometrija",
    "_angos_sienose", "grindu_danga", "grindu_danga_saltinis", "_grindu_danga", "_grindu_dangos_dvi",
)


class OutlineAt(BaseModel):
    page: int = Field(ge=1)
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def _laid_onto(page: int, sutapdinimas: dict):
    """Page fractions of another sheet of the same plan → fractions of `page` (None when not the same plan)."""
    to = sutapdinimas.get(str(page))

    def lay(src: int, x: float, y: float):
        if int(src) == int(page):
            return x, y
        frm = sutapdinimas.get(str(src))
        if not frm or not to or frm.get("base") != to.get("base"):
            return None
        bx, by = frm["kx"] * x + frm["dx_pct"], frm["ky"] * y + frm["dy_pct"]
        return (bx - to["dx_pct"]) / to["kx"], (by - to["dy_pct"]) / to["ky"]
    return lay


# Plain `def`: PDF parsing and geometry, 100 % blocking — the threadpool's job.
@router.post("/{project_id}/rooms/{room_nr}/outline-at")
def api_room_outline_at(request: Request, project_id: str, room_nr: str, body: OutlineAt):
    project = _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "room_outline")

    wanted = str(room_nr).strip()
    if not any(_nr(r) == wanted for r in (project.get("patalpos") or []) if isinstance(r, dict)):
        raise HTTPException(status_code=404, detail="Patalpa nerasta")

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("room-outline pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    W, H, _ = page_geometry(pdf_bytes, body.page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")

    # Today's reading first: where the OTHER rooms are, every sheet's scale, how the sheets lie over each other.
    parsed = copy.deepcopy(project)
    dims = read_dimension_strings(pdf_bytes, pages=None)
    apply_geometry(parsed, pdf_bytes, dims)
    geo = (parsed.get("_meta") or {}).get("geometrija") or {}
    scale = ((geo.get("masteliai") or {}).get(str(body.page)) or {}).get("m_per_pt")
    if not scale:
        raise HTTPException(status_code=400, detail="Šio lapo mastelio neradau — parodykite patalpą plane, kuriame užrašyti matmenys.")
    rooms = [r for r in (parsed.get("patalpos") or []) if isinstance(r, dict)]
    room = next(r for r in rooms if _nr(r) == wanted)
    lay = _laid_onto(body.page, geo.get("sutapdinimas") or {})
    others: dict[str, list] = {}
    seats: dict[str, tuple[float, float]] = {}
    for r in rooms:
        if r is room:
            continue
        poly = r.get("polygon_pct")
        if str(r.get("polygon_source") or "") in KEEP_POLYGONS and isinstance(poly, list) and len(poly) >= 3:
            src = int((r.get("_konturas") or {}).get("page") or r.get("puslapio_nr") or 0)
            ring = [lay(src, float(x), float(y)) for x, y in poly]
            if all(pt is not None for pt in ring):
                others[_nr(r)] = [list(pt) for pt in ring]
            continue
        v = r.get("_vieta")
        if isinstance(v, dict) and v.get("saltinis") in STRONG:
            pt = lay(int(v["page"]), float(v["cx"]), float(v["cy"]))
            if pt is not None:
                seats[_nr(r)] = pt

    hit = outline_at(pdf_bytes, body.page, body.x_pct, body.y_pct, room.get("plotas_m2"), float(scale), (W, H),
                     others_pct=others, other_seats_pct=seats)
    if hit["status"] != "ok":
        return hit

    room["polygon_pct"] = hit["polygon_pct"]
    room["polygon_source"] = "corrected"
    room["polygon_corrected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # A person confirmed this outline: a disagreement with the table is SHOWN (`paklaida`), but it no
    # longer keeps the wall lengths from being added (dimension_sum reads `plotas_nesutampa`).
    room["_konturas"] = {"page": body.page, "plotas_m2": hit["plotas_m2"], "perimetras_m": hit["perimetras_m"],
                         "plotas_uzrasas_m2": room.get("plotas_m2"), "paklaida": hit["paklaida"],
                         "plotas_nesutampa": False, "sujungta": hit["sujungta"], "durys_m": hit["durys_m"],
                         "saltinis": POINTED_AT}
    for stale in ("_konturo_priezastis", "_atvira_erdve", "_angos_sienose"):
        room.pop(stale, None)
    if str(room.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis"):
        # an ESTIMATE made without this outline — the walls are read afresh
        for stale in ("perimetras_saltinis", "_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis"):
            room.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)

    return {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }
