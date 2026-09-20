"""/api/projects/{project_id}/rooms/{room_nr}/outline-at — a room gets its outline from ONE
click inside it, and its walls are read again right away. No Vision call, no cost.

A room the geometry lane could not outline (its number is not printed where it could be found,
its drawn area disagrees with the table) showed WHY on the check sheet and a blank perimeter —
and nothing there could fix it. The person points at the room; the outline is the face of the
wall solid under the click (extractor/vector_rooms.outline_at), marked `corrected`, which the
lane already honours: it is never re-traced, the strings along its walls are summed, the
openings in its walls are read.

`…/split-space` (2026-09-21) is its sibling for two rooms NO WALL separates — a kitchen and a living
room, usually the biggest rooms of a flat: one line a person draws divides the shared space
(vector_rooms.split_space); both rooms get their own outlines, and the boundary between them is
marked `menamos` — never a wall, never in a perimeter.

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
from extractor.vector_rooms import STRONG, outline_at, split_space

log = logging.getLogger("samatu.room_outline")

router = APIRouter(prefix="/api/projects", tags=["room-outline"])

POINTED_AT = "parodyta"           # `_konturas.saltinis` of an outline a person pointed at
DIVIDED = "padalinta"             # …of an outline that is one side of a line a person drew through a shared space
_ESTIMATE_KEYS = ("perimetras_saltinis", "_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis")

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


class PagePoint(BaseModel):
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)


class SplitSpace(BaseModel):
    page: int = Field(ge=1)
    a: PagePoint
    b: PagePoint


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


def _todays_reading(request: Request, project_id: str, room_nr: str, page: int, bucket: str):
    """Everything both endpoints start from: the owner's project, its drawing, and TODAY's lane reading on a
    deep copy — where the other rooms are, every sheet's scale, how the sheets lie over each other.
    → (pdf_bytes, (W, H), parsed copy, dims, geo meta, scale of `page`, rooms, the room)."""
    project = _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), bucket)

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
    W, H, _ = page_geometry(pdf_bytes, page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")

    parsed = copy.deepcopy(project)
    dims = read_dimension_strings(pdf_bytes, pages=None)
    apply_geometry(parsed, pdf_bytes, dims)
    geo = (parsed.get("_meta") or {}).get("geometrija") or {}
    scale = ((geo.get("masteliai") or {}).get(str(page)) or {}).get("m_per_pt")
    if not scale:
        raise HTTPException(status_code=400, detail="Šio lapo mastelio neradau — parodykite patalpą plane, kuriame užrašyti matmenys.")
    rooms = [r for r in (parsed.get("patalpos") or []) if isinstance(r, dict)]
    room = next(r for r in rooms if _nr(r) == wanted)
    return pdf_bytes, (W, H), parsed, dims, geo, float(scale), rooms, room


# Plain `def`: PDF parsing and geometry, 100 % blocking — the threadpool's job.
@router.post("/{project_id}/rooms/{room_nr}/outline-at")
def api_room_outline_at(request: Request, project_id: str, room_nr: str, body: OutlineAt):
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
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
        for stale in _ESTIMATE_KEYS:
            room.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)

    return {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }


@router.post("/{project_id}/rooms/{room_nr}/split-space")
def api_room_split_space(request: Request, project_id: str, room_nr: str, body: SplitSpace):
    """Two rooms no wall separates, divided by ONE line through `a` and `b` (vector_rooms.split_space). Both
    rooms come back with their own outlines — the boundary marked `menamos`, never a wall — and their walls
    read again. Saves nothing."""
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
    space = room.get("_atvira_erdve")
    members = [str(n) for n in (space.get("nariai") or [])] if isinstance(space, dict) else []
    if len(members) < 2:
        return {"status": "not_shared"}
    if len(members) > 2:
        return {"status": "too_many"}
    lay = _laid_onto(body.page, geo.get("sutapdinimas") or {})
    by_nr = {_nr(r): r for r in rooms}
    seats: dict[str, tuple[float, float]] = {}
    for nr in members:
        v = (by_nr.get(nr) or {}).get("_vieta")
        pt = lay(int(v["page"]), float(v["cx"]), float(v["cy"])) if isinstance(v, dict) and v.get("saltinis") in STRONG else None
        if pt is None:
            return {"status": "not_shared"}
        seats[nr] = pt
    hit = split_space(pdf_bytes, body.page, (body.a.x_pct, body.a.y_pct), (body.b.x_pct, body.b.y_pct), seats,
                      {nr: by_nr[nr].get("plotas_m2") for nr in members}, scale, (W, H))
    if hit["status"] != "ok":
        return hit

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for nr in members:
        r, part = by_nr[nr], hit["rooms"][nr]
        r["polygon_pct"] = part["polygon_pct"]
        r["polygon_source"] = "corrected"
        r["polygon_corrected_at"] = now
        r["_konturas"] = {"page": body.page, "plotas_m2": part["plotas_m2"], "perimetras_m": part["perimetras_m"],
                          "plotas_uzrasas_m2": r.get("plotas_m2"), "paklaida": part["paklaida"], "plotas_nesutampa": False,
                          "menamos": part["menamos"], "su": [m for m in members if m != nr], "saltinis": DIVIDED}
        for stale in ("_konturo_priezastis", "_atvira_erdve", "_angos_sienose"):
            r.pop(stale, None)
        if str(r.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis"):
            for stale in _ESTIMATE_KEYS:
                r.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)

    return {
        "status": "ok",
        "rooms": {nr: {k: by_nr[nr].get(k) for k in GEOMETRY_ROOM_KEYS} for nr in members},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if _nr(r) not in members and isinstance(r.get("_angos_sienose"), dict)},
    }
